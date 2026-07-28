# Releasing

This document is the canonical release playbook for the Tauri desktop app.

## What a Release Must Guarantee

- End users must not need Python, pip, or sidecar dependencies installed
- macOS artifacts must be signed and notarized before distribution
- macOS releases must include both Apple Silicon and Intel DMGs
- Windows artifacts must include the offline WebView2 runtime path
- Release diagnostics must be available in user log folders for startup failures
- Git tag, GitHub release, and binary versions must match

## Files That Must Stay in Sync

Update the version in all of these places before building a release:

- `CHANGELOG.md`
- `tauri-app/package.json`
- `tauri-app/src-tauri/Cargo.toml`
- `tauri-app/src-tauri/tauri.conf.json`
- any UI or sidecar files that hardcode the displayed app version

## Preflight

### Common Tooling

- Node.js 24.15+ (Node 24 LTS)
- Rust toolchain
- Python 3.11+
- GitHub CLI authenticated to `nerveband/Apple-Music-Play-History-Converter`

### macOS Signing and Notarization

Confirm that the Developer ID certificate exists:

```bash
security find-identity -v -p codesigning | grep "Developer ID Application"
```

Required environment variables:

- `APPLE_SIGNING_IDENTITY`
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APPLE_PASSWORD`

If local secrets are stored in `.env` with `APPLE_APP_SPECIFIC_PASSWORD`, export Tauri's expected variable before the build:

```bash
set -a
source .env
set +a
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
```

### Windows Packaging

No signing certificate is currently required for builds, but the resulting MSI and NSIS installer will be unsigned.

## Verify Before Building

From the repository root:

```bash
cd tauri-app
npm install
npm run test

cd src-tauri
cargo check

cd ../python-sidecar
python3 test_sidecar.py
```

## How the Release Build Works

`tauri-app/src-tauri/tauri.conf.json` runs `npm run build:release` before every packaged build.

That script does two things:

1. Builds the React frontend
2. Builds a bundled Python sidecar with PyInstaller via `tauri-app/scripts/build-sidecar.mjs`

Important sidecar behavior:

- build dependencies are installed into `tauri-app/python-sidecar/.bundle-venv-<arch>`
- the final sidecar binary is emitted to `tauri-app/python-sidecar/dist/`
- on macOS, the sidecar binary is signed during the build script
- on macOS, Intel builds follow `TAURI_ENV_ARCH=x86_64` and force the sidecar venv through `arch -x86_64`
- the packaged app includes sidecar resources from `tauri-app/python-sidecar/dist/*`

## Build the Signed macOS Releases

Build Apple Silicon:

```bash
cd tauri-app
set -a
source ../.env
set +a
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
export APPLE_SIGNING_IDENTITY="Developer ID Application: YOUR NAME (TEAM_ID)"

npm run tauri build
```

Expected Apple Silicon outputs:

- `tauri-app/src-tauri/target/release/bundle/macos/Apple Music History Converter.app`
- `tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg`

Build Intel:

```bash
cd tauri-app
set -a
source ../.env
set +a
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
export APPLE_SIGNING_IDENTITY="Developer ID Application: YOUR NAME (TEAM_ID)"

npm run tauri build -- --target x86_64-apple-darwin
```

Expected Intel outputs:

- `tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/macos/Apple Music History Converter.app`
- `tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg`

### Validate the macOS Build

Check both apps:

```bash
spctl -a -vv "tauri-app/src-tauri/target/release/bundle/macos/Apple Music History Converter.app"
spctl -a -vv "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/macos/Apple Music History Converter.app"
```

The expected result is `accepted` with `source=Notarized Developer ID`.

Validate both DMG staples:

```bash
xcrun stapler validate "tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg"
xcrun stapler validate "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg"
```

### Notarize the DMGs Explicitly

If you want to explicitly submit and staple the DMGs after the build:

```bash
xcrun notarytool submit "tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait

xcrun stapler staple "tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg"

xcrun notarytool submit "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait

xcrun stapler staple "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg"
```

## Build the Windows Release

Run the packaging step on a Windows machine:

```powershell
cd tauri-app
npm.cmd ci
npm.cmd run test

cd src-tauri
cargo check
cd ..

npm.cmd run tauri build
```

Expected outputs:

- `tauri-app\src-tauri\target\release\bundle\msi\Apple Music History Converter_<VERSION>_x64_en-US.msi`
- `tauri-app\src-tauri\target\release\bundle\nsis\Apple Music History Converter_<VERSION>_x64-setup.exe`

Notes:

- Windows builds bundle the offline WebView2 installer
- the Python sidecar is bundled into the app at build time
- the current release flow does not sign Windows binaries

## Stage Artifacts for Publishing

If the Windows build happened on another machine, copy the installers into a local staging directory:

```bash
mkdir -p "release-artifacts/v<VERSION>"
```

Recommended contents:

- `release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64_en-US.msi`
- `release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64-setup.exe`

Do not commit `release-artifacts/`.

## Generate Checksums

```bash
shasum -a 256 \
  "tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg" \
  "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg" \
  "release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64_en-US.msi" \
  "release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64-setup.exe"
```

## Publish

Commit and tag:

```bash
git status --short
git add <release-files-only>
git commit -m "release: v<VERSION>"
git tag -a v<VERSION> -m "v<VERSION>"
git push origin main
git push origin v<VERSION>
```

Confirm that `release-artifacts/` is still untracked before committing.

Prepare release notes, then publish with GitHub CLI after both macOS DMGs and both Windows installers are ready:

```bash
gh release create v<VERSION> \
  --repo nerveband/Apple-Music-Play-History-Converter \
  --title "v<VERSION> - <TITLE>" \
  --notes-file /tmp/release-notes.md \
  "tauri-app/src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg" \
  "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg#Apple.Music.History.Converter_<VERSION>_x64.dmg" \
  "release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64_en-US.msi" \
  "release-artifacts/v<VERSION>/Apple Music History Converter_<VERSION>_x64-setup.exe"
```

Only use `gh release upload` if the release already exists and you need to patch in a missing asset:

```bash
gh release upload v<VERSION> \
  --repo nerveband/Apple-Music-Play-History-Converter \
  "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg#Apple.Music.History.Converter_<VERSION>_x64.dmg"
```

## Logs to Request From Users

When investigating failed launches, search requests, or MusicBrainz download problems, ask for the latest session log:

- macOS: `~/Library/Logs/AppleMusicConverter`
- Windows: `%LOCALAPPDATA%\AppleMusicConverter\Logs`

Those logs include app version, OS details, launch timestamp, session metadata, and sidecar lifecycle events.
