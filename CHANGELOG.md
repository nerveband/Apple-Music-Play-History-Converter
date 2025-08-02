# Changelog

All notable changes to Apple Music Play History Converter will be documented in this file.

## [3.2.0] - 2025-08-02

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