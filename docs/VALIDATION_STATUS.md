# Validation status

## macOS smoke + integration tests (executed)

### Commands actually run in this update

```bash
scripts/tests/run_voice_assistant_unit.sh
HEYBOY_ALLOW_DAEMON_SKIP=1 scripts/tests/e2e_smoke_macos.sh
```

Additional Codex latency spot-check (manual):

```bash
codex exec -m gpt-5.3-codex "Reply with exactly OK"
codex exec -m gpt-5.2 -c model_reasoning_effort=none "Reply with exactly OK"
```

### Unit test result (latest run)

- test suite: `tests/test_voice_assistant.py`
- total: `17`
- pass: `17`
- fail: `0`

Newly added regression coverage:

- duplicate/jagged second-turn TTS overlap guard
- duplicate short-prompt suppression window
- wake-suppression cooldown after playback
- early endpointing (trailing silence stop)
- 3-turn multi-turn stability path
- codex command normalization (`-m` + `model_reasoning_effort` defaults)

### E2E result (latest run)

- overall: `PASS`
- cli_status: `PASS`
- daemon_status: `PASS`
- run_loop_status: `PASS`
- artifact directory: `artifacts/e2e/20260308-014532/`

Key artifacts:

- `artifacts/e2e/20260308-014532/summary.txt`
- `artifacts/e2e/20260308-014532/summary.json`
- `artifacts/e2e/20260308-014532/03-doctor.log`
- `artifacts/e2e/20260308-014532/06-app-status.log`
- `artifacts/e2e/20260308-014532/08-run-loop.log`

### Codex latency spot-check observations

`Reply with exactly OK` prompt (3-run spot check, local machine/network variability applies):

- `codex exec -m gpt-5.3-codex`
  - avg: `2.390s`, median: `2.160s`
- `codex exec -m gpt-5.2 -c model_reasoning_effort=none`
  - avg: `2.046s`, median: `2.068s`

Takeaway: `gpt-5.2 + reasoning none` was measurably faster in this sample and is now the
Codex default for latency-sensitive HeyBoy voice turns.

## Coverage gaps

- No true desktop UI automation coverage (CLI + daemon lifecycle covered).
- No Windows live execution coverage (docs/scripts only).
