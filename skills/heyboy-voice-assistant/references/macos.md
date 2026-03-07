# macOS reference (tested)

## Install and PATH

Preferred installer:

```bash
curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash
```

Installer links:

- `~/.local/bin/heyboy` -> `~/.local/share/heyboy-voice-assistant/scripts/heyboy`

If `heyboy` is not found, add to PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
source ~/.zshrc
```

For bash:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Basic setup

```bash
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

## LaunchAgent mode

```bash
heyboy app install
heyboy app start
heyboy app status
```

Logs:

- `~/Library/Logs/heyboy-voice-assistant/stdout.log`
- `~/Library/Logs/heyboy-voice-assistant/stderr.log`

LaunchAgent plist:

- `~/Library/LaunchAgents/io.github.ethansk.heyboy.voice-assistant.plist`
