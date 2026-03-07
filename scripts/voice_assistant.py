#!/usr/bin/env python3
"""
openclaw heyboy voice assistant – Part 1
=========================================
Flow:
    1. Always-on vosk streaming → detect wake phrase "hey boy"
    2. Record RECORD_SECONDS of audio
    3. Transcribe locally with vosk (offline, no cloud STT)
    4. POST to OpenAI-compatible /v1/chat/completions (bearer token auth)
    5. Speak reply via pyttsx3; stop immediately on barge-in (mic RMS monitor)

Environment config via .env (see .env.example).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from typing import Dict, List, Optional

import numpy as np
import pyttsx3
import requests
import sounddevice as sd
import vosk
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration  (all overridable via .env)
# ---------------------------------------------------------------------------

load_dotenv()

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
VOSK_MODEL_PATH: str = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us")
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://api.openai.com")
API_KEY: str = os.getenv("API_KEY", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-5.2")
SYSTEM_PROMPT: str = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, concise voice assistant. Keep responses short and clear.",
)

SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
CHANNELS: int = 1
CHUNK_DURATION: float = 0.1  # seconds per audio chunk fed to vosk
CHUNK_SIZE: int = int(SAMPLE_RATE * CHUNK_DURATION)

WAKE_PHRASE: str = os.getenv("WAKE_PHRASE", "hey boy").lower()
RECORD_SECONDS: int = int(os.getenv("RECORD_SECONDS", "7"))

# RMS amplitude (float32, 0-1 scale) that triggers barge-in
BARGE_IN_THRESHOLD: float = float(os.getenv("BARGE_IN_THRESHOLD", "0.02"))

# "Low thinking" LLM config – deterministic, low-latency for voice
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

# Rolling conversation window (number of messages kept in history)
HISTORY_MAX_MESSAGES: int = int(os.getenv("HISTORY_MAX_MESSAGES", "20"))

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

# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def compute_rms(audio: np.ndarray) -> float:
    """Root-mean-square amplitude of an audio chunk.

    Used by the barge-in monitor to detect when the user starts speaking
    while TTS is active.

    Args:
        audio: numpy array of audio samples (any dtype, cast to float32).

    Returns:
        RMS value in the range [0, 1] for float32 input.
    """
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))


# ---------------------------------------------------------------------------
# Vosk model loader
# ---------------------------------------------------------------------------


def load_vosk_model(model_path: str) -> vosk.Model:
    """Load vosk acoustic model from disk.

    Exits with an informative message if the model directory is missing
    rather than raising a cryptic vosk exception.

    Args:
        model_path: Path to the vosk model directory.

    Returns:
        Initialised vosk.Model instance.
    """
    if not os.path.exists(model_path):
        logger.error(
            "Vosk model not found at '%s'. "
            "Run scripts/install_part1_deps.sh or download manually from "
            "https://alphacephei.com/vosk/models and set VOSK_MODEL_PATH in .env",
            model_path,
        )
        sys.exit(1)

    logger.info("Loading vosk model from '%s' …", model_path)
    model = vosk.Model(model_path)
    logger.info("Vosk model ready.")
    return model


# ---------------------------------------------------------------------------
# Wake-phrase detection (always-on streaming)
# ---------------------------------------------------------------------------


def wait_for_wake_phrase(model: vosk.Model) -> None:
    """Block until WAKE_PHRASE is heard on the default microphone.

    Opens a raw PCM input stream and feeds CHUNK_SIZE frames through a
    vosk recogniser on every iteration.  Both partial and final results
    are checked so detection is as low-latency as possible.

    Args:
        model: Loaded vosk.Model to use for recognition.
    """
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)  # word timestamps not needed here

    logger.info("Listening for wake phrase: %r …", WAKE_PHRASE)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        dtype="int16",
        channels=CHANNELS,
    ) as stream:
        while True:
            raw, _ = stream.read(CHUNK_SIZE)
            data = bytes(raw)

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower()
                logger.debug("Vosk final: %r", text)
            else:
                partial = json.loads(rec.PartialResult())
                text = partial.get("partial", "").lower()
                logger.debug("Vosk partial: %r", text)

            if WAKE_PHRASE in text:
                logger.info("Wake phrase detected.")
                return


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------


def record_audio(duration: int = RECORD_SECONDS) -> np.ndarray:
    """Record `duration` seconds from the default microphone.

    Uses sounddevice blocking record for simplicity; the function returns
    only after all frames are captured.

    Args:
        duration: Recording duration in seconds.

    Returns:
        Mono int16 numpy array of shape (duration * SAMPLE_RATE, 1).
    """
    logger.info("Recording %d second(s) …", duration)
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocking=True,
    )
    logger.debug("Recording complete. Shape: %s", audio.shape)
    return audio


# ---------------------------------------------------------------------------
# Local transcription
# ---------------------------------------------------------------------------


def transcribe(audio: np.ndarray, model: vosk.Model) -> str:
    """Transcribe a mono int16 numpy array offline using vosk.

    Feeds raw PCM bytes through a fresh KaldiRecogniser in fixed-size
    chunks, then returns the final decoded text.

    Args:
        audio: Mono int16 numpy array (output of record_audio).
        model: Loaded vosk.Model.

    Returns:
        Transcribed text, or an empty string if nothing was recognised.
    """
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)

    raw = audio.tobytes()
    step = 8000  # ~0.25 s worth of int16 bytes at 16 kHz
    for i in range(0, len(raw), step):
        rec.AcceptWaveform(raw[i : i + step])

    result = json.loads(rec.FinalResult())
    text = result.get("text", "").strip()
    logger.info("Transcribed: %r", text)
    return text


# ---------------------------------------------------------------------------
# LLM query
# ---------------------------------------------------------------------------


def query_llm(user_text: str, history: List[Dict[str, str]]) -> str:
    """Send `user_text` to an OpenAI-compatible chat completions endpoint.

    Prepends the system prompt and full conversation history so the model
    has context.  Uses a "low thinking" configuration (low temperature,
    bounded max_tokens) to prioritise fast, deterministic voice responses.

    Args:
        user_text: The user's transcribed utterance.
        history:   Rolling list of {"role": …, "content": …} dicts.

    Returns:
        The assistant's reply string, or an error message on failure.
    """
    url = f"{API_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    messages: List[Dict[str, str]] = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_text}]
    )
    payload: Dict = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": LLM_MAX_TOKENS,
        # Low thinking config: low temperature → fast, deterministic responses
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
    }

    logger.debug(
        "LLM POST %s  model=%s  messages=%d", url, MODEL_NAME, len(messages)
    )

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        reply: str = data["choices"][0]["message"]["content"].strip()
        logger.info("LLM reply (%d chars): %r", len(reply), reply[:160])
        return reply

    except requests.exceptions.Timeout:
        logger.error("LLM request timed out after %ds.", LLM_TIMEOUT)
        return "Sorry, the request timed out."

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        body = (exc.response.text[:200] if exc.response is not None else "")
        logger.error("LLM HTTP error %s: %s", status, body)
        return "Sorry, the language model returned an error."

    except requests.exceptions.RequestException as exc:
        logger.error("LLM request failed: %s", exc)
        return "Sorry, I couldn't reach the language model."

    except (KeyError, IndexError, ValueError) as exc:
        logger.error("Unexpected LLM response format: %s", exc)
        return "Sorry, I received an unexpected response."


# ---------------------------------------------------------------------------
# TTS with barge-in detection
# ---------------------------------------------------------------------------


class BargeInTTS:
    """Text-to-speech speaker with real-time barge-in detection.

    Runs pyttsx3 in a daemon thread while simultaneously monitoring the
    microphone for energy above BARGE_IN_THRESHOLD.  If the user starts
    speaking during playback, speech is stopped and speak() returns False.

    Usage::

        tts = BargeInTTS()
        completed = tts.speak("Hello, how can I help?")
        if not completed:
            print("User interrupted.")
    """

    def __init__(self) -> None:
        self._done_event: threading.Event = threading.Event()
        self._engine: Optional[object] = None  # pyttsx3.engine.Engine

    # ------------------------------------------------------------------
    # Private

    def _tts_worker(self, text: str) -> None:
        """Run pyttsx3 synthesis in a background thread."""
        try:
            self._engine = pyttsx3.init()
            self._engine.say(text)  # type: ignore[union-attr]
            self._engine.runAndWait()  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("pyttsx3 error: %s", exc)
        finally:
            self._done_event.set()

    # ------------------------------------------------------------------
    # Public

    def speak(self, text: str) -> bool:
        """Speak `text` and return when done or interrupted.

        Args:
            text: String to synthesise and play.

        Returns:
            True if speech completed fully.
            False if barge-in interrupted playback.
        """
        if not text:
            return True

        logger.info("TTS speaking: %r", text[:80])
        self._done_event.clear()
        self._engine = None

        tts_thread = threading.Thread(
            target=self._tts_worker, args=(text,), daemon=True
        )
        tts_thread.start()

        interrupted = False
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=CHUNK_SIZE,
            ) as mic:
                while not self._done_event.is_set():
                    chunk, _ = mic.read(CHUNK_SIZE)
                    rms = compute_rms(chunk)
                    logger.debug(
                        "Barge-in RMS=%.5f threshold=%.5f", rms, BARGE_IN_THRESHOLD
                    )

                    if rms > BARGE_IN_THRESHOLD:
                        logger.info(
                            "Barge-in detected (RMS %.4f > %.4f) — stopping TTS.",
                            rms,
                            BARGE_IN_THRESHOLD,
                        )
                        if self._engine is not None:
                            try:
                                self._engine.stop()  # type: ignore[union-attr]
                            except Exception:
                                pass
                        interrupted = True
                        break

                    time.sleep(0.01)

        except Exception as exc:
            logger.warning("Mic monitoring error during TTS: %s", exc)

        tts_thread.join(timeout=2.0)
        return not interrupted


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: initialise and run the voice assistant event loop."""
    logger.info("=" * 60)
    logger.info("openclaw heyboy voice assistant — Part 1")
    logger.info("  Model   : %s", MODEL_NAME)
    logger.info("  API     : %s", API_BASE_URL)
    logger.info("  Wake    : %r", WAKE_PHRASE)
    logger.info("  Record  : %ds", RECORD_SECONDS)
    logger.info("  Barge-in: RMS > %.3f", BARGE_IN_THRESHOLD)
    logger.info("=" * 60)

    if not API_KEY:
        logger.warning("API_KEY is not set — LLM calls will fail.")

    model = load_vosk_model(VOSK_MODEL_PATH)
    tts = BargeInTTS()
    history: List[Dict[str, str]] = []

    while True:
        try:
            # ── Step 1: Always-on wake-phrase detection ──────────────────
            wait_for_wake_phrase(model)

            # ── Step 2: Acknowledge ──────────────────────────────────────
            tts.speak("Yes?")

            # ── Step 3: Record user utterance ────────────────────────────
            audio = record_audio(RECORD_SECONDS)

            # ── Step 4: Transcribe locally ───────────────────────────────
            user_text = transcribe(audio, model)
            if not user_text:
                logger.info("No speech detected after wake phrase; resuming listen.")
                tts.speak("I didn't catch that.")
                continue

            # ── Step 5: Query LLM ────────────────────────────────────────
            reply = query_llm(user_text, history)

            # ── Step 6: Update rolling conversation history ──────────────
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            if len(history) > HISTORY_MAX_MESSAGES:
                history = history[-HISTORY_MAX_MESSAGES:]

            # ── Step 7: Speak reply; barge-in stops playback ─────────────
            completed = tts.speak(reply)
            if not completed:
                logger.info("User barged in; returning to wake-phrase listen.")

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt — shutting down.")
            break

        except Exception:
            logger.exception("Unhandled exception in main loop; continuing in 1 s …")
            time.sleep(1.0)

    logger.info("Goodbye.")


if __name__ == "__main__":
    main()
