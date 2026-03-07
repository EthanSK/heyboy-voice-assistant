#!/usr/bin/env bash
# run_voice_assistant.sh — launch heyboy voice assistant

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_ROOT}/.env"

if [ -f "$ENV_FILE" ]; then
  echo "[run] Found config at ${ENV_FILE}"
  echo "[run] Note: .env is parsed by python-dotenv inside voice_assistant.py"
else
  echo "[run] WARNING: .env not found. Copy .env.example -> .env first."
fi

PYTHON_BIN="python3"
if [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
fi

cd "$PROJECT_ROOT"

echo "[run] Using Python: $PYTHON_BIN"
exec "$PYTHON_BIN" "${SCRIPT_DIR}/voice_assistant.py" "$@"
