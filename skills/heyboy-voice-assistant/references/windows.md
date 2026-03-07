# Windows reference (best-effort, untested)

> Status: scripts and docs prepared, but no manual Windows execution in this run.

## Install

Run installer from PowerShell:

```powershell
iwr https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.ps1 -UseBasicParsing | iex
```

Installer behavior:

- Clone/update repo into `%USERPROFILE%\.local\share\heyboy-voice-assistant`
- Create venv and install Python dependencies
- Download Vosk model with primary+fallback URLs
- Create `%USERPROFILE%\.local\bin\heyboy.cmd` shim
- Add `%USERPROFILE%\.local\bin` to user PATH

## Setup

```powershell
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

Alternative backends:

```powershell
heyboy setup codex
heyboy setup claude
heyboy setup generic --command "ollama run llama3.2"
```

## Known limitations on Windows

- `heyboy app ...` LaunchAgent commands are macOS-only.
- Audio device behavior may require local tuning and has not been validated.
- PATH updates usually require a new PowerShell session.
