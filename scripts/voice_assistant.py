#!/usr/bin/env python3
"""
heyboy voice assistant — Part 1 scaffold

Pipeline:
1) Always-on local wake phrase detection ("hey boy") with Vosk
2) 5–10s listen window (default 7s)
3) Transcription (Vosk local or Deepgram API)
4) Route transcript to selected assistant backend:
   - OpenAI-compatible HTTP (OpenClaw/OpenAI/OpenRouter/etc.)
   - Codex CLI
   - Claude Code CLI
   - Generic CLI command
5) Speak response with local TTS (pyttsx3) and stop on barge-in
"""

from __future__ import annotations

import atexit
import io
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pyttsx3
import requests
import sounddevice as sd
import soundfile as sf
import vosk
from dotenv import load_dotenv

if os.name == "posix":
    import fcntl


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        print(
            f"[heyboy] Invalid integer for {name}={raw!r}; using default {default}.",
            file=sys.stderr,
        )
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        print(
            f"[heyboy] Invalid float for {name}={raw!r}; using default {default}.",
            file=sys.stderr,
        )
        return default

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ASSISTANT_BACKEND = os.getenv("ASSISTANT_BACKEND", "openclaw_api").strip().lower()

# Wake/listen
WAKE_PHRASE_RAW = os.getenv("WAKE_PHRASE", "hey boy")
LISTEN_ACK = os.getenv("LISTEN_ACK", "Hi, I'm listening.")
LISTEN_SECONDS = _env_int("LISTEN_SECONDS", _env_int("RECORD_SECONDS", 7))
SAMPLE_RATE = _env_int("SAMPLE_RATE", 16000)
CHANNELS = 1
CHUNK_DURATION_S = _env_float("AUDIO_CHUNK_DURATION_S", 0.20)
if CHUNK_DURATION_S < 0.05:
    CHUNK_DURATION_S = 0.05
if CHUNK_DURATION_S > 0.50:
    CHUNK_DURATION_S = 0.50
CHUNK_SIZE = max(1, int(SAMPLE_RATE * CHUNK_DURATION_S))
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us")

# Multi-turn session behavior
MULTI_TURN_ENABLED = _env_bool("MULTI_TURN_ENABLED", True)
MULTI_TURN_MAX_TURNS = max(1, _env_int("MULTI_TURN_MAX_TURNS", 3))
FOLLOWUP_LISTEN_SECONDS = max(1, _env_int("FOLLOWUP_LISTEN_SECONDS", LISTEN_SECONDS))
NO_SPEECH_RETRY_LIMIT = max(0, _env_int("NO_SPEECH_RETRY_LIMIT", 1))
WAKE_ONLY_RETRY_LIMIT = max(0, _env_int("WAKE_ONLY_RETRY_LIMIT", 1))
NO_SPEECH_PROMPT = os.getenv("NO_SPEECH_PROMPT", "I didn't catch that.")
WAKE_ONLY_PROMPT = os.getenv(
    "WAKE_ONLY_PROMPT",
    "I heard the wake phrase, but not your request.",
)
FOLLOWUP_PROMPT = os.getenv("FOLLOWUP_PROMPT", "")
FOLLOWUP_NO_SPEECH_PROMPT = os.getenv(
    "FOLLOWUP_NO_SPEECH_PROMPT",
    "Still here. What next?",
)
FOLLOWUP_TIMEOUT_PROMPT = os.getenv(
    "FOLLOWUP_TIMEOUT_PROMPT",
    "Okay, pausing now.",
)
SESSION_END_PROMPT = os.getenv("SESSION_END_PROMPT", "")
EMPTY_BACKEND_REPLY = os.getenv(
    "EMPTY_BACKEND_REPLY", "Sorry, I don't have a response right now."
)
MAX_TRANSCRIPT_CHARS = max(80, _env_int("MAX_TRANSCRIPT_CHARS", 1200))

# Speech-to-text backend
_STT_BACKEND_RAW = os.getenv("STT_BACKEND", "vosk_local").strip().lower()
if _STT_BACKEND_RAW in ("vosk", "vosk_local", "local"):
    STT_BACKEND = "vosk_local"
elif _STT_BACKEND_RAW in ("deepgram", "deepgram_api"):
    STT_BACKEND = "deepgram"
else:
    STT_BACKEND = _STT_BACKEND_RAW

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-3")
DEEPGRAM_TIMEOUT = _env_int("DEEPGRAM_TIMEOUT", 20)

# API backend (OpenAI-compatible)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:3333")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.2")
THINKING_LEVEL = os.getenv("THINKING_LEVEL", "low").strip().lower()
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.2)
LLM_TOP_P = _env_float("LLM_TOP_P", 0.9)
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 400)
LLM_TIMEOUT = _env_int("LLM_TIMEOUT", 30)

# CLI backends
CODEX_CLI_COMMAND = os.getenv("CODEX_CLI_COMMAND", "codex exec")
CODEX_MODEL_NAME = os.getenv("CODEX_MODEL_NAME", "gpt-5.2").strip()
CODEX_REASONING_LEVEL = os.getenv("CODEX_REASONING_LEVEL", "none").strip().lower()
CLAUDE_CLI_COMMAND = os.getenv(
    "CLAUDE_CLI_COMMAND", "claude --dangerously-skip-permissions --print"
)
GENERIC_CLI_COMMAND = os.getenv("GENERIC_CLI_COMMAND", "")
CLI_TIMEOUT = _env_int("CLI_TIMEOUT", 120)

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a concise, helpful voice assistant. Keep responses short and clear.",
)

# Barge-in
BARGE_IN_THRESHOLD = _env_float("BARGE_IN_THRESHOLD", 0.03)
BARGE_IN_HOLD_MS = _env_int("BARGE_IN_HOLD_MS", 220)
BARGE_IN_GRACE_MS = _env_int("BARGE_IN_GRACE_MS", 350)

# TTS/wake echo protections
TTS_DUPLICATE_WINDOW_MS = max(0, _env_int("TTS_DUPLICATE_WINDOW_MS", 1200))
WAKE_SUPPRESS_AFTER_TTS_MS = max(0, _env_int("WAKE_SUPPRESS_AFTER_TTS_MS", 900))

# Speech endpointing (latency)
EARLY_ENDPOINTING_ENABLED = _env_bool("EARLY_ENDPOINTING_ENABLED", True)
ENDPOINT_SPEECH_THRESHOLD = _env_float("ENDPOINT_SPEECH_THRESHOLD", 0.015)
ENDPOINT_MIN_SPEECH_MS = max(0, _env_int("ENDPOINT_MIN_SPEECH_MS", 220))
ENDPOINT_TRAILING_SILENCE_MS = max(0, _env_int("ENDPOINT_TRAILING_SILENCE_MS", 680))

# Audio recovery / diagnostics
AUDIO_RETRY_ATTEMPTS = max(1, _env_int("AUDIO_RETRY_ATTEMPTS", 3))
AUDIO_RETRY_BACKOFF_S = max(0.0, _env_float("AUDIO_RETRY_BACKOFF_S", 0.35))
AUDIO_RETRY_BACKOFF_MAX_S = max(0.1, _env_float("AUDIO_RETRY_BACKOFF_MAX_S", 2.0))

# Context + debug
HISTORY_MAX_MESSAGES = max(2, _env_int("HISTORY_MAX_MESSAGES", 20))
HISTORY_MAX_CHARS = max(800, _env_int("HISTORY_MAX_CHARS", 12000))
DEBUG_SAVE_AUDIO = _env_bool("DEBUG_SAVE_AUDIO", False)
DEBUG_AUDIO_DIR = Path(os.getenv("DEBUG_AUDIO_DIR", "tmp/audio"))
INSTANCE_LOCK_PATH = os.getenv("INSTANCE_LOCK_PATH", "/tmp/heyboy-voice-assistant.lock")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("heyboy")

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_LAST_STT_ERROR: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Normalize speech text for robust wake phrase matching."""
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


WAKE_PHRASE = normalize_text(WAKE_PHRASE_RAW)


def run_audio_with_retries(operation_name: str, fn: Callable[[], object]) -> object:
    """Retry transient audio failures before surfacing an error."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, AUDIO_RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - audio stack errors vary by host/driver
            last_exc = exc
            if attempt >= AUDIO_RETRY_ATTEMPTS:
                break
            delay = min(AUDIO_RETRY_BACKOFF_MAX_S, AUDIO_RETRY_BACKOFF_S * attempt)
            logger.warning(
                "%s failed (attempt %s/%s): %s. Retrying in %.2fs",
                operation_name,
                attempt,
                AUDIO_RETRY_ATTEMPTS,
                exc,
                delay,
            )
            time.sleep(delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{operation_name} failed unexpectedly")


def is_wake_only_transcript(text: str) -> bool:
    """True when transcript only repeats the wake phrase with no command."""
    normalized = normalize_text(text)
    return bool(normalized and WAKE_PHRASE and normalized == WAKE_PHRASE)


def sanitize_transcript(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        logger.warning(
            "Transcript exceeded MAX_TRANSCRIPT_CHARS=%s; truncating.",
            MAX_TRANSCRIPT_CHARS,
        )
        return cleaned[:MAX_TRANSCRIPT_CHARS].strip()
    return cleaned


def trim_history(history: List[Dict[str, str]]) -> None:
    """Bound history by message count and total character budget."""
    if len(history) > HISTORY_MAX_MESSAGES:
        del history[:-HISTORY_MAX_MESSAGES]

    if HISTORY_MAX_CHARS <= 0:
        return

    total_chars = sum(len((msg.get("content") or "")) for msg in history)
    while history and total_chars > HISTORY_MAX_CHARS:
        dropped = history.pop(0)
        total_chars -= len((dropped.get("content") or ""))


def append_history_turn(history: List[Dict[str, str]], user_text: str, reply: str) -> None:
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    trim_history(history)



def set_last_stt_error(message: Optional[str]) -> None:
    global _LAST_STT_ERROR
    _LAST_STT_ERROR = message


def get_last_stt_error() -> Optional[str]:
    return _LAST_STT_ERROR


def compute_rms(audio: np.ndarray) -> float:
    """Compute RMS amplitude for a chunk."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))



def ensure_recommended_listen_window() -> None:
    if LISTEN_SECONDS < 5 or LISTEN_SECONDS > 10:
        logger.warning(
            "LISTEN_SECONDS=%s is outside recommended 5-10 second range.",
            LISTEN_SECONDS,
        )

    if FOLLOWUP_LISTEN_SECONDS < 3 or FOLLOWUP_LISTEN_SECONDS > 12:
        logger.warning(
            "FOLLOWUP_LISTEN_SECONDS=%s is outside typical 3-12 second range.",
            FOLLOWUP_LISTEN_SECONDS,
        )

    if MULTI_TURN_MAX_TURNS > 8:
        logger.warning(
            "MULTI_TURN_MAX_TURNS=%s is high and may increase latency/cost.",
            MULTI_TURN_MAX_TURNS,
        )



def validate_runtime_config() -> bool:
    """Return False for invalid runtime settings that should stop startup."""
    valid = True

    if SAMPLE_RATE <= 0:
        logger.error("SAMPLE_RATE must be > 0 (got %s)", SAMPLE_RATE)
        valid = False
    if LISTEN_SECONDS <= 0:
        logger.error("LISTEN_SECONDS must be > 0 (got %s)", LISTEN_SECONDS)
        valid = False
    if FOLLOWUP_LISTEN_SECONDS <= 0:
        logger.error("FOLLOWUP_LISTEN_SECONDS must be > 0 (got %s)", FOLLOWUP_LISTEN_SECONDS)
        valid = False
    if HISTORY_MAX_MESSAGES < 2:
        logger.error("HISTORY_MAX_MESSAGES must be >= 2 (got %s)", HISTORY_MAX_MESSAGES)
        valid = False
    if HISTORY_MAX_CHARS < 200:
        logger.error("HISTORY_MAX_CHARS is too low (%s). Increase it to >= 200.", HISTORY_MAX_CHARS)
        valid = False
    if ENDPOINT_SPEECH_THRESHOLD <= 0 or ENDPOINT_SPEECH_THRESHOLD > 1.0:
        logger.error(
            "ENDPOINT_SPEECH_THRESHOLD must be in (0,1], got %s",
            ENDPOINT_SPEECH_THRESHOLD,
        )
        valid = False

    return valid



def command_exists(command_prefix: str) -> bool:
    """Return True if the command's executable exists on PATH."""
    parts = shlex.split(command_prefix)
    if not parts:
        return False
    return shutil.which(parts[0]) is not None



def _looks_like_executable(token: str, name: str) -> bool:
    base = os.path.basename(token).lower()
    target = name.lower()
    return base == target or base == f"{target}.exe"



def _has_cli_option(args: List[str], short_flag: str, long_flag: str) -> bool:
    for token in args:
        if token == short_flag or token == long_flag:
            return True
        if token.startswith(f"{long_flag}="):
            return True
        if token.startswith(short_flag) and token != short_flag:
            # Handles compact forms like -mgpt-5.3-codex
            return True
    return False



def _has_model_reasoning_config(args: List[str]) -> bool:
    for idx, token in enumerate(args):
        if token.startswith("model_reasoning_effort="):
            return True
        if idx > 0 and args[idx - 1] in ("--config", "-c"):
            if token.startswith("model_reasoning_effort="):
                return True
    return False



def build_codex_cli_command(command_prefix: str) -> str:
    """Normalize Codex CLI command for low-latency voice usage.

    Guarantees non-interactive mode (`exec`) and injects model/reasoning defaults
    unless already specified in the configured command.
    """
    args = shlex.split(command_prefix)
    if not args:
        return command_prefix

    if not _looks_like_executable(args[0], "codex"):
        return command_prefix

    if "exec" not in args and "e" not in args:
        args.insert(1, "exec")

    if CODEX_MODEL_NAME and not _has_cli_option(args, "-m", "--model"):
        args.extend(["-m", CODEX_MODEL_NAME])

    if CODEX_REASONING_LEVEL and not _has_model_reasoning_config(args):
        args.extend(["-c", f"model_reasoning_effort={CODEX_REASONING_LEVEL}"])

    return " ".join(shlex.quote(part) for part in args)



def render_conversation(history: List[Dict[str, str]], user_text: str) -> str:
    """Render a clean text prompt for CLI model backends."""
    lines: List[str] = []
    for msg in history[-HISTORY_MAX_MESSAGES:]:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    lines.append(f"USER: {user_text}")
    lines.append("ASSISTANT:")
    convo = "\n".join(lines)

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Answer the USER directly in plain text. Keep it concise and useful for voice.\n\n"
        f"Conversation so far:\n{convo}"
    )



def clean_cli_output(text: str) -> str:
    """Remove ANSI codes and obvious CLI banner noise."""
    stripped = ANSI_ESCAPE_RE.sub("", text or "").strip()
    if not stripped:
        return ""

    noise_prefixes = (
        "OpenAI Codex",
        "workdir:",
        "model:",
        "provider:",
        "approval:",
        "sandbox:",
        "reasoning",
        "session id:",
        "mcp startup:",
        "--------",
    )
    filtered_lines: List[str] = []
    for line in stripped.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(lowered.startswith(prefix.lower()) for prefix in noise_prefixes):
            continue
        filtered_lines.append(candidate)

    if not filtered_lines:
        return stripped
    return "\n".join(filtered_lines).strip()


def _looks_like_codex_auth_error(blob: str) -> bool:
    lowered = (blob or "").lower()
    indicators = (
        "refresh_token_reused",
        "provided authentication token is expired",
        "token is expired",
        "failed to refresh token",
        "log out and sign in again",
        "sign in again",
        "401 unauthorized",
    )
    return any(token in lowered for token in indicators)


def summarize_cli_failure_for_user(
    backend_name: str,
    returncode: int,
    raw_stdout: str,
    raw_stderr: str,
) -> str:
    """Map CLI backend failures to actionable, voice-safe user messages."""
    combined = f"{raw_stderr or ''}\n{raw_stdout or ''}".lower()

    if backend_name == "Codex CLI" and _looks_like_codex_auth_error(combined):
        return (
            "Codex CLI authentication expired. "
            "Please run codex logout, then codex login, then try again."
        )

    if "command not found" in combined or "no such file or directory" in combined:
        return (
            f"{backend_name} is not available on PATH. "
            "Run scripts/heyboy doctor for setup help."
        )

    if "permission denied" in combined:
        return (
            f"{backend_name} does not have permission to run. "
            "Check executable permissions and try again."
        )

    if "rate limit" in combined or "quota" in combined:
        return (
            f"{backend_name} hit a rate limit or quota. "
            "Please retry shortly."
        )

    logger.debug("%s non-zero return code=%s did not match known patterns.", backend_name, returncode)
    return f"Sorry, {backend_name} returned an error."


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------

_INSTANCE_LOCK_HANDLE = None


def release_instance_lock() -> None:
    global _INSTANCE_LOCK_HANDLE

    if _INSTANCE_LOCK_HANDLE is None:
        return

    try:
        if os.name == "posix":
            fcntl.flock(_INSTANCE_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
    except Exception:
        logger.debug("Failed to unlock instance file cleanly", exc_info=True)
    finally:
        try:
            _INSTANCE_LOCK_HANDLE.close()
        except Exception:
            logger.debug("Failed to close instance lock file", exc_info=True)
        _INSTANCE_LOCK_HANDLE = None


def acquire_instance_lock() -> bool:
    """Ensure only one heyboy runtime is active at a time."""
    global _INSTANCE_LOCK_HANDLE

    if os.name != "posix":
        return True

    try:
        _INSTANCE_LOCK_HANDLE = open(INSTANCE_LOCK_PATH, "w")
        fcntl.flock(_INSTANCE_LOCK_HANDLE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _INSTANCE_LOCK_HANDLE.write(str(os.getpid()))
        _INSTANCE_LOCK_HANDLE.flush()
        atexit.register(release_instance_lock)
        return True
    except BlockingIOError:
        logger.error(
            "Another heyboy instance is already running (lock: %s). Exiting.",
            INSTANCE_LOCK_PATH,
        )
        return False
    except Exception:
        logger.exception("Failed to acquire instance lock; exiting for safety.")
        return False


# ---------------------------------------------------------------------------
# Audio + Vosk
# ---------------------------------------------------------------------------


def load_vosk_model(model_path: str) -> vosk.Model:
    if not os.path.isdir(model_path):
        logger.error(
            "Vosk model not found at '%s'. Run scripts/install_part1_deps.sh first.",
            model_path,
        )
        raise FileNotFoundError(model_path)

    logger.info("Loading Vosk model: %s", model_path)
    model = vosk.Model(model_path)
    logger.info("Vosk model loaded.")
    return model



def wait_for_wake_phrase(model: vosk.Model, suppress_until_mono: float = 0.0) -> None:
    """Block until wake phrase is detected from live mic stream."""

    now = time.monotonic()
    if suppress_until_mono > now:
        delay = suppress_until_mono - now
        logger.info("Wake detector cooldown active for %.2fs", delay)
        time.sleep(delay)

    def _listen_until_wake() -> None:
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(False)

        logger.info("Listening for wake phrase: %r", WAKE_PHRASE)
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            dtype="int16",
            channels=CHANNELS,
        ) as stream:
            while True:
                raw, _overflow = stream.read(CHUNK_SIZE)
                pcm = bytes(raw)

                if recognizer.AcceptWaveform(pcm):
                    res = json.loads(recognizer.Result())
                    text = normalize_text(res.get("text", ""))
                    logger.debug("Vosk final: %r", text)
                else:
                    partial = json.loads(recognizer.PartialResult())
                    text = normalize_text(partial.get("partial", ""))
                    logger.debug("Vosk partial: %r", text)

                if WAKE_PHRASE and WAKE_PHRASE in text:
                    logger.info("Wake phrase detected.")
                    return

    run_audio_with_retries("wake listener", _listen_until_wake)



def record_audio(duration_s: int, label: str = "listen") -> np.ndarray:
    """Record mono int16 audio from default microphone.

    Uses optional early endpointing so we can stop shortly after the user stops
    speaking instead of always waiting the full listen window.
    """
    duration_s = max(1, int(duration_s))

    def _capture() -> np.ndarray:
        logger.info("Recording %s window: %ss", label, duration_s)

        max_frames = int(duration_s * SAMPLE_RATE)
        min_speech_chunks = max(
            1,
            int(ENDPOINT_MIN_SPEECH_MS / max(1.0, CHUNK_DURATION_S * 1000.0)),
        )
        trailing_silence_chunks = max(
            1,
            int(ENDPOINT_TRAILING_SILENCE_MS / max(1.0, CHUNK_DURATION_S * 1000.0)),
        )

        captured_chunks: List[np.ndarray] = []
        speech_started = False
        speech_chunk_count = 0
        silence_after_speech_chunks = 0
        total_frames = 0

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_SIZE,
        ) as stream:
            while total_frames < max_frames:
                chunk, _overflow = stream.read(CHUNK_SIZE)
                chunk_np = np.asarray(chunk, dtype=np.float32)
                if chunk_np.ndim == 1:
                    chunk_np = chunk_np.reshape(-1, 1)

                frame_count = int(chunk_np.shape[0])
                if frame_count <= 0:
                    continue

                captured_chunks.append(chunk_np[:, :1].copy())
                total_frames += frame_count

                rms = compute_rms(chunk_np)
                if rms >= ENDPOINT_SPEECH_THRESHOLD:
                    speech_started = True
                    speech_chunk_count += 1
                    silence_after_speech_chunks = 0
                elif speech_started:
                    silence_after_speech_chunks += 1

                if (
                    EARLY_ENDPOINTING_ENABLED
                    and speech_started
                    and speech_chunk_count >= min_speech_chunks
                    and silence_after_speech_chunks >= trailing_silence_chunks
                ):
                    logger.info(
                        "Early endpoint reached (%s speech chunks, %s trailing silence chunks).",
                        speech_chunk_count,
                        silence_after_speech_chunks,
                    )
                    break

        if captured_chunks:
            audio_float = np.concatenate(captured_chunks, axis=0)
        else:
            audio_float = np.zeros((1, 1), dtype=np.float32)

        recorded = (np.clip(audio_float, -1.0, 1.0) * 32767.0).astype(np.int16)

        if DEBUG_SAVE_AUDIO:
            DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            path = DEBUG_AUDIO_DIR / f"capture_{label}_{int(time.time())}.wav"
            sf.write(path.as_posix(), recorded, SAMPLE_RATE, subtype="PCM_16")
            logger.debug("Saved debug capture: %s", path)

        return recorded

    audio = run_audio_with_retries(f"audio capture ({label})", _capture)
    if isinstance(audio, np.ndarray):
        return audio
    raise TypeError("audio capture returned unexpected payload")



def transcribe_vosk_local(audio: np.ndarray, model: vosk.Model) -> str:
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetWords(True)

    raw = audio.tobytes()
    step = int(SAMPLE_RATE * 2 * 0.25)  # bytes for 250ms (int16 mono)
    for idx in range(0, len(raw), step):
        recognizer.AcceptWaveform(raw[idx : idx + step])

    final = json.loads(recognizer.FinalResult())
    set_last_stt_error(None)
    return (final.get("text") or "").strip()



def transcribe_deepgram(audio: np.ndarray) -> str:
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY is empty but STT_BACKEND=deepgram.")
        set_last_stt_error("Deepgram API key is missing. Please update DEEPGRAM_API_KEY.")
        return ""

    wav_io = io.BytesIO()
    sf.write(wav_io, audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
    wav_io.seek(0)

    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav",
    }
    params = {
        "model": DEEPGRAM_MODEL,
        "smart_format": "true",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            params=params,
            data=wav_io.read(),
            timeout=DEEPGRAM_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        channels = data.get("results", {}).get("channels", [])
        if not channels:
            set_last_stt_error(None)
            return ""
        alternatives = channels[0].get("alternatives", [])
        if not alternatives:
            set_last_stt_error(None)
            return ""

        set_last_stt_error(None)
        return (alternatives[0].get("transcript") or "").strip()
    except requests.exceptions.Timeout:
        logger.error("Deepgram STT timed out after %ss", DEEPGRAM_TIMEOUT)
        set_last_stt_error("Deepgram transcription timed out. Please try again.")
        return ""
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "?"
        body = (exc.response.text[:240] if exc.response is not None else "")
        logger.error("Deepgram STT HTTP error %s: %s", status, body)

        if status in (401, 403):
            set_last_stt_error("Deepgram authentication failed. Please refresh the API key.")
        elif status == 429:
            set_last_stt_error("Deepgram rate limit reached. Please retry shortly.")
        elif isinstance(status, int) and status >= 500:
            set_last_stt_error("Deepgram is temporarily unavailable. Please try again shortly.")
        else:
            set_last_stt_error("Deepgram returned an STT error.")
        return ""
    except requests.exceptions.RequestException as exc:
        logger.error("Deepgram STT request failed: %s", exc)
        set_last_stt_error("Deepgram network request failed. Check connection and retry.")
        return ""
    except (ValueError, KeyError, IndexError) as exc:
        logger.error("Deepgram STT response parse error: %s", exc)
        set_last_stt_error("Deepgram response could not be parsed.")
        return ""



def transcribe(audio: np.ndarray, model: vosk.Model) -> str:
    if STT_BACKEND == "vosk_local":
        text = sanitize_transcript(transcribe_vosk_local(audio, model))
        logger.info("Transcribed (vosk_local): %r", text)
        return text

    if STT_BACKEND == "deepgram":
        text = sanitize_transcript(transcribe_deepgram(audio))
        logger.info("Transcribed (deepgram:%s): %r", DEEPGRAM_MODEL, text)
        return text

    logger.error("Unsupported STT_BACKEND=%r", STT_BACKEND)
    set_last_stt_error("STT backend configuration is invalid.")
    return ""


# ---------------------------------------------------------------------------
# Backend routing
# ---------------------------------------------------------------------------


def query_backend(user_text: str, history: List[Dict[str, str]]) -> str:
    backend = ASSISTANT_BACKEND
    if backend == "openclaw_api":
        return query_openclaw_api(user_text, history)
    if backend == "codex_cli":
        codex_command = build_codex_cli_command(CODEX_CLI_COMMAND)
        return query_cli_backend(codex_command, user_text, history, "Codex CLI")
    if backend == "claude_cli":
        return query_cli_backend(
            CLAUDE_CLI_COMMAND, user_text, history, "Claude Code CLI"
        )
    if backend == "generic_cli":
        return query_cli_backend(
            GENERIC_CLI_COMMAND, user_text, history, "Generic CLI backend"
        )

    logger.error("Unsupported ASSISTANT_BACKEND=%r", backend)
    return (
        "Sorry — backend configuration is invalid. "
        "Set ASSISTANT_BACKEND to openclaw_api, codex_cli, claude_cli, or generic_cli."
    )



def query_openclaw_api(user_text: str, history: List[Dict[str, str]]) -> str:
    if not API_KEY:
        logger.error("API_KEY is empty. Configure .env before using openclaw_api backend.")
        return "I need an API key configured before I can answer."

    url = f"{API_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-HISTORY_MAX_MESSAGES:])
    messages.append({"role": "user", "content": user_text})

    payload: Dict = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "max_tokens": LLM_MAX_TOKENS,
    }

    # Explicit low-thinking routing for GPT-5.2-class models when supported.
    if THINKING_LEVEL:
        payload["reasoning"] = {"effort": THINKING_LEVEL}
        payload["reasoning_effort"] = THINKING_LEVEL

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        if response.status_code == 400 and (
            "reasoning" in payload or "reasoning_effort" in payload
        ):
            logger.warning(
                "Backend rejected reasoning fields; retrying request without them."
            )
            payload.pop("reasoning", None)
            payload.pop("reasoning_effort", None)
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=LLM_TIMEOUT,
            )

        response.raise_for_status()
        data = response.json()
        reply = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        logger.info("LLM reply chars=%s", len(reply))
        return reply or EMPTY_BACKEND_REPLY

    except requests.exceptions.Timeout:
        logger.error("LLM request timed out after %ss", LLM_TIMEOUT)
        return "Sorry, that request timed out."
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "?"
        body = (exc.response.text[:240] if exc.response is not None else "")
        logger.error("LLM HTTP error %s: %s", status, body)

        if status in (401, 403):
            return "Model API authentication failed. Please refresh your API key."
        if status == 404:
            return "Model API endpoint or model name looks invalid."
        if status == 408:
            return "Model API timed out before responding."
        if status == 429:
            return "Model API rate limit reached. Please retry in a moment."
        if isinstance(status, int) and status >= 500:
            return "Model API is temporarily unavailable. Please try again shortly."

        return "Sorry, the model API returned an error."
    except (KeyError, IndexError, ValueError) as exc:
        logger.error("Unexpected API response format: %s", exc)
        return "Sorry, I received an unexpected response payload."
    except requests.exceptions.RequestException as exc:
        logger.error("LLM request failed: %s", exc)
        return "Sorry, I couldn't reach the model backend."



def query_cli_backend(
    command_prefix: str,
    user_text: str,
    history: List[Dict[str, str]],
    backend_name: str,
) -> str:
    if not command_prefix.strip():
        logger.error("%s command is empty.", backend_name)
        return f"{backend_name} command is not configured."

    if not command_exists(command_prefix):
        logger.error("%s not found on PATH: %r", backend_name, command_prefix)
        return (
            f"{backend_name} is not installed or not on PATH. "
            "Run scripts/heyboy doctor for setup help."
        )

    prompt = render_conversation(history, user_text)
    args = shlex.split(command_prefix) + [prompt]

    logger.info("Querying %s", backend_name)
    logger.debug("CLI args: %s", args)

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("%s timed out after %ss", backend_name, CLI_TIMEOUT)
        return f"Sorry, {backend_name} timed out."
    except Exception as exc:
        logger.error("%s invocation failed: %s", backend_name, exc)
        return f"Sorry, {backend_name} invocation failed."

    raw_stdout = completed.stdout or ""
    raw_stderr = completed.stderr or ""
    stdout = clean_cli_output(raw_stdout)
    stderr = clean_cli_output(raw_stderr)

    if completed.returncode != 0:
        logger.error(
            "%s exited non-zero (%s). stderr=%r", backend_name, completed.returncode, stderr
        )
        return summarize_cli_failure_for_user(
            backend_name=backend_name,
            returncode=completed.returncode,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

    reply = (stdout or stderr).strip()
    if not reply:
        return f"Sorry, {backend_name} returned no text response."

    # Keep spoken responses reasonably short for TTS.
    return reply[:4000]


# ---------------------------------------------------------------------------
# Session orchestration
# ---------------------------------------------------------------------------


def handle_wake_session(model: vosk.Model, tts: "BargeInTTS", history: List[Dict[str, str]]) -> None:
    """Run one wake-initiated interaction session (single-turn or multi-turn)."""
    max_turns = MULTI_TURN_MAX_TURNS if MULTI_TURN_ENABLED else 1
    completed_turns = 0
    initial_no_speech_count = 0
    followup_no_speech_count = 0
    wake_only_count = 0

    while completed_turns < max_turns:
        is_followup = completed_turns > 0

        if is_followup:
            logger.info(
                "Opening multi-turn follow-up window: %ss (turn %s/%s)",
                FOLLOWUP_LISTEN_SECONDS,
                completed_turns + 1,
                max_turns,
            )
            if FOLLOWUP_PROMPT:
                tts.speak(FOLLOWUP_PROMPT, allow_barge_in=False)
            audio = record_audio(
                FOLLOWUP_LISTEN_SECONDS,
                label=f"followup{completed_turns}",
            )
        else:
            tts.speak(LISTEN_ACK, allow_barge_in=False)
            audio = record_audio(LISTEN_SECONDS, label="listen")

        user_text = transcribe(audio, model)

        if not user_text:
            stt_error = get_last_stt_error()
            if stt_error:
                logger.info("STT error encountered during %s turn: %s", "follow-up" if is_followup else "initial", stt_error)
                tts.speak(stt_error, allow_barge_in=False)
                return

            if is_followup:
                followup_no_speech_count += 1
                logger.info(
                    "No speech detected in follow-up window (%s/%s).",
                    followup_no_speech_count,
                    NO_SPEECH_RETRY_LIMIT + 1,
                )
                if followup_no_speech_count > NO_SPEECH_RETRY_LIMIT:
                    end_prompt = SESSION_END_PROMPT or FOLLOWUP_TIMEOUT_PROMPT
                    if end_prompt:
                        tts.speak(end_prompt, allow_barge_in=False)
                    return

                if FOLLOWUP_NO_SPEECH_PROMPT:
                    tts.speak(FOLLOWUP_NO_SPEECH_PROMPT, allow_barge_in=False)
                continue

            initial_no_speech_count += 1
            tts.speak(NO_SPEECH_PROMPT, allow_barge_in=False)
            if initial_no_speech_count > NO_SPEECH_RETRY_LIMIT:
                return
            continue

        initial_no_speech_count = 0
        followup_no_speech_count = 0

        if is_wake_only_transcript(user_text):
            wake_only_count += 1
            logger.info(
                "Transcript contained only wake phrase (%s/%s).",
                wake_only_count,
                WAKE_ONLY_RETRY_LIMIT + 1,
            )
            tts.speak(WAKE_ONLY_PROMPT, allow_barge_in=False)
            if wake_only_count > WAKE_ONLY_RETRY_LIMIT:
                return
            continue

        wake_only_count = 0

        reply = (query_backend(user_text, history) or "").strip() or EMPTY_BACKEND_REPLY
        append_history_turn(history, user_text, reply)

        completed = tts.speak(reply, allow_barge_in=True)
        if not completed:
            logger.info("Reply interrupted by user barge-in.")

        completed_turns += 1

    if SESSION_END_PROMPT:
        tts.speak(SESSION_END_PROMPT, allow_barge_in=False)


# ---------------------------------------------------------------------------
# TTS with barge-in
# ---------------------------------------------------------------------------


class _PlaybackState:
    """Tracks one in-flight pyttsx3 utterance."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.engine: Optional[object] = None
        self.engine_ready = threading.Event()
        self.done_event = threading.Event()
        self.thread: Optional[threading.Thread] = None


class BargeInTTS:
    """pyttsx3 playback that can be interrupted when user speaks."""

    def __init__(self) -> None:
        self._speak_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._active_playback: Optional[_PlaybackState] = None
        self._last_text: str = ""
        self._last_text_started_mono: float = 0.0
        self._last_playback_end_mono: float = 0.0

    def _set_active_playback(self, state: Optional[_PlaybackState]) -> None:
        with self._state_lock:
            self._active_playback = state

    def _get_active_playback(self) -> Optional[_PlaybackState]:
        with self._state_lock:
            return self._active_playback

    def _worker(self, state: _PlaybackState) -> None:
        try:
            engine = pyttsx3.init()
            state.engine = engine
            state.engine_ready.set()
            engine.say(state.text)
            engine.runAndWait()
        except Exception as exc:
            logger.warning("TTS engine error: %s", exc)
        finally:
            if not state.engine_ready.is_set():
                state.engine_ready.set()
            state.done_event.set()
            with self._state_lock:
                self._last_playback_end_mono = time.monotonic()
                if self._active_playback is state:
                    self._active_playback = None

    def _request_stop(self, state: _PlaybackState, reason: str) -> None:
        state.engine_ready.wait(timeout=0.25)
        engine = state.engine
        if engine is None:
            logger.debug("TTS stop requested before engine init (%s).", reason)
            return
        try:
            engine.stop()
        except Exception:
            logger.debug("TTS engine stop failed (%s)", reason, exc_info=True)

    def _join_playback_thread(self, state: _PlaybackState, timeout_s: float) -> bool:
        thread = state.thread
        if thread is None:
            return state.done_event.is_set()
        thread.join(timeout=timeout_s)
        return not thread.is_alive()

    def _drain_stale_playback(self) -> None:
        stale = self._get_active_playback()
        if stale is None or stale.done_event.is_set():
            return

        logger.warning(
            "Detected unfinished TTS playback from previous turn; stopping before next utterance."
        )
        self._request_stop(stale, reason="stale playback")
        stale.done_event.wait(timeout=2.0)
        self._join_playback_thread(stale, timeout_s=1.0)

    def _non_interruptible_timeout_s(self, text: str) -> float:
        return max(2.0, min(15.0, len(text) * 0.11))

    def wake_suppress_until(self) -> float:
        with self._state_lock:
            return self._last_playback_end_mono + (WAKE_SUPPRESS_AFTER_TTS_MS / 1000.0)

    def _dedupe_text_within_window(self, text: str) -> bool:
        if TTS_DUPLICATE_WINDOW_MS <= 0:
            return False

        candidate = normalize_text(text)
        if not candidate:
            return False

        now = time.monotonic()
        with self._state_lock:
            last_text = normalize_text(self._last_text)
            elapsed_ms = (now - self._last_text_started_mono) * 1000.0
            is_duplicate = bool(
                last_text
                and candidate == last_text
                and elapsed_ms <= float(TTS_DUPLICATE_WINDOW_MS)
            )
            if not is_duplicate:
                self._last_text = text
                self._last_text_started_mono = now
            return is_duplicate

    def speak(self, text: str, allow_barge_in: bool = True) -> bool:
        """Speak text. Returns False if interrupted by barge-in."""
        if not text:
            return True

        with self._speak_lock:
            if self._dedupe_text_within_window(text):
                logger.warning(
                    "Dropping duplicate TTS within %sms window: %r",
                    TTS_DUPLICATE_WINDOW_MS,
                    text[:80],
                )
                return True

            self._drain_stale_playback()

            state = _PlaybackState(text)
            thread = threading.Thread(target=self._worker, args=(state,), daemon=True)
            state.thread = thread
            self._set_active_playback(state)

            logger.info("TTS speaking (%s chars)", len(text))
            thread.start()

            if not allow_barge_in:
                timeout_s = self._non_interruptible_timeout_s(text)
                finished = state.done_event.wait(timeout=timeout_s)
                if not finished:
                    logger.warning(
                        "TTS playback exceeded %.1fs timeout; forcing stop.",
                        timeout_s,
                    )
                    self._request_stop(state, reason="non-interruptible timeout")
                    state.done_event.wait(timeout=2.0)

                if not self._join_playback_thread(state, timeout_s=1.0):
                    logger.warning(
                        "TTS worker thread did not exit cleanly after non-interruptible playback."
                    )
                    self._request_stop(state, reason="non-interruptible forced join")
                    self._join_playback_thread(state, timeout_s=2.0)
                return True

            required_frames = max(1, int(BARGE_IN_HOLD_MS / (CHUNK_DURATION_S * 1000)))
            grace_until = time.monotonic() + (BARGE_IN_GRACE_MS / 1000.0)
            consecutive_frames = 0
            interrupted = False

            try:
                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    blocksize=CHUNK_SIZE,
                ) as stream:
                    while not state.done_event.is_set():
                        chunk, _overflow = stream.read(CHUNK_SIZE)
                        if time.monotonic() < grace_until:
                            continue

                        rms = compute_rms(chunk)
                        if rms > BARGE_IN_THRESHOLD:
                            consecutive_frames += 1
                        else:
                            consecutive_frames = 0

                        logger.debug(
                            "Barge-in rms=%.5f threshold=%.5f frames=%s/%s",
                            rms,
                            BARGE_IN_THRESHOLD,
                            consecutive_frames,
                            required_frames,
                        )

                        if consecutive_frames >= required_frames:
                            logger.info("Barge-in detected. Stopping TTS playback.")
                            self._request_stop(state, reason="barge-in")
                            interrupted = True
                            break

                        time.sleep(0.01)

            except Exception as exc:
                logger.warning("Barge-in monitor error: %s", exc)

            if not state.done_event.wait(timeout=2.0):
                self._request_stop(state, reason="barge-in monitor timeout")
                state.done_event.wait(timeout=2.0)

            if not self._join_playback_thread(state, timeout_s=1.0):
                logger.warning("TTS worker thread did not exit cleanly after barge-in monitor.")
                self._request_stop(state, reason="barge-in forced join")
                self._join_playback_thread(state, timeout_s=2.0)

            return not interrupted


# ---------------------------------------------------------------------------
# Main event loop
# ---------------------------------------------------------------------------


def print_startup_banner() -> None:
    logger.info("=" * 66)
    logger.info("heyboy voice assistant — Part 1")
    logger.info("Backend    : %s", ASSISTANT_BACKEND)
    logger.info("STT        : %s", STT_BACKEND)
    if STT_BACKEND == "deepgram":
        logger.info("STT model  : %s", DEEPGRAM_MODEL)

    if ASSISTANT_BACKEND == "codex_cli":
        logger.info("Codex model: %s", CODEX_MODEL_NAME)
        logger.info("Codex think: %s", CODEX_REASONING_LEVEL or "(unset)")
        logger.info("Codex cmd  : %s", build_codex_cli_command(CODEX_CLI_COMMAND))
    else:
        logger.info("Model      : %s", MODEL_NAME)
        logger.info("Thinking   : %s", THINKING_LEVEL)

    logger.info("Wake phrase: %r", WAKE_PHRASE)
    logger.info("Listen ack : %r", LISTEN_ACK)
    if FOLLOWUP_PROMPT:
        logger.info("Follow-up  : %r", FOLLOWUP_PROMPT)
    logger.info("Listen win : %ss", LISTEN_SECONDS)
    logger.info(
        "Endpoint   : %s (thr=%.3f min=%sms tail=%sms)",
        "on" if EARLY_ENDPOINTING_ENABLED else "off",
        ENDPOINT_SPEECH_THRESHOLD,
        ENDPOINT_MIN_SPEECH_MS,
        ENDPOINT_TRAILING_SILENCE_MS,
    )
    logger.info(
        "Multi-turn : %s (max=%s turns, follow-up=%ss)",
        "on" if MULTI_TURN_ENABLED else "off",
        MULTI_TURN_MAX_TURNS,
        FOLLOWUP_LISTEN_SECONDS,
    )
    logger.info(
        "Retries    : no-speech=%s wake-only=%s audio=%s",
        NO_SPEECH_RETRY_LIMIT,
        WAKE_ONLY_RETRY_LIMIT,
        AUDIO_RETRY_ATTEMPTS,
    )
    logger.info(
        "TTS guard  : dedupe=%sms wake-suppress=%sms",
        TTS_DUPLICATE_WINDOW_MS,
        WAKE_SUPPRESS_AFTER_TTS_MS,
    )
    logger.info("History    : %s msgs / %s chars", HISTORY_MAX_MESSAGES, HISTORY_MAX_CHARS)
    logger.info("Audio chunk: %.2fs", CHUNK_DURATION_S)
    logger.info("Barge-in   : rms>%.3f hold=%sms", BARGE_IN_THRESHOLD, BARGE_IN_HOLD_MS)
    if ASSISTANT_BACKEND == "openclaw_api":
        logger.info("API base   : %s", API_BASE_URL)
    logger.info("=" * 66)



def main() -> None:
    if not acquire_instance_lock():
        return

    if STT_BACKEND not in ("vosk_local", "deepgram"):
        logger.error(
            "Unsupported STT_BACKEND=%r. Use one of: vosk_local, deepgram",
            STT_BACKEND,
        )
        return

    if STT_BACKEND == "deepgram" and not DEEPGRAM_API_KEY:
        logger.error(
            "STT_BACKEND is deepgram but DEEPGRAM_API_KEY is missing. "
            "Set it in your environment or .env file."
        )
        return

    if not validate_runtime_config():
        return

    ensure_recommended_listen_window()
    print_startup_banner()

    model = load_vosk_model(VOSK_MODEL_PATH)
    tts = BargeInTTS()
    history: List[Dict[str, str]] = []

    while True:
        try:
            # 1) Wait for wake phrase
            wait_for_wake_phrase(model, suppress_until_mono=tts.wake_suppress_until())

            # 2) Handle one wake-triggered interaction session
            handle_wake_session(model, tts, history)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received; shutting down.")
            break
        except Exception:
            logger.exception("Unhandled loop error; recovering in 1s")
            time.sleep(1.0)

    logger.info("Goodbye.")


if __name__ == "__main__":
    main()
