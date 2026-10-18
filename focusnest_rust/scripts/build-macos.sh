#!/usr/bin/env bash
set -euo pipefail

app_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
architecture=native
bundles=app,dmg
skip_install=false
skip_tests=false
dry_run=false

usage() {
  cat <<'HELP'
Build FocusNest on macOS.
Usage: bash scripts/build-macos.sh [options]
  --arch native|arm64|x64|universal  Default: native
  --bundles app,dmg|app|dmg        Default: app,dmg
  --skip-install                   Use existing node_modules instead of npm ci
  --skip-tests                     Skip frontend and host Rust tests
  --dry-run                        Print commands only (works on any OS)
  --help                           Show this help
Requires Node.js 20.19+ or 22+, Rust/rustup and Xcode command-line tools.
HELP
}
fail() { echo "Error: $*" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --arch|--bundles)
      (($# >= 2)) || fail "Missing value for $1"
      if [[ "$1" == --arch ]]; then architecture="$2"; else bundles="$2"; fi
      shift 2 ;;
    --skip-install) skip_install=true; shift ;;
    --skip-tests) skip_tests=true; shift ;;
    --dry-run) dry_run=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown option: $1 (use --help)" ;;
  esac
done
case "$architecture" in native|arm64|x64|universal) ;; *) fail "Invalid architecture: $architecture" ;; esac
case "$bundles" in app|dmg|app,dmg) ;; *) fail "Bundles must be app, dmg or app,dmg" ;; esac
if ! $dry_run && [[ "$(uname -s)" != Darwin ]]; then fail "Run this script on macOS."; fi
if [[ "$architecture" == native ]]; then
  case "$(uname -m)" in arm64|aarch64) architecture=arm64 ;; x86_64) architecture=x64 ;; *) fail "Unsupported host architecture" ;; esac
fi
case "$architecture" in
  arm64) target=aarch64-apple-darwin; rust_targets=(aarch64-apple-darwin) ;;
  x64) target=x86_64-apple-darwin; rust_targets=(x86_64-apple-darwin) ;;
  universal) target=universal-apple-darwin; rust_targets=(aarch64-apple-darwin x86_64-apple-darwin) ;;
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
  for tool in node npm cargo rustup xcode-select; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool. See BUILD.md."
  done
  xcode-select -p >/dev/null 2>&1 || fail "Install Xcode command-line tools: xcode-select --install"
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (!(a>=22 || a===20 && b>=19)) { console.error("Use Node.js 20.19+ or 22+."); process.exit(1); }'
  if $skip_install && [[ ! -f node_modules/@tauri-apps/cli/tauri.js ]]; then fail "Run npm ci before using --skip-install."; fi
fi
echo "Building FocusNest for macOS ($architecture)."
if ! $skip_install; then run npm ci; fi
run rustup target add "${rust_targets[@]}"
if ! $skip_tests; then
  run npm test
  run cargo test --manifest-path src-tauri/Cargo.toml --locked
fi
run node scripts/tauri.mjs build --target "$target" --bundles "$bundles" -- --locked
echo "Bundle output: $CARGO_TARGET_DIR/$target/release/bundle/"
echo "Public distribution requires your own signing identity and notarization; see BUILD.md."
