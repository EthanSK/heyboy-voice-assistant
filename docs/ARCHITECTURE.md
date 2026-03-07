# Architecture — heyboy voice assistant

## Product intent

**Works with any of your AI subscriptions.**

The core design is local-first for voice processing, with pluggable response backends.

- local wake phrase detection (`hey boy`)
- local recording + transcription
- backend router that can hit API or local CLIs
- local TTS with interruption/barge-in support

---

## System diagram

```text
Microphone
   │
   ▼
Always-on wake listener (Vosk streaming)
   │ wake phrase detected
   ▼
Listen window recorder (default 7s)
   │
   ▼
Offline transcription (Vosk)
   │ transcript text
   ▼
Backend router
   ├── openclaw_api  -> POST /v1/chat/completions (Bearer token)
   ├── codex_cli     -> codex exec "...prompt..."
   ├── claude_cli    -> claude --dangerously-skip-permissions --print "...prompt..."
   └── generic_cli   -> user-defined command prefix
   │ response text
   ▼
TTS speaker (pyttsx3) + barge-in monitor (mic RMS)
   │
   └─ if user starts speaking while TTS is active -> stop playback immediately
```

---

## Runtime components

## 1) Wake phrase detector

- Input: microphone stream (`sounddevice.RawInputStream`)
- Decoder: `vosk.KaldiRecognizer`
- Match logic: normalized substring check for `WAKE_PHRASE`
- Default sample rate: `16kHz`

Why this default:
- runs locally
- no cloud call needed
- practical for early scaffold

## 2) Listen window capture

- fixed duration from `LISTEN_SECONDS` (recommended 5–10s)
- default is **7s**
- captured as int16 mono audio buffer

## 3) Local STT

- same Vosk model reused for post-wake transcript
- no cloud dependency for transcription

## 4) Backend router

The router supports 4 compatibility targets:

### A) `openclaw_api` (default)

- OpenAI-compatible API call via `requests`
- endpoint: `{API_BASE_URL}/v1/chat/completions`
- auth: `Bearer API_KEY`
- default model: `gpt-5.2`
- low-thinking path defaults:
  - `THINKING_LEVEL=low`
  - `LLM_TEMPERATURE=0.2`

Request includes both compatibility forms when supported:
- `reasoning: { effort: low }`
- `reasoning_effort: low`

If backend rejects these fields, request auto-retries without them.

### B) `codex_cli`

Runs local Codex CLI command, default:
- `codex exec`

### C) `claude_cli`

Runs local Claude Code CLI command, default:
- `claude --dangerously-skip-permissions --print`

### D) `generic_cli`

Runs user-defined command prefix (e.g. Ollama or any other compatible local CLI).

## 5) TTS + barge-in

- playback with `pyttsx3`
- concurrent mic monitor computes RMS
- barge-in triggers when RMS exceeds threshold for configurable hold period

Config:
- `BARGE_IN_THRESHOLD`
- `BARGE_IN_HOLD_MS`
- `BARGE_IN_GRACE_MS`

This reduces false interruptions from speaker bleed while still allowing quick user interruption.

---

## CLI UX layer

`scripts/heyboy` provides a simple command model inspired by OpenClaw ergonomics:

- `scripts/heyboy install`
- `scripts/heyboy setup <backend>`
- `scripts/heyboy doctor`
- `scripts/heyboy run`
- `scripts/heyboy quickstart <backend>`

This keeps setup minimal for different user environments.

## macOS app/daemon layer

For always-on operation, `scripts/heyboy app ...` manages a LaunchAgent:

- label: `io.github.ethansk.heyboy.voice-assistant`
- plist: `~/Library/LaunchAgents/io.github.ethansk.heyboy.voice-assistant.plist`
- stdout/stderr logs in `~/Library/Logs/heyboy-voice-assistant/`

This gives app-like behavior (launch-at-login + keepalive) while still using the same core Python runtime.

## Download/distribution layer

Current practical download paths:

- `scripts/install.sh` (curl installer)
- git clone + `scripts/heyboy install`
- Homebrew HEAD formula (`Formula/heyboy-voice-assistant.rb`)

A notarized `.app` bundle + Homebrew cask can be added in Part 2 once signing/notarization pipeline is ready.

---

## Chosen defaults + alternatives

### Wake-word alternatives

- **Porcupine (Picovoice):** lower CPU and stronger wake-word precision
- **openWakeWord:** open-source detector with trainable custom words
- **Deepgram streaming keywords:** cloud-first option combining detection + STT

### STT alternatives

- faster-whisper (local)
- Deepgram / OpenAI / Google (cloud)

### TTS alternatives

- Coqui TTS (local neural)
- macOS `say`
- ElevenLabs (cloud)

Current Part 1 default favors practical local operation with minimal setup friction.
