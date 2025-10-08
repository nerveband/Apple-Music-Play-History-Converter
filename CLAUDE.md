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

## Current Status (v2.0.0)

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

### Latest Release
- **Version**: 2.0.0 (October 4, 2025)
- **Status**: Production ready, fully signed and notarized
- **Test Coverage**: 44/44 tests passing
- **Performance**: Handles 253,525 rows efficiently with 10,000+ tracks/sec search speed
