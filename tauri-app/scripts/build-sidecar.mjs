import { existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const tauriRoot = path.resolve(__dirname, "..");
const sidecarDir = path.join(tauriRoot, "python-sidecar");
const requirementsPath = path.join(sidecarDir, "requirements.txt");
const specPath = path.join(sidecarDir, "sidecar.spec");
const distDir = path.join(sidecarDir, "dist");
const buildDir = path.join(sidecarDir, "build");
const outputBinary = process.platform === "win32"
  ? path.join(distDir, "sidecar.exe")
  : path.join(distDir, "sidecar");
const targetArch = normalizeArch(process.env.TAURI_ENV_ARCH || process.arch);
const venvDir = path.join(sidecarDir, `.bundle-venv-${targetArch}`);
const pyInstallerMarker = process.platform === "win32"
  ? path.join(venvDir, "Scripts", "pyinstaller.exe")
  : path.join(venvDir, "bin", "pyinstaller");
const venvPython = process.platform === "win32"
  ? path.join(venvDir, "Scripts", "python.exe")
  : path.join(venvDir, "bin", "python");
const venvPythonCommand = process.platform === "darwin" && targetArch === "x86_64"
  ? { command: "/usr/bin/arch", baseArgs: ["-x86_64", venvPython] }
  : { command: venvPython, baseArgs: [] };

function normalizeArch(arch) {
  const normalized = arch.toLowerCase();

  if (normalized === "x64" || normalized === "x86_64" || normalized === "amd64") {
    return "x86_64";
  }

  if (normalized === "aarch64" || normalized === "arm64") {
    return "arm64";
  }

  return normalized;
}

function run(command, args, options = {}) {
  const display = [command, ...args].join(" ");
  console.log(`[build-sidecar] ${display}`);
  const result = spawnSync(command, args, {
    stdio: "inherit",
    ...options,
  });

  if (result.status !== 0) {
    throw new Error(`Command failed (${result.status ?? "unknown"}): ${display}`);
  }
}

function probePython(command, baseArgs, expectedArch) {
  const probe = spawnSync(
    command,
    [
      ...baseArgs,
      "-c",
      [
        "import platform",
        "import sys",
        `expected = ${JSON.stringify(expectedArch)}`,
        "machine = platform.machine().lower()",
        "aliases = {'x64': 'x86_64', 'amd64': 'x86_64', 'aarch64': 'arm64'}",
        "actual = aliases.get(machine, machine)",
        "print(actual)",
        "sys.exit(0 if actual == expected else 1)",
      ].join("; "),
    ],
    { encoding: "utf8" },
  );

  return probe.status === 0;
}

function findPython() {
  const preferredPython = process.env.SIDECAR_PYTHON?.trim();

  if (preferredPython) {
    const candidate = { command: preferredPython, baseArgs: [] };
    if (probePython(candidate.command, candidate.baseArgs, targetArch)) {
      return candidate;
    }
  }

  const candidates = process.platform === "win32"
    ? [
        ["py", ["-3"]],
        ["python", []],
        ["python3", []],
      ]
    : process.platform === "darwin" && targetArch === "x86_64"
      ? [
          ["/usr/bin/arch", ["-x86_64", "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"]],
          ["/usr/bin/arch", ["-x86_64", "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"]],
          ["/usr/bin/arch", ["-x86_64", "/usr/local/bin/python3"]],
        ]
    : [
        ["python3", []],
        ["python", []],
      ];

  for (const [command, baseArgs] of candidates) {
    if (probePython(command, baseArgs, targetArch)) {
      return { command, baseArgs };
    }
  }

  return null;
}

function ensureVenv(python) {
  if (!existsSync(venvPython)) {
    run(python.command, [...python.baseArgs, "-m", "venv", venvDir], { cwd: sidecarDir });
  }
}

function ensureBuildEnvironment() {
  if (!existsSync(pyInstallerMarker)) {
    run(venvPythonCommand.command, [...venvPythonCommand.baseArgs, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], { cwd: sidecarDir });
    run(venvPythonCommand.command, [...venvPythonCommand.baseArgs, "-m", "pip", "install", "-r", requirementsPath, "pyinstaller==6.21.0"], { cwd: sidecarDir });
  } else {
    run(venvPythonCommand.command, [...venvPythonCommand.baseArgs, "-m", "pip", "install", "--disable-pip-version-check", "-r", requirementsPath], { cwd: sidecarDir });
  }
}

function cleanBuildArtifacts() {
  rmSync(buildDir, { recursive: true, force: true });
  rmSync(distDir, { recursive: true, force: true });
  mkdirSync(distDir, { recursive: true });
}

function signMacSidecar() {
  if (process.platform !== "darwin") {
    return;
  }

  const identity = process.env.APPLE_SIGNING_IDENTITY?.trim() || "-";
  const entitlementsPath = path.join(tauriRoot, "src-tauri", "entitlements.plist");
  const args = ["--force", "--sign", identity];

  if (identity !== "-") {
    args.push("--options", "runtime", "--timestamp");
    if (existsSync(entitlementsPath)) {
      args.push("--entitlements", entitlementsPath);
    }
  }

  args.push(outputBinary);
  run("codesign", args, { cwd: sidecarDir });
}

function main() {
  if (!["darwin", "win32"].includes(process.platform)) {
    console.log(`[build-sidecar] Skipping bundled sidecar build on unsupported platform: ${process.platform}`);
    return;
  }

  if (!existsSync(specPath)) {
    throw new Error(`Missing PyInstaller spec: ${specPath}`);
  }

  const python = findPython();
  if (!python) {
    throw new Error(`Python 3.8+ for target arch ${targetArch} is required to build the bundled sidecar`);
  }

  console.log(`[build-sidecar] Building ${process.platform} sidecar for ${targetArch}`);
  ensureVenv(python);
  ensureBuildEnvironment();
  cleanBuildArtifacts();

  run(venvPythonCommand.command, [...venvPythonCommand.baseArgs, "-m", "PyInstaller", "--noconfirm", specPath], { cwd: sidecarDir });

  if (!existsSync(outputBinary)) {
    throw new Error(`Bundled sidecar binary was not created at ${outputBinary}`);
  }

  signMacSidecar();
  console.log(`[build-sidecar] Bundled sidecar ready: ${outputBinary}`);
}

main();
