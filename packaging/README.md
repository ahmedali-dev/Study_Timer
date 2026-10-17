# FocusNest desktop packaging

Use [the complete build guide](../BUILD.md) for macOS, Windows, and Linux commands,
prerequisites, installer compilation, data locations, and release checks.

## Files

- `scripts/build_desktop.py`: native bundle/archive/installer preparation.
- `scripts/export_icons.py`: PNG, ICO, and ICNS format exports from the approved logo master.
- `src/branding.py`: FocusNest name, version, bundle ID, and icon filenames.
- `windows.iss`: per-user Windows installer, compiled with Inno Setup 6.
- `focusnest.desktop`: Linux launcher, included in the Debian package.
- `hooks/hook-flet.py`: includes the FocusNest-branded macOS renderer.
- `src/desktop_runtime.py`: selects the renderer's versioned private runtime cache in frozen macOS builds.
- `.github/workflows/desktop.yml`: native build job definitions; no remote workflow is run by the local build script.

macOS builds use PyInstaller with a branded native renderer. Windows and Linux
use the pinned Flet packaging command. Every build writes a new timestamped
folder in `dist/`, preserving previous outputs. The macOS renderer and app bundle
are ad-hoc signed locally; distribution signing/notarization remain separate.

The database intentionally retains the legacy `StudyTimer/study_timer.sqlite3`
storage location for upgrades. Branding does not move or delete task data.
