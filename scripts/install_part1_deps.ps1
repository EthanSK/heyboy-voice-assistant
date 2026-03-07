#!/usr/bin/env pwsh
# install_part1_deps.ps1 — one-shot installer for heyboy voice assistant Part 1
# - creates/updates local .venv
# - installs Python requirements
# - downloads a Vosk English model (with fallback mirror)

[CmdletBinding()]
param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$ModelDir = Join-Path $ProjectRoot "models"
$ModelTargetPath = Join-Path $ModelDir "vosk-model-small-en-us"
$PrimaryModelName = "vosk-model-small-en-us-0.22"
$PrimaryModelUrl = "https://alphacephei.com/vosk/models/$PrimaryModelName.zip"
$FallbackModelName = "vosk-model-small-en-us-0.15"
$FallbackModelUrl = "https://huggingface.co/rhasspy/vosk-models/resolve/main/en/$FallbackModelName.zip?download=true"

function Resolve-PythonLauncher {
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return "python"
  }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return "py"
  }
  throw "Python launcher not found. Install Python 3.11+ and retry."
}

$PythonLauncher = Resolve-PythonLauncher

function Invoke-Python {
  param([Parameter(Mandatory = $true)][string[]]$Args)

  if ($PythonLauncher -eq "py") {
    & py -3 @Args
  }
  else {
    & python @Args
  }

  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $($Args -join ' ')"
  }
}

function Print-BackendStatus {
  Write-Host ""
  Write-Host "Optional backend tools detected:"
  foreach ($cmd in @("openclaw", "codex", "claude")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
      Write-Host "  ✅ $cmd"
    }
    else {
      Write-Host "  ⚪ $cmd (not found)"
    }
  }
}

Write-Host "=============================================="
Write-Host " heyboy-voice-assistant Part 1 — dependency install"
Write-Host "=============================================="

Write-Host "[1/4] Python launcher: $PythonLauncher"

$venvDir = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $venvDir)) {
  Write-Host "[2/4] Creating virtual environment at .venv"
  Invoke-Python -Args @("-m", "venv", $venvDir)
}
else {
  Write-Host "[2/4] Reusing existing virtual environment at .venv"
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "Virtualenv python not found at $venvPython"
}

Write-Host "[3/4] Installing Python dependencies"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

& $venvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "requirements install failed" }

Write-Host "[4/4] Ensuring Vosk model exists at $ModelTargetPath"
if (Test-Path $ModelTargetPath) {
  Write-Host "      Vosk model already present."
}
else {
  New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

  $downloadScript = @'
import pathlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile

model_dir = pathlib.Path(sys.argv[1])
target_path = model_dir / "vosk-model-small-en-us"

candidates = [
    ("vosk-model-small-en-us-0.22", "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.22.zip"),
    ("vosk-model-small-en-us-0.15", "https://huggingface.co/rhasspy/vosk-models/resolve/main/en/vosk-model-small-en-us-0.15.zip?download=true"),
]

model_dir.mkdir(parents=True, exist_ok=True)

for name, url in candidates:
    tmp_zip = pathlib.Path(tempfile.mkstemp(prefix="heyboy-model-", suffix=".zip")[1])
    try:
        print(f"      Downloading {name}…")
        urllib.request.urlretrieve(url, tmp_zip)

        with zipfile.ZipFile(tmp_zip, "r") as zf:
            bad = zf.testzip()
            if bad:
                raise RuntimeError(f"corrupt member: {bad}")
            zf.extractall(model_dir)

        extracted = model_dir / name
        if not extracted.exists() or not extracted.is_dir():
            candidates_dirs = sorted(
                [p for p in model_dir.glob("vosk-model-small-en-us*") if p.is_dir() and p.name != "vosk-model-small-en-us"]
            )
            if candidates_dirs:
                extracted = candidates_dirs[-1]

        if not extracted.exists() or not extracted.is_dir():
            raise RuntimeError("model folder not found after extraction")

        if target_path.exists():
            shutil.rmtree(target_path)

        extracted.rename(target_path)
        print(f"      Model installed at {target_path}")
        sys.exit(0)

    except Exception as exc:
        print(f"      Failed using {name}: {exc}")
    finally:
        try:
            tmp_zip.unlink(missing_ok=True)
        except Exception:
            pass

print("ERROR: unable to download and install a valid Vosk model archive.")
sys.exit(1)
'@

  $downloadScript | & $venvPython - $ModelDir
  if ($LASTEXITCODE -ne 0) {
    throw "Model installation failed"
  }
}

Print-BackendStatus

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1) .\scripts\heyboy.ps1 setup openclaw --api-key \"YOUR_TOKEN\"   # or codex / claude / generic"
Write-Host "  2) .\scripts\heyboy.ps1 doctor"
Write-Host "  3) .\scripts\heyboy.ps1 run"
