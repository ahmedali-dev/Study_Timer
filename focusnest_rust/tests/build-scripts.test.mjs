import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const script = (name) =>
  fileURLToPath(new URL(`../scripts/${name}`, import.meta.url));
const hasBash =
  spawnSync("bash", ["--version"], { encoding: "utf8" }).status === 0;
const shellTest = { skip: !hasBash && "Bash is not installed on this host" };
function bash(name, args) {
  // Deliberately run outside the repository to verify path independence.
  return spawnSync("bash", [script(name), ...args], {
    cwd: tmpdir(),
    encoding: "utf8",
  });
}
for (const [arch, target] of [
  ["arm64", "aarch64-apple-darwin"],
  ["x64", "x86_64-apple-darwin"],
  ["universal", "universal-apple-darwin"],
]) {
  test(`macOS ${arch} dry run selects ${target}`, shellTest, () => {
    const r = bash("build-macos.sh", ["--arch", arch, "--dry-run"]);
    assert.equal(r.status, 0, r.stderr);
    assert.ok(r.stdout.includes(`--target ${target}`));
    assert.ok(r.stdout.includes(`target/${target}/release/bundle/`));
    assert.ok(r.stdout.includes("+ npm ci"));
    assert.ok(
      r.stdout.includes(
        "cargo test --manifest-path src-tauri/Cargo.toml --locked",
      ),
    );
    if (arch === "universal")
      assert.ok(
        r.stdout.includes(
          "rustup target add aarch64-apple-darwin x86_64-apple-darwin",
        ),
      );
  });
}
test(
  "macOS skip options remove install and test commands, not locked builds",
  shellTest,
  () => {
    const r = bash("build-macos.sh", [
      "--dry-run",
      "--skip-install",
      "--skip-tests",
      "--bundles",
      "app",
    ]);
    assert.equal(r.status, 0, r.stderr);
    assert.ok(!r.stdout.includes("+ npm ci"));
    assert.ok(!r.stdout.includes("+ npm test"));
    assert.ok(!r.stdout.includes("+ cargo test"));
    assert.ok(r.stdout.includes("--bundles app -- --locked"));
  },
);
test(
  "Linux dry run keeps the GNU architecture and requested package type",
  shellTest,
  () => {
    const r = bash("build-linux.sh", ["--dry-run", "--bundles", "rpm"]);
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stdout, /--target (aarch64|x86_64)-unknown-linux-gnu/);
    assert.ok(r.stdout.includes("--bundles rpm -- --locked"));
  },
);
for (const name of ["build-macos.sh", "build-linux.sh"]) {
  test(`${name} rejects malformed flags without building`, shellTest, () => {
    for (const args of [
      ["--dry-run", "--unknown"],
      ["--bundles"],
      ["--dry-run", "--bundles", "exe"],
    ]) {
      const r = bash(name, args);
      assert.notEqual(r.status, 0);
      assert.ok(r.stderr.includes("Error:"));
      assert.ok(!r.stdout.includes("+ node"));
    }
    assert.equal(bash(name, ["--help"]).status, 0);
  });
}
test("macOS rejects unknown architecture values", shellTest, () => {
  const r = bash("build-macos.sh", ["--dry-run", "--arch", "arm32"]);
  assert.equal(r.status, 2);
  assert.ok(r.stderr.includes("Invalid architecture"));
});
test(
  "real builds reject the wrong host operating system before installing anything",
  shellTest,
  () => {
    const name =
      process.platform === "darwin"
        ? "build-linux.sh"
        : process.platform === "linux"
          ? "build-macos.sh"
          : null;
    if (!name) return;
    const r = bash(name, []);
    assert.equal(r.status, 2);
    assert.ok(r.stderr.includes("Run this script on"));
    assert.equal(r.stdout, "");
  },
);
const powershell = ["pwsh", "powershell"].find(
  (name) =>
    spawnSync(
      name,
      [
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$PSVersionTable.PSVersion.ToString()",
      ],
      { encoding: "utf8" },
    ).status === 0,
);
test(
  "Windows dry run builds separate native x64 and ARM64 application installers",
  {
    skip:
      !powershell &&
      "PowerShell is not installed on this host; runs on Windows CI",
  },
  () => {
    const r = spawnSync(
      powershell,
      [
        "-NoProfile",
        "-NonInteractive",
        "-File",
        script("build-windows.ps1"),
        "-Architecture",
        "both",
        "-DryRun",
      ],
      { cwd: tmpdir(), encoding: "utf8" },
    );
    assert.equal(r.status, 0, r.stderr);
    for (const target of [
      "x86_64-pc-windows-msvc",
      "aarch64-pc-windows-msvc",
    ]) {
      assert.ok(
        r.stdout.includes(`--target ${target} --bundles nsis -- --locked`),
      );
      assert.ok(r.stdout.includes(`${target}/release/bundle/nsis/`));
    }
  },
);
