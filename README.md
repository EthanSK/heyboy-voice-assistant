# heyboy voice assistant

**Works with any of your AI subscriptions.**

A local-first voice assistant scaffold that wakes on **"hey boy"**, records a short listen window, transcribes locally, routes to your chosen AI backend, and speaks the reply with barge-in interruption.

---

## Features (Part 1)

- Always-on wake phrase detection (`hey boy`) via **Vosk**
- 5–10s listen window (default `7s`)
- Offline local STT via **Vosk**
- Backend routing:
  - `openclaw_api` (OpenAI-compatible token/API path)
  - `codex_cli`
  - `claude_cli`
  - `generic_cli`
- Barge-in interruption while assistant is speaking
- OpenClaw-style helper CLI: `scripts/heyboy`
- macOS app/daemon mode with LaunchAgent

---

## Quick start

```bash
scripts/heyboy install
scripts/heyboy setup openclaw --api-key "YOUR_TOKEN"
scripts/heyboy doctor
scripts/heyboy run
```

---

## One-command-ish install options

## 1) Curl installer

```bash
curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash
```

Then:

```bash
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

## 2) Homebrew (interim tap + formula)

```bash
brew tap EthanSK/heyboy-voice-assistant https://github.com/EthanSK/heyboy-voice-assistant
brew install --HEAD ethansk/heyboy-voice-assistant/heyboy-voice-assistant
heyboy install
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

---

## App / daemon mode (macOS)

Install and start launch-at-login agent:

```bash
heyboy app install
heyboy app start
heyboy app status
```

Stop/uninstall:

```bash
heyboy app stop
heyboy app uninstall
```

LaunchAgent location:

- `~/Library/LaunchAgents/io.github.ethansk.heyboy.voice-assistant.plist`

Logs:

- `~/Library/Logs/heyboy-voice-assistant/stdout.log`
- `~/Library/Logs/heyboy-voice-assistant/stderr.log`

---

## Backend compatibility

### OpenClaw/OpenAI-compatible API path

- endpoint: `POST /v1/chat/completions`
- auth: `Authorization: Bearer <API_KEY>`
- default model: `gpt-5.2`
- low-thinking target: `THINKING_LEVEL=low`

Runtime sends both:

- `reasoning: { effort: "low" }`
- `reasoning_effort: "low"`

If unsupported by backend, it auto-retries without those fields.

### Codex CLI path

```bash
scripts/heyboy setup codex
```

### Claude Code CLI path

```bash
scripts/heyboy setup claude
```

### Generic CLI path

```bash
scripts/heyboy setup generic --command "ollama run llama3.2"
```

---

## Smoke test commands actually executed (2026-03-07)

```bash
scripts/heyboy install
scripts/heyboy setup generic --command "python3 -c \"import sys; print('SMOKE BACKEND OK')\""
scripts/heyboy doctor
scripts/heyboy app start
scripts/heyboy app status
scripts/heyboy app stop
scripts/heyboy run   # observed startup + wake-listen loop logs for ~10s
```

Proof screenshot saved at:

- `/Users/ethansk/.openclaw/workspace/artifacts/heyboy-voice-proof.png`

---

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PART1_IMPLEMENTATION.md](docs/PART1_IMPLEMENTATION.md)
- [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md)
- [PLAN.md](PLAN.md) (canonical append-only project conversation log)

---

## Open source hygiene

- License: [MIT](LICENSE)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Homebrew formula: [Formula/heyboy-voice-assistant.rb](Formula/heyboy-voice-assistant.rb)
