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
✅ **MIGRATION COMPLETE (v2.0.0)** - The project has successfully migrated from tkinter to Toga/Briefcase for cross-platform support and modern packaging.

**Completed:**
- ✅ Main application entry point converted to Toga (`app.py`, `run_toga_app.py`)
- ✅ Main converter UI fully converted to Toga (`apple_music_play_history_converter.py`)
- ✅ Progress dialog converted to Toga (`progress_dialog.py`)
- ✅ Database dialogs removed (unused dead code)
- ✅ Briefcase configuration in `pyproject.toml`
- ✅ Comprehensive test suite established (44 tests passing)
- ✅ Thread-safe async/await architecture implemented
- ✅ All tkinter dependencies and legacy code removed

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

#### Rate Limit Tracking (iTunes API)
The application tracks 403 Forbidden errors separately from permanent failures:
- **Rate-Limited Tracks**: Tracks that hit the iTunes API rate limit (403 error) are stored in `self.rate_limited_tracks[]` for retry after the rate limit resets
- **Failed Tracks**: Permanent failures (network errors, not found, etc.) are tracked separately
- **UI Feedback**: The progress display shows rate-limited track count separately (e.g., "✅ iTunes: Found 150/200 in 45s | 10 rate limited")
- **Logging**: Rate-limited tracks are logged with ⏸️ emoji and "can retry later" message

**Retry Functionality**:
- **Retry Button**: `Retry Rate-Limited (N)` button appears after iTunes search with count of rate-limited tracks
- **Export Option**: `Export Rate-Limited List` button exports rate-limited tracks to CSV for manual review
- **Smart Retry**: Retries only tracks that were rate-limited (403), not permanently failed tracks
- **User Warning**: Retry dialog warns user to wait 60+ seconds after last rate limit to avoid immediate 403 errors

Implementation details:
- Rate limit detection: `music_search_service_v2.py` lines 540-546
- Track collection: `apple_music_play_history_converter.py` lines 6142-6153
- Retry logic: `apple_music_play_history_converter.py` lines 6817-6861
- Export logic: `apple_music_play_history_converter.py` lines 6863-6911
- Button updates: `apple_music_play_history_converter.py` lines 6913-6919

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

## Logging System

The application uses a centralized **SmartLogger** system with feature flag support, zero-overhead design, and comprehensive settings control.

### SmartLogger Overview

**SmartLogger** is a custom logging wrapper that provides:
- **Feature Flag Control**: Enable/disable logging globally via `settings.json`
- **Zero Overhead**: Disabled logging has < 0.01ms overhead for 10,000 calls
- **Dual Output**: Separate file and console logging controls
- **User-Facing Output**: `print_always()` method for critical messages
- **Thread-Safe**: Safe for concurrent access from multiple threads
- **Settings Persistence**: Configuration stored in platform-appropriate locations

### Configuration

Logging settings are stored in `settings.json` (located at `~/Library/Application Support/AppleMusicConverter/settings.json` on macOS):

```json
{
  "logging": {
    "enabled": false,
    "file_logging": false,
    "console_logging": true,
    "level": "WARNING",
    "use_emoji": false,
    "max_file_size_mb": 5,
    "backup_count": 3
  }
}
```

**Configuration Options:**
- `enabled` (bool): Master switch for all logging (default: `false` for production)
- `file_logging` (bool): Write logs to files (default: `false`)
- `console_logging` (bool): Print logs to terminal (default: `true`)
- `level` (str): Minimum log level - DEBUG, INFO, WARNING, ERROR, CRITICAL (default: `WARNING`)
- `use_emoji` (bool): Emoji prefixes in terminal output (default: `false`)
- `max_file_size_mb` (int): Log rotation size (default: 5)
- `backup_count` (int): Rotated logs to keep (default: 3)

### Usage Patterns

**Basic Usage:**
```python
from apple_music_history_converter.logging_config import get_logger

logger = get_logger(__name__)

# Standard log levels (only logged when enabled=true)
logger.debug("Detailed debugging information")
logger.info("General informational message")
logger.warning("Warning message about potential issue")
logger.error("Error occurred but recoverable")
logger.critical("Critical error, application may fail")

# User-facing output (ALWAYS prints, regardless of settings)
logger.print_always("✅ File processing completed!")
logger.print_always("=" * 80)  # Separator lines
```

**When to Use Each Method:**

| Method | Use Case | Logged When Disabled? | Example |
|--------|----------|----------------------|---------|
| `logger.debug()` | Internal debugging, trace logs | ❌ No | `logger.debug("Cache hit: {key}")` |
| `logger.info()` | Internal status updates | ❌ No | `logger.info("MusicBrainz initialized")` |
| `logger.warning()` | Potential issues, degraded mode | ❌ No | `logger.warning("Rate limit approaching")` |
| `logger.error()` | Errors, exceptions | ❌ No | `logger.error(f"API call failed: {e}")` |
| `logger.critical()` | Fatal errors | ❌ No | `logger.critical("Database corrupted")` |
| `logger.print_always()` | User-facing messages | ✅ Yes | `logger.print_always("✅ Done!")` |

**Print Always Examples:**
```python
# Progress indicators (always visible to user)
logger.print_always("\n🚀 Starting CSV processing...")
logger.print_always(f"✅ Processed {count:,} rows")
logger.print_always("=" * 70)

# Success/failure messages
logger.print_always("✅ Export completed successfully!")
logger.print_always("❌ Export failed - check file permissions")

# User-facing warnings (different from internal warnings)
logger.print_always("⚠️ Large file detected - this may take several minutes")
```

### Migration Guidelines

When converting `print()` statements to logger calls:

**1. Categorize by audience:**
- **User-facing** → `logger.print_always()`
- **Developer-facing** → `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()`

**2. Categorize by severity:**
- **Errors/Exceptions** → `logger.error()` or `logger.critical()`
- **Warnings** → `logger.warning()`
- **Status/Info** → `logger.info()`
- **Debug traces** → `logger.debug()`

**3. Common patterns:**

```python
# Before: Progress indicators
print("✅ Processing completed")
print(f"🚀 Starting optimization...")
print("=" * 80)

# After: User-facing output
logger.print_always("✅ Processing completed")
logger.print_always("🚀 Starting optimization...")
logger.print_always("=" * 80)

# Before: Debug traces
print(f"DEBUG: Cache size = {size}")
print(f"Calling API with params: {params}")

# After: Debug logging
logger.debug(f"Cache size = {size}")
logger.debug(f"Calling API with params: {params}")

# Before: Error messages
print(f"ERROR: Failed to load file: {e}")
print(f"❌ Database connection failed")

# After: Error logging
logger.error(f"Failed to load file: {e}")
logger.error("❌ Database connection failed")
```

**4. Automated migration tools:**
```bash
# Analyze print statements in a file
python migrate_prints.py path/to/file.py

# Automatically replace print() with logger calls
python auto_replace_prints.py path/to/file.py
```

### Performance Characteristics

**Zero-Overhead Design:**
- Disabled logging returns immediately after checking `enabled` flag
- No string formatting or I/O when disabled
- Measured overhead: < 0.01ms for 10,000 disabled log calls

**Performance Benchmarks:**
```python
# 10,000 disabled log calls: < 10ms total (< 0.001ms each)
logger.debug("Message")  # Instant return when disabled

# 1,000 enabled log calls: < 100ms total (< 0.1ms each)
logger.info("Message")   # Minimal overhead when enabled
```

**Thread Safety:**
- Logger caching prevents recreation overhead
- Minor race conditions (1-2 duplicate loggers) tolerated
- No crashes or data corruption under concurrent access

### Testing Logging Code

**Test Suite Location:** `tests_toga/test_logging_system.py`

**Running logging tests:**
```bash
# All logging tests
python -m pytest tests_toga/test_logging_system.py -v

# Specific test categories
python -m pytest tests_toga/test_logging_system.py::TestFeatureFlags -v
python -m pytest tests_toga/test_logging_system.py::TestPerformance -v
```

**Testing with custom settings:**
```python
from apple_music_history_converter.logging_config import get_logger

def test_my_feature():
    # Force logging disabled for this test
    settings = {"enabled": False}
    logger = get_logger("test.myfeature", settings=settings)

    # Your test code here
    logger.debug("This won't be logged")
```

**Clearing logger cache in tests:**
```python
from apple_music_history_converter.logging_config import clear_logger_cache

def setup_method(self):
    """Clear logger cache before each test"""
    clear_logger_cache()
```

### Production vs Development Settings

**Production (Default):**
```json
{
  "logging": {
    "enabled": false,          // Minimal overhead
    "file_logging": false,     // No file I/O
    "console_logging": true,   // User sees print_always() only
    "level": "WARNING",        // Only warnings/errors if enabled
    "use_emoji": false         // Clean output
  }
}
```

**Development/Debugging:**
```json
{
  "logging": {
    "enabled": true,           // Full logging active
    "file_logging": true,      // Logs saved to files
    "console_logging": true,   // Logs printed to console
    "level": "DEBUG",          // All log levels
    "use_emoji": true          // Visual emoji indicators
  }
}
```

**Log file locations (when file_logging=true):**
- **macOS**: `~/Library/Logs/AppleMusicConverter/`
- **Windows**: `%LOCALAPPDATA%\AppleMusicConverter\Logs\`
- **Linux**: `~/.cache/AppleMusicConverter/log/`

### Migration Status

**Logging migration completed** (v2.0.0):
- ✅ 606/635 print statements migrated (95.4%)
- ✅ 25/25 logging tests passing (100%)
- ✅ 68/69 existing tests passing (98.6%)
- ✅ Zero-overhead validated: < 0.01ms when disabled
- ✅ Thread safety confirmed under concurrent access

**Remaining prints (29):**
- Intentionally preserved in `__main__` blocks (demo/test code)
- Non-application code (build scripts, utilities)

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

**Production Test Suite**: Comprehensive Toga-based tests in `tests_toga/` directory. All 44 tests passing (100% success rate).

Test categories:
- **Basic Functionality**: File type detection, CSV processing, security fixes, data normalization, cross-platform compatibility
- **Real CSV Files**: Structure validation, encoding detection, missing artist detection, chunk processing performance
- **Security**: Shell injection prevention, input validation, data sanitization, file system safety
- **Memory Efficiency**: Chunked vs full load memory testing, nrows parameter optimization
- **Data Quality**: Empty row detection, special character handling, format validation

Run tests:
```bash
python -m pytest tests_toga/ -v              # All tests
python -m pytest tests_toga/test_security.py # Security tests only
python -m pytest tests_toga/ -k "test_csv"   # CSV-related tests
```

Legacy tkinter tests are archived in `_history/tests/` for reference.

## Build System

Briefcase-based builds for Windows, macOS, and Linux:
- Modern Python packaging using BeeWare's Briefcase
- Native app bundles for each platform
- Automatic dependency management and resolution
- Built-in code signing and notarization support for macOS
- Clean separation of source code and build artifacts

### Standard Build Process

**NO MANUAL FIXES REQUIRED**: The Toga framework is fully supported by Briefcase with no manual intervention needed.

#### Complete Build Process:
```bash
# Standard Briefcase build (no tkinter workarounds needed!)
python build.py clean
python build.py create
python build.py build

# Sign and package
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Create distribution DMG (automatic via Briefcase)
# DMG is created in: build/apple-music-history-converter/macos/
```

**Why Toga is better**: Toga is a native Briefcase framework with full support, eliminating the need for manual dependency copying that tkinter required.

### GitHub Actions Automated Builds

**Windows builds are automated via GitHub Actions** - no local Windows machine required.

#### Workflow Configuration

The Windows build workflow is located at `.github/workflows/build-windows.yml` and supports:
- **Push triggers**: Builds on push to `main` or `feature/ui-rewrite` branches
- **Tag triggers**: Builds and releases on version tags (`v*.*.*`)
- **Pull request triggers**: Builds on PRs to `main`
- **Manual triggers**: Can be triggered manually via GitHub UI

#### Triggering a Windows Build

**Option 1: Automatic build on version tag (recommended)**
```bash
# Update version in pyproject.toml first, then:
git add pyproject.toml
git commit -m "chore: bump version to 2.0.2"
git push origin main

# Create and push version tag
git tag v2.0.2
git push origin v2.0.2

# GitHub Actions will:
# 1. Build Windows x86_64 MSI installer
# 2. Upload as build artifact (90 day retention)
# 3. Automatically attach to GitHub release (if tag exists)
```

**Option 2: Manual workflow trigger**
1. Go to GitHub repository → Actions tab
2. Select "Build Windows App" workflow
3. Click "Run workflow" button
4. Select branch (usually `main`)
5. Click "Run workflow"

**Option 3: Automatic build on push**
```bash
# Any push to main branch triggers a build
git push origin main
```

#### Build Artifacts

After the workflow completes:
1. **Build Artifacts**: Available under Actions → Workflow run → Artifacts
   - Artifact name: `apple-music-history-converter-windows-x86_64-msi`
   - Contains: `Apple Music History Converter-2.0.2.msi`
   - Retention: 90 days

2. **GitHub Release** (if triggered by tag):
   - MSI file automatically attached to the release
   - Available at: `https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/tag/v2.0.2`

#### Monitoring Build Status

**View build progress:**
```bash
# Using GitHub CLI
gh run list --workflow=build-windows.yml
gh run watch

# Or visit:
# https://github.com/nerveband/Apple-Music-Play-History-Converter/actions
```

**Check build logs:**
- Click on the workflow run in GitHub Actions
- Expand each step to view detailed logs
- Download build artifact if successful

#### Complete Release Process

To release a new version with both macOS and Windows builds:

```bash
# 1. Update version in pyproject.toml
#    Update both [project] version and [tool.briefcase.app.*.windows] version_triple

# 2. Build and sign macOS version locally
python build.py clean
python build.py create
python build.py build
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# 3. Commit and tag
git add pyproject.toml
git commit -m "chore: release v2.0.2"
git push origin main
git tag v2.0.2
git push origin v2.0.2

# 4. Create GitHub release manually or with gh CLI
gh release create v2.0.2 \
  --title "v2.0.2 - Bug Fixes and Improvements" \
  --notes "Release notes here" \
  "dist/Apple Music History Converter-2.0.2.dmg#macOS DMG Installer"

# 5. GitHub Actions will automatically build Windows MSI and attach it to the release
#    Monitor at: https://github.com/nerveband/Apple-Music-Play-History-Converter/actions
```

#### Troubleshooting GitHub Actions

**Build fails with Briefcase error:**
- Check Python version in workflow (currently 3.12)
- Verify all dependencies are in pyproject.toml
- Check workflow logs for specific error

**MSI not attached to release:**
- Verify tag format matches `v*.*.*` (e.g., `v2.0.2`)
- Check workflow permissions (GITHUB_TOKEN needs write access)
- Ensure workflow completed successfully before creating release

**Artifact download issues:**
- Artifacts expire after 90 days
- Only available for successful builds
- Use `actions/upload-artifact@v4` (current version)

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

## Debugging and Troubleshooting

### Debug Logging

The application uses a centralized SmartLogger system with feature flag control. To enable detailed debugging logs:

**1. Enable Debug Logging:**

Edit `~/Library/Application Support/AppleMusicConverter/settings.json`:
```json
{
  "logging": {
    "enabled": true,
    "file_logging": true,
    "console_logging": true,
    "level": "DEBUG",
    "use_emoji": true,
    "max_file_size_mb": 10,
    "backup_count": 5
  }
}
```

**2. Log File Locations:**
- **macOS**: `~/Library/Logs/AppleMusicConverter/`
- **Windows**: `%LOCALAPPDATA%\AppleMusicConverter\Logs\`
- **Linux**: `~/.cache/AppleMusicConverter/log/`

**3. View Logs in Application:**
- Click "View Logs" button in the Database Management section
- Opens log directory in Finder/Explorer

**4. Network Debugging:**

For debugging network issues (iTunes API, MusicBrainz downloads):
```bash
# Run with console output visible
briefcase dev

# Or run from terminal to see all debug output
python run_toga_app.py
```

Key network debug messages to look for:
- `🌐 Testing connection to` - Network connectivity tests
- `📡 iTunes API request` - API call details
- `⚠️ Rate limit` - Rate limiting status
- `❌ Network error` - Connection failures
- `✅ Response received` - Successful API calls

**5. Common Debug Scenarios:**

**Network Issues:**
```bash
# Enable debug logging, then run network diagnostics
python -c "from src.apple_music_history_converter.network_diagnostics import run_diagnostics; run_diagnostics(verbose=True)"
```

**CSV Processing Issues:**
```bash
# Test CSV file processing with debug output
python -c "
from src.apple_music_history_converter.apple_music_play_history_converter import AppleMusicConverterApp
app = AppleMusicConverterApp()
app.main_loop()
"
```

**Database Issues:**
```bash
# Check database status with logging enabled
python -c "
from src.apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2
service = MusicSearchServiceV2()
print(service.get_database_info())
"
```

**6. Debug Build Distribution:**

To distribute a debug build with logging enabled:
```bash
# 1. Enable logging in settings.json (shown above)

# 2. Build and sign the app
python build.py clean
python build.py create
python build.py build

# 3. Sign all binaries (172 .so/.dylib files)
find "build/apple-music-history-converter/macos/app/Apple Music History Converter.app" \
  \( -name "*.so" -o -name "*.dylib" \) | \
  while read file; do
    codesign --force --options runtime --timestamp \
      --sign "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" "$file"
  done

# 4. Sign framework files
find "build/apple-music-history-converter/macos/app/Apple Music History Converter.app/Contents/Frameworks" \
  -type f \( -name "*.dylib" -o -name "*.so" -o -perm +111 \) | \
  while read file; do
    codesign --force --options runtime --timestamp \
      --sign "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" "$file"
  done

# 5. Re-sign main app bundle
codesign --force --options runtime --timestamp \
  --entitlements "build/apple-music-history-converter/macos/app/Entitlements.plist" \
  --sign "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" \
  "build/apple-music-history-converter/macos/app/Apple Music History Converter.app"

# 6. Create distribution archive (tar.gz preserves signatures, zip corrupts them!)
tar -czf "Apple_Music_History_Converter_DEBUG.tar.gz" \
  -C "build/apple-music-history-converter/macos/app" \
  "Apple Music History Converter.app"
```

**CRITICAL**: Always use `tar -czf` for distribution, never `zip`. ZIP corrupts code signatures and notarization tickets.

**7. Collecting Debug Information:**

When reporting issues, collect:
1. **Log files** from `~/Library/Logs/AppleMusicConverter/`
2. **Settings** from `~/Library/Application Support/AppleMusicConverter/settings.json`
3. **Network diagnostics** output
4. **Console output** if running from terminal
5. **System info**: macOS version, Python version

## Build Practices & Release Process

This section provides comprehensive guidance for building, releasing, and maintaining the application across platforms.

### Version Management

**Version Number Format**: `MAJOR.MINOR.PATCH` (e.g., `2.0.2`)

**Version Locations** (all must be updated together):
1. `pyproject.toml` line 7: `[project]` → `version = "2.0.2"`
2. `pyproject.toml` line 56: `[tool.briefcase]` → `version = "2.0.2"`
3. `pyproject.toml` line 132: `[tool.briefcase.app.*.windows]` → `version_triple = "2.0.2"`

**Version Bumping Guidelines**:
- **MAJOR**: Breaking changes, major architecture changes, incompatible API changes
- **MINOR**: New features, significant improvements, non-breaking API changes
- **PATCH**: Bug fixes, minor improvements, documentation updates

### macOS Build Process

**Prerequisites**:
- Xcode installed (not just command line tools)
- Apple Developer Program membership (for distribution)
- Developer ID Application certificate installed in Keychain
- Apple app-specific password stored in `.env` file

**Step-by-Step Build Process**:

```bash
# 1. Clean previous builds
python build.py clean

# 2. Create application scaffold
python build.py create
# - Downloads Python support package (~50MB, cached)
# - Installs all dependencies from pyproject.toml
# - Creates universal binary structure (arm64 + x86_64)
# - Expected duration: 1-3 minutes (first time), 30s (subsequent)

# 3. Build the application
python build.py build
# - Compiles Python bytecode
# - Links frameworks and libraries
# - Creates app bundle structure
# - Expected duration: 10-30 seconds

# 4. Sign and package with Developer ID
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
# - Signs all binaries with hardened runtime
# - Creates DMG installer
# - Submits for notarization (requires internet)
# - Waits for Apple approval (can take 1-30 minutes)
# - Staples notarization ticket to DMG
# - Expected duration: 5-45 minutes (depends on Apple's queue)

# 5. Verify the signed DMG
spctl -a -t exec -vv "dist/Apple Music History Converter-2.0.2.dmg"
# Should output: "accepted, source=Notarized Developer ID"
```

**Build Output Locations**:
- App bundle: `build/apple-music-history-converter/macos/app/Apple Music History Converter.app`
- Signed DMG: `dist/Apple Music History Converter-2.0.2.dmg`
- Build logs: `build/apple-music-history-converter/macos/logs/`

**Common Build Issues**:

| Issue | Cause | Solution |
|-------|-------|----------|
| "Developer ID certificate not found" | Certificate not installed | Add Apple ID to Xcode → Accounts → Manage Certificates |
| "Notarization rejected" | Missing entitlements | Check `pyproject.toml` entitlements section |
| "Package damaged" after distribution | ZIP corruption | Always use `tar -czf`, never `zip` |
| Universal build fails | Architecture mismatch | Clean build directory and rebuild |
| DMG not notarized | Network timeout | Re-run with `--resume <UUID>` from error message |

**Testing Signed Builds**:

```bash
# 1. Verify code signature
codesign -dvvv "dist/Apple Music History Converter-2.0.2.dmg"

# 2. Verify notarization
spctl -a -t exec -vv "dist/Apple Music History Converter-2.0.2.dmg"

# 3. Test installation
# - Mount DMG and drag to Applications
# - Launch app and verify all features work
# - Test CSV conversion, MusicBrainz download, iTunes API
# - Check "About" dialog shows correct version

# 4. Test Gatekeeper
# - Download DMG from GitHub release URL
# - Open in fresh user account or different Mac
# - Should open without "damaged app" warning
```

### Windows Build Process

**Strategy**: All Windows builds are automated via GitHub Actions. No local Windows machine required.

**Automatic Build via Tag Push**:

```bash
# 1. Ensure all version numbers are updated (see Version Management above)

# 2. Commit version changes
git add pyproject.toml
git commit -m "chore: bump version to 2.0.3"
git push origin main

# 3. Create and push version tag
git tag v2.0.3
git push origin v2.0.3

# 4. GitHub Actions automatically:
# - Builds Windows x86_64 MSI installer
# - Uploads as artifact (90 day retention)
# - Attempts to upload to GitHub release (if it exists)
```

**Manual Workflow Trigger**:

```bash
# Via GitHub CLI
gh workflow run build-windows.yml

# Via GitHub Web UI
# 1. Go to Actions tab
# 2. Select "Build Windows App"
# 3. Click "Run workflow"
# 4. Select branch and click "Run workflow"
```

**Monitoring Build Progress**:

```bash
# List recent workflow runs
gh run list --workflow=build-windows.yml --limit 5

# Watch specific run
gh run watch <RUN_ID>

# View logs
gh run view <RUN_ID> --log

# Download MSI artifact
gh run download <RUN_ID> --name apple-music-history-converter-windows-x86_64-msi
```

**Build Output**:
- MSI installer: `Apple Music History Converter-2.0.3.msi`
- Build duration: ~3-4 minutes
- Artifact retention: 90 days
- Artifact size: ~48-50MB

**Testing Windows Builds**:

```bash
# 1. Download MSI from GitHub Actions artifacts
gh run download <RUN_ID> --name apple-music-history-converter-windows-x86_64-msi

# 2. Test in Windows VM or physical machine
# - Run MSI installer
# - Verify installation to Program Files
# - Launch app from Start Menu
# - Test all features (CSV conversion, database download, etc.)
# - Check version in About dialog

# 3. Test uninstallation
# - Use Windows Settings → Apps
# - Verify clean removal (no leftover files)
```

### Complete Release Checklist

Use this checklist for every release to ensure consistency and quality.

#### Pre-Release (1-2 days before)

- [ ] **Run full test suite**: `python -m pytest tests_toga/ -v`
  - All 44+ tests must pass
  - Check for deprecation warnings
  - Review any skipped tests

- [ ] **Test on target platforms**:
  - [ ] macOS: Test on both Intel and Apple Silicon if possible
  - [ ] Windows: Test on Windows 10 and Windows 11
  - [ ] Linux: Optional but recommended for Briefcase compatibility

- [ ] **Test real-world scenarios**:
  - [ ] Large CSV files (100k+ rows)
  - [ ] MusicBrainz database download from scratch
  - [ ] iTunes API rate limiting behavior
  - [ ] Exit/quit functionality (especially on macOS)
  - [ ] Database optimization workflow

- [ ] **Performance benchmarks**:
  - [ ] CSV processing: Should handle 10k rows in <5 seconds
  - [ ] MusicBrainz search: Should average <5ms per query
  - [ ] iTunes API: Should respect 20 req/min limit

- [ ] **Review code changes since last release**:
  ```bash
  git log v2.0.2..HEAD --oneline
  git diff v2.0.2..HEAD --stat
  ```

- [ ] **Update version numbers** (see Version Management above):
  - [ ] `pyproject.toml` (3 locations)
  - [ ] Verify no hardcoded version strings in code

- [ ] **Update documentation**:
  - [ ] README.md (if features changed)
  - [ ] CHANGELOG.md (if exists)
  - [ ] CLAUDE.md (if build process changed)
  - [ ] Latest Release section in CLAUDE.md

- [ ] **Review open issues/PRs**:
  - [ ] Address any critical bugs
  - [ ] Close resolved issues
  - [ ] Merge approved pull requests

#### Release Day

**Step 1: Build macOS Version**

```bash
# Clean and build
python build.py clean
python build.py create
python build.py build

# Sign and notarize (allow 5-45 minutes)
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Verify signing
spctl -a -t exec -vv "dist/Apple Music History Converter-2.0.3.dmg"
# Must show: "accepted, source=Notarized Developer ID"
```

**Step 2: Commit and Tag**

```bash
# Commit version bump
git add pyproject.toml
git commit -m "chore: release v2.0.3

- Update version to 2.0.3 in all locations
- Update Latest Release section in CLAUDE.md

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"

# Push to main
git push origin main

# Create and push tag
git tag v2.0.3
git push origin v2.0.3
```

**Step 3: Monitor Windows Build**

```bash
# Wait ~30 seconds for GitHub Actions to trigger
sleep 30

# Watch the build
gh run list --workflow=build-windows.yml --limit 1
gh run watch <LATEST_RUN_ID>

# Expected duration: 3-4 minutes
# Wait for "completed successfully" status
```

**Step 4: Create GitHub Release**

```bash
# Download Windows MSI from GitHub Actions
gh run download <RUN_ID> --name apple-music-history-converter-windows-x86_64-msi --dir ./release-windows

# Verify both files exist
ls -lh "dist/Apple Music History Converter-2.0.3.dmg"
ls -lh "release-windows/Apple Music History Converter-2.0.3.msi"

# Create release with both installers
gh release create v2.0.3 \
  --title "v2.0.3 - [Brief Title]" \
  --notes "## What's Changed

### New Features
- Feature 1
- Feature 2

### Bug Fixes
- Fix 1
- Fix 2

### Improvements
- Improvement 1
- Improvement 2

## Downloads
- **macOS**: Universal DMG installer (Apple Silicon + Intel)
- **Windows**: MSI installer (x86_64)

## Compatibility
- macOS 11+ (Big Sur or later)
- Windows 10/11 x86_64
- Python 3.8+ (bundled)

---

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)" \
  "dist/Apple Music History Converter-2.0.3.dmg#macOS DMG Installer (Universal)" \
  "release-windows/Apple Music History Converter-2.0.3.msi#Windows MSI Installer (x86_64)"
```

**Step 5: Post-Release Verification**

```bash
# 1. Verify release is published
gh release view v2.0.3

# 2. Check both installers are attached
# Should see: .dmg and .msi files

# 3. Download and test installers from GitHub
# - Test on clean machine or VM
# - Verify no "damaged app" warnings
# - Smoke test: open app, convert a CSV, verify output

# 4. Update project documentation
# - Update "Latest Release" section in CLAUDE.md
# - Update README.md badges if version displayed
# - Close milestone (if using GitHub milestones)

# 5. Announce release (optional)
# - Tweet/social media
# - Update documentation site
# - Notify users via email/newsletter
```

#### Post-Release (within 24 hours)

- [ ] **Monitor for issues**:
  - Check GitHub Issues for new bug reports
  - Monitor download counts
  - Review any user feedback

- [ ] **Create hotfix branch if needed**:
  ```bash
  git checkout -b hotfix/v2.0.4 v2.0.3
  # Fix critical bug
  # Follow release process for patch version
  ```

- [ ] **Start next version planning**:
  - Create GitHub milestone for next version
  - Triage open issues
  - Plan feature roadmap

### Rollback Procedure

If a release has critical issues:

**Option 1: Deprecate Release (Recommended)**

```bash
# Mark release as pre-release to warn users
gh release edit v2.0.3 --prerelease

# Update release notes with warning
gh release edit v2.0.3 --notes "⚠️ **DEPRECATED**: Critical bug found. Please use v2.0.2 instead.

Original release notes:
[keep original notes]

---

Known Issues:
- Issue 1 description
- Issue 2 description

Fix ETA: [date or \"in progress\"]"
```

**Option 2: Delete and Replace**

```bash
# Delete the problematic release
gh release delete v2.0.3 --yes

# Delete the tag
git tag -d v2.0.3
git push origin :refs/tags/v2.0.3

# Fix issues, bump to v2.0.4, and re-release
```

**Option 3: Quick Hotfix**

```bash
# Branch from problematic release
git checkout -b hotfix/v2.0.4 v2.0.3

# Fix the critical bug
git add <fixed_files>
git commit -m "fix: critical bug in [component]"

# Follow full release process for v2.0.4
# Publish as hotfix with clear release notes
```

## Development Workflow & Best Practices

This section establishes standard practices for efficient, high-quality development.

### Development Environment Setup

**Initial Setup**:

```bash
# 1. Clone repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install briefcase  # For building
pip install pytest pytest-cov  # For testing

# 4. Verify installation
python run_toga_app.py  # Should launch app
python -m pytest tests_toga/ -v  # Should pass all tests

# 5. Configure development settings
# Edit ~/.apple_music_converter/settings.json for debug logging
```

**Development Tools Recommended**:
- **IDE**: VS Code with Python extension, or PyCharm
- **Python**: 3.8+ (3.12 recommended for latest features)
- **Git**: Version control
- **gh CLI**: For GitHub Actions and releases
- **pytest**: For running tests
- **black**: For code formatting (optional)

### Branch Strategy

**Main Branches**:
- `main`: Production-ready code, always stable, all releases tagged from here
- `develop`: Integration branch for features (optional, can work directly on main for small team)

**Feature Branches**:

```bash
# Create feature branch
git checkout -b feature/descriptive-name main

# Work on feature with incremental commits
git add <files>
git commit -m "feat: add [feature description]"

# Keep branch up to date
git fetch origin
git rebase origin/main

# Push feature branch
git push origin feature/descriptive-name

# Create pull request via GitHub
gh pr create --title "Add [feature]" --body "Description..."

# After merge, delete feature branch
git checkout main
git pull
git branch -d feature/descriptive-name
```

**Branch Naming Conventions**:
- `feature/description`: New features
- `fix/description`: Bug fixes
- `refactor/description`: Code refactoring
- `docs/description`: Documentation updates
- `test/description`: Test additions/fixes
- `hotfix/vX.Y.Z`: Critical production fixes

### Commit Message Standards

Follow conventional commits format for better changelog generation and clarity.

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks (dependencies, build, release)
- `style`: Code style changes (formatting, no logic change)

**Examples**:

```bash
# Good commits
git commit -m "feat(csv): add support for Daily Tracks format"
git commit -m "fix(itunes): handle 403 rate limit errors gracefully"
git commit -m "perf(search): optimize MusicBrainz query with index"
git commit -m "docs(build): update macOS signing instructions"
git commit -m "chore: bump version to 2.0.3"

# Bad commits (avoid these)
git commit -m "fixed stuff"  # Too vague
git commit -m "WIP"  # Work in progress (squash before PR)
git commit -m "Updated files"  # Not descriptive
```

**Multi-line Commit Messages**:

```bash
git commit -m "feat(search): add batch search optimization

- Implement parallel search for multiple tracks
- Add caching layer for repeated queries
- Reduce search time by 80% for large CSVs

Closes #123"
```

### Testing Requirements

**Test Before Committing**:

```bash
# Run all tests
python -m pytest tests_toga/ -v

# Run specific test file
python -m pytest tests_toga/test_csv_processing.py -v

# Run with coverage report
python -m pytest tests_toga/ --cov=src/apple_music_history_converter --cov-report=html

# Run tests and watch for changes (during development)
python -m pytest tests_toga/ --watch
```

**Test Categories**:

1. **Unit Tests**: Test individual functions/methods
   - Location: `tests_toga/test_*.py`
   - Fast execution (<1 second per test)
   - No external dependencies (mock APIs, databases)

2. **Integration Tests**: Test component interactions
   - Test CSV parsing → music search → export
   - Test database download → optimization → search
   - May use real files/APIs with rate limiting

3. **UI Tests**: Test Toga UI components
   - Test button clicks, input validation
   - Test dialog flows
   - Use Toga's testing utilities

**Writing New Tests**:

```python
# tests_toga/test_new_feature.py
import pytest
from apple_music_history_converter.module import function

class TestNewFeature:
    """Test the new feature implementation"""

    def test_basic_functionality(self):
        """Test basic use case"""
        result = function(input_data)
        assert result == expected_output

    def test_edge_case(self):
        """Test edge case handling"""
        with pytest.raises(ValueError):
            function(invalid_input)

    def test_performance(self):
        """Test performance requirements"""
        import time
        start = time.time()
        function(large_dataset)
        duration = time.time() - start
        assert duration < 1.0  # Should complete in <1 second

# Run with: python -m pytest tests_toga/test_new_feature.py -v
```

**Test Coverage Goals**:
- **Minimum**: 70% overall coverage
- **Target**: 80%+ coverage for business logic
- **Critical paths**: 100% coverage (CSV parsing, music search, export)

### Code Quality Standards

**Code Formatting**:

```bash
# Use consistent style (PEP 8)
# Optional: Use black for automatic formatting
black src/apple_music_history_converter/

# Check style without modifying
black --check src/

# Format specific file
black src/apple_music_history_converter/csv_processor.py
```

**Code Review Checklist**:

Before submitting PR or committing to main:

- [ ] All tests pass (`pytest tests_toga/ -v`)
- [ ] No debug print statements (use `logger` instead)
- [ ] No hardcoded paths or credentials
- [ ] Error handling for all external calls (API, file I/O, database)
- [ ] Type hints for function signatures (when practical)
- [ ] Docstrings for public functions/classes
- [ ] No commented-out code blocks (delete or document why)
- [ ] No `TODO` comments without GitHub issue reference
- [ ] Dependencies added to `pyproject.toml` if new libraries used
- [ ] Performance tested for operations on large datasets

**Code Documentation Standards**:

```python
def search_track(artist: str, track: str, provider: str = "musicbrainz") -> dict:
    """Search for a track using the specified music provider.

    Args:
        artist: Artist name to search for
        track: Track title to search for
        provider: Music provider to use ("musicbrainz" or "itunes")

    Returns:
        Dictionary containing track metadata:
        {
            "artist": str,
            "track": str,
            "album": str,
            "year": int,
            "mbid": str or None
        }

    Raises:
        ValueError: If provider is invalid
        RateLimitError: If API rate limit exceeded
        NetworkError: If network request fails

    Example:
        >>> result = search_track("The Beatles", "Hey Jude")
        >>> print(result["album"])
        "Hey Jude"
    """
    # Implementation...
```

### Feature Development Workflow

**Standard Process for Adding New Features**:

1. **Planning Phase**:
   ```bash
   # Create GitHub issue
   gh issue create --title "Add [feature name]" --body "Description..."

   # Discuss design in issue comments
   # Get feedback on approach before coding
   ```

2. **Development Phase**:
   ```bash
   # Create feature branch
   git checkout -b feature/feature-name main

   # Implement incrementally with tests
   # Commit frequently with clear messages
   git add <files>
   git commit -m "feat: implement [component]"

   # Run tests continuously
   python -m pytest tests_toga/ -v
   ```

3. **Testing Phase**:
   ```bash
   # Write unit tests for new code
   # Add integration tests for workflows
   # Test on both macOS and Windows if UI changes

   # Verify performance
   python -m pytest tests_toga/test_performance.py -v

   # Check test coverage
   python -m pytest tests_toga/ --cov=src --cov-report=term-missing
   ```

4. **Documentation Phase**:
   ```bash
   # Update CLAUDE.md if architecture changed
   # Update README.md if user-facing features added
   # Add inline documentation for complex logic

   # Document new dependencies
   # Add usage examples
   ```

5. **Review Phase**:
   ```bash
   # Push branch
   git push origin feature/feature-name

   # Create pull request
   gh pr create --title "Add [feature]" \
     --body "## Changes
   - Change 1
   - Change 2

   ## Testing
   - Tested on macOS 14
   - All 44+ tests passing
   - Performance benchmarks met

   Closes #123"

   # Address review feedback
   # Make requested changes
   git add <files>
   git commit -m "refactor: address review feedback"
   git push
   ```

6. **Merge Phase**:
   ```bash
   # After approval, merge via GitHub
   gh pr merge --squash  # Squash commits for clean history

   # Or merge without squashing to preserve history
   gh pr merge --merge

   # Delete feature branch
   git branch -d feature/feature-name
   git push origin --delete feature/feature-name
   ```

### Database Migration Best Practices

When modifying MusicBrainz database schema or DuckDB queries:

**Schema Changes**:

```python
# 1. Create migration function
def migrate_database_v2_to_v3(db_path: str):
    """Migrate database from v2 to v3 schema.

    Changes:
    - Add album_id column to tracks table
    - Create album_tracks index for performance
    """
    conn = duckdb.connect(db_path)

    # Check current version
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= 3:
        logger.info("Database already at v3 or higher")
        return

    # Apply migration
    conn.execute("ALTER TABLE tracks ADD COLUMN album_id VARCHAR")
    conn.execute("CREATE INDEX idx_album_tracks ON tracks(album_id)")
    conn.execute("PRAGMA user_version = 3")

    conn.close()
    logger.info("Database migrated to v3")

# 2. Call migration on app startup
# In MusicBrainzManagerV2.__init__():
if self.db_exists():
    self._run_migrations()
```

**Testing Migrations**:

```bash
# 1. Test with old database format
cp ~/.apple_music_converter/musicbrainz_v2.db test_db.db

# 2. Run migration
python -c "from src.*.musicbrainz_manager_v2 import migrate_database_v2_to_v3; migrate_database_v2_to_v3('test_db.db')"

# 3. Verify schema
python -c "import duckdb; conn = duckdb.connect('test_db.db'); print(conn.execute('PRAGMA table_info(tracks)').fetchall())"

# 4. Test queries still work
python -c "import duckdb; conn = duckdb.connect('test_db.db'); print(conn.execute('SELECT * FROM tracks LIMIT 5').fetchall())"
```

### Dependency Management

**Adding New Dependencies**:

```bash
# 1. Install in development environment
pip install new-package

# 2. Test that feature works
python run_toga_app.py

# 3. Add to pyproject.toml
# Edit [project] dependencies for all platforms
# Edit [tool.briefcase.app.*.windows] requires for Windows-specific
# Edit [tool.briefcase.app.*.macOS] requires for macOS-specific

# 4. Test clean install
python build.py clean
python build.py create  # Should install new dependency

# 5. Commit changes
git add pyproject.toml
git commit -m "chore: add new-package dependency"
```

**Updating Dependencies**:

```bash
# 1. Check for updates
pip list --outdated

# 2. Update specific package
pip install --upgrade package-name

# 3. Test extensively (dependencies can break things)
python -m pytest tests_toga/ -v
python run_toga_app.py

# 4. Update version in pyproject.toml
# Change: "package>=1.0.0" to "package>=1.1.0"

# 5. Document breaking changes in commit message
git commit -m "chore: upgrade package from 1.0 to 1.1

Breaking changes:
- API method renamed from old_name to new_name
- Fixed compatibility with new version"
```

### Performance Optimization Guidelines

**Profiling Code**:

```python
# Use cProfile for CPU profiling
python -m cProfile -o profile.stats run_toga_app.py

# Analyze results
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"

# Memory profiling
pip install memory_profiler
python -m memory_profiler script.py
```

**Performance Targets**:

| Operation | Target | Current | Notes |
|-----------|--------|---------|-------|
| CSV parsing (10k rows) | <5s | ~3s | Use pandas chunking |
| MusicBrainz search | <5ms | ~2ms | DuckDB indexed search |
| iTunes API search | <200ms | ~150ms | Network dependent |
| Database optimization | <5min | ~3min | Download + build indices |
| App startup time | <3s | ~2s | Cold start |

**Optimization Checklist**:

- [ ] Use pandas chunking for large CSV files (`chunksize=10000`)
- [ ] Batch database queries instead of N+1 queries
- [ ] Use DuckDB indices for frequently queried columns
- [ ] Cache expensive computations (use `functools.lru_cache`)
- [ ] Use threading for I/O-bound tasks (API calls, file I/O)
- [ ] Use async/await for Toga UI to prevent blocking
- [ ] Profile before optimizing (don't guess bottlenecks)
- [ ] Benchmark before and after changes

### Debugging Techniques

**Development Mode Debugging**:

```bash
# 1. Enable debug logging
# Edit ~/.apple_music_converter/settings.json:
{
  "logging": {
    "enabled": true,
    "file_logging": true,
    "console_logging": true,
    "level": "DEBUG"
  }
}

# 2. Run with console output
python run_toga_app.py

# 3. Use breakpoints
# Add in code: import pdb; pdb.set_trace()
# Or use IDE debugger (VS Code, PyCharm)

# 4. Check logs
tail -f ~/Library/Logs/AppleMusicConverter/apple_music_converter.log
```

**Production Debugging**:

```bash
# 1. Collect user logs
# Ask user to send: ~/Library/Logs/AppleMusicConverter/

# 2. Enable logging remotely
# Provide settings.json with logging enabled

# 3. Reproduce locally
# Use user's CSV file and settings
# Follow exact steps to reproduce

# 4. Create test case
# Add regression test to prevent recurrence
```

### Continuous Integration (CI) Future Setup

When project scales, consider adding CI:

```yaml
# .github/workflows/ci.yml (example for future)
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: [3.8, 3.9, '3.10', 3.11, 3.12]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest tests_toga/ -v --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Common Development Tasks

### Development Workflow
The application is production-ready with a complete Toga implementation. Common tasks:

### Adding New CSV Format Support
1. Update format detection logic in `detect_file_type()` method in `apple_music_play_history_converter.py`
2. Add column mapping in `process_csv_data()` method
3. Create new tests in `tests_toga/` directory following existing patterns

### Modifying Search Providers
1. Update `MusicSearchServiceV2` for routing logic
2. Implement provider-specific methods in respective manager classes
3. Update settings UI using Toga widgets in the main application class

### UI Layout Changes
1. Main layout uses Toga's Pack layout system
2. All dialogs use HIG-compliant Toga widgets
3. Reference `apple_music_play_history_converter.py` for Toga layout patterns
4. Use `toga.Box` with Pack styling for all UI layouts

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

## Current Status (v2.0.2)

### ✅ Toga Migration Complete
The project has successfully completed its migration from tkinter to Toga. Current state:
- **app.py**: Fully converted to Toga (Briefcase entry point)
- **apple_music_play_history_converter.py**: Fully converted to Toga (main UI with 6,973 lines)
- **progress_dialog.py**: Fully converted to Toga (HIG-compliant dialogs)
- **database_dialogs.py**: Removed (unused dead code, 728 lines deleted)

### Production Ready Features
1. **Pure Toga Framework**: No tkinter dependencies remain in the codebase
2. **Comprehensive Test Suite**: 44 tests passing (100% success rate)
3. **Thread-Safe Architecture**: Proper async/await with background task management
4. **Cross-Platform Builds**: Native apps for Windows, macOS, and Linux via Briefcase
5. **Code Signing**: Full Apple Developer ID signing and notarization for macOS
6. **Performance**: 100x faster with ultra-fast batch processing and parallel searches
7. **Clean Exit**: Resolved Toga/Rubicon GIL crash on macOS app quit
8. **Automated Builds**: Windows MSI builds fully automated via GitHub Actions

### Latest Release
- **Version**: 2.0.2 (October 8, 2025)
- **Status**: Production ready, fully signed and notarized
- **Test Coverage**: 44/44 tests passing
- **Performance**: Handles 253,525 rows efficiently with 10,000+ tracks/sec search speed
- **Stability**: Clean exit on all platforms, no GIL crashes
- **Downloads**: [macOS DMG](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/tag/v2.0.2) • [Windows MSI](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/tag/v2.0.2)

### What's New in v2.0.2
- **macOS Exit Crash Fixed**: Eliminated fatal Python GIL crash during app quit
  - Implemented `os._exit()` workaround for Toga/Rubicon framework limitation
  - Proper ThreadPoolExecutor cleanup with tracked custom executor
  - Interruptible sleep system using threading.Event
  - Complete technical documentation in `TOGA_EXIT_CRASH_WORKAROUND.md`
- **Windows Build Automation**: GitHub Actions workflow for automated MSI builds
  - 3-4 minute build time, 90-day artifact retention
  - Automatic release uploads on version tags
- **Comprehensive Documentation**: 983 lines added to CLAUDE.md
  - Build practices and release process
  - Development workflow and best practices
  - Testing, code quality, and performance guidelines
