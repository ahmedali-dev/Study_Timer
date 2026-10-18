#!/usr/bin/env bash
set -euo pipefail

app_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
bundles=deb,appimage
skip_install=false
skip_tests=false
dry_run=false

usage() {
  cat <<'HELP'
Build FocusNest on Linux for the native x64 or ARM64 host.
Usage: bash scripts/build-linux.sh [options]
  --bundles deb,appimage|deb|appimage|rpm  Default: deb,appimage
  --skip-install                          Use existing node_modules instead of npm ci
  --skip-tests                            Skip frontend and host Rust tests
  --dry-run                               Print commands only (works on any OS)
  --help                                  Show this help
Install native WebKitGTK 4.1/GTK, SSL, AppIndicator and packaging prerequisites
from BUILD.md first. This script does not install system packages or use sudo.
Cross-compiling between Linux architectures is intentionally not supported.
HELP
}
fail() { echo "Error: $*" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --bundles) (($# >= 2)) || fail "Missing value for $1"; bundles="$2"; shift 2 ;;
    --skip-install) skip_install=true; shift ;;
    --skip-tests) skip_tests=true; shift ;;
    --dry-run) dry_run=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown option: $1 (use --help)" ;;
  esac
done
case "$bundles" in deb|appimage|deb,appimage|rpm) ;; *) fail "Bundles must be deb, appimage, deb,appimage or rpm" ;; esac
if ! $dry_run && [[ "$(uname -s)" != Linux ]]; then fail "Run this script on Linux."; fi
case "$(uname -m)" in
  x86_64) target=x86_64-unknown-linux-gnu ;;
  arm64|aarch64) target=aarch64-unknown-linux-gnu ;;
  *) fail "Use an x64 or ARM64 Linux host." ;;
esac
cd -- "$app_root"
if [[ -x "$app_root/.toolchain/cargo/bin/cargo" && -d "$app_root/.toolchain/rustup" ]]; then
  export CARGO_HOME="$app_root/.toolchain/cargo"
  export RUSTUP_HOME="$app_root/.toolchain/rustup"
  export PATH="$CARGO_HOME/bin:$PATH"
fi
export CARGO_TARGET_DIR="$app_root/src-tauri/target"
run() {
  printf '+ '; printf '%q ' "$@"; printf '\n'
  if ! $dry_run; then "$@"; fi
}
if ! $dry_run; then
  for tool in node npm cargo rustup rustc pkg-config; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool. See BUILD.md."
  done
  host="$(rustc -vV | sed -n 's/^host: //p')"
  [[ "$host" == "$target" ]] || fail "Use the native GNU Rust toolchain ($target), not $host."
  pkg-config --exists webkit2gtk-4.1 gtk+-3.0 openssl ayatana-appindicator3-0.1 || fail "Missing native development libraries; see the Linux prerequisites in BUILD.md."
  if [[ "$bundles" == rpm ]]; then command -v rpmbuild >/dev/null 2>&1 || fail "Install your distribution's rpm-build tools for RPM output."; fi
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (!(a>=22 || a===20 && b>=19)) { console.error("Use Node.js 20.19+ or 22+."); process.exit(1); }'
  if $skip_install && [[ ! -f node_modules/@tauri-apps/cli/tauri.js ]]; then fail "Run npm ci before using --skip-install."; fi
fi
echo "Building FocusNest for Linux ($target)."
if ! $skip_install; then run npm ci; fi
run rustup target add "$target"
if ! $skip_tests; then
  run npm test
  run cargo test --manifest-path src-tauri/Cargo.toml --locked
fi
run node scripts/tauri.mjs build --target "$target" --bundles "$bundles" -- --locked
echo "Bundle output: $CARGO_TARGET_DIR/$target/release/bundle/"
echo "Build on the oldest supported distribution, then test packages on each target system."
