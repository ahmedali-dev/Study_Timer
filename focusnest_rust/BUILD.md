# Building FocusNest 0.3.0

Run these commands **inside `focusnest_rust`**. Native installers must be built on the target operating system. Commit `package-lock.json` and `src-tauri/Cargo.lock`; use `npm ci` for repeatable dependency resolution.

## One-command build scripts

Three scripts resolve the project directory themselves, install locked npm dependencies, add the required Rust targets, run frontend and **host-native** Rust tests, and stop immediately if a command fails. They automatically use the project-local Rust toolchain when present. Otherwise Rust/rustup must be installed on PATH. They do not install system dependencies, modify your app database, change PowerShell security settings, or configure signing.

Run the appropriate script on its own operating system:

```sh
# macOS: native architecture, .app and .dmg
bash scripts/build-macos.sh

# macOS: alternatives
bash scripts/build-macos.sh --arch arm64
bash scripts/build-macos.sh --arch x64
bash scripts/build-macos.sh --arch universal

# Linux: native x64/ARM64, .deb and AppImage
bash scripts/build-linux.sh
```

```powershell
# Windows: both x64 and native ARM64 app installers (default)
.\scripts\build-windows.ps1

# Or build one architecture
.\scripts\build-windows.ps1 -Architecture x64
.\scripts\build-windows.ps1 -Architecture arm64
```

Equivalent npm shortcuts are `npm run build:mac`, `npm run build:windows`, and `npm run build:linux`. Pass options after `--`, for example `npm run build:windows -- -Architecture arm64`.

For a preview with **no downloads, builds, tests or file changes**:

```sh
bash scripts/build-macos.sh --arch universal --dry-run
bash scripts/build-linux.sh --dry-run
```

```powershell
.\scripts\build-windows.ps1 -Architecture both -DryRun
```

Dry runs can be used from a different OS (PowerShell is needed for the Windows script); actual builds reject the wrong OS. Use `--skip-install` / `-SkipInstall` only after `npm ci`, and `--skip-tests` / `-SkipTests` only if checks have already passed. On macOS, `--bundles app` skips DMG creation. Linux accepts `--bundles deb`, `appimage`, `deb,appimage`, or `rpm` (RPM requires your distribution's `rpmbuild` tools).

Scripts fix `CARGO_TARGET_DIR` to this project's `src-tauri/target` for predictable outputs, without changing the parent shell. Outputs are separated by explicit target:

- macOS: `src-tauri/target/<target>/release/bundle/macos/` and `dmg/`, where target is `aarch64-apple-darwin`, `x86_64-apple-darwin`, or `universal-apple-darwin`.
- Windows x64: `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/`.
- Windows ARM64: `src-tauri/target/aarch64-pc-windows-msvc/release/bundle/nsis/`.
- Linux: `src-tauri/target/x86_64-unknown-linux-gnu/release/bundle/` or `aarch64-unknown-linux-gnu/...`, with a directory for each requested package type.

These are not timestamped archives: repeat builds can replace earlier generated bundles for the same target/version. Retain release artifacts elsewhere before rebuilding if needed. Source files and user databases are not deleted.

Windows builds require the Windows SDK and MSVC C++ build tools for **each** requested architecture. Install the ARM64 C++ tools in Visual Studio Installer before using `-Architecture arm64` or `both`; installing the Rust target alone is insufficient. An x64 Windows host can build ARM64 this way. The NSIS installer runs through x86 emulation on ARM64, but the installed app is native ARM64. Run and verify it on an ARM64 device; host tests do not test an ARM64 executable. See [Tauri's Windows ARM64 instructions](https://v2.tauri.app/distribute/windows-installer/#building-for-32-bit-or-arm).

macOS Intel/Apple Silicon cross-builds require the appropriate Rust targets and Xcode SDK. Universal builds install both targets. Linux deliberately uses only the native GNU target; use a native ARM64 Linux machine/runner to create ARM64 packages. No script bypasses signing, Gatekeeper, execution policy, or certificate checks. If your Windows policy restricts local scripts, use your organization's approved signing/trust procedure.

## macOS

Install Xcode command-line tools (`xcode-select --install`), Node.js 20.19+ and Rust stable. The scripts above configure the local Rust environment automatically; for the manual `cargo` commands below, first export the three variables shown in [README.md](README.md) if using the project-local toolchain.

```sh
npm ci
npm test
cargo test --manifest-path src-tauri/Cargo.toml --locked
npm run bundle
```

Outputs: `src-tauri/target/release/bundle/macos/FocusNest.app` and `src-tauri/target/release/bundle/dmg/*.dmg`. Builds match the host architecture unless explicitly configured otherwise. An Apple Silicon build is not an Intel or Universal build.

For a quicker release smoke test without creating a DMG:

```sh
npm run tauri -- build --bundles app
```

Public distribution needs your own Apple Developer signing identity and notarization; local unsigned/ad-hoc builds are not notarized. Follow the [official signing guide](https://v2.tauri.app/distribute/sign/macos/). Never commit signing keys or credentials.

## Windows

Install Node.js, Rust stable with the MSVC toolchain, Visual Studio Build Tools with **Desktop development with C++**, and Microsoft Edge WebView2 Runtime. See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

In PowerShell:

```powershell
cd focusnest_rust
npm ci
npm test
cargo test --manifest-path src-tauri/Cargo.toml --locked
npm run tauri -- build --bundles nsis
```

Find the installer under `src-tauri/target/release/bundle/nsis/`. For an MSI, build on Windows with `npm run tauri -- build --bundles msi` and the required WiX/VBS prerequisites from the [installer guide](https://v2.tauri.app/distribute/windows-installer/). Test notifications in the installed app, not only a development executable. Signing requires your own certificate and separate secure CI setup.

## Linux (Ubuntu 22.04+ / Debian-family)

Install Node.js and Rust stable. Native dependencies vary by distribution; a typical Ubuntu setup is:

```sh
sudo apt update
sudo apt install build-essential curl wget file libssl-dev libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf
npm ci
npm test
cargo test --manifest-path src-tauri/Cargo.toml --locked
npm run tauri -- build --bundles deb,appimage
```

Outputs: `src-tauri/target/release/bundle/deb/` and `src-tauri/target/release/bundle/appimage/`. Follow the current [Linux prerequisites](https://v2.tauri.app/start/prerequisites/) for other distributions. Install a font package if text is missing. Build against the oldest distribution you intend to support, then smoke-test on each supported distribution. Notifications require a functioning desktop notification service; headless Linux is not a notification test.

## Development / test data isolation

On macOS/Linux, use an explicit disposable data folder without touching your personal workspace:

```sh
FOCUSNEST_RUST_DATA_DIR="$PWD/.test-data" npm run desktop
```

PowerShell equivalent:

```powershell
$env:FOCUSNEST_RUST_DATA_DIR = Join-Path $PWD '.test-data'
npm run desktop
```

Do not point this variable at the Python app's data directory. Import through Settings instead. Close the app and retain a database backup before testing migration or replacing a release.

## Release checklist

### Automated GitHub Releases

`.github/workflows/focusnest-release.yml` builds macOS ARM64/Intel DMGs, native Windows x64/ARM64 NSIS installers, and Linux x64 DEB/AppImage packages on matching hosted runners. Build jobs have read-only repository permissions. Only the final publication job has `contents: write`.

To publish a version, update `package.json`, `package-lock.json` (including its root package entry), `src-tauri/Cargo.toml`, `src-tauri/Cargo.lock`, `src-tauri/tauri.conf.json`, and `RELEASE_NOTES.md`, commit and push them, then push the matching tag:

```sh
git tag -a focusnest-v0.3.0 -m "FocusNest 0.3.0"
git push origin focusnest-v0.3.0
```

The `focusnest-v` prefix distinguishes Rust releases from the legacy Python `v*` workflow. A manual retry is available in Actions → FocusNest release → Run workflow: enter the **existing** tag. Version/tag mismatches fail before any build. All jobs check out the same validated source SHA, and publication rejects a tag moved after validation.

Every platform must pass tests, formatting, linting and packaging. The final job requires all six expected installers, writes `SHA256SUMS`, creates a draft, uploads/verifies the assets, and then publishes the release. Failed builds never publish a partial release. A failed upload leaves a draft that can be retried for the same tag/commit; already-published releases are not overwritten. Actions installer artifacts are retained for 14 days; GitHub Release assets remain available independently.

The workflow does not configure Apple notarization, Windows certificate signing or automatic updates. The release notes explicitly disclose unsigned builds and migration limitations. Keep system security protections enabled and complete the manual checks below before broad distribution.

- Run frontend tests, production compilation, Rust tests and formatting checks.
- Start a focus timer and verify remaining time decreases. Pause/resume, skip focus, skip break, zero break and final-break behavior must all work.
- Relaunch mid-session: recover paused, preserving remaining time/round. Verify clean close and crash recovery separately.
- Sleep/wake must pause without awarding sleep time as focus.
- Test task creation, editing, priorities, filtering, completion/reopening, delete/undo and date groups.
- Check actual daily totals, local-midnight boundaries, partial history and task auto-completion only after all focus rounds complete.
- Import a **copy** of a version-1 Python database into an empty workspace. Confirm source unchanged, history/settings copied and timer paused. Nonempty destination and unsupported versions must be refused.
- Enable/test OS notifications and sound in a packaged app; test denial/Do Not Disturb separately.
- Check second launch focuses the first instance and does not start a second timer process.
- Verify selected FN logo, app name, install/uninstall, OS permissions, signing and architecture on each native OS.
- Record cold launch time and idle/running memory for both packaged editions before making performance claims. Rust build time is not application startup time.

## Official references

- [Tauri project setup](https://v2.tauri.app/start/create-project/)
- [Vite integration](https://v2.tauri.app/start/frontend/vite/)
- [Tauri permissions](https://v2.tauri.app/security/capabilities/)
- [Native notifications](https://v2.tauri.app/plugin/notification/)
- [Tauri distribution](https://v2.tauri.app/distribute/)
