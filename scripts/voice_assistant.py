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
from typing import Dict, List, Optional

import numpy as np
import pyttsx3
import requests
import sounddevice as sd
import soundfile as sf
import vosk
from dotenv import load_dotenv

if os.name == "posix":
    import fcntl

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ASSISTANT_BACKEND = os.getenv("ASSISTANT_BACKEND", "openclaw_api").strip().lower()

# Wake/listen
WAKE_PHRASE_RAW = os.getenv("WAKE_PHRASE", "hey boy")
LISTEN_SECONDS = int(os.getenv("LISTEN_SECONDS", os.getenv("RECORD_SECONDS", "7")))
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHANNELS = 1
CHUNK_DURATION_S = float(os.getenv("AUDIO_CHUNK_DURATION_S", "0.20"))
if CHUNK_DURATION_S < 0.05:
    CHUNK_DURATION_S = 0.05
if CHUNK_DURATION_S > 0.50:
    CHUNK_DURATION_S = 0.50
CHUNK_SIZE = max(1, int(SAMPLE_RATE * CHUNK_DURATION_S))
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us")

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
DEEPGRAM_TIMEOUT = int(os.getenv("DEEPGRAM_TIMEOUT", "20"))

# API backend (OpenAI-compatible)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:3333")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.2")
THINKING_LEVEL = os.getenv("THINKING_LEVEL", "low").strip().lower()
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "400"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# CLI backends
CODEX_CLI_COMMAND = os.getenv("CODEX_CLI_COMMAND", "codex exec")
CLAUDE_CLI_COMMAND = os.getenv(
    "CLAUDE_CLI_COMMAND", "claude --dangerously-skip-permissions --print"
)
GENERIC_CLI_COMMAND = os.getenv("GENERIC_CLI_COMMAND", "")
CLI_TIMEOUT = int(os.getenv("CLI_TIMEOUT", "120"))

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a concise, helpful voice assistant. Keep responses short and clear.",
)

# Barge-in
BARGE_IN_THRESHOLD = float(os.getenv("BARGE_IN_THRESHOLD", "0.03"))
BARGE_IN_HOLD_MS = int(os.getenv("BARGE_IN_HOLD_MS", "220"))
BARGE_IN_GRACE_MS = int(os.getenv("BARGE_IN_GRACE_MS", "350"))

# Context + debug
HISTORY_MAX_MESSAGES = int(os.getenv("HISTORY_MAX_MESSAGES", "20"))
DEBUG_SAVE_AUDIO = os.getenv("DEBUG_SAVE_AUDIO", "0") == "1"
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



def command_exists(command_prefix: str) -> bool:
    """Return True if the command's executable exists on PATH."""
    parts = shlex.split(command_prefix)
    if not parts:
        return False
    return shutil.which(parts[0]) is not None



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



def wait_for_wake_phrase(model: vosk.Model) -> None:
    """Block until wake phrase is detected from live mic stream."""
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



def record_audio(duration_s: int) -> np.ndarray:
    """Record mono int16 audio from default microphone."""
    logger.info("Recording listen window: %ss", duration_s)
    audio = sd.rec(
        int(duration_s * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocking=True,
    )

    if DEBUG_SAVE_AUDIO:
        DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_AUDIO_DIR / f"capture_{int(time.time())}.wav"
        sf.write(path.as_posix(), audio, SAMPLE_RATE, subtype="PCM_16")
        logger.debug("Saved debug capture: %s", path)

    return audio



def transcribe_vosk_local(audio: np.ndarray, model: vosk.Model) -> str:
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetWords(True)

    raw = audio.tobytes()
    step = int(SAMPLE_RATE * 2 * 0.25)  # bytes for 250ms (int16 mono)
    for idx in range(0, len(raw), step):
        recognizer.AcceptWaveform(raw[idx : idx + step])

    final = json.loads(recognizer.FinalResult())
    return (final.get("text") or "").strip()



def transcribe_deepgram(audio: np.ndarray) -> str:
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY is empty but STT_BACKEND=deepgram.")
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
            return ""
        alternatives = channels[0].get("alternatives", [])
        if not alternatives:
            return ""
        return (alternatives[0].get("transcript") or "").strip()
    except requests.exceptions.Timeout:
        logger.error("Deepgram STT timed out after %ss", DEEPGRAM_TIMEOUT)
        return ""
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "?"
        body = (exc.response.text[:240] if exc.response is not None else "")
        logger.error("Deepgram STT HTTP error %s: %s", status, body)
        return ""
    except requests.exceptions.RequestException as exc:
        logger.error("Deepgram STT request failed: %s", exc)
        return ""
    except (ValueError, KeyError, IndexError) as exc:
        logger.error("Deepgram STT response parse error: %s", exc)
        return ""



def transcribe(audio: np.ndarray, model: vosk.Model) -> str:
    if STT_BACKEND == "vosk_local":
        text = transcribe_vosk_local(audio, model)
        logger.info("Transcribed (vosk_local): %r", text)
        return text

    if STT_BACKEND == "deepgram":
        text = transcribe_deepgram(audio)
        logger.info("Transcribed (deepgram:%s): %r", DEEPGRAM_MODEL, text)
        return text

    logger.error("Unsupported STT_BACKEND=%r", STT_BACKEND)
    return ""


# ---------------------------------------------------------------------------
# Backend routing
# ---------------------------------------------------------------------------


def query_backend(user_text: str, history: List[Dict[str, str]]) -> str:
    backend = ASSISTANT_BACKEND
    if backend == "openclaw_api":
        return query_openclaw_api(user_text, history)
    if backend == "codex_cli":
        return query_cli_backend(CODEX_CLI_COMMAND, user_text, history, "Codex CLI")
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
        reply = data["choices"][0]["message"]["content"].strip()
        logger.info("LLM reply chars=%s", len(reply))
        return reply or ""

    except requests.exceptions.Timeout:
        logger.error("LLM request timed out after %ss", LLM_TIMEOUT)
        return "Sorry, that request timed out."
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response else "?"
        body = (exc.response.text[:240] if exc.response is not None else "")
        logger.error("LLM HTTP error %s: %s", status, body)
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
# TTS with barge-in
# ---------------------------------------------------------------------------


class BargeInTTS:
    """pyttsx3 playback that can be interrupted when user speaks."""

    def __init__(self) -> None:
        self._engine: Optional[object] = None
        self._done_event = threading.Event()

    def _worker(self, text: str) -> None:
        try:
            self._engine = pyttsx3.init()
            self._engine.say(text)  # type: ignore[union-attr]
            self._engine.runAndWait()  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("TTS engine error: %s", exc)
        finally:
            self._done_event.set()

    def speak(self, text: str, allow_barge_in: bool = True) -> bool:
        """Speak text. Returns False if interrupted by barge-in."""
        if not text:
            return True

        self._done_event.clear()
        self._engine = None

        logger.info("TTS speaking (%s chars)", len(text))
        thread = threading.Thread(target=self._worker, args=(text,), daemon=True)
        thread.start()

        if not allow_barge_in:
            thread.join(timeout=max(1.0, len(text) * 0.08))
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
                while not self._done_event.is_set():
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
                        if self._engine is not None:
                            try:
                                self._engine.stop()  # type: ignore[union-attr]
                            except Exception:
                                pass
                        interrupted = True
                        break

                    time.sleep(0.01)

        except Exception as exc:
            logger.warning("Barge-in monitor error: %s", exc)

        thread.join(timeout=2.0)
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
    logger.info("Model      : %s", MODEL_NAME)
    logger.info("Thinking   : %s", THINKING_LEVEL)
    logger.info("Wake phrase: %r", WAKE_PHRASE)
    logger.info("Listen win : %ss", LISTEN_SECONDS)
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

    ensure_recommended_listen_window()
    print_startup_banner()

    model = load_vosk_model(VOSK_MODEL_PATH)
    tts = BargeInTTS()
    history: List[Dict[str, str]] = []

    while True:
        try:
            # 1) Wait for wake phrase
            wait_for_wake_phrase(model)

            # 2) Quick acknowledgement (not interruptible)
            tts.speak("Yes?", allow_barge_in=False)

            # 3) Listen window (default 7s)
            audio = record_audio(LISTEN_SECONDS)

            # 4) Local transcription
            user_text = transcribe(audio, model)
            if not user_text:
                tts.speak("I didn't catch that.", allow_barge_in=False)
                continue

            # 5) Route to selected backend
            reply = query_backend(user_text, history)

            # 6) Update rolling context
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            if len(history) > HISTORY_MAX_MESSAGES:
                history = history[-HISTORY_MAX_MESSAGES:]

            # 7) Speak reply (interruptible)
            completed = tts.speak(reply, allow_barge_in=True)
            if not completed:
                logger.info("Reply interrupted by user barge-in.")

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received; shutting down.")
            break
        except Exception:
            logger.exception("Unhandled loop error; recovering in 1s")
            time.sleep(1.0)

    logger.info("Goodbye.")


if __name__ == "__main__":
    main()
