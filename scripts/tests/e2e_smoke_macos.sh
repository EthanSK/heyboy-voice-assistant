#!/usr/bin/env bash
# e2e_smoke_macos.sh
# Practical smoke/integration coverage for heyboy-voice-assistant on macOS.
# Covers:
#   - CLI install/setup/doctor
#   - LaunchAgent app install/start/status/stop
#   - Foreground run-loop startup assertion

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ARTIFACT_ROOT="${PROJECT_ROOT}/artifacts/e2e"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="${ARTIFACT_ROOT}/${RUN_ID}"
SUMMARY_JSON="${RUN_DIR}/summary.json"
SUMMARY_TXT="${RUN_DIR}/summary.txt"
ALLOW_DAEMON_SKIP="${HEYBOY_ALLOW_DAEMON_SKIP:-0}"

mkdir -p "$RUN_DIR"

failures=0
cli_status="PASS"
daemon_status="PASS"
run_loop_status="PASS"
coverage_gaps=()
app_started=0

run_cmd() {
  local name="$1"
  shift
  local cmd="$*"
  local logfile="${RUN_DIR}/${name}.log"

  {
    echo "$ $cmd"
    cd "$PROJECT_ROOT"
    eval "$cmd"
  } >"$logfile" 2>&1
}

assert_log_contains() {
  local logfile="$1"
  local needle="$2"
  if ! grep -Fq "$needle" "$logfile"; then
    echo "[assert] Missing text in $(basename "$logfile"): $needle" >>"${RUN_DIR}/assertions.log"
    return 1
  fi
  return 0
}

assert_log_regex() {
  local logfile="$1"
  local regex="$2"
  if ! grep -Eq "$regex" "$logfile"; then
    echo "[assert] Missing pattern in $(basename "$logfile"): $regex" >>"${RUN_DIR}/assertions.log"
    return 1
  fi
  return 0
}

cleanup() {
  if [ "$app_started" -eq 1 ]; then
    (
      cd "$PROJECT_ROOT"
      scripts/heyboy app stop >"${RUN_DIR}/app-stop-cleanup.log" 2>&1 || true
    )
  fi
}
trap cleanup EXIT

# 1) CLI install/setup/doctor
if ! run_cmd "01-install" "scripts/heyboy install"; then
  cli_status="FAIL"
  failures=$((failures + 1))
fi

if ! run_cmd "02-setup-generic" "scripts/heyboy setup generic --command \"python3 scripts/tests/smoke_backend.py\""; then
  cli_status="FAIL"
  failures=$((failures + 1))
fi

if ! run_cmd "03-doctor" "scripts/heyboy doctor"; then
  cli_status="FAIL"
  failures=$((failures + 1))
else
  if ! assert_log_regex "${RUN_DIR}/03-doctor.log" "doctor result: OK( with warnings)?"; then
    cli_status="FAIL"
    failures=$((failures + 1))
  fi
fi

# 2) LaunchAgent daemon lifecycle
if ! run_cmd "04-app-install" "scripts/heyboy app install"; then
  daemon_status="FAIL"
  failures=$((failures + 1))
fi

if ! run_cmd "05-app-start" "scripts/heyboy app start"; then
  if grep -Fq "Likely blocker: no active GUI login session" "${RUN_DIR}/05-app-start.log" && [ "$ALLOW_DAEMON_SKIP" = "1" ]; then
    daemon_status="SKIPPED_HEADLESS"
    coverage_gaps+=("LaunchAgent daemon lifecycle skipped because no active GUI login session was available.")
  else
    daemon_status="FAIL"
    failures=$((failures + 1))
  fi
else
  app_started=1
fi

if [ "$daemon_status" = "PASS" ]; then
  daemon_ok=0
  for attempt in 1 2 3 4 5; do
    if run_cmd "06-app-status-attempt-${attempt}" "scripts/heyboy app status"; then
      if grep -Fq "state = running" "${RUN_DIR}/06-app-status-attempt-${attempt}.log"; then
        daemon_ok=1
        cp "${RUN_DIR}/06-app-status-attempt-${attempt}.log" "${RUN_DIR}/06-app-status.log"
        break
      fi
    fi
    sleep 1
  done

  if [ "$daemon_ok" -ne 1 ]; then
    daemon_status="FAIL"
    failures=$((failures + 1))
  fi

  if ! run_cmd "07-app-stop" "scripts/heyboy app stop"; then
    daemon_status="FAIL"
    failures=$((failures + 1))
  else
    app_started=0
  fi
fi

# 3) Foreground run-loop startup (timed smoke)
RUN_LOOP_LOG="${RUN_DIR}/08-run-loop.log"
if ! python3 - "$PROJECT_ROOT" "$RUN_LOOP_LOG" <<'PY'
import os
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(sys.argv[1])
log_path = Path(sys.argv[2])
cmd = [str(project_root / "scripts" / "heyboy"), "run"]

max_seconds = 10.0

with log_path.open("w", encoding="utf-8", errors="ignore") as log_file:
    env = dict(os.environ)
    env["INSTANCE_LOCK_PATH"] = str(log_path.parent / "run-loop-smoke.lock")

    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    time.sleep(max_seconds)

    # Long-running service; terminate after smoke window.
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    # If process exited before timeout with non-zero, mark failure.
    if proc.returncode not in (0, -15, None):
        raise SystemExit(proc.returncode)
PY
then
  run_loop_status="FAIL"
  failures=$((failures + 1))
else
  if ! grep -Fq "Listening for wake phrase" "$RUN_LOOP_LOG"; then
    run_loop_status="FAIL"
    failures=$((failures + 1))
  fi
fi

# Summary
if [ "$daemon_status" = "SKIPPED_HEADLESS" ]; then
  overall="PASS_WITH_GAPS"
elif [ "$failures" -gt 0 ]; then
  overall="FAIL"
else
  overall="PASS"
fi

{
  echo "overall=${overall}"
  echo "cli_status=${cli_status}"
  echo "daemon_status=${daemon_status}"
  echo "run_loop_status=${run_loop_status}"
  echo "artifact_dir=${RUN_DIR}"
  if [ "${#coverage_gaps[@]}" -gt 0 ]; then
    echo "coverage_gaps="
    for gap in "${coverage_gaps[@]}"; do
      echo "- ${gap}"
    done
  else
    echo "coverage_gaps=none"
  fi
} >"$SUMMARY_TXT"

coverage_joined=""
if [ "${#coverage_gaps[@]}" -gt 0 ]; then
  coverage_joined="$(printf '%s||' "${coverage_gaps[@]}")"
  coverage_joined="${coverage_joined%||}"
fi

python3 - "$SUMMARY_JSON" "$overall" "$cli_status" "$daemon_status" "$run_loop_status" "$RUN_DIR" "$coverage_joined" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
summary = {
    "overall": sys.argv[2],
    "cli_status": sys.argv[3],
    "daemon_status": sys.argv[4],
    "run_loop_status": sys.argv[5],
    "artifact_dir": sys.argv[6],
    "coverage_gaps": [g for g in sys.argv[7].split("||") if g] if len(sys.argv) > 7 else [],
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(summary_path)
PY

echo "[e2e] Summary:"
cat "$SUMMARY_TXT"

if [ "$overall" = "FAIL" ]; then
  exit 1
fi
