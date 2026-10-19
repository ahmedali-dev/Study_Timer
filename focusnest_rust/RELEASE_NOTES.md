## FocusNest 0.3.0 — Rust desktop edition

A separate Tauri + Rust + React version of FocusNest with the warm cream/terracotta interface and FN logo.

- Recoverable focus/break timer with pause, resume, stop, next round, skip break and optional final break.
- SQLite tasks with planned dates, priorities, search, completion, and delete/undo.
- Actual focus time, partial-session history and daily/weekly progress.
- Opt-in desktop notifications and session sounds.
- Explicit one-way import from the Python edition's version-1 SQLite database; the source is opened read-only, and any recovered timer starts paused.

### Downloads

- **macOS:** choose `macos-arm64.dmg` for Apple Silicon or `macos-x64.dmg` for Intel.
- **Windows:** choose `windows-x64.exe` for Intel/AMD or `windows-arm64.exe` for Windows on ARM.
- **Linux x64:** install the `.deb` on compatible Debian/Ubuntu systems or use the `.AppImage`.
- `SHA256SUMS` contains SHA-256 checksums for every installer.

### Important

These builds are **not Developer ID signed/notarized on macOS or certificate-signed on Windows**. Your OS may warn about or block untrusted software. Public signing is a separate future setup; do not disable system security protections. The files are built in GitHub Actions from the tagged source commit.

This Rust edition uses its own data directory and does not automatically modify or synchronize the Python app's data. Back up your database before explicitly importing it. Background music/custom audio selection, automatic updates and a tray workflow have not been ported yet. CI builds and automated tests do not replace manual installer/UI testing on each OS and architecture.
