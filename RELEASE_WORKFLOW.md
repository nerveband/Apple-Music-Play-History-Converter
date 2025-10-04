# Release Workflow

Complete step-by-step guide for building and releasing a new version across all platforms.

## Prerequisites

- **macOS**: Your Mac (native build)
- **Windows**: UTM VM with Windows 11
- **Linux**: UTM VM with Ubuntu 22.04 LTS
- Git configured on all VMs
- Python 3.12+ installed on all platforms

---

## Step 1: Prepare for Release

### On macOS (your main machine):

```bash
# 1. Update version number in pyproject.toml
# Edit the version field: version = "1.3.2" (or whatever new version)

# 2. Update CHANGELOG.md with new features/fixes

# 3. Commit changes
git add .
git commit -m "chore: bump version to 1.3.2"
git push origin main

# 4. Create and push version tag
git tag v1.3.2
git push origin v1.3.2
```

---

## Step 2: Build on macOS

### On macOS (your main machine):

```bash
# Navigate to project
cd ~/path/to/Apple-Music-Play-History-Converter

# Pull latest code
git pull origin main

# Clean previous builds
rm -rf build/ dist/

# Build macOS app
briefcase create macOS
briefcase build macOS

# Package with full signing and notarization (for public distribution)
briefcase package macOS --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# The DMG will be in: dist/Apple Music History Converter-1.3.2.dmg
# Verify it's signed and notarized:
spctl -a -t exec -vv "dist/Apple Music History Converter-1.3.2.dmg"
# Should show: "accepted, source=Notarized Developer ID"

# Copy DMG to shared folder for later
cp "dist/Apple Music History Converter-1.3.2.dmg" ~/Desktop/releases/
```

---

## Step 3: Build on Windows

### On Windows 11 UTM VM:

1. **Start Windows VM in UTM**

2. **Clone repository** (first time only):
   ```cmd
   git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
   cd Apple-Music-Play-History-Converter
   ```

3. **Pull latest code**:
   ```cmd
   git pull origin main
   ```

4. **Install Python 3.12+** (first time only):
   - Download from https://www.python.org/downloads/windows/
   - Check "Add Python to PATH" during installation

5. **Install Briefcase** (first time only):
   ```cmd
   pip install briefcase
   ```

6. **Build Windows installer**:
   ```cmd
   # Clean previous builds
   rmdir /s /q build dist

   # Build
   briefcase create windows
   briefcase build windows
   briefcase package windows --adhoc-sign

   # MSI will be in: dist\Apple Music History Converter-1.3.2.msi
   ```

7. **Copy MSI to shared folder**:
   - Copy `dist\Apple Music History Converter-1.3.2.msi` to a shared folder between Mac and VM
   - Or use UTM's file sharing feature to access Mac folders

---

## Step 4: Build on Linux

### On Ubuntu 22.04 UTM VM:

1. **Start Ubuntu VM in UTM**

2. **Clone repository** (first time only):
   ```bash
   git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
   cd Apple-Music-Play-History-Converter
   ```

3. **Pull latest code**:
   ```bash
   git pull origin main
   ```

4. **Install dependencies** (first time only):
   ```bash
   sudo apt-get update
   sudo apt-get install -y \
     python3 python3-pip \
     libgirepository1.0-dev \
     libcairo2-dev \
     libpango1.0-dev \
     libgdk-pixbuf-2.0-dev \
     libffi-dev \
     shared-mime-info \
     gobject-introspection \
     libgtk-3-dev
   ```

5. **Install Briefcase** (first time only):
   ```bash
   pip3 install briefcase
   ```

6. **Build Linux AppImage**:
   ```bash
   # Clean previous builds
   rm -rf build/ dist/

   # Build
   briefcase create linux appimage
   briefcase build linux appimage
   briefcase package linux appimage

   # AppImage will be in: dist/Apple_Music_History_Converter-1.3.2-x86_64.AppImage
   ```

7. **Copy AppImage to shared folder**:
   - Copy to shared folder accessible from macOS
   - Or use UTM file sharing

---

## Step 5: Create GitHub Release

### On macOS (your main machine):

```bash
# Navigate to releases folder with all 3 builds
cd ~/Desktop/releases/

# Verify you have all 3 files:
# - Apple Music History Converter-1.3.2.dmg (macOS)
# - Apple Music History Converter-1.3.2.msi (Windows)
# - Apple_Music_History_Converter-1.3.2-x86_64.AppImage (Linux)

# Create GitHub release using gh CLI
gh release create v1.3.2 \
  --title "v1.3.2 - [Brief Description]" \
  --notes "## What's New

- Feature 1
- Feature 2
- Bug fix 1

## Downloads

- **macOS**: Apple Music History Converter-1.3.2.dmg (signed & notarized)
- **Windows**: Apple Music History Converter-1.3.2.msi (unsigned - Windows will show SmartScreen warning)
- **Linux**: Apple_Music_History_Converter-1.3.2-x86_64.AppImage

## Installation

### macOS
1. Download DMG
2. Open DMG
3. Drag app to Applications folder

### Windows
1. Download MSI
2. Double-click to install
3. Click 'More info' → 'Run anyway' on SmartScreen warning (expected for unsigned apps)

### Linux
1. Download AppImage
2. Make executable: \`chmod +x Apple_Music_History_Converter-1.3.2-x86_64.AppImage\`
3. Run: \`./Apple_Music_History_Converter-1.3.2-x86_64.AppImage\`
" \
  "Apple Music History Converter-1.3.2.dmg" \
  "Apple Music History Converter-1.3.2.msi" \
  "Apple_Music_History_Converter-1.3.2-x86_64.AppImage"
```

---

## Step 6: Verify Release

1. **Check GitHub Release page**:
   ```bash
   # Open in browser
   open https://github.com/nerveband/Apple-Music-Play-History-Converter/releases
   ```

2. **Verify all 3 artifacts are uploaded**

3. **Test download links work**

4. **Share release announcement**:
   - Update README.md with latest version
   - Post on social media/forums if applicable

---

## Quick Reference: UTM Setup (One-Time)

### Windows 11 VM Setup:
1. Download Windows 11 ARM ISO from Microsoft
2. Create VM in UTM:
   - Architecture: ARM64
   - RAM: 4-8 GB
   - Storage: 40+ GB
3. Install Windows 11
4. Install Python 3.12+
5. Install Git for Windows
6. Enable file sharing with macOS

### Ubuntu 22.04 VM Setup:
1. Download Ubuntu 22.04 ARM ISO
2. Create VM in UTM:
   - Architecture: ARM64
   - RAM: 4 GB
   - Storage: 30+ GB
3. Install Ubuntu 22.04
4. Install dependencies (see Step 4)
5. Enable file sharing with macOS

### File Sharing Between VMs and macOS:
- **UTM**: Use built-in folder sharing feature
- **Alternative**: Use network share or USB drive passthrough
- **Quick method**: Use `scp` to copy files over network

---

## Troubleshooting

### macOS Build Issues:
- **Signature fails**: Verify certificate with `security find-identity -v -p codesigning`
- **Notarization fails**: Check App Store Connect credentials

### Windows Build Issues:
- **Python not found**: Add Python to PATH
- **Build fails**: Install Visual Studio Build Tools

### Linux Build Issues:
- **GTK errors**: Verify all dependencies installed
- **AppImage fails**: Ubuntu 24.04 has issues - use 22.04

### GitHub Release Issues:
- **gh not authenticated**: Run `gh auth login`
- **Upload fails**: Check file paths are correct

---

## Version Bump Checklist

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Commit and push to main
- [ ] Create and push git tag
- [ ] Build on macOS
- [ ] Build on Windows (UTM VM)
- [ ] Build on Linux (UTM VM)
- [ ] Copy all builds to release folder
- [ ] Create GitHub release with all 3 artifacts
- [ ] Verify downloads work
- [ ] Update README if needed
