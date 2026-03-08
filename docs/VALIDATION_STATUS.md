# Validation status

## macOS smoke + integration tests (executed)

### Commands actually run in this update

```bash
scripts/tests/run_voice_assistant_unit.sh
HEYBOY_ALLOW_DAEMON_SKIP=1 scripts/tests/e2e_smoke_macos.sh
scripts/heyboy doctor
```

Additional Codex latency spot-check (manual):

```bash
codex exec -m gpt-5.3-codex "Reply with exactly OK"
codex exec -m gpt-5.3-codex -c model_reasoning_effort=low "Reply with exactly OK"
```

### Unit test result (latest run)

- test suite: `tests/test_voice_assistant.py`
- total: `14`
- pass: `14`
- fail: `0`

Newly added regression coverage:

- duplicate/jagged second-turn TTS overlap guard
- 3-turn multi-turn stability path
- codex command normalization (`-m` + `model_reasoning_effort` defaults)

### E2E result (latest run)

- overall: `PASS`
- cli_status: `PASS`
- daemon_status: `PASS`
- run_loop_status: `PASS`
- artifact directory: `artifacts/e2e/20260308-013324/`

Key artifacts:

- `artifacts/e2e/20260308-013324/summary.txt`
- `artifacts/e2e/20260308-013324/summary.json`
- `artifacts/e2e/20260308-013324/03-doctor.log`
- `artifacts/e2e/20260308-013324/06-app-status.log`
- `artifacts/e2e/20260308-013324/08-run-loop.log`

### Codex latency spot-check observations

`Reply with exactly OK` prompt (warm runs, local machine/network variability applies):

- before wrapper normalization (`codex exec -m gpt-5.3-codex`)
  - avg: `2.093s`, median: `2.091s`
- after wrapper normalization (`codex exec -m gpt-5.3-codex -c model_reasoning_effort=low`)
  - avg: `3.074s`, median: `2.397s` (one slower outlier observed)

Takeaway: latency is network/model-load variable, but wrapper now deterministically
applies model/reasoning defaults for voice path so runtime behavior is predictable.

## UI/manual verification status

Tested now:

- ✅ CLI install/setup/doctor flow
- ✅ Foreground run loop startup (wake-listen loop observed)
- ✅ LaunchAgent lifecycle on macOS (`app install/start/status/stop`)
- ✅ OpenClaw skill archive packaging (`scripts/package_openclaw_skill.sh`)

Not manually UI-verified yet:

- ❌ No desktop GUI/Electron/Swift interface was manually clicked through in this run.
- ❌ No Windows runtime/manual UI validation (docs/scripts only, untested).

## Coverage gaps

- No true UI automation yet for a desktop app shell (Electron/Swift UI not exercised).
- No Windows live execution coverage (best-effort scripts/docs only).
