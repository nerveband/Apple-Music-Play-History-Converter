# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Apple Music Play History Converter is a Python-based desktop application that converts Apple Music CSV files into Last.fm compatible format. The application features a modern tkinter GUI with two music search providers: MusicBrainz (offline database) and iTunes API (online).

## Key Commands

### Running the Application
```bash
# Recommended way - auto-handles dependencies and virtual environment
python run_app.py

# Direct execution (requires manual dependency installation)
python apple_music_play_history_converter.py
```

### Testing
```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --category core      # Core functionality tests
python run_tests.py --category ui        # UI and dialog tests
python run_tests.py --category import    # Import functionality tests
python run_tests.py --category platform  # Cross-platform compatibility tests

# Run specific test file
python run_tests.py --file test_app.py
```

### Building
```bash
# Complete build pipeline (create, build, package)
python build.py all

# Individual build steps
python build.py create    # Create app bundle
python build.py build     # Build the application
python build.py package   # Package for distribution

# Development and testing
python build.py dev       # Run in development mode
python build.py run       # Run the built application
python build.py clean     # Clean build artifacts
```

### Development Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Core Components
- **CSVProcessorApp** (`apple_music_play_history_converter.py`): Main GUI application with tkinter interface
- **MusicSearchService** (`music_search_service.py`): Routing layer between MusicBrainz and iTunes API
- **MusicBrainzManager** (`musicbrainz_manager.py`): Handles offline database operations (download, search, updates)
- **DatabaseDialogs** (`database_dialogs.py`): Setup wizards and configuration dialogs
- **ProgressDialog** (`progress_dialog.py`): Progress tracking for long operations

### Search Provider Architecture
The application uses a dual-provider system:
1. **MusicBrainz**: Offline database (~2GB) for fast searches (1-5ms)
2. **iTunes API**: Online fallback with rate limiting (20 requests/minute)

Search routing is handled by `MusicSearchService` which can automatically fallback between providers.

### Data Flow
1. CSV file parsing with automatic encoding detection
2. File type detection (Play Activity, Recently Played, Daily Tracks)
3. Artist/track lookup via configured search provider
4. Reverse-chronological timestamp calculation
5. Export to Last.fm compatible CSV format

### Threading Model
- Main UI thread handles GUI updates
- Background threads for file processing and API calls
- Thread-safe progress reporting via queue-based communication
- Pause/resume functionality for long operations

## File Processing

### CSV Format Support
- **Play Activity**: Standard Apple Music export format
- **Recently Played Tracks**: Alternative export format
- **Play History Daily Tracks**: Daily aggregated format

Auto-detection based on filename patterns and column structure.

### Encoding Handling
Supports multiple encodings with automatic detection:
- UTF-8 (with/without BOM)
- Latin-1
- Windows-1252

## Database Management

### MusicBrainz Integration
- Downloads canonical MusicBrainz data (.tar.zst format, ~2GB compressed)
- Uses DuckDB for fast CSV querying without database building
- Automatic latest version discovery from canonical data exports
- Manual import support for offline scenarios
- Supports both canonical and legacy database formats

### Settings Storage
- JSON-based settings in `~/.apple_music_converter/settings.json`
- Cross-platform path handling with proper user directory storage
- Persistent search provider preferences
- No read-only file system issues in packaged apps

## Testing Strategy

Tests are categorized by functionality:
- **Core tests**: Basic conversion and data processing
- **UI tests**: Interface components and dialogs
- **Import tests**: MusicBrainz and manual import workflows
- **Platform tests**: Cross-platform compatibility verification

Use `python run_tests.py --category <name>` to run specific test suites.

## Build System

Briefcase-based builds for Windows, macOS, and Linux:
- Modern Python packaging using BeeWare's Briefcase
- Native app bundles for each platform
- Automatic dependency management and resolution
- Built-in code signing and notarization support for macOS
- Clean separation of source code and build artifacts

### macOS Code Signing and Notarization

**Important**: The macOS build process includes full Apple Developer ID signing and notarization for distribution without security warnings.

#### Prerequisites
1. **Apple Developer Account**: Must be enrolled in Apple Developer Program
2. **Xcode**: Full Xcode installation (not just command line tools)
3. **Certificates**: Developer ID Application certificate must be installed

#### Apple Developer Setup Process
1. **Add Apple ID to Xcode**:
   - Open Xcode → Settings → Accounts
   - Click "+" → Add Apple ID (nerveband@gmail.com)
   - Sign in with Apple ID credentials

2. **Create Developer ID Certificate**:
   - In Accounts tab, select your Apple ID
   - Click "Manage Certificates..."
   - Click "+" → Select "Developer ID Application"
   - Certificate will be automatically created and installed

3. **Verify Certificate Installation**:
   ```bash
   security find-identity -v -p codesigning
   ```
   Should show: `Developer ID Application: Ashraf Ali (7HQVB2S4BX)`

#### Build and Signing Process
1. **Standard Build**: 
   ```bash
   briefcase create    # Create app structure
   briefcase build     # Build the application
   briefcase package   # Package with signing and notarization
   ```

2. **Automatic Signing**: Briefcase handles signing automatically based on pyproject.toml configuration
3. **Notarization**: Fully automated during `briefcase package` when credentials are configured

#### Critical Briefcase Configuration Details
- **Signing Identity**: Configured in pyproject.toml: `Developer ID Application: Ashraf Ali (7HQVB2S4BX)`
- **Team ID**: `7HQVB2S4BX`
- **Bundle ID**: `com.nerveband.apple-music-history-converter`
- **Entitlements**: Configured directly in pyproject.toml for hardened runtime
- **Build Location**: `build/apple-music-history-converter/macos/app/`
- **Package Command**: `briefcase package` handles all signing and distribution

#### Entitlements Configuration
Entitlements are now configured directly in `pyproject.toml` under the macOS section:
```toml
[tool.briefcase.app.apple-music-history-converter.macOS.entitlement]
"com.apple.security.cs.allow-unsigned-executable-memory" = true
"com.apple.security.cs.disable-library-validation" = true
"com.apple.security.automation.apple-events" = true
"com.apple.security.files.user-selected.read-write" = true
```

#### Briefcase Notarization Process

**Current Status (v1.3.1)**: Briefcase notarization is fully functional and automated. The app is properly signed and notarized without any manual steps required.

**Automatic Notarization Configuration**:
```toml
[tool.briefcase.app.apple-music-history-converter.macOS]
universal_build = true
signing_identity = "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
notarize = true
notarize_team_id = "7HQVB2S4BX"
notarize_apple_id = "nerveband@gmail.com"
```

**Resolved Issues (v1.3.1)**:
- ✅ Briefcase notarization now works automatically with proper credential setup
- ✅ All binaries are properly signed during the packaging process
- ✅ No manual intervention required for notarization

**Important**: Apple app-specific password and credentials are stored in `.env` file (git-ignored):
```bash
APPLE_ID=nerveband@gmail.com
APPLE_TEAM_ID=7HQVB2S4BX
APPLE_APP_SPECIFIC_PASSWORD=enfg-cbng-xxzz-nxmb
DEVELOPER_ID_APPLICATION="Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
```

For automatic notarization with Briefcase:
1. **Store credentials in keychain** (one-time setup):
   ```bash
   source .env
   xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
     --apple-id "$APPLE_ID" \
     --team-id "$APPLE_TEAM_ID" \
     --password "$APPLE_APP_SPECIFIC_PASSWORD"
   ```

2. **Build and notarize**:
   ```bash
   briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
   ```
   
   Briefcase automatically handles:
   - Signing all binaries and frameworks
   - Submitting for notarization
   - Waiting for approval
   - Stapling the notarization ticket
   - Creating the final DMG

#### Manual Notarization for Complex Briefcase Apps

For apps with many binary dependencies (like this project with numpy, pandas, duckdb), manual signing is required:

1. **Build with Briefcase**:
   ```bash
   python build.py create
   python build.py build
   ```

2. **Sign all binary files individually**:
   ```bash
   source .env
   find "build/apple-music-history-converter/macos/app/Apple Music History Converter.app" -name "*.so" -o -name "*.dylib" | while read file; do
     codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID_APPLICATION" "$file"
   done
   ```

3. **Re-sign the main app bundle**:
   ```bash
   codesign --force --options runtime --timestamp --entitlements "build/apple-music-history-converter/macos/app/Entitlements.plist" --sign "$DEVELOPER_ID_APPLICATION" "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"
   ```

4. **Create distribution package**:
   ```bash
   ditto -c -k --keepParent "build/apple-music-history-converter/macos/app/Apple Music History Converter.app" "Apple_Music_History_Converter_Signed.zip"
   ```

5. **Submit for notarization**:
   ```bash
   xcrun notarytool submit "Apple_Music_History_Converter_Signed.zip" \
     --apple-id "$APPLE_ID" \
     --password "$APPLE_APP_SPECIFIC_PASSWORD" \
     --team-id "$APPLE_TEAM_ID" \
     --wait
   ```

6. **Create final DMG**:
   ```bash
   hdiutil create -format UDZO -srcfolder "build/apple-music-history-converter/macos/app/Apple Music History Converter.app" "Apple_Music_History_Converter_Final.dmg"
   ```

#### App-Specific Password Setup
- Visit https://appleid.apple.com/account/manage
- Sign in with nerveband@gmail.com
- Generate app-specific password for notarization
- Use format: `xxxx-xxxx-xxxx-xxxx`

#### Critical Lessons Learned
1. **NEVER use standard `zip` for macOS app bundles** - it corrupts the bundle structure
2. **Always use `ditto -c -k` for creating archives** and `ditto -xk` for extraction
3. **Sign frameworks individually first** before signing the main bundle
4. **Include hardened runtime entitlements** for modern macOS compatibility
5. **Notarization is essential** for distribution without security warnings
6. **Staple the notarization ticket** before final distribution

#### Troubleshooting Common Issues
- **"App is damaged" error**: Usually caused by using `zip` instead of `ditto`
- **Signature verification failed**: Check that all frameworks are signed individually
- **Notarization rejected**: Verify entitlements and hardened runtime settings
- **Certificate not found**: Ensure Developer ID Application certificate is installed in Keychain

## Common Development Tasks

### Adding New CSV Format Support
1. Update format detection logic in `detect_file_type()` method
2. Add column mapping in `process_csv_data()` method
3. Test with sample files using `test_csv_query_simulation.py`

### Modifying Search Providers
1. Update `MusicSearchService` for routing logic
2. Implement provider-specific methods in respective manager classes
3. Update settings UI in `create_widgets()` method

### UI Layout Changes
1. Main layout is in `create_widgets()` method using grid system
2. Dialog layouts are in respective classes in `database_dialogs.py`
3. Use sv-ttk for modern styling consistency