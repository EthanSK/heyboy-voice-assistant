# Part 1 implementation — heyboy voice assistant

## Scope delivered in Part 1

- always-on wake phrase detection for **"hey boy"**
- post-wake listen/capture window (**default 7 seconds**, configurable 5–10)
- offline local transcription via Vosk
- response routing via:
  - OpenClaw/OpenAI-compatible API token path
  - Codex CLI
  - Claude Code CLI
  - Generic CLI command
- local TTS playback with **barge-in interruption detection**
- OpenClaw-inspired setup UX via `scripts/heyboy`

---

## Setup flows

### Standard flow

```bash
scripts/heyboy install
scripts/heyboy setup openclaw --api-key "YOUR_TOKEN"
scripts/heyboy doctor
scripts/heyboy run
```

### One-command quickstart

```bash
scripts/heyboy quickstart openclaw --api-key "YOUR_TOKEN"
```

### Alternate backend examples

```bash
scripts/heyboy setup codex
scripts/heyboy setup claude
scripts/heyboy setup generic --command "ollama run llama3.2"
```

---

## Backend details

## 1) OpenClaw/OpenAI-compatible API (`ASSISTANT_BACKEND=openclaw_api`)

Request target:

- `POST {API_BASE_URL}/v1/chat/completions`
- header: `Authorization: Bearer API_KEY`

Default model/latency config for this project:

- `MODEL_NAME=gpt-5.2`
- `THINKING_LEVEL=low`
- `LLM_TEMPERATURE=0.2`
- `LLM_TOP_P=0.9`

Compatibility behavior:

- sends both `reasoning` and `reasoning_effort`
- retries without reasoning fields if backend returns validation error

This keeps routing fast while surviving backend schema differences.

## 2) Codex CLI (`ASSISTANT_BACKEND=codex_cli`)

- command prefix from `CODEX_CLI_COMMAND` (default `codex exec`)
- builds a plain-text prompt from recent conversation + latest user utterance
- captures stdout as assistant response

## 3) Claude Code CLI (`ASSISTANT_BACKEND=claude_cli`)

- command prefix from `CLAUDE_CLI_COMMAND`
- same prompt pipeline as Codex backend

## 4) Generic CLI (`ASSISTANT_BACKEND=generic_cli`)

- command prefix from `GENERIC_CLI_COMMAND`
- allows plugging in other local model CLIs without code changes

---

## Barge-in implementation

When assistant speech starts:

1. pyttsx3 runs in a worker thread
2. main thread samples mic stream
3. computes per-chunk RMS
4. if RMS > `BARGE_IN_THRESHOLD` for `BARGE_IN_HOLD_MS`, `engine.stop()` is called

Extra controls:

- `BARGE_IN_GRACE_MS` avoids immediate false trigger from the first speaker output burst

---

## Key files

- `scripts/voice_assistant.py` — runtime loop + wake/STT/router/TTS
- `scripts/heyboy` — CLI command UX (`install/setup/doctor/run/quickstart`)
- `scripts/install_part1_deps.sh` — venv + dependency + model setup
- `scripts/run_voice_assistant.sh` — launch helper
- `.env.example` — full config template

---

## Validation performed

```bash
python3 -m py_compile scripts/voice_assistant.py
scripts/heyboy doctor
```

Smoke-test run commands (executed):

```bash
scripts/heyboy install
scripts/heyboy setup generic --command "python3 -c \"import sys; print('SMOKE BACKEND OK')\""
scripts/heyboy doctor
scripts/heyboy app start
scripts/heyboy app status
scripts/heyboy app stop
scripts/heyboy run
```

Screenshot proof path:

- `/Users/ethansk/.openclaw/workspace/artifacts/heyboy-voice-proof.png`

---

## Known limitations (Part 1)

- wake phrase uses Vosk substring matching (practical but not as precise as dedicated wake-word engines)
- fixed listen window (no VAD-based early stop yet)
- TTS quality is local OS-engine dependent

These are intentional tradeoffs for a stable first implementation.
