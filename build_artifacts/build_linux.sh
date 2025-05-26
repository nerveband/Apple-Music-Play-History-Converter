#!/bin/bash
# Linux Build Script for Apple Music Play History Converter

set -e  # Exit on any error

echo "🐧 Building Apple Music Play History Converter for Linux..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "📁 Project root: $PROJECT_ROOT"

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "⚠️  Warning: Not running on Linux, but continuing anyway"
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
pyinstaller --clean --noconfirm build_linux.spec

# Verify the build
if [ -f "dist/Apple Music History Converter" ]; then
    echo "✅ Linux build successful!"
    echo "🖥️  Executable location: $PROJECT_ROOT/build_artifacts/dist/Apple Music History Converter"
    
    # Get file size
    EXE_SIZE=$(du -sh "dist/Apple Music History Converter" | cut -f1)
    echo "📏 Executable size: $EXE_SIZE"
    
    # Make executable
    chmod +x "dist/Apple Music History Converter"
    
    # Create tar.gz package
    echo "📦 Creating distribution package..."
    cd dist
    tar -czf "../Apple_Music_History_Converter_Linux.tar.gz" "Apple Music History Converter"
    cd ..
    
    echo "📦 Distribution package: $PROJECT_ROOT/build_artifacts/Apple_Music_History_Converter_Linux.tar.gz"
else
    echo "❌ Build failed - Executable not found"
    exit 1
fi

echo "🎉 Linux build complete!"
