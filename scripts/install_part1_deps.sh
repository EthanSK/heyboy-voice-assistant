#!/usr/bin/env bash
# install_part1_deps.sh — one-shot installer for heyboy voice assistant Part 1
# - creates/updates local .venv
# - installs Python requirements
# - downloads a Vosk English model (with fallback mirror)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_ROOT}/.venv"

MODEL_DIR="${PROJECT_ROOT}/models"
MODEL_SYMLINK_NAME="vosk-model-small-en-us"
MODEL_TARGET_PATH="${MODEL_DIR}/${MODEL_SYMLINK_NAME}"

PRIMARY_MODEL_NAME="vosk-model-small-en-us-0.22"
PRIMARY_MODEL_URL="https://alphacephei.com/vosk/models/${PRIMARY_MODEL_NAME}.zip"

# Practical fallback mirror (official community mirror on HuggingFace)
FALLBACK_MODEL_NAME="vosk-model-small-en-us-0.15"
FALLBACK_MODEL_URL="https://huggingface.co/rhasspy/vosk-models/resolve/main/en/${FALLBACK_MODEL_NAME}.zip?download=true"

print_backend_status() {
  echo ""
  echo "Optional backend tools detected:"
  for cmd in openclaw codex claude; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "  ✅ ${cmd}"
    else
      echo "  ⚪ ${cmd} (not found)"
    fi
  done
}

download_file() {
  local url="$1"
  local out="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --progress-bar "$url" -o "$out"
    return 0
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -q --show-progress "$url" -O "$out"
    return 0
  fi

  echo "ERROR: neither curl nor wget found."
  return 1
}

zip_is_valid() {
  local zip_path="$1"
  python3 - "$zip_path" <<'PY'
import sys
import zipfile

path = sys.argv[1]
try:
    with zipfile.ZipFile(path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"corrupt member: {bad}")
except Exception:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

extract_zip() {
  local zip_path="$1"
  local out_dir="$2"

  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$zip_path" -d "$out_dir"
  else
    python3 - "$zip_path" "$out_dir" <<'PY'
import sys
import zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
  fi
}

install_model() {
  mkdir -p "$MODEL_DIR"
  local zip_path="${MODEL_DIR}/vosk-model.zip"

  echo "      Downloading primary model (${PRIMARY_MODEL_NAME})…"
  if download_file "$PRIMARY_MODEL_URL" "$zip_path" && zip_is_valid "$zip_path"; then
    echo "      Primary model download valid."
    extract_zip "$zip_path" "$MODEL_DIR"
    if [ -d "${MODEL_DIR}/${PRIMARY_MODEL_NAME}" ]; then
      rm -rf "$MODEL_TARGET_PATH"
      mv "${MODEL_DIR}/${PRIMARY_MODEL_NAME}" "$MODEL_TARGET_PATH"
    fi
    rm -f "$zip_path"
    return 0
  fi

  echo "      Primary model download failed or invalid zip. Trying fallback mirror…"
  rm -f "$zip_path"

  if download_file "$FALLBACK_MODEL_URL" "$zip_path" && zip_is_valid "$zip_path"; then
    echo "      Fallback model download valid."
    extract_zip "$zip_path" "$MODEL_DIR"
    if [ -d "${MODEL_DIR}/${FALLBACK_MODEL_NAME}" ]; then
      rm -rf "$MODEL_TARGET_PATH"
      mv "${MODEL_DIR}/${FALLBACK_MODEL_NAME}" "$MODEL_TARGET_PATH"
    fi
    rm -f "$zip_path"
    return 0
  fi

  echo "ERROR: unable to download a valid Vosk model archive."
  echo "Tried:"
  echo "  - ${PRIMARY_MODEL_URL}"
  echo "  - ${FALLBACK_MODEL_URL}"
  return 1
}

echo "=============================================="
echo " heyboy voice assistant Part 1 — dependency install"
echo "=============================================="

# 1) Python checks
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.11+ and retry."
  exit 1
fi

echo "[1/4] Python: $(python3 --version)"

# 2) Create venv
if [ ! -d "$VENV_DIR" ]; then
  echo "[2/4] Creating virtual environment at .venv"
  python3 -m venv "$VENV_DIR"
else
  echo "[2/4] Reusing existing virtual environment at .venv"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# 3) Install Python deps
echo "[3/4] Installing Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r "${PROJECT_ROOT}/requirements.txt"

# 4) Download vosk model if needed
echo "[4/4] Ensuring Vosk model exists at ${MODEL_TARGET_PATH}"
if [ -d "$MODEL_TARGET_PATH" ]; then
  echo "      Vosk model already present."
else
  install_model
  echo "      Model installed at ${MODEL_TARGET_PATH}."
fi

print_backend_status

echo ""
echo "Done. Next steps:"
echo "  1) scripts/heyboy setup openclaw   # or codex / claude / generic"
echo "  2) scripts/heyboy doctor"
echo "  3) scripts/heyboy run"
