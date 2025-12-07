# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Apple Music Play History Converter is a Python-based desktop application that converts Apple Music CSV files into Last.fm compatible format. Built with Toga/Briefcase for cross-platform support, featuring dual music search: MusicBrainz (offline database, ~2GB) and iTunes API (online).

## Key Commands

```bash
# Running
python run_toga_app.py    # Run Toga application
briefcase dev             # Development mode
briefcase run             # Run built app

# Testing
python -m pytest tests_toga/ -v                    # All tests
python -m pytest tests_toga/test_security.py       # Specific category
python -m pytest tests_toga/ -k "test_csv"         # Pattern match

# Building
python build.py clean && python build.py create && python build.py build
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# Debug
python debug_music_search.py   # Test music search
python debug_csv.py             # Test CSV processing
```

## Architecture

### Core Components (src/apple_music_history_converter/)
- **App** (`app.py`): Briefcase entry point
- **AppleMusicConverterApp** (`apple_music_play_history_converter.py`): Main Toga UI
- **MusicSearchServiceV2** (`music_search_service_v2.py`): Routes between MusicBrainz/iTunes
- **MusicBrainzManagerV2** (`musicbrainz_manager_v2.py`): DuckDB database manager
- **OptimizationModal** (`optimization_modal.py`): Async optimization workflow

### Search Provider System
1. **MusicBrainz**: Offline DuckDB database (~2GB), 1-5ms searches
2. **iTunes API**: Online fallback, 20 requests/minute limit

**Rate Limit Tracking**: iTunes API 403 errors stored separately for retry. Rate-limited tracks shown in UI with retry button. Implementation: `music_search_service_v2.py:540-546`, `apple_music_play_history_converter.py:6142-6153,6817-6861`.

### Data Flow
CSV parsing → encoding detection → file type detection → artist/track lookup → timestamp calculation → Last.fm CSV export

### Threading Model
Main UI thread for Toga, background threads for processing/API calls, queue-based progress reporting, async/await patterns.

## Logging System

**SmartLogger** provides feature-flag controlled logging with zero overhead when disabled (<0.01ms for 10k calls).

### Configuration
Edit `~/Library/Application Support/AppleMusicConverter/settings.json`:
```json
{
  "logging": {
    "enabled": false,        // Master switch (false for production)
    "file_logging": false,   // Write to files
    "console_logging": true, // Print to console
    "level": "WARNING",      // DEBUG, INFO, WARNING, ERROR, CRITICAL
    "use_emoji": false
  }
}
```

### Usage Patterns
```python
from apple_music_history_converter.logging_config import get_logger
logger = get_logger(__name__)

# Developer-facing (only when enabled=true)
logger.debug("Cache hit: {key}")
logger.info("MusicBrainz initialized")
logger.error(f"API call failed: {e}")

# User-facing (ALWAYS prints)
logger.print_always("✅ Processing completed!")
logger.print_always("=" * 80)
```

**Migration Rule**: User-facing messages → `print_always()`, developer-facing → `debug/info/warning/error()`

**Log Locations**: macOS: `~/Library/Logs/AppleMusicConverter/`, Windows: `%LOCALAPPDATA%\AppleMusicConverter\Logs\`

## File Processing & Database

### CSV Format Support
- **Play Activity**: Standard Apple Music export
- **Recently Played Tracks**: Alternative export
- **Play History Daily Tracks**: Daily aggregated format

Auto-detection via filename patterns and column structure. Supports UTF-8, Latin-1, Windows-1252 with automatic detection.

### MusicBrainz Integration
- Downloads canonical data (.tar.zst, ~2GB compressed)
- DuckDB for fast CSV querying without database building
- Automatic version discovery, manual import support
- Settings in `~/.apple_music_converter/settings.json`

## Testing

**Test Suite**: 44 tests (100% passing) in `tests_toga/` covering basic functionality, real CSV files, security, memory efficiency, data quality.

```bash
python -m pytest tests_toga/ -v              # All tests
python -m pytest tests_toga/ --cov=src       # With coverage
```

**Test Coverage Goals**: 70% minimum, 80%+ for business logic, 100% for critical paths (CSV parsing, music search, export).

**Test Data Policy**: NEVER use mock data or hardcoded test values. Always use real test CSV files from `_test_csvs/` directory. Tests should load actual track/artist/album data from these CSVs rather than inventing fake data like "Blinding Lights" or "The Weeknd". Available test CSVs contain real play history (Joe Hisaishi, Memory Tapes, Matchbox Twenty, etc.).

## Testing Infrastructure (Programmatic UI Testing)

Feature-flagged infrastructure for programmatic UI testing with zero overhead when disabled.

### Enabling Test Mode

```bash
# CLI (recommended)
python run_toga_app.py --test-mode              # Enable testing
python run_toga_app.py --test-mode --test-verbose  # With verbose logging

# Environment variable
TEST_MODE=1 python run_toga_app.py
TEST_MODE=1 TEST_VERBOSE=1 python run_toga_app.py

# Settings file (~/Library/Application Support/AppleMusicConverter/settings.json)
{
  "testing": {
    "enabled": true,
    "log_actions": true,
    "log_state": true,
    "verbose": false
  }
}
```

### Core Components

- **TestHarness** (`test_harness.py`): Programmatic control interface
- **WidgetRegistry**: Auto-discovers all Toga widgets via introspection
- **Injection Points**: File dialog bypass without mocking

### TestHarness API

Access via `app.test` property (only available when testing enabled):

```python
# Widget Access
app.test.get_widget("search_button")       # Get any widget by name
app.test.get_button("search_button")       # Get typed button
app.test.get_switch("use_musicbrainz")     # Get typed switch

# Actions (trigger real widget behavior)
app.test.press_button("search_button")     # Press button
app.test.set_switch("use_musicbrainz", True)  # Toggle switch
app.test.set_text("artist_input", "Beatles")  # Set text input
app.test.select_option("format_select", "CSV") # Select dropdown

# State Queries
app.test.get_widget_value("artist_input")  # Get current value
app.test.is_enabled("search_button")       # Check if enabled
app.test.is_visible("progress_bar")        # Check visibility
app.test.get_state()                       # Snapshot all widget states

# Assertions
app.test.assert_enabled("search_button")   # Raises if disabled
app.test.assert_disabled("stop_button")    # Raises if enabled
app.test.assert_value("status_label", "Ready")  # Check value

# Human Handoff
response = app.test.wait_for_human("Please verify the UI looks correct")
# Pauses execution, prints message, waits for human input, returns response
```

### Widget Naming Conventions

Widgets discovered via Python attribute introspection. Names match instance variable names in `AppleMusicConverterApp`:

| Widget Type | Example Names |
|-------------|---------------|
| Buttons | `browse_button`, `convert_button`, `save_button` |
| Switches | `use_musicbrainz_switch`, `use_itunes_switch` |
| Text Inputs | `file_path_input`, `artist_filter_input` |
| Labels | `status_label`, `progress_label` |
| Tables | `results_table`, `tracks_table` |

List all available widgets:
```python
app.test.registry.list_all()      # All widget names
app.test.registry.list_buttons()  # Just buttons
app.test.registry.list_switches() # Just switches
```

### File Dialog Injection

Bypass OS file dialogs by injecting paths directly (no mocking):

```python
# Browse file - inject path instead of showing dialog
await app.browse_file(widget=None, injected_path="/path/to/test.csv")

# Save file - inject path instead of showing dialog
await app.save_results(widget=None, injected_path="/path/to/output.csv")
```

### Test Logging Methods

SmartLogger extended with test-specific methods:

```python
from apple_music_history_converter.logging_config import get_logger
logger = get_logger(__name__)

# Log widget interactions (when log_actions=true)
logger.test_action("Button pressed: search_button")

# Log state snapshots (when log_state=true)
logger.test_state({"enabled": True, "value": "test"}, label="search_button")

# Verbose details (when verbose=true)
logger.test_verbose("Internal cache hit for key: abc123")
```

### Usage Example

```python
import asyncio
from apple_music_history_converter.apple_music_play_history_converter import main

# Start app in test mode (set TEST_MODE=1 first)
app = main()

# Access test harness
harness = app.test

# List available widgets
print(harness.registry.list_buttons())

# Simulate user workflow
await app.browse_file(None, injected_path="test_data/sample.csv")
harness.press_button("convert_button")

# Wait and check state
await asyncio.sleep(2)
harness.assert_enabled("save_button")

# Human verification
harness.wait_for_human("Check that results table shows 100 rows")

# Save results
await app.save_results(None, injected_path="output/result.csv")
```

### Zero Overhead Guarantee

When `testing.enabled=false` (default):
- No widget registry created
- No action/state logging
- TestHarness not initialized
- `app.test` raises `TestingNotEnabledError`
- Performance overhead: <0.01ms

### Testing Modes

Two testing modes are available:

**Visual Mode (PREFERRED)** - Run the app with visible GUI:
```bash
# Launch app with test mode - GUI is visible
python run_toga_app.py --test-mode

# Or with environment variable
TEST_MODE=1 python run_toga_app.py
```
- User can watch the app respond to actions
- Useful for debugging UI/UX issues
- Human can verify visual correctness
- Test harness available inside the running app

**Headless Mode** - Programmatic testing without GUI:
```python
# Create app and call startup() but NOT main_loop()
app = main()
app.startup()  # Creates widgets
harness = app.test  # Access test harness
# main_loop() NOT called - no window shown
```
- Faster execution for CI/CD pipelines
- No GUI overhead
- Good for automated regression testing
- Cannot verify visual appearance

**Priority**: Visual mode is preferred for development testing. Headless mode is for automated CI/CD only.

## Build System

### macOS Build Process

**Prerequisites**: Xcode, Apple Developer Program, Developer ID certificate, app-specific password in `.env`

**Build Steps**:
```bash
python build.py clean && python build.py create && python build.py build
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
spctl -a -t exec -vv "dist/Apple Music History Converter-2.0.2.dmg"  # Verify
```

**Output**: `build/.../macos/app/`, `dist/Apple Music History Converter-2.0.2.dmg`

**Common Issues**:
- Certificate not found → Add Apple ID to Xcode → Accounts → Manage Certificates
- Notarization rejected → Check pyproject.toml entitlements
- Package damaged → Never use `zip`, always use DMG or `tar -czf`

### Windows Build Process

**Prerequisites**: Python 3.12+, Git, Windows 10/11

**Pull and Setup**:
```cmd
cd C:\path\to\Apple-Music-Play-History-Converter
git fetch origin
git checkout <branch-name>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install briefcase
```

**Build Steps**:
```cmd
briefcase create windows
briefcase build windows
briefcase package windows
```

**Output**: `dist\Apple Music History Converter-2.0.2.msi` (~48-50MB)

**Test Before Packaging** (optional):
```cmd
python -m pytest tests_toga/ -v
briefcase dev  # Run in development mode
```

### Linux Build Process

**No pre-built binaries available**. Linux users must compile from source:

```bash
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_toga_app.py  # Run directly from source
```

For packaged builds, use Briefcase:
```bash
pip install briefcase
briefcase create linux
briefcase build linux
briefcase package linux
```

### Code Signing & Notarization

**Automatic Notarization** (configured in pyproject.toml):
- Signing Identity: `Developer ID Application: Ashraf Ali (7HQVB2S4BX)`
- Team ID: `7HQVB2S4BX`
- Bundle ID: `com.nerveband.apple-music-history-converter`

**One-time Setup**:
```bash
source .env
xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
  --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD"
```

**Manual Signing** (for complex apps with many binaries):
```bash
# Sign all .so/.dylib files
find "build/.../Apple Music History Converter.app" \( -name "*.so" -o -name "*.dylib" \) | \
  while read file; do codesign --force --options runtime --timestamp \
    --sign "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" "$file"; done

# Re-sign app bundle
codesign --force --options runtime --timestamp \
  --entitlements "build/.../Entitlements.plist" \
  --sign "Developer ID Application: Ashraf Ali (7HQVB2S4BX)" \
  "build/.../Apple Music History Converter.app"
```

### Critical: macOS Distribution

**⚠️ NEVER use ZIP for macOS app distribution** - it corrupts code signatures and notarization.

**✅ Use DMG** (primary): `briefcase package` creates properly signed DMG
**✅ Use TAR.GZ** (alternative): `tar -czf "App.tar.gz" "App.app"` preserves signatures
**❌ NEVER use ZIP**: Strips extended attributes, breaks signatures, causes "damaged app" errors

**Verification**: `spctl -a -t exec -vv "App.app"` should show "accepted, source=Notarized Developer ID"

## Release Process

### Version Management
Update 3 locations in `pyproject.toml`:
1. `[project]` → `version = "2.0.3"`
2. `[tool.briefcase]` → `version = "2.0.3"`
3. `[tool.briefcase.app.*.windows]` → `version_triple = "2.0.3"`

Format: `MAJOR.MINOR.PATCH` - MAJOR: breaking changes, MINOR: new features, PATCH: bug fixes

### Release Workflow

**Pre-Release Checklist**:
- [ ] All 44+ tests passing
- [ ] Performance benchmarks met (CSV <5s, MusicBrainz <5ms, iTunes <200ms)
- [ ] Tested on macOS Intel/Apple Silicon, Windows 10/11
- [ ] Version updated in 3 locations
- [ ] Documentation updated

**Release Day**:
```bash
# 1. Build macOS (on Mac)
python build.py clean && python build.py create && python build.py build
briefcase package --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"

# 2. Build Windows (on Windows machine)
git fetch origin && git checkout main
briefcase create windows && briefcase build windows && briefcase package windows

# 3. Commit and tag
git add pyproject.toml && git commit -m "chore: release v2.0.3"
git push origin main && git tag v2.0.3 && git push origin v2.0.3

# 4. Create release
gh release create v2.0.3 --title "v2.0.3 - [Title]" --notes "[Release notes]" \
  "dist/Apple Music History Converter-2.0.3.dmg#macOS DMG Installer (Universal)" \
  "dist/Apple Music History Converter-2.0.3.msi#Windows MSI Installer"
```

**Post-Release**:
- Verify release published: `gh release view v2.0.3`
- Test installers on clean machines
- Monitor GitHub Issues for bug reports

### Rollback Options
1. **Deprecate**: `gh release edit v2.0.3 --prerelease` + update notes with warning
2. **Delete**: `gh release delete v2.0.3 --yes` + `git tag -d v2.0.3` + `git push origin :refs/tags/v2.0.3`
3. **Hotfix**: Branch from tag, fix bug, release v2.0.4

## Development Workflow

### Environment Setup
```bash
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt briefcase pytest pytest-cov
python run_toga_app.py  # Verify
```

### Branch Strategy
- `main`: Production-ready, all releases tagged here
- `feature/name`: New features
- `fix/name`: Bug fixes
- `hotfix/vX.Y.Z`: Critical production fixes

### Commit Standards
Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `style`

Examples:
```bash
git commit -m "feat(csv): add support for Daily Tracks format"
git commit -m "fix(itunes): handle 403 rate limit errors gracefully"
git commit -m "perf(search): optimize MusicBrainz query with index"
```

### Code Quality Checklist
- [ ] All tests pass
- [ ] No debug print statements (use logger)
- [ ] Error handling for external calls
- [ ] Type hints for function signatures
- [ ] Docstrings for public functions
- [ ] No hardcoded paths/credentials
- [ ] Dependencies added to pyproject.toml

### Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| CSV parsing (10k rows) | <5s | ~3s |
| MusicBrainz search | <5ms | ~2ms |
| iTunes API search | <200ms | ~150ms |
| Database optimization | <5min | ~3min |
| App startup | <3s | ~2s |

### Debugging

**Enable Debug Logging**: Edit `~/Library/Application Support/AppleMusicConverter/settings.json` → `enabled: true`, `level: "DEBUG"`

**Common Scenarios**:
```bash
# Network issues
python -c "from src.*.network_diagnostics import run_diagnostics; run_diagnostics(verbose=True)"

# Check logs
tail -f ~/Library/Logs/AppleMusicConverter/apple_music_converter.log
```

**Debug Build Distribution**:
```bash
# Build, sign binaries, create tar.gz (NEVER zip!)
tar -czf "Apple_Music_History_Converter_DEBUG.tar.gz" \
  -C "build/.../macos/app" "Apple Music History Converter.app"
```

### Dependency Management
```bash
# Add dependency
pip install new-package
# Edit pyproject.toml [project] dependencies
python build.py clean && python build.py create  # Test
git add pyproject.toml && git commit -m "chore: add new-package dependency"

# Update dependency
pip install --upgrade package-name
# Test extensively, update pyproject.toml version constraint
```

### Database Migrations
```python
def migrate_database_v2_to_v3(db_path: str):
    """Migrate database schema"""
    conn = duckdb.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= 3: return

    conn.execute("ALTER TABLE tracks ADD COLUMN album_id VARCHAR")
    conn.execute("CREATE INDEX idx_album_tracks ON tracks(album_id)")
    conn.execute("PRAGMA user_version = 3")
    conn.close()
```

## Common Development Tasks

### Adding CSV Format Support
1. Update `detect_file_type()` in `apple_music_play_history_converter.py`
2. Add column mapping in `process_csv_data()`
3. Create tests in `tests_toga/`

### Modifying Search Providers
1. Update routing in `MusicSearchServiceV2`
2. Implement provider methods in manager classes
3. Update settings UI with Toga widgets

### UI Layout Changes
Uses Toga's Pack layout system. Reference `apple_music_play_history_converter.py` for patterns. All dialogs use HIG-compliant Toga widgets.

## Current Status (v2.0.2)

### Production Ready
- **Toga Migration**: Complete (no tkinter dependencies)
- **Test Suite**: 44/44 tests passing (100%)
- **Architecture**: Thread-safe async/await
- **Build System**: Native apps for Windows/macOS/Linux via Briefcase
- **Code Signing**: Full Apple Developer ID signing and notarization
- **Performance**: 10,000+ tracks/sec search speed
- **Stability**: Clean exit on all platforms (GIL crash fixed)
- **Automation**: Windows MSI builds via GitHub Actions

### Latest Release
- **Version**: 2.0.2 (October 8, 2025)
- **Downloads**: [macOS DMG](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/tag/v2.0.2) • [Windows MSI](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/tag/v2.0.2)

### Key Features
- Dual search providers (MusicBrainz offline + iTunes API)
- iTunes rate limit tracking with retry functionality
- SmartLogger system with zero-overhead when disabled
- Automatic CSV format detection and encoding handling
- Universal macOS builds (Apple Silicon + Intel)
- Automated Windows builds via GitHub Actions
