import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const json = (file) => JSON.parse(readFileSync(path.join(root, file), "utf8"));
const packageVersion = json("package.json").version;
const values = new Map([
  ["package.json", packageVersion],
  ["src-tauri/tauri.conf.json", json("src-tauri/tauri.conf.json").version],
]);

const extract = (file, pattern) => {
  const content = readFileSync(path.join(root, file), "utf8");
  const match = content.match(pattern);
  if (!match) throw new Error(`Could not find app version in ${file}`);
  return match[1];
};

values.set("src-tauri/Cargo.toml", extract("src-tauri/Cargo.toml", /^version = "([^"]+)"/m));
values.set("../pyproject.toml", extract("../pyproject.toml", /^version = "([^"]+)"/m));
values.set("python-sidecar/sidecar.py", extract("python-sidecar/sidecar.py", /^APP_VERSION = "([^"]+)"/m));
values.set("src/components/Dialogs.tsx", extract("src/components/Dialogs.tsx", /Version ([0-9]+\.[0-9]+\.[0-9]+)/));
values.set("e2e/run-tests.mjs", extract("e2e/run-tests.mjs", /app\.version === '([^']+)'/));

const mismatches = [...values].filter(([, version]) => version !== packageVersion);
if (mismatches.length) {
  throw new Error(
    `Version mismatch; expected ${packageVersion}:\n` +
    mismatches.map(([file, version]) => `  ${file}: ${version}`).join("\n"),
  );
}

console.log(`All application version sources agree on ${packageVersion}.`);
