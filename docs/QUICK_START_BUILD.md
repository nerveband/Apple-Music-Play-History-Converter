# Quick Start: Building & Releasing

Fast guide to build and release the Apple Music History Converter locally.

---

## 🚀 One-Command Build (Current Platform)

```bash
# Build for your current platform
./build_all_platforms.sh

# Files will be in: release_builds/
```

That's it! The script handles everything automatically.

---

## 📦 Building for All Platforms

You need access to **three computers** (or VMs):
1. **Mac** - for macOS builds
2. **Windows PC** - for Windows builds
3. **Linux PC** - for Linux builds

### On macOS:

```bash
./build_all_platforms.sh macos
```

**Output**: `release_builds/Apple_Music_History_Converter_macOS.dmg` (~50MB, signed & notarized)

### On Windows:

```bash
./build_all_platforms.sh windows
```

**Output**: `release_builds/Apple_Music_History_Converter_Windows.msi` (~40MB)

### On Linux:

```bash
./build_all_platforms.sh linux
```

**Output**:
- `release_builds/Apple_Music_History_Converter_Linux.AppImage` (~80MB)
- `release_builds/Apple_Music_History_Converter_Linux.deb` (~10MB)

---

## ✅ Testing

### Quick Test (macOS):

```bash
# Open the DMG
open release_builds/Apple_Music_History_Converter_macOS.dmg

# Drag to Applications and launch
```

### Verify Signing (macOS):

```bash
# Check signature
codesign -vvv "/Applications/Apple Music History Converter.app"

# Check notarization
spctl -a -t exec -vv "/Applications/Apple Music History Converter.app"
# Should say: "accepted, source=Notarized Developer ID"
```

### Critical Test:

**Test on a DIFFERENT computer** to ensure signing/notarization works!

---

## 📤 Creating a GitHub Release

### 1. Create and Push Tag:

```bash
git tag -a v1.4.0 -m "Release v1.4.0"
git push origin v1.4.0
```

### 2. Go to GitHub:

https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/new

### 3. Fill in Release Form:

- **Tag**: v1.4.0
- **Title**: Apple Music History Converter v1.4.0
- **Description**: Copy from `docs/RELEASE_NOTES_TEMPLATE.md`

### 4. Upload Files:

Drag and drop from `release_builds/`:
- `Apple_Music_History_Converter_macOS.dmg`
- `Apple_Music_History_Converter_Windows.msi`
- `Apple_Music_History_Converter_Linux.AppImage`
- `Apple_Music_History_Converter_Linux.deb`

### 5. Publish!

Click **"Publish release"**

---

## 🔧 Prerequisites

### All Platforms:

```bash
pip install briefcase
```

### macOS Only:

- Developer ID certificate (✅ you have this)
- `.env` file with Apple credentials (✅ you have this)

### Windows Only:

- Visual Studio Build Tools (Briefcase will prompt if needed)

### Linux Only:

```bash
# Ubuntu/Debian
sudo apt install libgirepository1.0-dev libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev

# Fedora
sudo dnf install gobject-introspection-devel cairo-gobject-devel gtk3-devel
```

---

## 📁 File Structure

```
release_builds/                    # Git-ignored, created by build script
├── Apple_Music_History_Converter_macOS.dmg
├── Apple_Music_History_Converter_Windows.msi
├── Apple_Music_History_Converter_Linux.AppImage
└── Apple_Music_History_Converter_Linux.deb

build/                            # Git-ignored, Briefcase build artifacts
dist/                             # Git-ignored, Briefcase distribution files
```

---

## 💡 Tips

1. **Clean builds**: Delete `build/` and `dist/` directories between releases
2. **Version bumps**: Update version in `pyproject.toml` before building
3. **Test thoroughly**: Always test on a different machine before releasing
4. **Keep archives**: Save `release_builds/` for each version

---

## 🆘 Troubleshooting

### Build fails:

```bash
# Check detailed logs
./build_all_platforms.sh 2>&1 | tee build.log

# Clean and retry
rm -rf build/ dist/ release_builds/
./build_all_platforms.sh
```

### Notarization fails (macOS):

```bash
# Check credentials
source .env
echo $APPLE_ID
echo $APPLE_TEAM_ID

# View notarization history
xcrun notarytool history \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
```

---

## 📚 Full Documentation

- **Complete guide**: `docs/MANUAL_RELEASE_GUIDE.md`
- **Release notes template**: `docs/RELEASE_NOTES_TEMPLATE.md`
- **Build changes summary**: `BUILD_CHANGES_SUMMARY.md`

---

## ⏱️ Time Estimates

- **macOS build**: ~15 minutes (includes 5-10 min notarization)
- **Windows build**: ~7 minutes
- **Linux build**: ~6 minutes
- **Total**: ~30 minutes for all platforms

---

**That's it!** Build, test, upload, release. 🎉
