#!/bin/bash
# Simple build script for local development
# For full release workflow, see RELEASE_WORKFLOW.md

set -e

echo "🔨 Building Apple Music History Converter..."

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Create app structure
echo "Creating app structure..."
briefcase create macOS

# Build app
echo "Building app..."
briefcase build macOS

# Package (choose one option)
echo ""
echo "Build complete! Choose packaging option:"
echo ""
echo "1) Ad-hoc signing (for testing only):"
echo "   briefcase package macOS --adhoc-sign"
echo ""
echo "2) Full signing + notarization (for distribution):"
echo "   briefcase package macOS --identity \"Developer ID Application: Ashraf Ali (7HQVB2S4BX)\""
echo ""
echo "3) Run without packaging:"
echo "   briefcase run macOS"
echo ""

read -p "Enter choice (1/2/3) or press Enter to skip packaging: " choice

case $choice in
    1)
        echo "Packaging with ad-hoc signing..."
        briefcase package macOS --adhoc-sign
        echo "✅ Build complete: dist/Apple Music History Converter-*.dmg"
        ;;
    2)
        echo "Packaging with full signing and notarization..."
        briefcase package macOS --identity "Developer ID Application: Ashraf Ali (7HQVB2S4BX)"
        echo "✅ Build complete and notarized: dist/Apple Music History Converter-*.dmg"
        ;;
    3)
        echo "Running app..."
        briefcase run macOS
        ;;
    *)
        echo "✅ Build complete without packaging"
        echo "App location: build/apple-music-history-converter/macos/app/Apple Music History Converter.app"
        ;;
esac
