import { existsSync } from "node:fs";
import { delimiter, join, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

// Use this workspace's isolated Rust installation when present. On other
// machines/CI, Tauri uses the normal toolchain from PATH.
const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const cargoHome = join(root, ".toolchain", "cargo");
const rustupHome = join(root, ".toolchain", "rustup");
const env = { ...process.env };
if (
  existsSync(
    join(
      cargoHome,
      "bin",
      process.platform === "win32" ? "cargo.exe" : "cargo",
    ),
  ) &&
  existsSync(rustupHome)
) {
  env.CARGO_HOME = cargoHome;
  env.RUSTUP_HOME = rustupHome;
  env.PATH = `${join(cargoHome, "bin")}${delimiter}${env.PATH ?? ""}`;
}
const require = createRequire(import.meta.url);
const result = spawnSync(
  process.execPath,
  [require.resolve("@tauri-apps/cli/tauri.js"), ...process.argv.slice(2)],
  { cwd: root, env, stdio: "inherit" },
);
if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
