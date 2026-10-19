import {
  appendFileSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { execFileSync, spawnSync } from "node:child_process";

export const appRoot = fileURLToPath(new URL("..", import.meta.url));
export const targets = {
  "aarch64-apple-darwin": { label: "macos-arm64", extensions: ["dmg"] },
  "x86_64-apple-darwin": { label: "macos-x64", extensions: ["dmg"] },
  "x86_64-pc-windows-msvc": { label: "windows-x64", extensions: ["exe"] },
  "aarch64-pc-windows-msvc": { label: "windows-arm64", extensions: ["exe"] },
  "x86_64-unknown-linux-gnu": {
    label: "linux-x64",
    extensions: ["deb", "AppImage"],
  },
};
export function checkVersion(tag, version) {
  if (!/^\d+\.\d+\.\d+$/.test(version) || tag !== `focusnest-v${version}`) {
    throw new Error(`Release tag must exactly match focusnest-v${version}.`);
  }
  return version;
}
export function versionFromFiles(root = appRoot) {
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  const config = JSON.parse(
    readFileSync(join(root, "src-tauri/tauri.conf.json"), "utf8"),
  );
  const lock = JSON.parse(
    readFileSync(join(root, "package-lock.json"), "utf8"),
  );
  const cargo = readFileSync(join(root, "src-tauri/Cargo.toml"), "utf8").match(
    /^version\s*=\s*"([^"]+)"/m,
  )?.[1];
  if (
    [config.version, cargo, lock.version, lock.packages[""].version].some(
      (v) => v !== pkg.version,
    )
  ) {
    throw new Error(
      "package.json, npm lockfile, Cargo.toml and Tauri config versions must agree.",
    );
  }
  checkVersion(`focusnest-v${pkg.version}`, pkg.version);
  return pkg.version;
}
export function assetNames(version) {
  return Object.values(targets)
    .flatMap((t) =>
      t.extensions.map((ext) => `FocusNest-${version}-${t.label}.${ext}`),
    )
    .sort();
}
function filesIn(path) {
  if (!existsSync(path)) throw new Error(`Missing build directory: ${path}`);
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const file = join(path, entry.name);
    if (entry.isDirectory() && !entry.name.endsWith(".app"))
      return filesIn(file);
    return entry.isFile() ? [file] : [];
  });
}
export function collect(target, root = appRoot) {
  const spec = targets[target];
  if (!spec) throw new Error(`Unsupported release target: ${target}`);
  const version = versionFromFiles(root);
  const source = join(root, "src-tauri/target", target, "release/bundle");
  const files = filesIn(source);
  const destination = join(root, "dist/release");
  mkdirSync(destination, { recursive: true });
  return spec.extensions.map((ext) => {
    const matches = files.filter((file) => file.endsWith(`.${ext}`));
    if (matches.length !== 1 || statSync(matches[0]).size === 0)
      throw new Error(
        `Expected exactly one nonempty .${ext} installer in ${source}. Found ${matches.length}.`,
      );
    const name = `FocusNest-${version}-${spec.label}.${ext}`;
    copyFileSync(matches[0], join(destination, name));
    return name;
  });
}
export function manifest(directory, version = versionFromFiles()) {
  const expected = assetNames(version);
  const actual = readdirSync(directory)
    .filter((name) => name !== "SHA256SUMS")
    .sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected))
    throw new Error(
      `Installer set is incomplete or unexpected. Required: ${expected.join(", ")}`,
    );
  const sums =
    expected
      .map((name) => {
        const path = join(directory, name);
        if (!statSync(path).isFile() || statSync(path).size === 0)
          throw new Error(`Empty or invalid installer: ${name}`);
        return `${createHash("sha256").update(readFileSync(path)).digest("hex")}  ${name}`;
      })
      .join("\n") + "\n";
  writeFileSync(join(directory, "SHA256SUMS"), sums);
  return sums;
}
function gh(args) {
  return execFileSync("gh", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}
function publish(directory) {
  const version = versionFromFiles();
  const tag = process.env.RELEASE_TAG;
  const commit = process.env.RELEASE_COMMIT;
  checkVersion(tag, version);
  if (!/^[a-f0-9]{40}$/.test(commit ?? ""))
    throw new Error("Missing immutable release commit SHA.");
  const taggedCommit = gh([
    "api",
    `repos/${process.env.GH_REPO}/commits/${tag}`,
    "--jq",
    ".sha",
  ]);
  if (taggedCommit !== commit)
    throw new Error(
      "The release tag moved after validation; refusing to publish mismatched assets.",
    );
  manifest(directory, version);
  const probe = spawnSync(
    "gh",
    ["api", `repos/${process.env.GH_REPO}/releases/tags/${tag}`],
    { encoding: "utf8" },
  );
  if (probe.error) throw probe.error;
  if (probe.status === 0) {
    const release = JSON.parse(probe.stdout);
    if (!release.draft || release.target_commitish !== commit)
      throw new Error(
        "Refusing to replace a published release or a draft from a different commit.",
      );
  } else if (probe.stderr.includes("HTTP 404")) {
    gh([
      "release",
      "create",
      tag,
      "--verify-tag",
      "--target",
      commit,
      "--title",
      `FocusNest ${version}`,
      "--notes-file",
      join(appRoot, "RELEASE_NOTES.md"),
      "--draft",
    ]);
  } else {
    throw new Error(probe.stderr || "Could not inspect existing releases.");
  }
  gh([
    "release",
    "upload",
    tag,
    ...assetNames(version).map((name) => join(directory, name)),
    join(directory, "SHA256SUMS"),
    "--clobber",
  ]);
  const uploaded = JSON.parse(
    gh(["release", "view", tag, "--json", "assets"]),
  ).assets;
  if (uploaded.length !== assetNames(version).length + 1)
    throw new Error(
      "Uploaded asset count does not match. Release remains a draft.",
    );
  for (const asset of uploaded) {
    const path = join(directory, asset.name);
    if (!existsSync(path) || statSync(path).size !== asset.size)
      throw new Error(
        `Upload verification failed: ${asset.name}. Release remains a draft.`,
      );
  }
  gh(["release", "edit", tag, "--draft=false", "--latest"]);
  console.log(gh(["release", "view", tag, "--json", "url", "--jq", ".url"]));
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const [command, value] = process.argv.slice(2);
    if (command === "validate") {
      const version = checkVersion(value, versionFromFiles());
      const commit = execFileSync("git", ["rev-parse", "HEAD"], {
        encoding: "utf8",
      }).trim();
      if (process.env.GITHUB_OUTPUT)
        appendFileSync(
          process.env.GITHUB_OUTPUT,
          `version=${version}\ncommit=${commit}\n`,
        );
      console.log(`Validated ${value} at ${commit}`);
    } else if (command === "collect") console.log(collect(value).join("\n"));
    else if (command === "manifest") console.log(manifest(resolve(value)));
    else if (command === "publish") publish(resolve(value));
    else
      throw new Error(
        "Usage: release.mjs validate TAG | collect TARGET | manifest DIRECTORY | publish DIRECTORY",
      );
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
