# Release Workflow

Complete step-by-step guide for building and releasing a new version.

## Build Strategy (v2.0.0+)

- **macOS**: Build locally (fast, secure, you have Mac)
- **Windows**: GitHub Actions (automated, no Windows machine needed)
- **Linux**: Source code only (users compile from source)

## Prerequisites

- **macOS Machine**: Your primary Mac
- **GitHub Account**: For automated Windows builds
- **Apple Developer ID**: For macOS code signing & notarization
- **Git & Python 3.12+**: Installed locally

---

## Step 1: Prepare for Release

### Update Version Numbers

```bash
# 1. Update version in THREE places:
#    - pyproject.toml: [project] version = "2.0.0"
#    - pyproject.toml: [tool.briefcase] version = "2.0.0"
#    - src/apple_music_history_converter/__init__.py: __version__ = "2.0.0"

# 2. Update CHANGELOG.md with new features/fixes

# 3. Commit version bump
git add .
git commit -m "chore: bump version to 2.0.0"
git push origin main

# 4. Create and push version tag
git tag v2.0.0
git push origin v2.0.0
```

---

## Step 2: Build macOS (Local)

### Why Local?
- [OK] Fast (2 minutes vs 10+ on CI/CD)
- [OK] Secure (signing cert stays on your Mac)
- [OK] You have a Mac anyway

### Commands

```bash
# Navigate to project
cd ~/path/to/Apple-Music-Play-History-Converter

# Pull latest code
git pull origin main

# Clean previous builds
rm -rf build/ dist/

# Build and package with signing & notarization
briefcase package macOS --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Output: dist/Apple Music History Converter-2.0.0.dmg
# This DMG is fully signed, notarized, and stapled - ready for distribution

# Verify notarization
spctl -a -t exec -vv "dist/Apple Music History Converter-2.0.0.dmg"
# Should show: "accepted, source=Notarized Developer ID"

# Optional: Copy to Desktop for safekeeping
cp "dist/Apple Music History Converter-2.0.0.dmg" ~/Desktop/
```

---

## Step 3: Build Windows (GitHub Actions)

### Why GitHub Actions?
- [OK] Automated (no Windows VM needed)
- [OK] Free for public repos
- [OK] Consistent build environment

### Trigger Build

The build triggers automatically when you push to `main` or `feature/ui-rewrite` branches.

**Or manually trigger:**

1. Go to GitHub Actions: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions
2. Click "Build Windows App" workflow
3. Click "Run workflow" → Select branch → "Run workflow"

### Monitor Build

```bash
# Watch build progress from terminal
gh run list --workflow=build-windows.yml --limit 1

# Or watch live
gh run watch <run-id>
```

### Download Build

```bash
# Download latest Windows build artifact
gh run list --workflow=build-windows.yml --limit 1 --json databaseId,status
gh run download <run-id> --dir ~/Desktop/windows-build

# The ZIP will be in: ~/Desktop/windows-build/apple-music-history-converter-windows-x86_64/
```

**Output**: Portable Windows ZIP (no installer - just extract and run .exe)

**Format**: x86_64 architecture (compatible with ARM Windows via emulation)

---

## Step 4: Linux (No Builds)

### Why No Linux Builds?
- [OK] Linux users are tech-savvy enough to compile from source
- [OK] Reduces maintenance overhead
- [OK] Multiple distro formats would be complex (deb, rpm, AppImage, Flatpak)
- [OK] Briefcase AppImage support is discouraged by BeeWare team

### Linux Installation Instructions (for README)

```bash
# Clone repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# Install dependencies
pip install -r requirements.txt

# Run application
python run_toga_app.py
```

---

## Step 5: Create GitHub Release

### Upload Both Builds

```bash
# Navigate to folder with both builds
cd ~/Desktop/

# Create GitHub release with both artifacts
gh release create v2.0.0 \
  --title "v2.0.0 - Feature Release Title" \
  --notes "## What's New

- Feature 1
- Feature 2
- Bug fix 1

## Downloads

### macOS (Recommended)
- **Apple Music History Converter-2.0.0.dmg** (Signed & Notarized)
- Extract and drag to Applications folder
- No security warnings (fully notarized)

### Windows
- **Apple_Music_History_Converter_Windows_2.0.0.zip** (Portable)
- Extract ZIP and run \`Apple Music History Converter.exe\`
- No installation needed
- Windows Defender may show SmartScreen warning (click 'More info' → 'Run anyway')

### Linux
- **Source code only** - see installation instructions in README
- Linux users: Clone repo and run from source

## Installation

### macOS
1. Download DMG
2. Open DMG
3. Drag app to Applications folder
4. Launch from Applications

### Windows
1. Download ZIP
2. Extract to any folder
3. Run \`Apple Music History Converter.exe\`
4. If SmartScreen appears: Click 'More info' → 'Run anyway'

### Linux
See README for source installation instructions.
" \
  "Apple Music History Converter-2.0.0.dmg" \
  "Apple_Music_History_Converter_Windows_2.0.0.zip"
```

---

## Step 6: Verify Release

```bash
# Open release page
open https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest

# Verify:
# [OK] macOS DMG uploaded
# [OK] Windows ZIP uploaded
# [OK] Release notes are correct
# [OK] Download links work
# [OK] Version tag matches
```

---

## Build Architecture Summary

| Platform | Build Method | Format | Architecture | Distribution |
|----------|--------------|---------|--------------|--------------|
| **macOS** | Local (Briefcase) | DMG | Universal (x86_64 + ARM64) | Signed & Notarized |
| **Windows** | GitHub Actions | Portable ZIP | x86_64 | Unsigned |
| **Linux** | N/A | Source Code | Any | Users compile |

---

## Troubleshooting

### macOS Build Issues

**Signature fails**:
```bash
# Verify certificate installed
security find-identity -v -p codesigning
# Should show: Developer ID Application: Ashraf Ali (7HQVB2S4BX)
```

**Notarization fails**:
```bash
# Check credentials stored
xcrun notarytool history --apple-id nerveband@gmail.com

# Re-store credentials if needed
source .env
xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
```

### Windows Build Issues

**Build fails on GitHub Actions**:
- Check workflow logs: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions
- Common issues:
  - Version number mismatch (check all 3 locations)
  - Dependency installation failures
  - Briefcase compatibility issues

**Wrong version in ZIP filename**:
- The ZIP folder name comes from Briefcase metadata
- Ensure `pyproject.toml` has correct version in both places
- Workflow includes clean step to prevent caching

### GitHub Release Issues

**gh CLI not authenticated**:
```bash
gh auth login
```

**Upload fails**:
- Check file paths are correct
- Ensure files exist in current directory
- Verify you have write access to repo

---

## Version Bump Checklist

- [ ] Update version in `pyproject.toml` (2 places)
- [ ] Update version in `__init__.py`
- [ ] Update `CHANGELOG.md`
- [ ] Commit and push to main
- [ ] Create and push git tag
- [ ] Build macOS locally with Briefcase
- [ ] Verify Windows build completed on GitHub Actions
- [ ] Download Windows ZIP artifact
- [ ] Create GitHub release with both builds
- [ ] Verify downloads work
- [ ] Update README if needed
- [ ] Announce release (optional)

---

## GitHub Actions Workflow Details

**Workflow File**: `.github/workflows/build-windows.yml`

**Triggers**:
- Push to `main` or `feature/ui-rewrite`
- Manual dispatch via Actions tab

**Steps**:
1. Checkout repository
2. Set up Python 3.12 (x64)
3. Install Briefcase
4. Clean previous builds
5. Create Windows app
6. Build Windows app
7. Package as ZIP
8. Upload artifact (90-day retention)

**Build Time**: ~2 minutes

**Output**: Portable ZIP in artifacts section of workflow run

---

## Quick Commands Reference

```bash
# Check current version
grep "version =" pyproject.toml

# macOS: Full build + sign + notarize
briefcase package macOS --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Windows: Download latest build
gh run list --workflow=build-windows.yml --limit 1 --json databaseId | jq -r '.[0].databaseId'
gh run download <id> --dir ~/Desktop/windows-build

# Create release
gh release create v2.0.0 --title "v2.0.0" --notes "Release notes..." file1.dmg file2.zip

# View releases
gh release list
```
