# openclaw heyboy voice assistant

> **Part 1 scaffold** — Local wake-word → local STT → remote LLM → TTS with barge-in

A fully local, always-on voice assistant that wakes on **"hey boy"**, transcribes your speech offline with [vosk](https://alphacephei.com/vosk/), queries any OpenAI-compatible API, and speaks the reply via pyttsx3 — with real-time barge-in detection.

---

## Quick start

```bash
# 1. Install Python deps + download vosk model
bash scripts/install_part1_deps.sh

# 2. Configure
cp .env.example .env
$EDITOR .env          # fill in API_KEY, API_BASE_URL, MODEL_NAME

# 3. Run
bash scripts/run_voice_assistant.sh
```

Say **"hey boy"** — the assistant acknowledges with "Yes?", records 7 seconds of audio, transcribes it offline, sends it to the LLM, and speaks the reply. Start talking during the reply to trigger **barge-in** and cut it off.

---

## Features

| Feature | Implementation |
|---|---|
| Wake phrase | vosk streaming recogniser (fully offline) |
| Speech-to-text | vosk KaldiRecogniser (offline) |
| LLM backend | Any OpenAI-compatible `/v1/chat/completions` |
| Text-to-speech | pyttsx3 (native OS TTS) |
| Barge-in | Mic RMS threshold monitor during TTS |
| Config | Environment variables via `.env` |
| Logging | Python `logging`, configurable level |

---

## Project layout

```
.
├── .env.example                  # env config template
├── README.md
├── PLAN.md                       # project roadmap + original brief
├── requirements.txt
├── docs/
│   ├── ARCHITECTURE.md           # system design + alternative tech choices
│   └── PART1_IMPLEMENTATION.md   # step-by-step implementation notes
├── models/                       # vosk model downloaded here by install script
└── scripts/
    ├── install_part1_deps.sh     # one-shot dep + model installer
    ├── run_voice_assistant.sh    # launcher
    └── voice_assistant.py        # main assistant script
```

---

## Configuration

All settings are read from `.env` (or real environment variables).  See `.env.example` for the full reference.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(required)* | Bearer token for the LLM API |
| `API_BASE_URL` | `https://api.openai.com` | Base URL of OpenAI-compatible server |
| `MODEL_NAME` | `gpt-5.2` | Model identifier sent in the request |
| `WAKE_PHRASE` | `hey boy` | Phrase that activates the assistant |
| `RECORD_SECONDS` | `7` | How long to record after wake |
| `BARGE_IN_THRESHOLD` | `0.02` | Mic RMS to trigger barge-in |
| `VOSK_MODEL_PATH` | `models/vosk-model-small-en-us` | Path to vosk model dir |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Requirements

- Python 3.8+
- PortAudio (for sounddevice) — `brew install portaudio` on macOS
- A working microphone and speakers
- An OpenAI-compatible API endpoint + bearer token

---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — component diagram, data flow, alternative technologies
- [docs/PART1_IMPLEMENTATION.md](docs/PART1_IMPLEMENTATION.md) — implementation walkthrough
- [PLAN.md](PLAN.md) — original brief and phased roadmap
