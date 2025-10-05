# Building from Source

Complete guide for building Apple Music Play History Converter for distribution.

## Build Strategy (v2.0.0)

The project uses a tiered build approach:

- **macOS**: Build locally (requires Mac, fast signing/notarization)
- **Windows**: GitHub Actions CI/CD (automated portable ZIP builds)
- **Linux**: Source code only (users compile from source)

This strategy balances ease of use, automation, and maintenance overhead.

## Prerequisites

### All Platforms

- Python 3.8 or higher
- pip 21.0+
- git
- 8GB+ RAM
- 5GB+ free disk space

### Platform-Specific

**macOS**:
- Xcode Command Line Tools: `xcode-select --install`
- For signing: Apple Developer ID Application certificate

**Windows**:
- Visual Studio Build Tools (for local builds)
- Windows SDK
- **Note**: GitHub Actions handles Windows builds automatically

**Linux**:
```bash
# Ubuntu/Debian
sudo apt install build-essential python3-dev libgtk-3-dev

# Fedora
sudo dnf install gcc python3-devel gtk3-devel
```
**Note**: No Linux binaries are distributed - users install from source

## Quick Build

```bash
# Clone repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# Install Briefcase
pip install briefcase

# Create app structure
briefcase create

# Build application
briefcase build

# Package for distribution
briefcase package
```

## Development Workflow

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install briefcase

# Run in development mode
briefcase dev
```

### Development Mode Benefits

- Hot reload on file changes
- Direct console output
- Faster iteration
- No packaging overhead

### Testing Changes

```bash
# Run development version
briefcase dev

# Run built version
briefcase run

# Package and test distribution
briefcase package
```

## Platform-Specific Builds

### macOS

#### Standard Build

```bash
briefcase create macOS
briefcase build macOS
briefcase package macOS
```

Output: `build/apple-music-history-converter/macos/app/*.dmg`

#### Signed and Notarized Build

**Prerequisites**:
1. Apple Developer Program membership ($99/year)
2. Developer ID Application certificate installed
3. App-specific password for notarization

**Setup** (one-time):
```bash
# Store notarization credentials
source .env  # Contains APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD
xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"
```

**Build with Signing**:
```bash
# Automatic signing and notarization
briefcase package macOS --identity "Developer ID Application: Your Name (TEAMID)"

# Manual signing (if needed)
codesign --force --options runtime --timestamp \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"
```

**Verify Signature**:
```bash
codesign --verify --deep --strict "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"
spctl -a -t exec -vv "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"
```

### Windows

#### Local Build

```bash
briefcase create windows
briefcase build windows
briefcase package windows app -p zip
```

Output: `dist/*.zip` (portable ZIP format)

#### GitHub Actions (Recommended)

Windows builds are automated via GitHub Actions:

1. **Trigger**: Push to `main` or `feature/ui-rewrite` branches, or manual trigger
2. **Process**: Clean → Create → Build → Package ZIP
3. **Output**: Portable ZIP artifact (90-day retention)
4. **Download**: From GitHub Actions run artifacts

**Workflow File**: `.github/workflows/build-windows.yml`

**Manual Trigger**:
1. Go to Actions tab on GitHub
2. Select "Build Windows App" workflow
3. Click "Run workflow"
4. Download artifact when complete

**Code Signing** (optional):
Requires Windows code signing certificate. Configure in `pyproject.toml`:
```toml
[tool.briefcase.app.apple-music-history-converter.windows]
signing_identity = "Your Certificate Name"
```

### Linux

**No binaries are built or distributed for Linux.**

Linux users are expected to install from source:

```bash
# Clone repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# Install dependencies
pip install -r requirements.txt

# Run application
python run_toga_app.py
```

**Rationale**: Linux users are typically tech-savvy enough to compile from source, and maintaining Linux builds across multiple distributions adds significant complexity.

**For package maintainers**: If you want to create distribution-specific packages (.deb, .rpm, etc.), you can use Briefcase locally:

```bash
# Create .deb package (Ubuntu/Debian)
briefcase create linux
briefcase build linux
briefcase package linux --package-format deb

# Create .rpm package (Fedora/RHEL)
briefcase package linux --package-format rpm

# Create AppImage (universal)
briefcase package linux --package-format appimage
```

## Build Configuration

### pyproject.toml

Key configuration sections:

```toml
[project]
version = "2.0.0"  # Update for releases

[tool.briefcase.app.apple-music-history-converter]
formal_name = "Apple Music History Converter"
bundle = "com.nerveband"

[tool.briefcase.app.apple-music-history-converter.macOS]
universal_build = true  # Apple Silicon + Intel
signing_identity = "Developer ID Application: Name (TEAMID)"
notarize = true
```

### Version Updates

Update version in **three** places for each release:

1. **pyproject.toml**: `[project] version = "X.Y.Z"`
2. **pyproject.toml**: `[tool.briefcase] version = "X.Y.Z"`
3. **src/apple_music_history_converter/__init__.py**: `__version__ = "X.Y.Z"`

All three must match for consistency across the application.

## Build Troubleshooting

### Common Issues

**"Module not found" errors**:
```bash
# Clean build and recreate
briefcase build --clean
briefcase create
briefcase build
```

**Slow macOS builds**:
- Disable universal builds: Set `universal_build = false` in `pyproject.toml`
- Use `--no-universal` flag: `briefcase build macOS --no-universal`

**Notarization fails**:
```bash
# Check notarization logs
xcrun notarytool log <submission-id> --keychain-profile "briefcase-macOS-TEAMID"

# Common fixes:
# 1. Verify all .so files are signed
# 2. Check entitlements.plist is valid
# 3. Ensure hardened runtime is enabled
```

**Windows MSI errors**:
- Requires WiX Toolset installed
- Run Visual Studio Build Tools installer
- Verify PATH includes WiX binaries

### Clean Build

```bash
# Remove all build artifacts
briefcase build --clean

# Or manually delete
rm -rf build/

# Recreate from scratch
briefcase create
briefcase build
briefcase package
```

## CI/CD Integration

### GitHub Actions

The project uses GitHub Actions for automated Windows builds.

**Active Workflow**: `.github/workflows/build-windows.yml`

**Triggers**:
- Push to `main` branch
- Push to `feature/ui-rewrite` branch
- Pull requests to `main`
- Manual workflow dispatch

**Build Process**:
1. Clean previous builds (removes build/ and dist/)
2. Create app structure with Briefcase
3. Build Windows application
4. Package as portable ZIP
5. Upload artifact (90-day retention)

**Accessing Builds**:
1. Go to repository → Actions tab
2. Select completed workflow run
3. Download artifact from "Artifacts" section

**macOS Builds**: Not automated (requires local Mac with signing certificates)

**Linux Builds**: Not needed (users install from source)

## Testing Built Applications

### Automated Testing

```bash
# Run test suite against built app
python -m pytest tests/

# Briefcase test command
briefcase test
```

### Manual Testing Checklist

- [ ] Application launches without errors
- [ ] CSV file selection works
- [ ] Preview table displays correctly
- [ ] MusicBrainz database download works
- [ ] iTunes search functions properly
- [ ] Progress updates show live
- [ ] Save CSV generates valid output
- [ ] Settings persist across restarts
- [ ] Dark mode (if applicable) works

## Distribution

### Creating Release

1. Update version numbers in `pyproject.toml`
2. Update CHANGELOG.md
3. Build for all platforms
4. Test each platform build
5. Create GitHub release
6. Upload platform binaries
7. Update documentation

### File Naming Convention

- macOS: `Apple_Music_History_Converter_v2.0.0.dmg`
- Windows: `Apple_Music_History_Converter_Windows.zip` (from GitHub Actions)
- Linux: No binaries distributed (source only)

## Next Steps

- [Development Guide](Development) - Code architecture and contribution guidelines
- [User Guide](User-Guide) - Test built app functionality
- [Troubleshooting](Troubleshooting) - Debug build issues
