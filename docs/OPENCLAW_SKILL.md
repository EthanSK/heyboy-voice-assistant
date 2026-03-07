# OpenClaw skill wrapper — heyboy-voice-assistant

This repo now includes an OpenClaw-skill-style wrapper at:

- `skills/heyboy-voice-assistant/SKILL.md`

## What the skill covers

- install `heyboy` if missing
- fix PATH issues
- configure backend (`openclaw`, `codex`, `claude`, `generic`)
- run `heyboy doctor`
- start foreground run loop
- manage macOS background app mode (LaunchAgent)
- include Windows best-effort setup notes (explicitly marked untested)

## Install the skill into your OpenClaw workspace

From this repo root:

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R skills/heyboy-voice-assistant ~/.openclaw/workspace/skills/
```

## Build a distributable `.skill` archive

```bash
scripts/package_openclaw_skill.sh
```

Output:

- `artifacts/heyboy-voice-assistant.skill`

You can share this archive and extract it into another OpenClaw `skills/` directory.
