# Distribution & downloadability

## Goal

Make **heyboy-voice-assistant** downloadable and easy to run out of the box as:

- a CLI tool
- a launch-at-login app/daemon on macOS (LaunchAgent)

---

## Fast install paths

## A) One-command curl installer (recommended for Git users)

```bash
curl -fsSL https://raw.githubusercontent.com/EthanSK/heyboy-voice-assistant/main/scripts/install.sh | bash
```

Then:

```bash
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

## B) Manual git clone

```bash
git clone https://github.com/EthanSK/heyboy-voice-assistant.git
cd heyboy-voice-assistant
scripts/heyboy install
scripts/heyboy setup openclaw --api-key "YOUR_TOKEN"
scripts/heyboy doctor
scripts/heyboy run
```

## C) Homebrew (interim tap + formula path)

```bash
brew tap EthanSK/heyboy-voice-assistant https://github.com/EthanSK/heyboy-voice-assistant
brew install --HEAD ethansk/heyboy-voice-assistant/heyboy-voice-assistant
heyboy install
heyboy setup openclaw --api-key "YOUR_TOKEN"
heyboy doctor
heyboy run
```

---

## App/daemon mode on macOS

```bash
heyboy app install
heyboy app start
heyboy app status
```

Stop/uninstall:

```bash
heyboy app stop
heyboy app uninstall
```

This uses a LaunchAgent at:

- `~/Library/LaunchAgents/io.github.ethansk.heyboy.voice-assistant.plist`

Logs:

- `~/Library/Logs/heyboy-voice-assistant/stdout.log`
- `~/Library/Logs/heyboy-voice-assistant/stderr.log`

---

## Homebrew support status

Implemented for now as a **HEAD formula + tap workflow**:

- `Formula/heyboy-voice-assistant.rb`
- tap command: `brew tap EthanSK/heyboy-voice-assistant https://github.com/EthanSK/heyboy-voice-assistant`

Validated command (dry-run):

```bash
brew install --HEAD ethansk/heyboy-voice-assistant/heyboy-voice-assistant --dry-run
```

This gives users immediate `brew install` support without waiting for signed app bundles.

---

## Release blockers for full macOS app-cask distribution

For a polished `.app` + cask flow, these remain:

1. Build distributable `.app` bundle (PyInstaller/Briefcase or native app wrapper).
2. Apple Developer signing certificate setup.
3. Notarization pipeline (`xcrun notarytool submit`, staple).
4. Stable versioned release artifacts (GitHub Releases).
5. Homebrew cask repo/tap automation for checksums per release.

Until those are complete, the formula + launchd path is the best practical install flow.
