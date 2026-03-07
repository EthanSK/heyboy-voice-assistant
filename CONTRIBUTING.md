# Contributing to heyboy voice assistant

Thanks for helping improve the project.

## Development setup

```bash
scripts/heyboy install
scripts/heyboy setup openclaw --api-key "YOUR_TOKEN"
scripts/heyboy doctor
```

## Contribution guidelines

1. Keep changes focused and small.
2. Update docs (`README.md`, `docs/*`) when behavior changes.
3. Keep `PLAN.md` append-only for project conversation tracking.
4. Validate Python syntax before committing:

```bash
python3 -m py_compile scripts/voice_assistant.py
```

## Pull requests

- Use clear commit messages.
- Include what was changed and why.
- Mention any behavior/config changes in the PR description.

## Reporting issues

Open an issue with:
- OS + Python version
- backend mode (`openclaw_api`, `codex_cli`, `claude_cli`, `generic_cli`)
- relevant `.env` keys (redact secrets)
- logs/error output
