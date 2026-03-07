# heyboy-voice-assistant

**Works with any of your AI subscriptions.**

A local-first voice assistant scaffold that wakes on **"hey boy"**, records a short listen window, transcribes with **local Vosk or Deepgram STT**, routes to your chosen AI backend, and speaks the reply with barge-in interruption.

---

## Features (current)

- Always-on wake phrase detection (`hey boy`) via **Vosk**
- 5–10s listen window (default `7s`)
- STT options:
  - `vosk_local` (offline local)
  - `deepgram` (API, higher quality)
- Backend routing:
  - `openclaw_api` (OpenAI-compatible token/API path)
  - `codex_cli`
  - `claude_cli`
  - `generic_cli`
- Barge-in interruption while assistant is speaking
- OpenClaw-style helper CLI: `heyboy` / `scripts/heyboy`
- macOS app/daemon mode with LaunchAgent
- OpenClaw-skill-style wrapper under `skills/heyboy-voice-assistant/`

---

## Quick start (macOS tested)

```bash
scripts/heyboy install
scripts/heyboy setup openclaw --api-key "YOUR_TOKEN"
scripts/heyboy doctor
scripts/heyboy run
```

Use Deepgram for transcription:

```bash
scripts/heyboy setup codex --stt-backend deepgram --deepgram-api-key "$DEEPGRAM_API_KEY"
scripts/heyboy doctor
scripts/heyboy run
```

---

## Install options

### 1) Curl installer

```bash
curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash
```

Then:

```bash
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

If `heyboy` is not found in a new shell, add `~/.local/bin` to PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
source ~/.zshrc
```

### 2) Homebrew (interim tap + formula)

```bash
brew tap EthanSK/heyboy-voice-assistant https://github.com/EthanSK/heyboy-voice-assistant
brew install --HEAD ethansk/heyboy-voice-assistant/heyboy-voice-assistant
heyboy install
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

### 3) Windows PowerShell (best-effort, untested)

```powershell
iwr https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.ps1 -UseBasicParsing | iex
```

Then:

```powershell
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

Windows notes/limitations: [docs/WINDOWS.md](docs/WINDOWS.md)

---

## OpenClaw skill wrapper

Skill path in this repo:

- `skills/heyboy-voice-assistant/SKILL.md`

Install skill into local OpenClaw workspace:

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R skills/heyboy-voice-assistant ~/.openclaw/workspace/skills/
```

Build distributable `.skill` archive:

```bash
scripts/package_openclaw_skill.sh
```

Output:

- `artifacts/heyboy-voice-assistant.skill`

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

## Practical E2E/smoke tests

Run macOS smoke+integration coverage now:

```bash
scripts/tests/e2e_smoke_macos.sh
```

Headless macOS mode (allow daemon step skip):

```bash
HEYBOY_ALLOW_DAEMON_SKIP=1 scripts/tests/e2e_smoke_macos.sh
```

Artifacts produced per run:

- `artifacts/e2e/<timestamp>/summary.txt`
- `artifacts/e2e/<timestamp>/summary.json`
- per-step logs (`01-install.log`, `03-doctor.log`, `06-app-status.log`, `08-run-loop.log`, ...)

---

## Validation status (current)

Tested in this repo on macOS:

- ✅ CLI install/setup/doctor flow
- ✅ foreground run-loop startup
- ✅ LaunchAgent lifecycle (`app install/start/status/stop`)
- ✅ practical smoke+integration script (`scripts/tests/e2e_smoke_macos.sh`)

Not yet manually UI-verified in this run:

- ❌ No desktop GUI/Electron/Swift interface click-through QA
- ❌ Windows runtime/manual verification (docs/scripts only)

See: [docs/VALIDATION_STATUS.md](docs/VALIDATION_STATUS.md)

---

## STT compatibility

### Vosk local STT

Default local path:

- `STT_BACKEND=vosk_local`
- requires local Vosk model files

### Deepgram STT

Use when you want higher transcription quality:

- `STT_BACKEND=deepgram`
- `DEEPGRAM_API_KEY=<your key>`
- `DEEPGRAM_MODEL=nova-3` (default)

You can set these via CLI setup flags:

```bash
scripts/heyboy setup codex --stt-backend deepgram --deepgram-api-key "$DEEPGRAM_API_KEY"
```

`heyboy doctor` validates Deepgram key presence when `STT_BACKEND=deepgram`.

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

`heyboy doctor` now runs an active Codex auth probe when `ASSISTANT_BACKEND=codex_cli`.
If your token is stale/reused, it reports:

- `Codex CLI auth invalid/expired — run: codex logout && codex login`

Runtime responses now surface this remediation directly instead of only saying
`Codex CLI returned an error`.

### Claude Code CLI path

```bash
scripts/heyboy setup claude
```

### Generic CLI path

```bash
scripts/heyboy setup generic --command "ollama run llama3.2"
```

---

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PART1_IMPLEMENTATION.md](docs/PART1_IMPLEMENTATION.md)
- [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md)
- [docs/OPENCLAW_SKILL.md](docs/OPENCLAW_SKILL.md)
- [docs/WINDOWS.md](docs/WINDOWS.md)
- [docs/VALIDATION_STATUS.md](docs/VALIDATION_STATUS.md)
- [PLAN.md](PLAN.md) (canonical append-only project conversation log)

---

## Open source hygiene

- License: [MIT](LICENSE)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Homebrew formula: [Formula/heyboy-voice-assistant.rb](Formula/heyboy-voice-assistant.rb)
