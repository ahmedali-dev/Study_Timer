# Building FocusNest on macOS, Windows, and Linux

FocusNest uses the selected **concept 03 FN monogram** and the warm ivory/terracotta theme.
Build each platform on that platform; the packaging tools do not cross-compile desktop apps.
See the [Flet packaging documentation](https://flet.dev/docs/publish/using-pyinstaller/)
and [PyInstaller platform guidance](https://pyinstaller.org/en/stable/operating-mode.html).

## What you need

- This complete project folder, including `src/assets`, `packaging`, and `scripts`.
- Python 3.11 recommended. The project supports Python 3.9 and newer; the build configuration pins Flet 0.27.6 and PyInstaller 6.12.0. Use the pinned dependencies rather than upgrading Flet independently.
- Internet access to install dependencies; builds include the desktop runtime so users do not install Python.
- Build for the architecture you intend to ship. An Apple Silicon build is not an Intel macOS build.
- A graphical desktop for manual application checks.

Run the commands from the project root. Its folder may still be called `Study_Timer-main`; the application and output files are named **FocusNest**.

## macOS

Install Python 3.11 and Apple's command-line developer tools if missing:

```sh
xcode-select --install
```

Create a project-only build environment, install dependencies, run checks, and build:

```sh
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-build.txt
.venv-build/bin/python -m unittest discover -s tests -v
.venv-build/bin/python scripts/build_desktop.py
```

Each build creates a new folder such as `dist/darwin-arm64-<timestamp>/` containing:

- `FocusNest.app`
- `FocusNest-0.2.0-darwin-arm64.zip`
- `FocusNest-0.2.0-darwin-arm64.dmg`

Open the DMG and drag **FocusNest** to **Applications** to install. Test the app from
Applications, not only from its build directory. For a quick local launch, use the
actual output path printed by the build:

```sh
open "dist/darwin-arm64-<timestamp>/FocusNest.app"
```

The macOS build also brands Flet's native renderer with the FocusNest name, icon,
and renderer bundle identity. A versioned private runtime cache avoids picking up
the generic Flet icon left by development runs. Source-mode `python src/main.py`
still uses the development Flet host; the packaged app carries full native branding.

Local builds use ad-hoc signatures and are **not notarized public releases**.
Distribution outside your development machine requires your Apple distribution
identity, appropriate signing, notarization, and a clean-machine check. These
credentials are not included in the repository. Do not bypass OS security prompts
as part of automated installation tests.

## Windows

Install Python 3.11 and **Inno Setup 6**. Open PowerShell at the project root.
The following commands use the environment's Python directly and do not require
changing PowerShell execution policy:

```powershell
py -3.11 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-build\Scripts\python.exe scripts\build_desktop.py
```

This creates a timestamped folder such as `dist/win32-AMD64-<timestamp>/` with:

- `FocusNest/FocusNest.exe` and its bundled dependencies.
- `FocusNest-0.2.0-win32-AMD64.zip` for portable distribution.

Keep the entire executable folder together. Do not copy only `FocusNest.exe` out
of its folder. Compile the Windows installer after the bundle finishes:

```powershell
$bundle = Get-ChildItem .\dist -Directory -Filter "win32-*" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $bundle) { throw "Build the Windows bundle first." }
$compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $compiler)) { throw "Install Inno Setup 6 or set the correct compiler path." }
& $compiler "/DAppSource=$($bundle.FullName)\FocusNest" "/DOutputDir=$($bundle.FullName)" .\packaging\windows.iss
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed." }
```

Output: `FocusNest-0.2.0-Setup.exe` inside that bundle's output folder. The installer
uses a per-user installation location, offers a desktop shortcut, and retains the
existing installer identity for upgrades. User task data is separate from program
files and is not deleted on uninstall. For compiler flags, see the
[Inno Setup command-line reference](https://jrsoftware.org/ishelp/topic_compilercmdline.htm).

## Linux (Debian / Ubuntu)

The native CI target is Ubuntu 22.04. Install Python, virtual-environment support,
Debian packaging tools, desktop libraries, and notification support:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev dpkg-dev libgtk-3-0 libasound2 libmpv1 libnotify-bin
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-build.txt
.venv-build/bin/python -m unittest discover -s tests -v
.venv-build/bin/python scripts/build_desktop.py
```

Library package names vary by distribution/version; newer releases may provide
`libmpv2` instead of `libmpv1` and `libasound2t64` instead of `libasound2`.
Install the equivalents for your system. The `.deb` currently targets the declared
Debian/Ubuntu dependencies; validate it against your target release.

The output folder, such as `dist/linux-x86_64-<timestamp>/`, contains:

- `FocusNest/` — portable executable folder.
- `FocusNest-0.2.0-linux-x86_64.zip` — portable archive.
- `FocusNest-0.2.0-amd64.deb` — Debian package (`arm64` on supported ARM64 builds).

Install the exact package you just built:

```sh
sudo apt install ./dist/linux-x86_64-<timestamp>/FocusNest-0.2.0-amd64.deb
FocusNest
```

Replace the timestamp and architecture with the printed output. The package
installs under `/opt/focusnest`, provides a `FocusNest` command, and adds a launcher
and icon to the desktop application menu. Notifications need a running desktop
notification service; headless environments cannot show desktop banners.
RPM and AppImage outputs are not currently configured.

## Run from source instead

After installing the runtime dependencies in your environment:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

Use `python3` or your environment's Python path as appropriate.

## Icons and branding

- Selected concept: `design/branding/focusnest-concept-03.png`.
- Transparent production master: `design/branding/focusnest-mark-master.png`.
- Application image: `src/assets/focusnest-icon.png`.
- Windows icon: `src/assets/focusnest.ico`.
- macOS icon: `src/assets/focusnest.icns`.
- Linux icon: `src/assets/focusnest-256.png`.
- Shared app name/version/identity: `src/branding.py`.

The exported files are already included with the source deliverables; building
does not require image generation. To regenerate native icon formats from the
existing approved master, use the build environment:

```sh
python scripts/export_icons.py
```

This only exports formats/sizes; it does not redesign the artwork. Do not replace
the master with the numbered concept board, which includes a wordmark and margins.

## Data compatibility and backups

Renaming the app does not rename or move existing databases. This deliberately
preserves tasks, settings, history, and recoverable timer state:

- Development: `data/study_timer.sqlite3` in the project.
- Windows packages: `%LOCALAPPDATA%/StudyTimer/study_timer.sqlite3`.
- macOS packages: `~/Library/Application Support/StudyTimer/study_timer.sqlite3`.
- Linux packages: `$XDG_DATA_HOME/StudyTimer/study_timer.sqlite3`, normally `~/.local/share/StudyTimer/study_timer.sqlite3`.

The old `StudyTimer` storage folder is intentional, not a missed branding update.
`FOCUSNEST_DATA_DIR` selects a different data folder; the legacy
`STUDY_TIMER_DATA_DIR` remains supported. If both are set, `FOCUSNEST_DATA_DIR` wins.
Do not use different data-folder settings when checking an upgrade unless that is
intentional. Development and installed apps use separate defaults.

Back up the database while the app is closed. Do not include development data,
backups, environment folders, or signing secrets in release packages.

## CI and release checklist

`.github/workflows/desktop.yml` builds on Windows, macOS, and Ubuntu natively.
It is available through `workflow_dispatch` and version-tag pushes, uploads
artifacts, and does not publish releases automatically. No remote workflow run is
performed merely by running the local build script.

Before distributing a release:

1. Run all tests and launch the packaged executable on its target OS.
2. Check the FocusNest name and FN logo in the window, sidebar, launcher, and Dock/taskbar.
3. Create/edit a task, pause a timer, close the app, reopen, and recover it.
4. Check audio, notifications, settings persistence, skips, and daily totals.
5. Upgrade over an existing installation and confirm that previous data remains.
6. Test on a clean machine without Python installed.
7. Finish distribution signing/notarization where applicable.

Windows and Linux packages require native build/install validation; a successful
macOS build does not verify those systems.
