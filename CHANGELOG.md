# Changelog

All notable changes to Apple Music Play History Converter will be documented in this file.

## [2.0.0] - 2025-10-05

### 🚀 Major Rewrite: Toga GUI Framework

**This release represents a complete architectural rewrite from tkinter to BeeWare's Toga framework for true cross-platform native applications.**

### Added
- **Toga GUI Framework**: Complete migration from tkinter to Toga for modern, native cross-platform UI
- **Ultra-Fast MusicBrainz Search**: New DuckDB-based batch processor with 10,000+ tracks/sec throughput
- **Parallel iTunes Search**: 10 concurrent workers with adaptive rate limiting (up to 600 req/min)
- **Rate-Limited Track Management**: Separate tracking and retry system for iTunes 403 rate limit errors
  - **Retry Button**: Retry all rate-limited tracks after cooldown period
  - **Export Functionality**: Export rate-limited tracks to CSV for manual review
  - **Smart Separation**: Rate-limited tracks (temporary) vs permanently failed tracks
  - **Live Count Updates**: Button shows current count of rate-limited tracks
- **Live Progress Updates**: Real-time log updates during parallel batch searches
- **Thread-Safe Architecture**: Proper async/await patterns with background task management
- **Smart Missing Artist Tracking**: Button updates live as artists are found during search
- **Auto-Save Checkpoints**: Automatic progress saves every 50 tracks during long searches
- **Comprehensive Error Handling**: No silent failures, all errors properly logged and displayed
- **GitHub Actions CI/CD**: Automated Windows builds on push/PR with artifact uploads
- **SmartLogger System**: Centralized logging with feature flags for debugging

### Improved
- **Search Performance**: 100x faster with batch processing vs old row-by-row approach
- **UI Responsiveness**: Fully async UI never freezes during processing
- **Memory Efficiency**: Optimized DataFrame operations with explicit type casting
- **Code Quality**: Removed 1,051 lines of dead code and legacy fallback methods
- **Architecture**: Clean separation between UI thread and background processing threads
- **Database Management**: Better integration with MusicBrainz optimization workflow

### Changed
- **UI Framework**: Migrated from tkinter to Toga/Briefcase
- **Search Strategy**: Batch/parallel processing replaces sequential row-by-row
- **Threading Model**: Background daemon threads with thread-safe UI updates via `asyncio.run_coroutine_threadsafe()`
- **Progress Reporting**: Callback-based live updates instead of post-completion reporting
- **File Structure**: Legacy tkinter code archived to `_history/` folder

### Removed
- **Dead Code Cleanup**: Removed 323 lines of unused row-by-row iTunes methods
- **Legacy Dialogs**: Removed unused `database_dialogs.py` (728 lines)
- **tkinter Dependencies**: All tkinter code moved to archive

### Fixed
- **Critical Threading Bug**: Fixed 38 undefined `self.main_loop` references causing crashes
- **Pandas dtype Warnings**: Added explicit `str()` casts when updating DataFrame cells
- **iTunes Parallel Search**: Fixed missing live log updates during batch processing
- **UI Update Race Conditions**: All UI updates now properly scheduled on main event loop
- **Missing Artist Count**: Button now updates live during parallel searches
- **Network Access in macOS App**: Added missing network entitlements for hardened runtime (fixes "Cannot connect to iTunes API" in packaged builds)
- **SSL Certificate Bundling**: Added explicit certifi dependency to ensure SSL certificates are bundled in packaged apps
- **Debug Logging for Network Issues**: Added comprehensive file-based debug logging to `~/itunes_api_debug.log` with network diagnostics
- **iTunes 403 Forbidden Errors**: iTunes API now returns 403 instead of 429 when rate limited; added detection and adaptive response
- **Conservative Rate Limiting**: Reduced discovery mode from 600 to 120 req/min to prevent 403 blocking
- **iTunes Search Stop Button**: Fixed parallel search threads not respecting stop button clicks
- **App Crash on Exit**: Added graceful shutdown handler to prevent crashes when closing during active searches
- **Rate Limit Row Visibility**: Rate limit controls now only show when iTunes API is selected (hidden for MusicBrainz)
- **Windows Compatibility**: Comprehensive Windows-specific fixes for cross-platform reliability
  - **Event Loop Initialization**: Fixed "no running event loop" error on Windows startup using lazy initialization
  - **MusicBrainz Download**: Fixed Windows temp file handling using `mkstemp()` instead of deprecated `mktemp()`
  - **Cross-Drive File Operations**: Fixed Windows file installation failures using `copy2()` instead of `move()`
  - **MSI Packaging**: Configured GitHub Actions to build proper MSI installers instead of ZIP (avoids "Mark of the Web" DLL blocking)
- **UI Blocking Prevention**: Comprehensive audit and fixes to prevent UI freezing on slow hardware
  - **Large CSV Loading**: File analysis and CSV loading now run in background threads (200k+ rows won't freeze UI)
  - **CSV Save Operations**: All file saves use `run_in_executor()` with progress indicators
  - **Missing Artists Export**: Background threading prevents UI blocking when saving large lists
  - **Rate-Limited Export**: Background threading with detailed progress communication
  - **Progress Indicators**: Added real-time progress messages for all long-running operations
  - **Slow Hardware Support**: Validated on Windows ARM emulation and low-spec computers

### Technical Details
- **Framework**: BeeWare Toga v0.4.0+
- **Event Loop**: Stored reference to Toga's event loop for thread-safe UI updates
- **Background Threads**: 5 daemon threads (artist search, DB optimization, downloads)
- **Batch Processing**: Uses ThreadPoolExecutor for 10 parallel iTunes API workers
- **Rate Limiting**: Adaptive discovery starting at 600 req/min, auto-adjusts to actual limit
- **MusicBrainz**: DuckDB-based search with vectorized pandas operations
- **Cross-Platform**: Full compatibility verified for Windows, macOS, and Linux

### Distribution & Build
- **macOS**: Build locally with code signing & notarization (2 min build time)
- **Windows**: Automated GitHub Actions builds (portable ZIP, x86_64)
- **Linux**: Source code only (users compile from source)
- **CI/CD**: GitHub Actions workflow for Windows with 90-day artifact retention
- **Packaging**: Portable ZIP for Windows (no installer), DMG for macOS

### Migration Benefits
- ✅ True native applications on all platforms
- ✅ 100x faster batch search processing
- ✅ Live progress updates during parallel operations
- ✅ No UI freezing during long operations
- ✅ Proper async/threading architecture
- ✅ Clean, maintainable codebase
- ✅ Better error handling and reporting
- ✅ Enhanced cross-platform compatibility
- ✅ Rate-limited track retry system for resilience
- ✅ Automated Windows builds via CI/CD

---

## [1.3.1] - 2025-08-06

### Fixed
- **Dark Mode Support**: Fixed dark mode detection and proper theme application across all UI components
  - Added `darkdetect` dependency for system theme detection
  - Initialize sv_ttk with proper theme on app startup
  - Remove hardcoded colors and let sv_ttk handle theming
  - Fix URL text visibility in dark mode with theme-aware colors
  - Apply proper theming to all dialog boxes
  - Update tooltips to respect dark mode
  - Maintain theme-adaptive red button styling

### Improved
- **Manual Import Dialog**: Made MusicBrainz download URL clickable for easier access
  - URL now displays in blue with hand cursor on hover
  - Opens directly in default browser when clicked

### Technical
- **Briefcase Build Fix**: Resolved critical tkinter import issue in macOS builds
  - Added manual tkinter module and dynamic library inclusion to build process
  - Fixed `ModuleNotFoundError: No module named 'tkinter'` in packaged apps
  - Documented complete build process with tkinter fixes in CLAUDE.md and README.md
- **Distribution**: Now available as signed ZIP file for easier installation without Gatekeeper warnings

## [1.3.0] - 2025-08-02

### 🚀 Major Migration: PyInstaller → Briefcase

**This release represents a complete rebuild using BeeWare's Briefcase framework for modern, native app packaging.**

### Added
- **Briefcase Integration**: Complete migration from PyInstaller to BeeWare's Briefcase
- **Native App Bundles**: True native applications for macOS, Windows, and Linux
- **Modern Build System**: New `build.py` script with commands: create, build, package, run, dev, clean
- **Enhanced Logging**: Added `std-nslog` support for better macOS debugging
- **Universal macOS Builds**: Automatic Apple Silicon + Intel universal binaries
- **Improved CI/CD**: New GitHub Actions workflow for Briefcase builds
- **Package Structure**: Proper Python package organization under `src/apple_music_history_converter/`

### Improved
- **Build Reliability**: More robust build process with better dependency management
- **Documentation**: Updated all build instructions for Briefcase workflow
- **Code Organization**: Clean separation of source code and build artifacts
- **Cross-Platform Support**: Better Linux support with system package dependencies

### Changed
- **Build Commands**: New unified build system replaces platform-specific scripts
- **Project Structure**: Moved to standard Python package layout with `pyproject.toml`
- **Dependencies**: Streamlined dependency management through Briefcase
- **App Entry Point**: New Briefcase-compatible entry point with enhanced logging

### Removed
- **PyInstaller**: Removed all PyInstaller-specific files (.spec, build scripts)
- **Legacy Build Scripts**: Cleaned up old platform-specific build infrastructure
- **Duplicate Configuration**: Consolidated configuration into `pyproject.toml`

### Technical Details
- **Framework**: BeeWare Briefcase v0.3.24
- **Python Support**: 3.8+ (updated from 3.7+)
- **Bundle ID**: com.nerveband.apple-music-history-converter
- **macOS Signing**: Maintains Developer ID Application support
- **Build Output**: Native DMG for macOS, MSI for Windows, AppImage for Linux

---

## Previous Releases

For release notes prior to v2.0.0, see the legacy changelog in the wiki.
