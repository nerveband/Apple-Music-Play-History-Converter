# Manual Build Instructions

## macOS (Current Platform)

```bash
# Clean previous builds
briefcase create macOS
briefcase build macOS

# Option 1: Ad-hoc signing (for testing)
briefcase package macOS --adhoc-sign

# Option 2: Full signing + notarization (for distribution)
briefcase package macOS --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Output: build/apple-music-history-converter/macos/app/Apple Music History Converter.app
# DMG: dist/Apple Music History Converter-1.3.1.dmg
```

## Windows (Requires Windows Machine or VM)

### Prerequisites
- Windows 10/11
- Python 3.12+ installed
- Visual Studio Build Tools (for dependencies)

### Build Steps
```cmd
# Install dependencies
pip install briefcase

# Build
briefcase create windows
briefcase build windows
briefcase package windows --adhoc-sign

# Output: dist\Apple Music History Converter-1.3.1.msi
```

### Windows VM Options
- **VirtualBox**: Free, download Windows 11 dev VM from Microsoft
- **Parallels**: Paid, better performance on Mac
- **VMware Fusion**: Free for personal use
- **Cloud**: AWS EC2 Windows instance (pay per use)

## Linux (Requires Linux Machine or VM)

### Prerequisites
- Ubuntu 22.04 LTS recommended (avoid 24.04 due to GTK issues)
- Python 3.12+
- GTK development libraries

### Build Steps
```bash
# Install system dependencies
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

# Install Briefcase
pip3 install briefcase

# Build (WARNING: AppImage is unreliable - consider Flatpak instead)
briefcase create linux appimage
briefcase build linux appimage
briefcase package linux appimage

# Output: dist/Apple_Music_History_Converter-1.3.1-x86_64.AppImage
```

### Linux VM Options
- **VirtualBox**: Free, install Ubuntu 22.04 LTS
- **Multipass**: Free, lightweight Ubuntu VMs on Mac
- **Docker**: Not recommended for GUI apps
- **Cloud**: Oracle Cloud Free Tier (Ubuntu VM forever free)

## Recommended Multi-Platform Build Workflow

### Option 1: Use VMs
1. **macOS**: Build natively on your Mac
2. **Windows**: VirtualBox Windows 11 dev VM (free from Microsoft)
3. **Linux**: Multipass Ubuntu 22.04 VM (free, lightweight)

### Option 2: Use Cloud Services
1. **macOS**: Build natively
2. **Windows**: AWS EC2 Windows (pay per use, ~$0.50/hour)
3. **Linux**: Oracle Cloud Free Tier Ubuntu VM (free forever)

### Option 3: Alternative Formats (Easier)
Instead of native installers, consider:
- **Python Package**: Distribute via PyPI (`pip install apple-music-converter`)
- **Source Distribution**: Users run `python -m briefcase dev`
- **Web App**: Convert to web service (most accessible)

## Quick Test Builds

### macOS (Current Platform)
```bash
briefcase dev
```
Runs app directly without building package.

### Cross-Platform Testing
Use Docker for Linux builds (limited GUI support):
```bash
docker run -it ubuntu:22.04 bash
# Install dependencies and build inside container
```
