# Architecture — openclaw heyboy voice assistant

## Overview

heyboy is a local-first voice assistant pipeline.  Every stage from wake-word detection through speech recognition runs **on-device** with no network round-trips.  Only the LLM inference step calls an external (or self-hosted) API.

```
┌─────────────────────────────────────────────────────────────────┐
│                         heyboy pipeline                         │
│                                                                 │
│  Microphone                                                     │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────┐                                   │
│  │  Always-on wake listener  │  sounddevice raw stream          │
│  │  (vosk KaldiRecogniser)  │  100 ms chunks @ 16 kHz mono     │
│  └──────────────┬───────────┘                                   │
│                 │ "hey boy" detected                            │
│                 ▼                                               │
│  ┌──────────────────────────┐                                   │
│  │  Audio recorder          │  sd.rec() 7 s blocking           │
│  └──────────────┬───────────┘                                   │
│                 │ int16 numpy array                             │
│                 ▼                                               │
│  ┌──────────────────────────┐                                   │
│  │  Local STT (vosk)        │  KaldiRecogniser FinalResult      │
│  └──────────────┬───────────┘                                   │
│                 │ transcript string                             │
│                 ▼                                               │
│  ┌──────────────────────────┐   HTTPS POST /v1/chat/completions │
│  │  LLM client (requests)   │ ─────────────────────────────►   │
│  │  Bearer token auth       │ ◄─────────────────────────────   │
│  └──────────────┬───────────┘   JSON response                  │
│                 │ reply string                                  │
│                 ▼                                               │
│  ┌──────────────────────────┐                                   │
│  │  TTS + barge-in monitor  │  pyttsx3 (daemon thread)         │
│  │  (BargeInTTS)            │  + sd.InputStream RMS check       │
│  └──────────────────────────┘                                   │
│      │                                                          │
│      ▼                                                          │
│  Speakers / headphones                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component breakdown

### 1. Wake-phrase listener

- **Library:** `vosk` + `sounddevice`
- Streams raw PCM (int16, 16 kHz, mono) in 100 ms blocks.
- A `KaldiRecogniser` decodes partial and final hypotheses.
- The wake phrase is checked as a substring match against the lowercased hypothesis text — simple but effective for a fixed phrase.
- CPU usage: ~5–15 % on a modern laptop with the small English model.

### 2. Audio recorder

- **Library:** `sounddevice.rec()` (blocking)
- Records exactly `RECORD_SECONDS` (default 7) seconds after wake.
- Returns a mono int16 numpy array.
- Future improvement: voice-activity detection to stop early on silence.

### 3. Local speech-to-text

- **Library:** `vosk`
- Re-uses the same loaded `vosk.Model`; creates a fresh `KaldiRecogniser` per utterance.
- PCM bytes fed in 0.25 s steps; `FinalResult()` called after all bytes consumed.
- Entirely offline — no data leaves the device.

### 4. LLM client

- **Library:** `requests`
- Targets any OpenAI-compatible `/v1/chat/completions` endpoint.
- Auth: `Authorization: Bearer <API_KEY>` header.
- Low-thinking config: `temperature=0.3`, `top_p=0.9`, `max_tokens=512`.
- Sends a rolling conversation history (configurable window, default last 20 messages).
- Handles timeout, HTTP errors, and malformed responses gracefully.

### 5. TTS with barge-in

- **Library:** `pyttsx3` (TTS) + `sounddevice.InputStream` (barge-in monitor)
- pyttsx3 runs in a daemon thread; `engine.runAndWait()` blocks until speech ends.
- Simultaneously, the main thread opens a mic `InputStream` and computes RMS each chunk.
- If `RMS > BARGE_IN_THRESHOLD`, `engine.stop()` is called and the thread is joined.
- `speak()` returns `True` (completed) or `False` (interrupted).

---

## Data flow — sequence diagram

```
User          Mic           heyboy                     LLM API
 │             │              │                            │
 │  "hey boy"  │              │                            │
 │────────────►│  raw PCM     │                            │
 │             │─────────────►│ vosk partial match         │
 │             │              │──────┐                     │
 │             │              │ wake │                     │
 │             │              │◄─────┘                     │
 │             │◄─────────────│ TTS "Yes?"                 │
 │  utterance  │              │                            │
 │────────────►│ 7 s record   │                            │
 │             │─────────────►│                            │
 │             │              │ vosk transcribe             │
 │             │              │──────┐                     │
 │             │              │ text │                     │
 │             │              │◄─────┘                     │
 │             │              │── POST /v1/chat/completions►│
 │             │              │◄─────────────── reply ─────│
 │             │◄─────────────│ TTS reply                  │
 │  (speaks)   │ mic RMS mon. │                            │
 │────────────►│─────────────►│ barge-in? stop TTS         │
```

---

## Alternative technology choices

The table below lists drop-in alternatives for each pipeline stage, with trade-offs.

### Wake-word detection alternatives

| Technology | Type | Pros | Cons |
|---|---|---|---|
| **vosk** (current) | Offline full ASR | No registration, free, flexible phrase | Higher CPU than dedicated detectors; substring match can false-positive |
| **Porcupine** (Picovoice) | Offline, dedicated wake-word | Very low CPU (~1 %), low false-accept, custom wake-word training available | Requires Picovoice account + free-tier API key; commercial use requires license |
| **openWakeWord** | Offline, open-source DNN | Truly open (Apache 2), custom phrase training via transfer learning, good accuracy | Requires PyTorch; model training pipeline needed for custom phrases |
| **Deepgram** | Cloud streaming STT with keyword trigger | High accuracy, built-in keyword spotting, real-time | Requires internet + Deepgram account; latency depends on network; cost per minute |
| **Whisper** | Offline ASR (OpenAI) | Excellent multilingual accuracy | Too slow for real-time streaming on CPU; better suited for batch transcription |
| **Snowboy** | Offline, dedicated wake-word | Very low CPU | Unmaintained since 2020, limited platform support |

#### Recommended upgrade path

1. **Near-term:** replace vosk wake detection with **openWakeWord** — truly open, custom phrase, lower CPU.
2. **Production / commercial:** use **Porcupine** for best accuracy + lowest latency at the cost of a license.
3. **Cloud-first deployment:** use **Deepgram** streaming with `keywords` parameter for wake detection + STT in one round-trip.

### STT alternatives

| Technology | Offline | Notes |
|---|---|---|
| **vosk** (current) | Yes | Good accuracy, small models available |
| **Whisper (faster-whisper)** | Yes | Excellent accuracy; use `tiny`/`base` for real-time |
| **Deepgram** | No | Best accuracy + punctuation; streaming capable |
| **Google STT** | No | High accuracy; requires GCP credentials |

### TTS alternatives

| Technology | Offline | Notes |
|---|---|---|
| **pyttsx3** (current) | Yes | Uses OS native TTS (macOS: NSS, Linux: espeak, Windows: SAPI) |
| **Coqui TTS** | Yes | Neural TTS, natural-sounding, multiple voices |
| **edge-tts** | No | Microsoft Edge neural voices via unofficial API, high quality |
| **macOS `say` subprocess** | Yes | Simple, no deps; macOS only |
| **ElevenLabs** | No | Highest quality; paid API |

---

## Configuration reference

All values configurable via `.env`.  See `.env.example` for defaults.

| Variable | Component | Effect |
|---|---|---|
| `VOSK_MODEL_PATH` | Wake + STT | Path to vosk model directory |
| `WAKE_PHRASE` | Wake | Substring to detect (lowercased) |
| `RECORD_SECONDS` | Recorder | Fixed recording window in seconds |
| `API_BASE_URL` | LLM | Base URL of OpenAI-compatible server |
| `API_KEY` | LLM | Bearer token |
| `MODEL_NAME` | LLM | Model identifier (`gpt-5.2`, etc.) |
| `LLM_TEMPERATURE` | LLM | Sampling temperature (0.3 = low thinking) |
| `LLM_MAX_TOKENS` | LLM | Max reply tokens |
| `LLM_TIMEOUT` | LLM | HTTP timeout in seconds |
| `BARGE_IN_THRESHOLD` | TTS | Mic RMS above which barge-in fires |
| `SAMPLE_RATE` | Audio | PCM sample rate in Hz (must match vosk model) |
| `LOG_LEVEL` | Logging | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HISTORY_MAX_MESSAGES` | LLM | Rolling conversation window size |
