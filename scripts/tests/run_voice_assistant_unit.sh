#!/usr/bin/env bash
# Run focused unit tests for core voice assistant behavior/regressions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

PY_BIN="python3"
if [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
  PY_BIN="${PROJECT_ROOT}/.venv/bin/python"
fi

cd "$PROJECT_ROOT"

"$PY_BIN" -m unittest -v tests/test_voice_assistant.py
