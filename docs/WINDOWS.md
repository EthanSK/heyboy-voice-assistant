# Windows support (best-effort, untested)

> Important: Windows steps are provided for parity but were **not** executed on a real Windows machine in this run.

## Install

PowerShell one-liner:

```powershell
iwr https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.ps1 -UseBasicParsing | iex
```

What this does:

1. Clone/update repo into `%USERPROFILE%\.local\share\heyboy-voice-assistant`
2. Run `scripts/install_part1_deps.ps1`
3. Create `%USERPROFILE%\.local\bin\heyboy.cmd`
4. Add `%USERPROFILE%\.local\bin` to user PATH

Open a fresh PowerShell session after install.

## Commands

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

## Notes and limitations

- `heyboy app ...` is macOS-only (LaunchAgent).
- Audio devices/microphone defaults may differ by Windows hardware.
- PATH changes may not appear until terminal restart/sign-out.
