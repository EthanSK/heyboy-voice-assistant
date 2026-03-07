#!/usr/bin/env bash
# One-command installer for heyboy voice assistant
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/EthanSK/heyboy-voice-assistant.git"
INSTALL_ROOT="${HEYBOY_INSTALL_ROOT:-$HOME/.local/share/heyboy-voice-assistant}"
BIN_DIR="${HEYBOY_BIN_DIR:-$HOME/.local/bin}"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required for installer."
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_ROOT")"

if [ -d "$INSTALL_ROOT/.git" ]; then
  echo "[install] Updating existing install at $INSTALL_ROOT"
  git -C "$INSTALL_ROOT" pull --ff-only
else
  echo "[install] Cloning $REPO_URL -> $INSTALL_ROOT"
  git clone "$REPO_URL" "$INSTALL_ROOT"
fi

cd "$INSTALL_ROOT"
chmod +x scripts/*.sh scripts/heyboy scripts/voice_assistant.py || true

scripts/heyboy install

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_ROOT/scripts/heyboy" "$BIN_DIR/heyboy"

echo ""
echo "Installed ✅"
echo "Binary linked: $BIN_DIR/heyboy"
echo ""
echo "Next:"
echo "  heyboy setup openclaw --api-key \"YOUR_TOKEN\""
echo "  heyboy doctor"
echo "  heyboy run"
echo ""
echo "For app/daemon mode:"
echo "  heyboy app install"
echo "  heyboy app start"
