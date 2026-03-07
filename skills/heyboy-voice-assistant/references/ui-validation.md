# UI validation reference

Current validation state:

- ✅ Confirmed: CLI install/setup/doctor/run loop on macOS.
- ✅ Confirmed: macOS LaunchAgent lifecycle (`app install/start/status/stop`).
- ❌ Not manually UI-verified in this run: any dedicated desktop GUI/Electron/Swift visual interface.

Interpretation:

- Treat the shipped runtime as CLI-first + LaunchAgent-first.
- Do not claim desktop GUI parity or end-to-end GUI QA unless explicitly tested later.
