#!/bin/bash
# Build All Platforms - Local Build Script
# Builds macOS, Windows, and Linux versions locally for manual upload to GitHub Releases

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Apple Music History Converter - Multi-Platform Builder    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect current platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    CURRENT_PLATFORM="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CURRENT_PLATFORM="Linux"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    CURRENT_PLATFORM="Windows"
else
    echo -e "${RED}✗ Unsupported platform: $OSTYPE${NC}"
    exit 1
fi

echo -e "${BLUE}Current Platform: $CURRENT_PLATFORM${NC}"
echo ""

# Parse command line arguments
BUILD_MACOS=false
BUILD_WINDOWS=false
BUILD_LINUX=false
BUILD_ALL=false

if [ $# -eq 0 ]; then
    echo -e "${YELLOW}No platform specified. Building for current platform only.${NC}"
    case $CURRENT_PLATFORM in
        "macOS") BUILD_MACOS=true ;;
        "Linux") BUILD_LINUX=true ;;
        "Windows") BUILD_WINDOWS=true ;;
    esac
else
    for arg in "$@"; do
        case $arg in
            macos|macOS) BUILD_MACOS=true ;;
            windows|Windows) BUILD_WINDOWS=true ;;
            linux|Linux) BUILD_LINUX=true ;;
            all) BUILD_ALL=true ;;
            *)
                echo -e "${RED}Unknown platform: $arg${NC}"
                echo "Usage: $0 [macos] [windows] [linux] [all]"
                exit 1
                ;;
        esac
    done
fi

if [ "$BUILD_ALL" = true ]; then
    BUILD_MACOS=true
    BUILD_WINDOWS=true
    BUILD_LINUX=true
fi

echo -e "${BLUE}Platforms to build:${NC}"
[ "$BUILD_MACOS" = true ] && echo "  ✓ macOS"
[ "$BUILD_WINDOWS" = true ] && echo "  ✓ Windows"
[ "$BUILD_LINUX" = true ] && echo "  ✓ Linux"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2)${NC}"

# Check Briefcase
if ! command -v briefcase &> /dev/null; then
    echo -e "${YELLOW}⚠ Briefcase not found. Installing...${NC}"
    pip install briefcase
fi
echo -e "${GREEN}✓ Briefcase $(briefcase --version 2>&1 | head -1)${NC}"

echo ""

# Create release directory
RELEASE_DIR="release_builds"
mkdir -p "$RELEASE_DIR"
echo -e "${GREEN}✓ Release directory: $RELEASE_DIR/${NC}"
echo ""

# Function to build for a platform
build_platform() {
    local platform=$1
    local platform_name=$2

    echo -e "${CYAN}"
    echo "════════════════════════════════════════════════════════════"
    echo "  Building for $platform_name"
    echo "════════════════════════════════════════════════════════════"
    echo -e "${NC}"

    # Clean previous build
    echo -e "${YELLOW}Cleaning previous $platform_name build...${NC}"
    if [ -d "build/apple-music-history-converter/$platform" ]; then
        rm -rf "build/apple-music-history-converter/$platform"
    fi

    # Create
    echo -e "${BLUE}Step 1/3: Creating app structure...${NC}"
    briefcase create $platform

    # Build
    echo -e "${BLUE}Step 2/3: Building app...${NC}"
    briefcase build $platform

    # Package
    echo -e "${BLUE}Step 3/3: Packaging app...${NC}"

    case $platform in
        macOS)
            # Check for signing credentials
            if [ -f ".env" ]; then
                source .env
                if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ] && [ -n "$APPLE_APP_SPECIFIC_PASSWORD" ]; then
                    echo -e "${GREEN}✓ Signing credentials found, will sign and notarize${NC}"

                    # Store notarization credentials
                    xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
                      --apple-id "$APPLE_ID" \
                      --team-id "$APPLE_TEAM_ID" \
                      --password "$APPLE_APP_SPECIFIC_PASSWORD" 2>/dev/null || true

                    # Build with signing and notarization
                    briefcase package macOS \
                      --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
                else
                    echo -e "${YELLOW}⚠ Incomplete credentials, using ad-hoc signing${NC}"
                    briefcase package macOS --adhoc-sign
                fi
            else
                echo -e "${YELLOW}⚠ No .env file, using ad-hoc signing${NC}"
                briefcase package macOS --adhoc-sign
            fi

            # Find and copy DMG
            DMG_FILE=$(find dist -name "*.dmg" 2>/dev/null | head -1)
            if [ -n "$DMG_FILE" ]; then
                cp "$DMG_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_macOS.dmg"
                echo -e "${GREEN}✓ DMG created: $RELEASE_DIR/Apple_Music_History_Converter_macOS.dmg${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_macOS.dmg" | cut -f1)${NC}"

                # Verify signature
                APP_PATH=$(find build -name "*.app" | head -1)
                echo ""
                echo -e "${YELLOW}Verifying signature...${NC}"
                codesign -vvv "$APP_PATH" 2>&1 | head -5

                echo ""
                echo -e "${YELLOW}Checking notarization...${NC}"
                spctl -a -t exec -vv "$APP_PATH" 2>&1 || echo -e "${YELLOW}Note: Not notarized (expected with ad-hoc signing)${NC}"
            fi
            ;;

        windows)
            # Build Windows installer
            briefcase package windows --adhoc-sign --no-input

            # Find MSI or EXE
            MSI_FILE=$(find dist -name "*.msi" 2>/dev/null | head -1)
            EXE_FILE=$(find dist -name "*.exe" 2>/dev/null | head -1)

            if [ -n "$MSI_FILE" ]; then
                cp "$MSI_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_Windows.msi"
                echo -e "${GREEN}✓ MSI created: $RELEASE_DIR/Apple_Music_History_Converter_Windows.msi${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Windows.msi" | cut -f1)${NC}"
            elif [ -n "$EXE_FILE" ]; then
                cp "$EXE_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_Windows.exe"
                echo -e "${GREEN}✓ EXE created: $RELEASE_DIR/Apple_Music_History_Converter_Windows.exe${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Windows.exe" | cut -f1)${NC}"
            fi
            ;;

        linux)
            # Build AppImage
            echo -e "${BLUE}Building AppImage...${NC}"
            briefcase package linux appimage --no-input || echo -e "${YELLOW}⚠ AppImage build failed, trying system package...${NC}"

            APPIMAGE=$(find dist -name "*.AppImage" 2>/dev/null | head -1)
            if [ -n "$APPIMAGE" ]; then
                cp "$APPIMAGE" "$RELEASE_DIR/Apple_Music_History_Converter_Linux.AppImage"
                chmod +x "$RELEASE_DIR/Apple_Music_History_Converter_Linux.AppImage"
                echo -e "${GREEN}✓ AppImage created: $RELEASE_DIR/Apple_Music_History_Converter_Linux.AppImage${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Linux.AppImage" | cut -f1)${NC}"
            fi

            # Build system package
            echo ""
            echo -e "${BLUE}Building system package...${NC}"
            briefcase package linux system --no-input || true

            # Find system package
            DEB_FILE=$(find dist -name "*.deb" 2>/dev/null | head -1)
            RPM_FILE=$(find dist -name "*.rpm" 2>/dev/null | head -1)
            TAR_FILE=$(find dist -name "*.tar.gz" 2>/dev/null | head -1)

            if [ -n "$DEB_FILE" ]; then
                cp "$DEB_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_Linux.deb"
                echo -e "${GREEN}✓ DEB created: $RELEASE_DIR/Apple_Music_History_Converter_Linux.deb${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Linux.deb" | cut -f1)${NC}"
            elif [ -n "$RPM_FILE" ]; then
                cp "$RPM_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_Linux.rpm"
                echo -e "${GREEN}✓ RPM created: $RELEASE_DIR/Apple_Music_History_Converter_Linux.rpm${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Linux.rpm" | cut -f1)${NC}"
            elif [ -n "$TAR_FILE" ]; then
                cp "$TAR_FILE" "$RELEASE_DIR/Apple_Music_History_Converter_Linux.tar.gz"
                echo -e "${GREEN}✓ TAR.GZ created: $RELEASE_DIR/Apple_Music_History_Converter_Linux.tar.gz${NC}"
                echo -e "${GREEN}  Size: $(du -h "$RELEASE_DIR/Apple_Music_History_Converter_Linux.tar.gz" | cut -f1)${NC}"
            fi
            ;;
    esac

    echo ""
}

# Build for selected platforms
if [ "$BUILD_MACOS" = true ]; then
    if [ "$CURRENT_PLATFORM" != "macOS" ]; then
        echo -e "${YELLOW}⚠ Warning: Building macOS on $CURRENT_PLATFORM may not work properly${NC}"
        echo -e "${YELLOW}  Recommendation: Build macOS apps on a Mac${NC}"
        echo ""
    fi
    build_platform "macOS" "macOS"
fi

if [ "$BUILD_WINDOWS" = true ]; then
    if [ "$CURRENT_PLATFORM" != "Windows" ]; then
        echo -e "${YELLOW}⚠ Warning: Building Windows on $CURRENT_PLATFORM may not work properly${NC}"
        echo -e "${YELLOW}  Recommendation: Build Windows apps on Windows${NC}"
        echo ""
    fi
    build_platform "windows" "Windows"
fi

if [ "$BUILD_LINUX" = true ]; then
    if [ "$CURRENT_PLATFORM" != "Linux" ]; then
        echo -e "${YELLOW}⚠ Warning: Building Linux on $CURRENT_PLATFORM may not work properly${NC}"
        echo -e "${YELLOW}  Recommendation: Build Linux apps on Linux${NC}"
        echo ""
    fi
    build_platform "linux" "Linux"
fi

# Summary
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    BUILD COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}All builds completed successfully!${NC}"
echo ""
echo -e "${BLUE}Release artifacts:${NC}"
ls -lh "$RELEASE_DIR"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test each build on the target platform"
if [ "$BUILD_MACOS" = true ]; then
    echo "   - macOS: Test on a different Mac to verify signing/notarization"
fi
if [ "$BUILD_WINDOWS" = true ]; then
    echo "   - Windows: Test SmartScreen bypass process"
fi
if [ "$BUILD_LINUX" = true ]; then
    echo "   - Linux: Test AppImage on Ubuntu, Fedora, Arch"
fi
echo ""
echo "2. Create a new GitHub Release:"
echo "   - Go to https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/new"
echo "   - Create a new tag (e.g., v1.4.0)"
echo "   - Upload all files from: $RELEASE_DIR/"
echo "   - Add release notes (see docs/RELEASE_NOTES_TEMPLATE.md)"
echo ""
echo "3. Publish the release!"
echo ""
