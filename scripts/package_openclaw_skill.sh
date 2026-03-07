#!/usr/bin/env bash
# package_openclaw_skill.sh
# Build a distributable .skill archive from skills/heyboy-voice-assistant.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SKILL_NAME="heyboy-voice-assistant"
SKILL_DIR="${PROJECT_ROOT}/skills/${SKILL_NAME}"
OUT_DIR="${1:-${PROJECT_ROOT}/artifacts}"
OUT_FILE="${OUT_DIR}/${SKILL_NAME}.skill"

if [ ! -d "$SKILL_DIR" ]; then
  echo "ERROR: skill directory not found: $SKILL_DIR"
  exit 1
fi

mkdir -p "$OUT_DIR"

python3 - "$SKILL_DIR" "$OUT_FILE" <<'PY'
from pathlib import Path
import sys
import zipfile

skill_dir = Path(sys.argv[1]).resolve()
out_file = Path(sys.argv[2]).resolve()
root_name = skill_dir.name

if not (skill_dir / "SKILL.md").exists():
    raise SystemExit(f"ERROR: missing SKILL.md in {skill_dir}")

with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            rel = Path(root_name) / path.relative_to(skill_dir)
            zf.write(path, rel.as_posix())

print(f"Packaged: {out_file}")
PY
