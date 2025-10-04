# Manual Release Guide

This guide explains how to build and release the Apple Music History Converter manually, without using GitHub Actions CI/CD.

---

## 🎯 Overview

**Strategy**: Build locally on each platform → Upload binaries to GitHub Releases → Distribute

**Benefits:**
- ✅ No GitHub Secrets needed
- ✅ Full control over build process
- ✅ Test before releasing
- ✅ Simpler workflow
- ✅ No CI/CD minutes used

---

## 🛠️ Prerequisites

### All Platforms

1. **Python 3.12** installed
2. **Briefcase** installed: `pip install briefcase`
3. **Git** for version control
4. Access to all three platforms (or use VMs/cloud services)

### macOS Only

- **Developer ID Application certificate** (already have!)
- **Apple ID credentials** in `.env` file
- **Xcode Command Line Tools** installed

### Windows Only

- **Visual Studio Build Tools** (Briefcase will prompt if needed)
- **WiX Toolset** (for MSI creation - Briefcase handles this)

### Linux Only

- **GTK development libraries**:
  ```bash
  # Ubuntu/Debian
  sudo apt install libgirepository1.0-dev libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev

  # Fedora
  sudo dnf install gobject-introspection-devel cairo-gobject-devel gtk3-devel
  ```

---

## 📦 Building Process

### Option 1: Build on Each Platform Separately (Recommended)

This is the **recommended approach** for best results.

#### On macOS:

```bash
# Build for macOS
./build_all_platforms.sh macos

# Verify the build
ls -lh release_builds/Apple_Music_History_Converter_macOS.dmg

# Test it works
open release_builds/Apple_Music_History_Converter_macOS.dmg
```

**Output**: `Apple_Music_History_Converter_macOS.dmg` (~50MB, signed & notarized)

#### On Windows:

```bash
# Build for Windows
./build_all_platforms.sh windows

# Verify the build
ls release_builds/
```

**Output**: `Apple_Music_History_Converter_Windows.msi` or `.exe` (~40MB)

#### On Linux:

```bash
# Build for Linux
./build_all_platforms.sh linux

# Verify the build
ls -lh release_builds/
```

**Output**:
- `Apple_Music_History_Converter_Linux.AppImage` (~80MB)
- `Apple_Music_History_Converter_Linux.deb` or `.rpm` (~10MB)

---

### Option 2: Build All from One Platform (Advanced)

You can attempt to build all platforms from a single machine, but **this may not work properly**.

```bash
# Try to build all platforms (not recommended)
./build_all_platforms.sh all
```

**Issues:**
- ❌ Cross-platform builds often fail
- ❌ Code signing won't work across platforms
- ❌ Platform-specific dependencies may be missing

**Recommendation**: Use **Option 1** and build on native platforms.

---

## 🧪 Testing Before Release

### macOS Testing

1. **Test on your Mac:**
   ```bash
   open release_builds/Apple_Music_History_Converter_macOS.dmg
   # Drag to Applications, launch
   ```

2. **Verify signature:**
   ```bash
   codesign -vvv "/Applications/Apple Music History Converter.app"
   ```

3. **Check notarization:**
   ```bash
   spctl -a -t exec -vv "/Applications/Apple Music History Converter.app"
   # Should show: "accepted, source=Notarized Developer ID"
   ```

4. **Critical: Test on a different Mac!**
   - Transfer DMG to another Mac
   - Open and install
   - Verify no warnings appear

### Windows Testing

1. **Test on your Windows PC:**
   - Run the MSI installer
   - Go through SmartScreen bypass (More info → Run anyway)
   - Verify app launches

2. **Test on a clean Windows VM:**
   - Windows 10/11 fresh install
   - No developer tools
   - Verify user experience

### Linux Testing

1. **Test AppImage:**
   ```bash
   chmod +x release_builds/Apple_Music_History_Converter_Linux.AppImage
   ./release_builds/Apple_Music_History_Converter_Linux.AppImage
   ```

2. **Test on multiple distros:**
   - Ubuntu 20.04/22.04/24.04
   - Fedora 38/39/40
   - Arch Linux
   - Debian

3. **Test system package:**
   ```bash
   # Ubuntu/Debian
   sudo dpkg -i release_builds/*.deb

   # Fedora
   sudo rpm -i release_builds/*.rpm
   ```

---

## 📤 Creating a GitHub Release

### Step 1: Prepare Release

1. **Update version number** in `pyproject.toml`:
   ```toml
   version = "1.4.0"
   ```

2. **Update CHANGELOG.md** with new version notes

3. **Commit changes:**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore: bump version to v1.4.0"
   git push origin main
   ```

### Step 2: Create Git Tag

```bash
# Create annotated tag
git tag -a v1.4.0 -m "Release v1.4.0 - [Brief description]"

# Push tag to GitHub
git push origin v1.4.0
```

### Step 3: Build All Platforms

```bash
# On macOS
./build_all_platforms.sh macos

# On Windows
./build_all_platforms.sh windows

# On Linux
./build_all_platforms.sh linux

# Collect all files in release_builds/ directory
```

### Step 4: Create GitHub Release

1. **Go to GitHub Releases:**
   - Navigate to: https://github.com/nerveband/Apple-Music-Play-History-Converter/releases
   - Click **"Draft a new release"**

2. **Fill in release form:**
   - **Tag**: Select `v1.4.0` (the tag you just created)
   - **Title**: `Apple Music History Converter v1.4.0`
   - **Description**: Copy from `docs/RELEASE_NOTES_TEMPLATE.md` and customize

3. **Upload binaries:**
   - Drag and drop all files from `release_builds/`:
     - ✅ `Apple_Music_History_Converter_macOS.dmg`
     - ✅ `Apple_Music_History_Converter_Windows.msi` (or .exe)
     - ✅ `Apple_Music_History_Converter_Linux.AppImage`
     - ✅ `Apple_Music_History_Converter_Linux.deb` (or .rpm)

4. **Publish release:**
   - ⚠️ Uncheck "Set as a pre-release" (unless it's a beta)
   - ✅ Check "Create a discussion for this release" (optional)
   - Click **"Publish release"**

---

## 📋 Release Checklist

Use this checklist for each release:

### Pre-Release

- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] Changes committed to git
- [ ] Git tag created and pushed
- [ ] All changes merged to main branch

### Building

- [ ] macOS build completed (DMG created)
- [ ] macOS build tested on different Mac
- [ ] macOS signature verified
- [ ] macOS notarization confirmed
- [ ] Windows build completed (MSI/EXE created)
- [ ] Windows build tested on clean Windows
- [ ] Windows SmartScreen bypass tested
- [ ] Linux AppImage created
- [ ] Linux AppImage tested on 2-3 distros
- [ ] Linux system package created (optional)

### Release

- [ ] GitHub Release created
- [ ] Release notes customized from template
- [ ] All binaries uploaded
- [ ] Release published (not draft)
- [ ] Release announcement posted (if applicable)

### Post-Release

- [ ] Download and test each binary from GitHub
- [ ] Update documentation/wiki
- [ ] Close related GitHub issues
- [ ] Tweet/announce release (optional)

---

## 🔄 Update Process for Users

### macOS

Users can simply:
1. Download new DMG
2. Drag to Applications (overwrite old version)
3. Launch

### Windows

Users can either:
1. Uninstall old version
2. Install new MSI

Or:
1. Run new MSI directly (may upgrade in-place)

### Linux (AppImage)

Users can:
1. Download new AppImage
2. Delete old AppImage
3. Run new AppImage

### Linux (System Package)

Users can:
```bash
# Debian/Ubuntu
sudo dpkg -i new_version.deb

# Fedora
sudo rpm -U new_version.rpm
```

---

## 🚨 Troubleshooting

### Build Fails on macOS

**Problem**: Notarization fails

**Solutions:**
- Verify `.env` credentials are correct
- Check Apple Developer membership is active
- Ensure certificate hasn't expired
- Review notarization logs:
  ```bash
  xcrun notarytool history \
    --apple-id "nerveband@gmail.com" \
    --team-id "7HQVB2S4BX" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD"
  ```

### Build Fails on Windows

**Problem**: Missing dependencies

**Solutions:**
- Install Visual Studio Build Tools
- Install .NET Framework 3.5+
- Run `briefcase` with `--log` flag for details

### Build Fails on Linux

**Problem**: Missing GTK libraries

**Solutions:**
```bash
# Ubuntu/Debian
sudo apt install libgirepository1.0-dev libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev

# Fedora
sudo dnf install gobject-introspection-devel cairo-gobject-devel gtk3-devel
```

### Upload Fails on GitHub

**Problem**: File too large

**Solutions:**
- GitHub has 2GB file limit (should be fine)
- For very large files, use GitHub Large File Storage (LFS)
- Compress binaries if needed (not recommended for apps)

---

## 💡 Tips and Best Practices

### 1. Version Numbering

Use **Semantic Versioning** (SemVer):
- **Major** (1.0.0): Breaking changes
- **Minor** (1.1.0): New features, backward compatible
- **Patch** (1.0.1): Bug fixes

Example:
- `v1.0.0` - Initial release
- `v1.1.0` - Added Linux AppImage support
- `v1.1.1` - Fixed crash bug
- `v2.0.0` - Major UI rewrite (breaking changes)

### 2. Release Frequency

- **Bug fixes**: Release quickly (within days)
- **New features**: Release monthly or quarterly
- **Major versions**: Release when ready, test extensively

### 3. Beta Releases

For major changes, create beta releases:

```bash
git tag -a v1.4.0-beta.1 -m "Beta release for testing"
git push origin v1.4.0-beta.1
```

Mark as "pre-release" on GitHub.

### 4. Keep Build Artifacts

Archive `release_builds/` for each version:

```bash
# Create archive
tar -czf releases_archive/v1.4.0_builds.tar.gz release_builds/

# Or use zip
zip -r releases_archive/v1.4.0_builds.zip release_builds/
```

### 5. Automated Testing

Before release, run:

```bash
# Run your test suite
python -m pytest tests/

# Test imports
python -c "from apple_music_history_converter import main"

# Quick functionality test
./test_build.sh
```

---

## 📊 Build Time Estimates

Typical build times on modern hardware:

| Platform | Create | Build | Package | Total |
|----------|--------|-------|---------|-------|
| macOS | 2 min | 1 min | 5-10 min* | ~13 min |
| Windows | 3 min | 2 min | 2 min | ~7 min |
| Linux | 2 min | 1 min | 3 min | ~6 min |

*macOS packaging includes notarization which can take 5-10 minutes

**Total time for all platforms: ~30 minutes**

---

## 🎓 Resources

- **Briefcase Documentation**: https://briefcase.readthedocs.io
- **Toga Documentation**: https://toga.readthedocs.io
- **GitHub Releases Guide**: https://docs.github.com/en/repositories/releasing-projects-on-github
- **Apple Notarization Guide**: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution

---

## 📞 Getting Help

If you encounter issues:

1. Check this guide first
2. Review `BUILD_CHANGES_SUMMARY.md`
3. Check Briefcase documentation
4. Create an issue on the BeeWare GitHub

---

**Happy releasing!** 🚀
