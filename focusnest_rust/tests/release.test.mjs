import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import {
  assetNames,
  checkVersion,
  collect,
  manifest,
  versionFromFiles,
} from "../scripts/release.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "focusnest-release-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, "src-tauri"), { recursive: true });
  writeFileSync(
    join(root, "package.json"),
    JSON.stringify({ version: "0.3.0" }),
  );
  writeFileSync(
    join(root, "package-lock.json"),
    JSON.stringify({
      version: "0.3.0",
      packages: { "": { version: "0.3.0" } },
    }),
  );
  writeFileSync(
    join(root, "src-tauri/tauri.conf.json"),
    JSON.stringify({ version: "0.3.0" }),
  );
  writeFileSync(
    join(root, "src-tauri/Cargo.toml"),
    '[package]\nversion = "0.3.0"\n',
  );
  return root;
}
test("release tags must match the complete app version", () => {
  assert.equal(checkVersion("focusnest-v0.3.0", "0.3.0"), "0.3.0");
  for (const tag of [
    "v0.3.0",
    "main",
    "focusnest-v0.3.1",
    "focusnest-v0.3.0\nextra",
  ])
    assert.throws(() => checkVersion(tag, "0.3.0"));
});
test("release versions must agree across package, lockfile, Rust and Tauri", (t) => {
  const root = fixture(t);
  assert.equal(versionFromFiles(root), "0.3.0");
  writeFileSync(
    join(root, "src-tauri/Cargo.toml"),
    '[package]\nversion = "0.4.0"\n',
  );
  assert.throws(() => versionFromFiles(root), /versions must agree/);
});
test("every installer has an architecture-specific unique release name", () => {
  const names = assetNames("0.3.0");
  assert.equal(names.length, 6);
  assert.equal(new Set(names).size, 6);
  assert.ok(names.includes("FocusNest-0.3.0-windows-arm64.exe"));
  assert.ok(names.includes("FocusNest-0.3.0-macos-x64.dmg"));
});
test("a partial installer set cannot be published", (t) => {
  const root = fixture(t);
  assert.throws(() => manifest(root, "0.3.0"), /incomplete or unexpected/);
});
test("manifest hashes all installers and can be regenerated identically", (t) => {
  const root = fixture(t);
  const destination = join(root, "assets");
  mkdirSync(destination);
  for (const name of assetNames("0.3.0"))
    writeFileSync(join(destination, name), `test binary for ${name}`);
  const result = manifest(destination, "0.3.0");
  const name = assetNames("0.3.0")[0];
  const hash = createHash("sha256")
    .update(readFileSync(join(destination, name)))
    .digest("hex");
  assert.ok(result.includes(`${hash}  ${name}`));
  assert.equal(result.trim().split("\n").length, 6);
  assert.equal(manifest(destination, "0.3.0"), result);
});
test("empty installers are rejected before publishing", (t) => {
  const root = fixture(t);
  const destination = join(root, "assets");
  mkdirSync(destination);
  for (const name of assetNames("0.3.0"))
    writeFileSync(join(destination, name), "");
  assert.throws(() => manifest(destination, "0.3.0"), /Empty or invalid/);
});
test("collector copies only the requested target installers", (t) => {
  const root = fixture(t);
  const bundle = join(
    root,
    "src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis",
  );
  mkdirSync(bundle, { recursive: true });
  writeFileSync(join(bundle, "original-setup.exe"), "test installer");
  assert.deepEqual(collect("x86_64-pc-windows-msvc", root), [
    "FocusNest-0.3.0-windows-x64.exe",
  ]);
  assert.equal(
    readFileSync(
      join(root, "dist/release/FocusNest-0.3.0-windows-x64.exe"),
      "utf8",
    ),
    "test installer",
  );
  writeFileSync(join(bundle, "stale-installer.exe"), "stale");
  assert.throws(() => collect("x86_64-pc-windows-msvc", root), /exactly one/);
});
