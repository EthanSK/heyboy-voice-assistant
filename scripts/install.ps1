#!/usr/bin/env pwsh
# One-command installer for heyboy-voice-assistant (Windows)
# Usage:
#   iwr https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.ps1 -UseBasicParsing | iex

[CmdletBinding()]
param(
  [string]$RepoUrl = "https://github.com/EthanSK/heyboy-voice-assistant.git",
  [string]$InstallRoot = "$HOME\.local\share\heyboy-voice-assistant",
  [string]$BinDir = "$HOME\.local\bin"
)

$ErrorActionPreference = "Stop"

function Require-Command {
  param([string]$Name)

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found on PATH."
  }
}

Require-Command git

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Python is required (python or py launcher). Install Python 3.11+ and retry."
}

$parent = Split-Path -Parent $InstallRoot
if (-not (Test-Path $parent)) {
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
}

if (Test-Path (Join-Path $InstallRoot ".git")) {
  Write-Host "[install] Updating existing install at $InstallRoot"
  & git -C $InstallRoot pull --ff-only
  if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
}
else {
  Write-Host "[install] Cloning $RepoUrl -> $InstallRoot"
  & git clone $RepoUrl $InstallRoot
  if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}

$depsScript = Join-Path $InstallRoot "scripts\install_part1_deps.ps1"
if (-not (Test-Path $depsScript)) {
  throw "Expected dependency installer not found at $depsScript"
}

& $depsScript -ProjectRoot $InstallRoot
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$targetPs1 = Join-Path $InstallRoot "scripts\heyboy.ps1"
$shimPath = Join-Path $BinDir "heyboy.cmd"
$shimContent = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$targetPs1" %*
"@
Set-Content -Path $shimPath -Value $shimContent -Encoding Ascii

$pathUpdated = $false
$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($currentUserPath)) {
  [Environment]::SetEnvironmentVariable("Path", $BinDir, "User")
  $pathUpdated = $true
}
else {
  $parts = $currentUserPath -split ";"
  if (-not ($parts -contains $BinDir)) {
    [Environment]::SetEnvironmentVariable("Path", "$currentUserPath;$BinDir", "User")
    $pathUpdated = $true
  }
}

Write-Host ""
Write-Host "Installed ✅"
Write-Host "Command shim: $shimPath"
Write-Host ""
if ($pathUpdated) {
  Write-Host "Updated user PATH with: $BinDir"
  Write-Host "Open a new PowerShell terminal before running 'heyboy'."
  Write-Host ""
}

Write-Host "Next:"
Write-Host "  heyboy setup openclaw --api-key \"YOUR_TOKEN\""
Write-Host "  heyboy doctor"
Write-Host "  heyboy run"
