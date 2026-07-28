# AGENTS.md

## Scope

This file documents the build, signing, packaging, and release workflow for this repository.
Use it as the short operational reference. The longer maintainer guide lives in `docs/RELEASING.md`.

## Stack

- Frontend: React + TypeScript in `tauri-app/src`
- Desktop host: Tauri + Rust in `tauri-app/src-tauri`
- Search/export engine: Python sidecar in `tauri-app/python-sidecar`
- Shared Python modules: `src/apple_music_history_converter`

## Commands

```bash
cd tauri-app && npm install
cd tauri-app && npm run test
cd tauri-app/src-tauri && cargo check
cd tauri-app/python-sidecar && python3 test_sidecar.py
cd tauri-app && npm run tauri dev
cd tauri-app && npm run tauri build
```

## Release Prerequisites

### Common

- Node.js 24.15+ (Node 24 LTS)
- Rust toolchain via `rustup`
- Python 3.11+ available as `python3`, `python`, or `py -3`
- `gh` authenticated for `nerveband/Apple-Music-Play-History-Converter`

### macOS Release Builds

- A valid `Developer ID Application` certificate must exist in the login keychain
- Export these environment variables before building:
  - `APPLE_SIGNING_IDENTITY`
  - `APPLE_ID`
  - `APPLE_TEAM_ID`
  - `APPLE_PASSWORD`
- If local secrets are stored as `APPLE_APP_SPECIFIC_PASSWORD`, map it before the build:

```bash
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
```

### Windows Release Builds

- Windows installers currently build unsigned
- WebView2 is bundled with Tauri's offline installer mode, so end users do not need a preinstalled runtime

## Important Release Rules

- Release builds must be self-contained. Do not rely on end users having Python, pip, or sidecar dependencies installed.
- `npm run tauri build` already runs `npm run build:release`, which builds the frontend and the bundled Python sidecar.
- macOS releases ship two DMGs:
  - Apple Silicon: `aarch64`
  - Intel: `x64`
- `release-artifacts/` is a local staging directory for copied installers. Do not commit it.
- Keep the app version in sync across:
  - `tauri-app/package.json`
  - `tauri-app/src-tauri/Cargo.toml`
  - `tauri-app/src-tauri/tauri.conf.json`
  - any UI/version display code that hardcodes the app version

## macOS Release Flow

Build Apple Silicon first:

```bash
cd tauri-app
set -a
source ../.env
set +a
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
export APPLE_SIGNING_IDENTITY="Developer ID Application: YOUR NAME (TEAM_ID)"

npm run test
cd src-tauri && cargo check
cd ..
npm run tauri build
```

Then build Intel on the same machine:

```bash
cd tauri-app
set -a
source ../.env
set +a
export APPLE_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
export APPLE_SIGNING_IDENTITY="Developer ID Application: YOUR NAME (TEAM_ID)"

npm run tauri build -- --target x86_64-apple-darwin
```

The sidecar build script follows `TAURI_ENV_ARCH`, so Intel builds use the `python-sidecar/.bundle-venv-x86_64` environment and emit an x86_64 sidecar binary before packaging.

Validate the signed apps and stapled DMGs:

```bash
spctl -a -vv "src-tauri/target/release/bundle/macos/Apple Music History Converter.app"
xcrun stapler validate "src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg"
xcrun stapler validate "src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg"
```

If you need to notarize the DMGs explicitly after the build:

```bash
xcrun notarytool submit "src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait

xcrun stapler staple "src-tauri/target/release/bundle/dmg/Apple Music History Converter_<VERSION>_aarch64.dmg"

xcrun notarytool submit "src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait

xcrun stapler staple "src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg"
```

## Windows Release Flow

Run the build on a Windows host:

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

## Publish Checklist

1. Bump versions and update `CHANGELOG.md`
2. Run tests and `cargo check`
3. Build the signed macOS release
4. Build the Windows installers
5. Copy Windows installers into `release-artifacts/v<VERSION>/` locally if you want a staging folder
6. Generate SHA-256 checksums with `shasum -a 256`
7. Commit, tag, and push:

```bash
git status --short
git add <release-files-only>
git commit -m "release: v<VERSION>"
git tag -a v<VERSION> -m "v<VERSION>"
git push origin main
git push origin v<VERSION>
```

Make sure `release-artifacts/` is still untracked before committing.

8. Publish the GitHub release after both macOS DMGs and both Windows installers are ready:

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

9. Only use `gh release upload` if the release already exists and you need to patch in a missing asset:

```bash
gh release upload v<VERSION> \
  --repo nerveband/Apple-Music-Play-History-Converter \
  "tauri-app/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/Apple Music History Converter_<VERSION>_x64.dmg#Apple.Music.History.Converter_<VERSION>_x64.dmg"
```

## Logs and Diagnostics

- macOS session logs: `~/Library/Logs/AppleMusicConverter`
- Windows session logs: `%LOCALAPPDATA%\AppleMusicConverter\Logs`

If a user reports startup, search, or database download failures, ask for the latest session log from that folder.
