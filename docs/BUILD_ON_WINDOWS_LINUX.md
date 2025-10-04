# Building for Windows and Linux

This guide explains how to build the Apple Music History Converter on Windows and Linux platforms.

## ⚠️ Important: Cross-Platform Building Limitations

Briefcase **requires native platform builds**:
- **Windows builds**: Must be built on Windows
- **Linux builds**: Must be built on Linux (or macOS with Docker)
- **macOS builds**: Must be built on macOS ✅ (already completed)

You **cannot** build Windows apps on macOS or Linux, and vice versa.

---

## Windows Build Instructions

### Prerequisites

1. **Windows 10/11** (64-bit)
2. **Python 3.12+** - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
3. **Git** - Download from [git-scm.com](https://git-scm.com/download/win)

### Build Steps

1. **Open PowerShell or Command Prompt**

2. **Clone the repository:**
   ```powershell
   git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
   cd Apple-Music-Play-History-Converter
   ```

3. **Install Briefcase:**
   ```powershell
   pip install briefcase
   ```

4. **Create the app structure:**
   ```powershell
   briefcase create windows
   ```

5. **Build the app:**
   ```powershell
   briefcase build windows
   ```

6. **Package the installer:**
   ```powershell
   briefcase package windows --adhoc-sign
   ```

7. **Find the installer:**
   - Location: `dist\Apple Music History Converter-1.3.1.msi`
   - Copy to: `release_builds\Apple_Music_History_Converter_Windows.msi`

### Expected Output

- **File**: `Apple_Music_History_Converter_Windows.msi`
- **Size**: ~80-100 MB
- **Format**: Windows Installer (MSI)

### ⚠️ SmartScreen Warning

**Expected Behavior**: Windows SmartScreen will show "Windows protected your PC" warning because the app is not signed with a code signing certificate ($250-700/year).

**User Instructions** (include in GitHub release):
1. Click "More info"
2. Click "Run anyway"
3. This is normal for unsigned apps and does not indicate malware

**To avoid this**: Purchase a Windows Code Signing Certificate from DigiCert or similar ($250-700/year).

---

## Linux Build Instructions

### Prerequisites

1. **Ubuntu 20.04+ / Debian / Fedora / or similar**
2. **Python 3.12+**
3. **Git**
4. **AppImage dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip git fuse libfuse2

   # Fedora
   sudo dnf install python3 python3-pip git fuse fuse-libs
   ```

### Build Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
   cd Apple-Music-Play-History-Converter
   ```

2. **Install Briefcase:**
   ```bash
   pip install briefcase
   ```

3. **Create the app structure:**
   ```bash
   briefcase create linux appimage
   ```

4. **Build the app:**
   ```bash
   briefcase build linux appimage
   ```

5. **Package the AppImage:**
   ```bash
   briefcase package linux appimage
   ```

6. **Find the AppImage:**
   - Location: `dist/Apple_Music_History_Converter-1.3.1-x86_64.AppImage`
   - Copy to: `release_builds/Apple_Music_History_Converter_Linux.AppImage`

7. **Make it executable:**
   ```bash
   chmod +x release_builds/Apple_Music_History_Converter_Linux.AppImage
   ```

### Expected Output

- **File**: `Apple_Music_History_Converter_Linux.AppImage`
- **Size**: ~100-120 MB
- **Format**: AppImage (portable, works on all distros)

### Using the AppImage

**User Instructions** (include in GitHub release):
1. Download the AppImage
2. Make it executable: `chmod +x Apple_Music_History_Converter_Linux.AppImage`
3. Run it: `./Apple_Music_History_Converter_Linux.AppImage`
4. Optional: Integrate with system using [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher)

---

## Alternative: Building Linux on macOS with Docker

If you have Docker Desktop installed and running on macOS:

```bash
# Start Docker Desktop first
open -a Docker

# Wait for Docker to start, then:
briefcase create linux appimage
briefcase build linux appimage
briefcase package linux appimage
```

This will use Docker containers to build Linux apps on macOS.

---

## Automated Build Script

You can use the provided build script on each platform:

```bash
# On Windows (PowerShell/CMD)
./build_all_platforms.sh windows

# On Linux
./build_all_platforms.sh linux

# On macOS (already completed)
./build_all_platforms.sh macos
```

The script will:
1. Clean previous builds
2. Create, build, and package the app
3. Copy the final artifact to `release_builds/`
4. Show file size and location

---

## Uploading to GitHub Release

Once you have all three builds:

1. **Collect all files in `release_builds/`:**
   - `Apple_Music_History_Converter_macOS.dmg` (113 MB)
   - `Apple_Music_History_Converter_Windows.msi` (~80-100 MB)
   - `Apple_Music_History_Converter_Linux.AppImage` (~100-120 MB)

2. **Create a new GitHub Release:**
   - Go to: https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/new
   - Create tag: `v1.3.1`
   - Title: `v1.3.1 - [Release Name]`
   - Copy release notes from `docs/RELEASE_NOTES_TEMPLATE.md`
   - Upload all 3 files from `release_builds/`
   - Publish!

---

## Troubleshooting

### Windows Issues

**"Python not found"**
- Reinstall Python with "Add to PATH" checked
- Or add manually: System Properties → Environment Variables → Path

**"Briefcase not found"**
- Use full path: `python -m briefcase create windows`

**MSI build fails**
- Ensure WiX Toolset is installed (Briefcase will prompt if needed)

### Linux Issues

**"AppImage build failed"**
- Install FUSE: `sudo apt install fuse libfuse2`
- Ensure you're running on actual Linux (not WSL)

**Permission denied**
- Make the AppImage executable: `chmod +x *.AppImage`

**"Cannot open shared library"**
- AppImage requires FUSE to be installed and enabled

### Docker Issues (macOS)

**"Cannot connect to Docker daemon"**
- Start Docker Desktop: `open -a Docker`
- Wait 30 seconds for Docker to fully start

**Docker build slow**
- First build downloads Linux base images (~500MB)
- Subsequent builds are much faster

---

## Build Time Estimates

- **Windows**: 15-20 minutes (first build)
- **Linux**: 20-25 minutes (first build)
- **Subsequent builds**: 5-10 minutes

---

## Next Steps

After building on Windows and Linux:
1. Test each build on the respective platform
2. Copy all files from `release_builds/` to a single location
3. Follow the release guide in `docs/MANUAL_RELEASE_GUIDE.md`
