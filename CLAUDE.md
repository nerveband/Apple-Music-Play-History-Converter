# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Apple Music Play History Converter is a Python-based desktop application that converts Apple Music CSV files into Last.fm compatible format. The application is undergoing a migration from tkinter to Toga/Briefcase for better cross-platform support, with dual music search providers: MusicBrainz (offline database, ~2GB) and iTunes API (online).

## Key Commands

### Running the Application
```bash
# Run the Toga-based application (current development)
python run_toga_app.py

# Run using Briefcase development mode
briefcase dev

# Run built application
briefcase run

# Debug scripts for specific features
python debug_music_search.py  # Test music search functionality
python debug_csv.py            # Test CSV processing
python debug_full_flow.py      # Test complete workflow
```

### Testing
```bash
# Run test suite (tests currently being migrated to Toga)
python run_tests.py                     # Run all tests
python run_tests.py --category core     # Run core tests
python run_tests.py --category ui       # Run UI tests
python run_tests.py --category import   # Run import tests
python run_tests.py --category platform # Run platform tests
python run_tests.py --file test_name    # Run specific test file

# Note: Tests in tests/ folder are tkinter-based and will need updating for Toga
```

### Building
```bash
# Briefcase build commands
briefcase create          # Create application scaffold
briefcase build           # Build the application
briefcase package         # Package for distribution (creates DMG on macOS)
briefcase package --adhoc-sign  # Package with ad-hoc signing for testing

# Build helper script (wrapper around Briefcase commands)
python build.py create    # Run briefcase create
python build.py build     # Run briefcase build
python build.py package   # Run briefcase package
python build.py clean     # Clean build artifacts
python build.py all       # Run full build pipeline
```

### Development Dependencies
```bash
pip install -r requirements.txt

# For Briefcase development
pip install briefcase

# Core dependencies for Toga application
pip install toga pandas requests darkdetect
```

## Project Migration Status

### UI Framework Migration: tkinter → Toga/Briefcase
This project is currently undergoing a migration from tkinter to Toga/Briefcase for better cross-platform support and modern packaging. 

**Current Status:**
- ✅ Main application entry point converted to Toga (`app.py`, `run_toga_app.py`)
- ✅ Legacy tkinter code moved to `_history/` folder
- ✅ Briefcase configuration in `pyproject.toml`
- ⚠️ **Dialogs and UI components need Toga conversion** (`database_dialogs.py`, `progress_dialog.py`)
- ⚠️ **Testing framework needs to be established** for Toga components
- ⚠️ **Main converter logic needs Toga GUI integration**

**Legacy Code Location:**
All tkinter-related code has been moved to `_history/` folder:
- `_history/apple_music_play_history_converter_tkinter_old.py` - Original tkinter application
- `_history/tests/` - Original tkinter test suite
- `_history/run_app.py` - Original tkinter runner

## Architecture

### Core Components (src/apple_music_history_converter/)
- **App** (`app.py`): Briefcase entry point that launches the Toga UI
- **AppleMusicConverterApp** (`apple_music_play_history_converter.py`): Main Toga application
- **MusicSearchServiceV2** (`music_search_service_v2.py`): Routes lookups between MusicBrainz and iTunes
- **MusicBrainzManagerV2** (`musicbrainz_manager_v2.py`): Maintains the optimized DuckDB and search indices
- **OptimizationModal** (`optimization_modal.py`): Async helpers for the MusicBrainz optimization workflow
- **DatabaseDialogs / ProgressDialog** (`database_dialogs.py`, `progress_dialog.py`): Legacy tkinter dialogs pending Toga parity

### Search Provider Architecture
The application uses a dual-provider system:
1. **MusicBrainz**: Offline database (~2GB) for fast searches (1-5ms)
2. **iTunes API**: Online fallback with rate limiting (20 requests/minute)

Search routing is handled by `MusicSearchServiceV2`, which automatically falls back to iTunes when MusicBrainz misses or is unavailable.

### Data Flow
1. CSV file parsing with automatic encoding detection
2. File type detection (Play Activity, Recently Played, Daily Tracks)
3. Artist/track lookup via configured search provider
4. Reverse-chronological timestamp calculation
5. Export to Last.fm compatible CSV format

### Threading Model (Toga/Briefcase)
- Main UI thread handles Toga GUI updates
- Background threads for file processing and API calls
- Thread-safe progress reporting via queue-based communication
- Pause/resume functionality for long operations
- Toga async/await patterns for non-blocking operations

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

**Note**: Test suite is currently tkinter-based and located in `tests/` folder. These tests will need updating for Toga compatibility.

Test categories:
- **Core tests**: Basic conversion and data processing (`test_app.py`, `test_app_workflow.py`, `test_full_integration.py`)
- **UI tests**: Interface components and dialogs (`test_ui_layout.py`, `test_dialog_crash.py`)
- **Import tests**: MusicBrainz and manual import workflows (`test_import_function.py`, `test_manual_import.py`)
- **Platform tests**: Cross-platform compatibility (`test_cross_platform.py`)
- **Database tests**: Database operations (`test_database_debug.py`, `test_musicbrainz_build.py`)

Use `python run_tests.py --category <name>` to run specific test suites.

## Build System

Briefcase-based builds for Windows, macOS, and Linux:
- Modern Python packaging using BeeWare's Briefcase
- Native app bundles for each platform
- Automatic dependency management and resolution
- Built-in code signing and notarization support for macOS
- Clean separation of source code and build artifacts

### Critical tkinter Fix for macOS Builds

**IMPORTANT**: Briefcase does not include tkinter by default in macOS builds, causing `ModuleNotFoundError: No module named 'tkinter'`. This must be manually fixed after building:

#### Required Steps After `briefcase build`:
1. **Copy tkinter module** from system Python:
   ```bash
   cp -r /Users/nerveband/.pyenv/versions/3.12.4/lib/python3.12/tkinter "build/apple-music-history-converter/macos/app/Apple Music History Converter.app/Contents/Frameworks/Python.framework/Versions/3.12/lib/python3.12/"
   ```

2. **Copy tkinter dynamic library**:
   ```bash
   cp /Users/nerveband/.pyenv/versions/3.12.4/lib/python3.12/lib-dynload/_tkinter.cpython-312-darwin.so "build/apple-music-history-converter/macos/app/Apple Music History Converter.app/Contents/Frameworks/Python.framework/Versions/3.12/lib/python3.12/lib-dynload/"
   ```

3. **Find system Python tkinter location** (if path differs):
   ```bash
   python -c "import tkinter; print(tkinter.__file__)"
   ```

#### Complete Build Process:
```bash
# Standard Briefcase build
python build.py clean
python build.py create  
python build.py build

# Manual tkinter fix (REQUIRED)
SYSTEM_PYTHON_PATH=$(python -c "import tkinter; print(tkinter.__file__.replace('/__init__.py', ''))")
SYSTEM_DYNLOAD_PATH=$(python -c "import sysconfig; print(sysconfig.get_path('stdlib'))")/../lib-dynload
APP_PYTHON_PATH="build/apple-music-history-converter/macos/app/Apple Music History Converter.app/Contents/Frameworks/Python.framework/Versions/3.12/lib/python3.12"

cp -r "$SYSTEM_PYTHON_PATH" "$APP_PYTHON_PATH/"
cp "$SYSTEM_DYNLOAD_PATH/_tkinter.cpython-312-darwin.so" "$APP_PYTHON_PATH/lib-dynload/"

# Sign and package
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" --no-notarize

# Create distribution zip
cd "build/apple-music-history-converter/macos/app/"
ditto -c -k --keepParent "Apple Music History Converter.app" "Apple_Music_History_Converter_1.3.1.zip"
```

**Why this happens**: Briefcase's Python support package doesn't include tkinter, which is required for GUI applications. The tkinter module and its native bindings must be manually copied from the system Python installation.

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

## Critical Lessons Learned: macOS App Distribution (August 2025)

### ⚠️ ZIP File Distribution Issues

**CRITICAL DISCOVERY**: Standard compression methods corrupt notarized macOS app bundles, causing "damaged app" errors even when the original app is perfectly signed and notarized.

#### What We Learned:

1. **System `zip` command CORRUPTS macOS app bundles**:
   ```bash
   # ❌ NEVER DO THIS - Corrupts app bundles
   zip -r MyApp.zip "My App.app"
   ```
   - Destroys internal bundle structure
   - Breaks code signatures
   - Results in "damaged app" errors

2. **`ditto` with compression ALSO corrupts app bundles**:
   ```bash
   # ❌ ALSO CORRUPTS - Even ditto with compression fails
   ditto -c -k "My App.app" MyApp.zip
   ditto -c -k --keepParent "My App.app" MyApp.zip
   ```
   - Even Apple's own ditto tool corrupts when compressing
   - Compression breaks the notarization ticket integration

3. **Only DMG and TAR.GZ preserve notarization**:
   ```bash
   # ✅ WORKS - DMG created by Briefcase (recommended)
   briefcase package  # Creates properly signed DMG
   
   # ✅ WORKS - TAR.GZ compression
   tar -czf "MyApp.tar.gz" "My App.app"
   ```

#### Distribution Strategy:

**Primary Distribution**: Always use DMG files created by Briefcase
- Preserves all signatures and notarization
- Native macOS installation experience
- No corruption issues

**Alternative Distribution**: TAR.GZ for platforms that don't support DMG
- Fully preserves app bundle structure
- Maintains notarization ticket
- Cross-platform compatible

**NEVER use ZIP files** for macOS app distribution - they will always corrupt the bundle.

#### Verification Commands:

```bash
# Always verify after extraction:
spctl -a -t exec -vv "My App.app"
# Should show: "accepted, source=Notarized Developer ID"

# If you see "invalid API object reference" = corrupted bundle
```

#### Root Cause Analysis:

The issue occurs because:
1. ZIP compression algorithms don't understand macOS extended attributes
2. Code signatures include metadata about file permissions and attributes
3. Compression strips extended attributes that are part of the signature
4. Notarization tickets are embedded in extended attributes
5. When extracted, the app bundle appears intact but lacks critical signing metadata

### Key Takeaways for Future Builds:

1. **Always test extracted apps** with `spctl -a -t exec -vv` before distribution
2. **Use DMG as primary distribution format** (created by Briefcase)
3. **Use TAR.GZ as secondary format** if ZIP-like compression is needed  
4. **Never use ZIP or compressed ditto** for macOS app distribution
5. **Document these limitations** to prevent future mistakes

## Common Development Tasks

### Toga Migration TODO
1. **Convert dialogs to Toga widgets** (`database_dialogs.py`, `progress_dialog.py`)
2. **Implement Toga main UI** in `apple_music_play_history_converter.py`
3. **Create Toga-based test suite** to replace moved tkinter tests
4. **Update build scripts** to work with Briefcase commands

### Adding New CSV Format Support
1. Update format detection logic in `detect_file_type()` method
2. Add column mapping in `process_csv_data()` method
3. Create new tests for Toga application (test framework TBD)

### Modifying Search Providers
1. Update `MusicSearchServiceV2` for routing logic
2. Implement provider-specific methods in respective manager classes
3. Update settings UI using Toga widgets (not tkinter grid system)

### UI Layout Changes (Toga)
1. Main layout needs conversion from tkinter to Toga widgets
2. Dialog layouts in `database_dialogs.py` need Toga conversion
3. Use Toga's native styling and layout system
4. Reference legacy UI in `_history/` folder for design patterns

### Running Development Commands
```bash
# Run current Toga application
python run_toga_app.py

# Briefcase development workflow
briefcase dev    # Development mode
briefcase create # Create app structure
briefcase build  # Build application
briefcase run    # Run built app

# Debug specific components
python debug_music_search.py  # Test music search service
python debug_csv.py            # Test CSV processing
python debug_full_flow.py      # Test complete conversion flow
```

## Current Migration Status and Known Issues

### ⚠️ Active UI Migration: tkinter → Toga
The project is in the middle of migrating from tkinter to Toga. Current state:
- **app.py**: Successfully converted to Toga (minimal UI)
- **apple_music_play_history_converter.py**: Still uses tkinter (main UI needs conversion)
- **database_dialogs.py**: Still uses tkinter (dialogs need conversion)
- **progress_dialog.py**: Still uses tkinter (progress tracking needs conversion)

### Known Issues
1. **Mixed UI Framework**: The app currently has both Toga and tkinter code, which may cause compatibility issues
2. **Test Suite**: All tests are tkinter-based and will fail with Toga components
3. **macOS tkinter Fix**: After building with Briefcase, tkinter must be manually copied (see build instructions above)
4. **Import Statements**: Some modules still import tkinter directly, which breaks in Toga-only builds

### Migration Priority
1. Convert main GUI in `apple_music_play_history_converter.py` to Toga
2. Replace tkinter dialogs with Toga equivalents
3. Update test suite for Toga compatibility
4. Remove all tkinter dependencies from `pyproject.toml`
