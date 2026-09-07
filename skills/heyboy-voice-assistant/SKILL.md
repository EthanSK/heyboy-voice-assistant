---
name: heyboy-voice-assistant
description: Install, configure, diagnose, and operate the heyboy-voice-assistant CLI voice loop. Use for requests to set up "hey boy" wake-word workflows, fix missing heyboy command/PATH issues, switch backends (OpenClaw API, Codex CLI, Claude CLI, generic CLI), or manage always-on background mode on macOS. Includes best-effort Windows setup notes.
---

# heyboy-voice-assistant

Use this workflow to run HeyBoy as a CLI-first voice assistant.

## 1) Detect platform and command availability

- Run `command -v heyboy` on macOS/Linux.
- Run `Get-Command heyboy` on Windows PowerShell.
- If command exists, skip install and move to setup.

## 2) Install when `heyboy` is missing

### macOS (tested)

- Run:

```bash
curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash
```

- If shell cannot find `heyboy`, apply PATH update guidance in `references/macos.md`.

### Windows PowerShell (best-effort, untested)

- Run:

```powershell
iwr https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.ps1 -UseBasicParsing | iex
```

- If shell cannot find `heyboy`, apply PATH update guidance in `references/windows.md` and restart terminal.

## 3) Configure backend

Run exactly one backend setup:

```bash
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy setup codex
heyboy setup claude
heyboy setup generic --command "ollama run llama3.2"
```

## 4) Validate environment

Run:

```bash
heyboy doctor
```

If doctor fails because dependency/model is missing, run:

```bash
heyboy install
```

Then re-run doctor.

## 5) Start assistant

Foreground loop:

```bash
heyboy run
```

macOS background app mode (LaunchAgent):

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

## 6) Platform notes

- Read `references/macos.md` for tested commands and log locations.
- Read `references/windows.md` for best-effort setup scripts and current limitations.
- Read `references/ui-validation.md` before making claims about desktop UI readiness.

## Weekly public updates

On first use in a task, or the next use after a week in a long task, follow [references/public-updates.md](references/public-updates.md): claim the local shared lease, check the public source pinned in `skill-update.json`, and explain any available update. Ask the user if they want it first; install only after they explicitly agree, through the appropriate safe route. Silence or continued use is not approval. This is agent-triggered, not a background service. Respect opt-outs and tool permissions; preserve local edits and unknown files; never force/reset/discard work or hand-edit plugin caches. Keep dates and locks outside the skill. Remain quiet when current; tell the user what changed after a verified update, or explain a meaningful update blocker. Updating files never authorizes the skill's domain actions.
