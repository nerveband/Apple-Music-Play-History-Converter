# Changelog

All notable changes to Apple Music Play History Converter will be documented in this file.

## [1.3.1] - 2025-08-06

### Fixed
- **Dark Mode Support**: Fixed dark mode detection and proper theme application across all UI components (fixes #5)
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

### Migration Benefits
- ✅ Native app bundles instead of generic executables
- ✅ Better dependency resolution and management
- ✅ Simplified build process with unified commands
- ✅ Modern Python packaging standards
- ✅ Improved maintainability and future-proofing
- ✅ Enhanced cross-platform compatibility

## [3.2.0] - 2025-08-02 (Legacy PyInstaller)

### Added
- **Apple Developer ID Code Signing**: Full code signing support for macOS builds
- **Apple Notarization**: Complete notarization workflow eliminates all macOS security warnings
- **Professional Distribution**: `Apple_Music_History_Converter_Notarized.zip` for seamless installation
- **Comprehensive Documentation**: Detailed build and code signing documentation in `CLAUDE.md`
- **Automated Certificate Detection**: Build scripts automatically detect and use available Developer ID certificates
- **macOS Entitlements**: Hardened runtime entitlements for modern macOS compatibility
- **Developer Utilities**: Added `sign_app_developer.sh`, `get_team_id.sh`, and `entitlements.plist`

### Improved
- **Repository Structure**: Clean, organized file hierarchy with only essential files
- **Build Process**: Enhanced macOS build with proper app bundle handling using `ditto` instead of `zip`
- **Documentation**: Clear file structure tables and comprehensive build instructions
- **Code Quality**: Removed development artifacts, test files, and unnecessary dependencies

### Changed
- **macOS Distribution**: Now uses fully notarized package instead of ad-hoc signed version
- **Build Scripts**: `build_macos.sh` automatically detects and applies proper code signing
- **File Organization**: Streamlined project structure with clear separation of concerns

### Technical Details
- **Signing Identity**: Developer ID Application: Ashraf Ali (7HQVB2S4BX)
- **Team ID**: 7HQVB2S4BX
- **Bundle ID**: com.nerveband.apple-music-history-converter
- **Notarization**: Submission ID: 9e1544dc-7aef-4297-8aa5-bb61002112a9
- **Distribution**: Uses `ditto -c -k` for proper macOS app bundle preservation

## [3.1.0] - 2025-01-10

### Fixed
- **Critical macOS Build Issue**: Fixed numpy dependency not being properly bundled in macOS builds
- **Application Icon**: Fixed missing/incorrect application icon in macOS builds
- **Build Configuration**: Improved PyInstaller configuration to properly collect all dependencies

### Added
- **Build Verification**: Added verification scripts to ensure build integrity
- **macOS Installation Guide**: Added comprehensive installation instructions for Gatekeeper bypass
- **Icon Support**: Added proper .icns file generation for macOS compatibility

### Changed
- **Build Size**: Increased from 47MB to 63MB to include all required dependencies
- **Build Process**: Enhanced build process with better dependency collection using PyInstaller's collect_all()

### Technical Details
- Updated PyInstaller spec to use `collect_all()` for numpy and pandas
- Removed numpy from excludes list (was causing import errors)
- Added proper .icns icon generation script
- Improved build scripts with better error handling

## [3.0.0] - 2024-12-20

### Added
- Enhanced user experience with improved GUI
- Rate limit management for API calls
- Better error handling and user feedback

## [2.1.1] - 2024-12-15

### Added
- macOS tcl-tk compatibility fixes
- Improved build process

## [2.0.0] - 2024-12-01

### Added
- Dual search provider system (MusicBrainz offline + iTunes API)
- Offline database support for faster searches
- Progress tracking for long operations

## [1.0.0] - 2024-11-01

### Initial Release
- Basic CSV conversion functionality
- Support for multiple Apple Music export formats
- Last.fm compatible output