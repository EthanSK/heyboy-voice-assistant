#!/usr/bin/env pwsh
# heyboy.ps1 CLI helper (Windows best-effort)

[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$EnvTemplate = Join-Path $ProjectRoot ".env.example"
$EnvFile = Join-Path $ProjectRoot ".env"
$DefaultApiBaseUrl = "http://127.0.0.1:3333"

function Show-Usage {
  @"
heyboy-voice-assistant CLI (PowerShell)

Usage:
  .\scripts\heyboy.ps1 install
  .\scripts\heyboy.ps1 setup <openclaw|codex|claude|generic> [options]
  .\scripts\heyboy.ps1 doctor
  .\scripts\heyboy.ps1 run
  .\scripts\heyboy.ps1 quickstart <openclaw|codex|claude|generic> [options]

  .\scripts\heyboy.ps1 app <...>

Setup options:
  --api-key <token>        Set API_KEY (openclaw backend)
  --api-base-url <url>     Set API_BASE_URL (openclaw backend)
  --model <name>           Set MODEL_NAME (default gpt-5.2)
  --thinking <level>       Set THINKING_LEVEL (default low)
  --codex-command <cmd>    Override CODEX_CLI_COMMAND
  --claude-command <cmd>   Override CLAUDE_CLI_COMMAND
  --command <cmd>          Required for generic backend (GENERIC_CLI_COMMAND)

Examples:
  .\scripts\heyboy.ps1 setup openclaw --api-key "YOUR_TOKEN"
  .\scripts\heyboy.ps1 setup codex
  .\scripts\heyboy.ps1 setup claude --claude-command "claude --dangerously-skip-permissions --print"
  .\scripts\heyboy.ps1 setup generic --command "ollama run llama3.2"
"@ | Write-Host
}

function Ensure-EnvFile {
  if (-not (Test-Path $EnvFile)) {
    Copy-Item -Path $EnvTemplate -Destination $EnvFile
    Write-Host "[setup] Created .env from .env.example"
  }
}

function Quote-EnvValue {
  param([string]$Value)

  $escaped = $Value.Replace('\\', '\\\\').Replace('"', '\\"')
  return "\"$escaped\""
}

function Set-EnvValue {
  param(
    [string]$Key,
    [string]$Value
  )

  $line = "$Key=$(Quote-EnvValue -Value $Value)"
  $needle = "$Key="

  if (Test-Path $EnvFile) {
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.AddRange([string[]](Get-Content -Path $EnvFile))
  }
  else {
    $lines = [System.Collections.Generic.List[string]]::new()
  }

  $updated = $false
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].StartsWith($needle)) {
      $lines[$i] = $line
      $updated = $true
      break
    }
  }

  if (-not $updated) {
    $lines.Add($line)
  }

  Set-Content -Path $EnvFile -Value $lines -Encoding utf8
}

function Load-EnvMap {
  $map = @{}

  if (-not (Test-Path $EnvFile)) {
    return $map
  }

  foreach ($raw in Get-Content -Path $EnvFile) {
    $line = $raw.Trim()
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line.StartsWith("#")) { continue }

    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { continue }

    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()

    if ($value.Length -ge 2) {
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }

    $value = $value.Replace('\\"', '"').Replace('\\\\', '\\')
    $map[$key] = $value
  }

  return $map
}

function Get-FirstToken {
  param([string]$CommandPrefix)

  if ([string]::IsNullOrWhiteSpace($CommandPrefix)) {
    return ""
  }

  $trim = $CommandPrefix.Trim()
  if ($trim.StartsWith('"')) {
    $end = $trim.IndexOf('"', 1)
    if ($end -gt 1) {
      return $trim.Substring(1, $end - 1)
    }
  }

  return ($trim -split '\s+')[0]
}

function Test-CommandPrefix {
  param(
    [string]$Label,
    [string]$Prefix
  )

  $token = Get-FirstToken -CommandPrefix $Prefix
  if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "  ❌ $Label: command is empty"
    return $false
  }

  if (Get-Command $token -ErrorAction SilentlyContinue) {
    Write-Host "  ✅ $Label: $Prefix"
    return $true
  }

  Write-Host "  ❌ $Label: executable '$token' not found on PATH"
  return $false
}

function Print-DetectedTools {
  foreach ($cmd in @("openclaw", "codex", "claude")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
      Write-Host "  ✅ $cmd"
    }
    else {
      Write-Host "  ⚪ $cmd (not found)"
    }
  }
}

function Setup-Backend {
  param(
    [string]$Backend,
    [string[]]$Args
  )

  Ensure-EnvFile

  $apiKey = ""
  $apiBaseUrl = $DefaultApiBaseUrl
  $model = "gpt-5.2"
  $thinking = "low"
  $codexCommand = "codex exec"
  $claudeCommand = "claude --dangerously-skip-permissions --print"
  $genericCommand = ""

  for ($i = 0; $i -lt $Args.Count; $i++) {
    $arg = $Args[$i]
    switch ($arg) {
      "--api-key" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --api-key" }
        $apiKey = $Args[$i]
      }
      "--api-base-url" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --api-base-url" }
        $apiBaseUrl = $Args[$i]
      }
      "--model" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --model" }
        $model = $Args[$i]
      }
      "--thinking" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --thinking" }
        $thinking = $Args[$i]
      }
      "--codex-command" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --codex-command" }
        $codexCommand = $Args[$i]
      }
      "--claude-command" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --claude-command" }
        $claudeCommand = $Args[$i]
      }
      "--command" {
        $i++
        if ($i -ge $Args.Count) { throw "Missing value for --command" }
        $genericCommand = $Args[$i]
      }
      "-h" { Show-Usage; exit 0 }
      "--help" { Show-Usage; exit 0 }
      default {
        throw "Unknown option: $arg"
      }
    }
  }

  switch ($Backend) {
    "openclaw" {
      Set-EnvValue -Key "ASSISTANT_BACKEND" -Value "openclaw_api"
      Set-EnvValue -Key "API_BASE_URL" -Value $apiBaseUrl
      Set-EnvValue -Key "MODEL_NAME" -Value $model
      Set-EnvValue -Key "THINKING_LEVEL" -Value $thinking
      if (-not [string]::IsNullOrWhiteSpace($apiKey)) {
        Set-EnvValue -Key "API_KEY" -Value $apiKey
      }
      Write-Host "[setup] Backend configured: openclaw_api"
      Write-Host "        API_BASE_URL=$apiBaseUrl"
      Write-Host "        MODEL_NAME=$model"
      Write-Host "        THINKING_LEVEL=$thinking"
    }

    "codex" {
      Set-EnvValue -Key "ASSISTANT_BACKEND" -Value "codex_cli"
      Set-EnvValue -Key "CODEX_CLI_COMMAND" -Value $codexCommand
      Write-Host "[setup] Backend configured: codex_cli"
      Write-Host "        CODEX_CLI_COMMAND=$codexCommand"
    }

    "claude" {
      Set-EnvValue -Key "ASSISTANT_BACKEND" -Value "claude_cli"
      Set-EnvValue -Key "CLAUDE_CLI_COMMAND" -Value $claudeCommand
      Write-Host "[setup] Backend configured: claude_cli"
      Write-Host "        CLAUDE_CLI_COMMAND=$claudeCommand"
    }

    "generic" {
      if ([string]::IsNullOrWhiteSpace($genericCommand)) {
        throw "generic backend requires --command \"<executable ...>\""
      }
      Set-EnvValue -Key "ASSISTANT_BACKEND" -Value "generic_cli"
      Set-EnvValue -Key "GENERIC_CLI_COMMAND" -Value $genericCommand
      Write-Host "[setup] Backend configured: generic_cli"
      Write-Host "        GENERIC_CLI_COMMAND=$genericCommand"
    }

    default {
      throw "backend must be one of openclaw|codex|claude|generic"
    }
  }

  Write-Host "[setup] .env updated: $EnvFile"
}

function Run-Doctor {
  $failures = 0
  $warnings = 0

  Write-Host "heyboy doctor"
  Write-Host "============="

  if (Get-Command python -ErrorAction SilentlyContinue) {
    $version = (& python --version 2>&1)
    Write-Host "  ✅ python: $version"
  }
  elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $version = (& py -3 --version 2>&1)
    Write-Host "  ✅ py launcher: $version"
  }
  else {
    Write-Host "  ❌ python not found"
    $failures++
  }

  $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    Write-Host "  ✅ virtualenv: $(Join-Path $ProjectRoot '.venv')"
  }
  else {
    Write-Host "  ⚪ virtualenv missing (.venv) — run .\scripts\heyboy.ps1 install"
    $warnings++
  }

  $cfg = @{}
  if (Test-Path $EnvFile) {
    Write-Host "  ✅ env file: $EnvFile"
    $cfg = Load-EnvMap
  }
  else {
    Write-Host "  ❌ env file missing: $EnvFile"
    $failures++
  }

  $voskPath = if ($cfg.ContainsKey("VOSK_MODEL_PATH")) { $cfg["VOSK_MODEL_PATH"] } else { "models/vosk-model-small-en-us" }
  $candidate1 = Join-Path $ProjectRoot $voskPath
  if ((Test-Path $candidate1) -or (Test-Path $voskPath)) {
    Write-Host "  ✅ vosk model path found: $voskPath"
  }
  else {
    Write-Host "  ⚪ vosk model path missing: $voskPath (run .\scripts\heyboy.ps1 install)"
    $warnings++
  }

  $backend = if ($cfg.ContainsKey("ASSISTANT_BACKEND")) { $cfg["ASSISTANT_BACKEND"] } else { "openclaw_api" }
  Write-Host "  ℹ️  backend: $backend"

  switch ($backend) {
    "openclaw_api" {
      if ($cfg.ContainsKey("API_BASE_URL") -and -not [string]::IsNullOrWhiteSpace($cfg["API_BASE_URL"])) {
        Write-Host "  ✅ API_BASE_URL: $($cfg['API_BASE_URL'])"
      }
      else {
        Write-Host "  ❌ API_BASE_URL missing"
        $failures++
      }

      if ($cfg.ContainsKey("API_KEY") -and -not [string]::IsNullOrWhiteSpace($cfg["API_KEY"]) -and $cfg["API_KEY"] -ne "replace-with-your-token") {
        Write-Host "  ✅ API_KEY is configured"
      }
      else {
        Write-Host "  ❌ API_KEY missing/placeholder"
        $failures++
      }

      $modelName = if ($cfg.ContainsKey("MODEL_NAME")) { $cfg["MODEL_NAME"] } else { "gpt-5.2" }
      $thinking = if ($cfg.ContainsKey("THINKING_LEVEL")) { $cfg["THINKING_LEVEL"] } else { "low" }
      Write-Host "  ✅ MODEL_NAME: $modelName"
      Write-Host "  ✅ THINKING_LEVEL: $thinking"
    }

    "codex_cli" {
      $prefix = if ($cfg.ContainsKey("CODEX_CLI_COMMAND")) { $cfg["CODEX_CLI_COMMAND"] } else { "codex exec" }
      if (-not (Test-CommandPrefix -Label "Codex CLI" -Prefix $prefix)) {
        $failures++
      }
    }

    "claude_cli" {
      $prefix = if ($cfg.ContainsKey("CLAUDE_CLI_COMMAND")) { $cfg["CLAUDE_CLI_COMMAND"] } else { "claude --dangerously-skip-permissions --print" }
      if (-not (Test-CommandPrefix -Label "Claude CLI" -Prefix $prefix)) {
        $failures++
      }
    }

    "generic_cli" {
      $prefix = if ($cfg.ContainsKey("GENERIC_CLI_COMMAND")) { $cfg["GENERIC_CLI_COMMAND"] } else { "" }
      if (-not (Test-CommandPrefix -Label "Generic CLI" -Prefix $prefix)) {
        $failures++
      }
    }

    default {
      Write-Host "  ❌ ASSISTANT_BACKEND invalid: $backend"
      $failures++
    }
  }

  $pyCheck = if (Test-Path $venvPython) { $venvPython } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "" }
  if (-not [string]::IsNullOrWhiteSpace($pyCheck)) {
    & $pyCheck -c "import importlib;mods=['vosk','sounddevice','soundfile','numpy','pyttsx3','requests','dotenv'];[importlib.import_module(m) for m in mods]" *> $null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "  ✅ Python deps import check"
    }
    else {
      Write-Host "  ⚪ Python deps incomplete — run .\scripts\heyboy.ps1 install"
      $warnings++
    }
  }
  else {
    Write-Host "  ⚪ Could not run Python dependency import check"
    $warnings++
  }

  Write-Host ""
  Write-Host "Detected optional backend tools:"
  Print-DetectedTools

  Write-Host ""
  if ($failures -gt 0) {
    Write-Host "doctor result: FAIL ($failures failure(s), $warnings warning(s))"
    exit 1
  }

  if ($warnings -gt 0) {
    Write-Host "doctor result: OK with warnings ($warnings)"
  }
  else {
    Write-Host "doctor result: OK"
  }
}

function Install-Dependencies {
  & (Join-Path $ScriptDir "install_part1_deps.ps1") -ProjectRoot $ProjectRoot
}

function Run-Assistant {
  param([string[]]$Args)

  if (Test-Path $EnvFile) {
    Write-Host "[run] Found config at $EnvFile"
    Write-Host "[run] Note: .env is parsed by python-dotenv inside voice_assistant.py"
  }
  else {
    Write-Host "[run] WARNING: .env not found. Copy .env.example -> .env first."
  }

  $pythonBin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
  if (-not (Test-Path $pythonBin)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
      $pythonBin = "python"
    }
    else {
      throw "No Python runtime found. Run .\scripts\heyboy.ps1 install first."
    }
  }

  Write-Host "[run] Using Python: $pythonBin"

  Push-Location $ProjectRoot
  try {
    & $pythonBin (Join-Path $ScriptDir "voice_assistant.py") @Args
  }
  finally {
    Pop-Location
  }
}

function Quickstart {
  param(
    [string]$Backend,
    [string[]]$Args
  )

  if ([string]::IsNullOrWhiteSpace($Backend)) {
    throw "quickstart requires a backend (openclaw|codex|claude|generic)"
  }

  Install-Dependencies
  Setup-Backend -Backend $Backend -Args $Args
  Run-Doctor
}

$command = if ($CliArgs.Count -gt 0) { $CliArgs[0] } else { "help" }
$rest = if ($CliArgs.Count -gt 1) { $CliArgs[1..($CliArgs.Count - 1)] } else { @() }

switch ($command) {
  "install" {
    Install-Dependencies
  }

  "setup" {
    if ($rest.Count -lt 1) {
      throw "setup requires backend argument"
    }
    $backend = $rest[0]
    $setupArgs = if ($rest.Count -gt 1) { $rest[1..($rest.Count - 1)] } else { @() }
    Setup-Backend -Backend $backend -Args $setupArgs
  }

  "doctor" {
    Run-Doctor
  }

  "run" {
    Run-Assistant -Args $rest
  }

  "quickstart" {
    if ($rest.Count -lt 1) {
      throw "quickstart requires backend argument"
    }
    $backend = $rest[0]
    $qsArgs = if ($rest.Count -gt 1) { $rest[1..($rest.Count - 1)] } else { @() }
    Quickstart -Backend $backend -Args $qsArgs
  }

  "app" {
    Write-Host "[app] LaunchAgent commands are macOS-only and unavailable on Windows."
    Write-Host "[app] Use '.\scripts\heyboy.ps1 run' for foreground operation on Windows."
    exit 1
  }

  "help" { Show-Usage }
  "-h" { Show-Usage }
  "--help" { Show-Usage }

  default {
    throw "Unknown command: $command"
  }
}
