#!/bin/bash
# Test Build Script for Apple Music History Converter
# Tests local builds for macOS, Windows, and Linux before pushing to CI/CD

set -e  # Exit on error

echo "=================================================="
echo "Apple Music History Converter - Local Build Test"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    BRIEFCASE_PLATFORM="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="Linux"
    BRIEFCASE_PLATFORM="linux"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    PLATFORM="Windows"
    BRIEFCASE_PLATFORM="windows"
else
    echo -e "${RED}✗ Unsupported platform: $OSTYPE${NC}"
    exit 1
fi

echo -e "${BLUE}Detected Platform: $PLATFORM${NC}"
echo ""

# Check if briefcase is installed
if ! command -v briefcase &> /dev/null; then
    echo -e "${RED}✗ Briefcase not found. Installing...${NC}"
    pip install briefcase
fi

# Check if credentials are set up (macOS only)
if [[ "$PLATFORM" == "macOS" ]]; then
    echo -e "${YELLOW}Checking macOS code signing setup...${NC}"

    # Check for .env file
    if [ -f ".env" ]; then
        echo -e "${GREEN}✓ .env file found${NC}"
        source .env

        if [ -z "$APPLE_ID" ] || [ -z "$APPLE_TEAM_ID" ] || [ -z "$APPLE_APP_SPECIFIC_PASSWORD" ]; then
            echo -e "${RED}✗ Missing credentials in .env file${NC}"
            echo "Required: APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD"
            exit 1
        fi
        echo -e "${GREEN}✓ Credentials loaded from .env${NC}"
    else
        echo -e "${YELLOW}⚠ No .env file found - notarization will be skipped${NC}"
    fi

    # Check for Developer ID certificate
    if security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
        echo -e "${GREEN}✓ Developer ID Application certificate found${NC}"
    else
        echo -e "${RED}✗ No Developer ID Application certificate found in Keychain${NC}"
        echo "Please install your certificate before building"
        exit 1
    fi
    echo ""
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
if [ -d "build" ]; then
    rm -rf build
    echo -e "${GREEN}✓ Cleaned build directory${NC}"
fi
if [ -d "dist" ]; then
    rm -rf dist
    echo -e "${GREEN}✓ Cleaned dist directory${NC}"
fi
echo ""

# Step 1: Create
echo -e "${BLUE}Step 1: Creating Briefcase app structure...${NC}"
briefcase create $BRIEFCASE_PLATFORM
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Create successful${NC}"
else
    echo -e "${RED}✗ Create failed${NC}"
    exit 1
fi
echo ""

# Step 2: Build
echo -e "${BLUE}Step 2: Building app...${NC}"
briefcase build $BRIEFCASE_PLATFORM
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi
echo ""

# Step 3: Package (platform-specific)
echo -e "${BLUE}Step 3: Packaging app...${NC}"

if [[ "$PLATFORM" == "macOS" ]]; then
    echo "Packaging macOS app with code signing and notarization..."
    echo ""

    # Check if we should attempt notarization
    if [ -f ".env" ]; then
        # Store notarization credentials
        echo "Storing notarization credentials..."
        xcrun notarytool store-credentials "briefcase-macOS-$APPLE_TEAM_ID" \
          --apple-id "$APPLE_ID" \
          --team-id "$APPLE_TEAM_ID" \
          --password "$APPLE_APP_SPECIFIC_PASSWORD" 2>/dev/null || true

        echo ""
        echo "Building DMG with signing and notarization..."
        briefcase package macOS \
          --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
    else
        echo "Building DMG with ad-hoc signing (no notarization)..."
        briefcase package macOS --adhoc-sign
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Package successful${NC}"

        # Find the DMG
        DMG_FILE=$(find dist -name "*.dmg" | head -1)
        if [ -n "$DMG_FILE" ]; then
            echo -e "${GREEN}✓ DMG created: $DMG_FILE${NC}"
            echo ""
            echo "File size: $(du -h "$DMG_FILE" | cut -f1)"

            # Verify signature
            echo ""
            echo "Verifying signature..."
            APP_PATH=$(find build -name "*.app" | head -1)
            codesign -vvv "$APP_PATH"

            echo ""
            echo "Checking notarization status..."
            spctl -a -t exec -vv "$APP_PATH" || echo "Note: App may not be notarized (expected if using ad-hoc signing)"
        fi
    else
        echo -e "${RED}✗ Package failed${NC}"
        exit 1
    fi

elif [[ "$PLATFORM" == "Linux" ]]; then
    echo "Building Linux AppImage..."
    briefcase package linux appimage --no-input

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ AppImage package successful${NC}"
    else
        echo -e "${YELLOW}⚠ AppImage failed, trying system package...${NC}"
        briefcase package linux system --no-input
    fi

    # Find the package
    PACKAGE_FILE=$(find dist -name "*.AppImage" -o -name "*.deb" -o -name "*.rpm" -o -name "*.tar.gz" | head -1)
    if [ -n "$PACKAGE_FILE" ]; then
        echo -e "${GREEN}✓ Package created: $PACKAGE_FILE${NC}"
        echo "File size: $(du -h "$PACKAGE_FILE" | cut -f1)"
    fi

elif [[ "$PLATFORM" == "Windows" ]]; then
    echo "Building Windows installer..."
    briefcase package windows --adhoc-sign --no-input

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Package successful${NC}"

        # Find the installer
        INSTALLER_FILE=$(find dist -name "*.msi" -o -name "*.exe" | head -1)
        if [ -n "$INSTALLER_FILE" ]; then
            echo -e "${GREEN}✓ Installer created: $INSTALLER_FILE${NC}"
            echo "File size: $(du -h "$INSTALLER_FILE" | cut -f1)"
        fi
    else
        echo -e "${RED}✗ Package failed${NC}"
        exit 1
    fi
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✓ BUILD TEST COMPLETE${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Test the built application manually"
if [[ "$PLATFORM" == "macOS" ]]; then
    echo "2. If notarization succeeded, verify with:"
    echo "   spctl -a -t exec -vv \"<path-to-app>\""
    echo "3. Test on a different Mac to ensure it runs without warnings"
fi
echo "4. If everything works, push to GitHub and create a release tag"
echo ""
echo "Build artifacts location:"
echo "  - App bundle: build/"
echo "  - Installer: dist/"
echo ""
