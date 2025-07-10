#!/bin/bash
# macOS Build Script for Apple Music Play History Converter

set -e  # Exit on any error

echo "🍎 Building Apple Music Play History Converter for macOS..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "📁 Project root: $PROJECT_ROOT"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  Warning: Not running on macOS, but continuing anyway"
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build_artifacts/build
rm -rf build_artifacts/dist
rm -f build_artifacts/*.zip

# Build the application
echo "🏗️  Building application..."
cd build_artifacts
pyinstaller --clean --noconfirm build_macos.spec

# Verify the build
if [ -d "dist/Apple Music History Converter.app" ]; then
    echo "✅ macOS build successful!"
    echo "📱 App location: $PROJECT_ROOT/build_artifacts/dist/Apple Music History Converter.app"
    
    # Get app size
    APP_SIZE=$(du -sh "dist/Apple Music History Converter.app" | cut -f1)
    echo "📏 App size: $APP_SIZE"
    
    # Ad-hoc sign the app bundle (required for proper launch)
    echo "🔐 Signing app bundle..."
    codesign --force --deep --sign - "dist/Apple Music History Converter.app"
    
    # Create zip package
    echo "📦 Creating distribution package..."
    cd dist
    zip -r "../Apple_Music_History_Converter_macOS.zip" "Apple Music History Converter.app"
    cd ..
    
    echo "📦 Distribution package: $PROJECT_ROOT/build_artifacts/Apple_Music_History_Converter_macOS.zip"
else
    echo "❌ Build failed - App not found"
    exit 1
fi

echo "🎉 macOS build complete!"
