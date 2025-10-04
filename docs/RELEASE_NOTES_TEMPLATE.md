# Release Notes Template

Copy and paste this template when creating a new GitHub Release.

---

## Apple Music History Converter v1.4.0

Built with Briefcase/Toga for native cross-platform experiences.

### 📦 Downloads

**macOS (Apple Silicon/Intel)** - Fully Signed & Notarized ✅
- Download: `Apple_Music_History_Converter_macOS.dmg`
- **No security warnings!** Just open and drag to Applications.

**Windows (10/11)** - Unsigned Build ⚠️
- Download: `Apple_Music_History_Converter_Windows.msi` or `.exe`
- **SmartScreen will appear** - this is normal for free, open-source apps
- How to install:
  1. Click "More info"
  2. Click "Run anyway"
  3. Click "Yes" on UAC prompt
- **The app is safe** - SmartScreen appears because we don't have a $300+/year code signing certificate

**Linux (All Distributions)** - Universal AppImage ✅
- Download: `Apple_Music_History_Converter_Linux.AppImage`
- Works on: Ubuntu, Fedora, Debian, Arch, Mint, openSUSE, and more
- Usage:
  ```bash
  chmod +x Apple_Music_History_Converter_Linux.AppImage
  ./Apple_Music_History_Converter_Linux.AppImage
  ```

**Linux (System Packages)** - Distribution-Specific
- Debian/Ubuntu: `Apple_Music_History_Converter_Linux.deb`
- Fedora/RHEL: `Apple_Music_History_Converter_Linux.rpm`
- Other: `Apple_Music_History_Converter_Linux.tar.gz`

---

### 🚀 What's New in v1.4.0

- ✨ New feature: [Describe your new features]
- 🐛 Bug fixes: [List bug fixes]
- 🔧 Improvements: [List improvements]
- 📚 Documentation: [Documentation updates]

---

### 💻 Installation Guide

#### macOS

1. Download `Apple_Music_History_Converter_macOS.dmg`
2. Double-click to open the DMG
3. Drag "Apple Music History Converter" to your Applications folder
4. Launch from Applications - **no warnings or prompts!**

**Why no warnings?** This app is:
- Signed with a Developer ID certificate
- Notarized by Apple
- Completely safe and verified

#### Windows

1. Download `Apple_Music_History_Converter_Windows.msi`
2. Run the installer
3. **When SmartScreen appears:**
   - Click "More info"
   - Click "Run anyway"
   - Click "Yes" on User Account Control
4. Complete the installation wizard

**Why SmartScreen?** Windows shows this warning for:
- Apps distributed outside the Microsoft Store
- Apps without expensive ($300-700/year) code signing certificates
- **This doesn't mean the app is unsafe!** The source code is public on GitHub.

#### Linux - AppImage (Recommended)

```bash
# Download and make executable
chmod +x Apple_Music_History_Converter_Linux.AppImage

# Run (no installation needed!)
./Apple_Music_History_Converter_Linux.AppImage
```

**Benefits:**
- Works on any modern Linux distribution
- No root/sudo required
- No dependency hell
- Self-contained and portable

**Troubleshooting:**
If it won't run, install FUSE:
```bash
# Ubuntu/Debian
sudo apt install fuse

# Fedora
sudo dnf install fuse
```

#### Linux - System Packages

**Debian/Ubuntu/Mint:**
```bash
sudo dpkg -i Apple_Music_History_Converter_Linux.deb
```

**Fedora/RHEL/CentOS:**
```bash
sudo rpm -i Apple_Music_History_Converter_Linux.rpm
```

**Other Distributions:**
```bash
tar -xzf Apple_Music_History_Converter_Linux.tar.gz
cd apple-music-history-converter
./apple-music-history-converter
```

---

### 📖 Usage Instructions

1. **Export your Apple Music data:**
   - From Apple Music app: File → Library → Export Library (XML format)
   - Or use Apple's Privacy & Data tool to export CSV files

2. **Run the converter:**
   - Launch the application
   - Select your CSV or XML file
   - Choose conversion options
   - Select output location
   - Click "Convert" to process your library

3. **Import to Last.fm:**
   - Use the generated CSV file with Last.fm scrobbling tools

---

### ✨ Features

- 📁 Support for multiple Apple Music export formats
- 🔍 Dual search providers:
  - **MusicBrainz** (offline database, ~2GB) - Fast, accurate
  - **iTunes API** (online) - Automatic fallback
- ⚡ Fast track matching with intelligent fallback
- 🎨 Modern, user-friendly interface with Toga
- 📊 Real-time progress tracking
- ⏸️ Pause/resume functionality for large files
- 🌍 Automatic encoding detection (international character support)
- 🔄 Detailed processing statistics and error reporting

---

### 📋 System Requirements

| Platform | Minimum Version | Recommended |
|----------|----------------|-------------|
| **macOS** | macOS 11 (Big Sur) | macOS 12+ |
| **Windows** | Windows 10 | Windows 11 |
| **Linux** | Ubuntu 20.04, Fedora 32 | Latest LTS |

**Additional Linux Requirements:**
- GTK 3.0 or later (usually pre-installed)
- FUSE (for AppImage) - `sudo apt install fuse`

---

### 🛠️ Troubleshooting

#### macOS Issues

**"App can't be opened"**
- Right-click the app → Open (first time only)
- Check System Settings → Privacy & Security for blocks

**"App is damaged"**
- This shouldn't happen! The app is properly signed and notarized.
- If it does, please report it as a bug.

#### Windows Issues

**SmartScreen blocks the app**
- Expected behavior for unsigned apps
- Click "More info" → "Run anyway"
- This is safe - all source code is publicly available

**Antivirus flags the app**
- False positive (common with newly built apps)
- Add exception in your antivirus software
- The app is open-source and safe

#### Linux Issues

**AppImage won't run**
- Make it executable: `chmod +x *.AppImage`
- Install FUSE: `sudo apt install fuse` (Ubuntu/Debian)
- Check for FUSE errors: `./app.AppImage --appimage-extract-and-run`

**Missing dependencies (system package)**
- Install GTK 3: `sudo apt install libgtk-3-0` (Ubuntu/Debian)
- Install GTK 3: `sudo dnf install gtk3` (Fedora)

---

### 🐛 Known Issues

- None currently reported for v1.4.0

Found a bug? [Report it here](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)

---

### 🙏 Acknowledgments

- Built with [Toga](https://beeware.org/project/toga/) and [Briefcase](https://beeware.org/project/briefcase/)
- MusicBrainz data from [MusicBrainz Foundation](https://musicbrainz.org/)
- Icons and design: [Your credits]

---

### 📄 Technical Details

**Code Signing Status:**
- ✅ **macOS**: Signed with Developer ID Application certificate
- ✅ **macOS**: Notarized by Apple (no GateKeeper warnings)
- ❌ **Windows**: Unsigned (to avoid $300-700/year certificate cost)
- N/A **Linux**: Code signing not applicable

**File Sizes:**
- macOS DMG: ~50 MB
- Windows MSI: ~40 MB
- Linux AppImage: ~80 MB
- Linux .deb/.rpm: ~10 MB

**Build Information:**
- Python: 3.12
- Toga: 0.4.0+
- Briefcase: Latest
- Build date: [Auto-populated by GitHub]

---

### 📞 Support

- 🐛 **Report bugs**: [Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
- 💬 **Discussions**: [Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)
- 📖 **Documentation**: [Wiki](https://github.com/nerveband/Apple-Music-Play-History-Converter/wiki)

---

### 📜 License

MIT License - See [LICENSE](LICENSE) file for details.

---

**Enjoy!** 🎵
