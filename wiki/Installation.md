# Installation Guide

This guide covers installing Apple Music Play History Converter on Windows, macOS, and Linux.

## Option 1: Pre-built Binaries (Recommended)

**No Python installation required!** These are standalone applications that include everything you need.

### macOS

**Download**: [Apple Music History Converter.dmg](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest)

1. Download the DMG file from the releases page
2. Open the DMG file
3. Drag "Apple Music History Converter.app" to your Applications folder
4. Launch from Applications - **no security warnings needed** (app is fully notarized)

**System Requirements**:
- macOS 10.13 (High Sierra) or later
- Apple Silicon or Intel processor
- 8GB RAM recommended for MusicBrainz mode

### Windows

**Download**: [Apple_Music_History_Converter_Windows.zip](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest)

1. Download the ZIP file from the releases page
2. Extract the ZIP to a folder (e.g., `C:\Program Files\Apple Music Converter`)
3. Run `Apple Music History Converter.exe`

**If Windows Defender blocks the app**:
1. Click "More info"
2. Click "Run anyway"

**System Requirements**:
- Windows 10 or later
- 8GB RAM recommended for MusicBrainz mode

### Linux

**No pre-built binaries available.** Linux users should install from source:

```bash
# Clone repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# Install dependencies
pip install -r requirements.txt

# Run application
python run_toga_app.py
```

**System Requirements**:
- Modern Linux distribution (Ubuntu 20.04+, Fedora 35+, etc.)
- Python 3.8+
- GTK 3.0+ (usually pre-installed)
- 8GB RAM recommended for MusicBrainz mode

See [Option 2: Run from Source](#option-2-run-from-source) below for detailed instructions.

## Option 2: Run from Source

For developers or users who want to run the latest development version.

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- git (optional, for cloning)

### Installation Steps

1. **Clone or download the repository**:
```bash
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv

# Activate on macOS/Linux:
source venv/bin/activate

# Activate on Windows:
venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the application**:
```bash
python run_toga_app.py
```

### Troubleshooting Source Install

**ImportError: No module named 'toga'**
```bash
pip install toga>=0.4.0
```

**DuckDB installation fails**
```bash
# Install build tools first
# macOS:
xcode-select --install

# Ubuntu/Debian:
sudo apt install build-essential python3-dev

# Then retry:
pip install duckdb
```

**GTK not found (Linux)**
```bash
# Ubuntu/Debian:
sudo apt install libgtk-3-dev libgirepository1.0-dev

# Fedora:
sudo dnf install gtk3-devel gobject-introspection-devel
```

## Verifying Installation

After installation, launch the application and verify:

1. The window opens without errors
2. You can select a CSV file
3. The search provider options appear
4. Settings can be accessed

If you encounter issues, see the [Troubleshooting](Troubleshooting) page.

## Next Steps

- [User Guide](User-Guide) - Learn how to use the application
- [MusicBrainz Database Setup](MusicBrainz-Database) - Setup offline search (recommended for large files)
