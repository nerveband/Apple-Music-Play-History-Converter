#!/bin/bash
# Verify macOS build integrity

set -e

echo "🔍 Verifying macOS build..."

APP_PATH="dist/Apple Music History Converter.app"
EXECUTABLE="$APP_PATH/Contents/MacOS/Apple Music History Converter"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: App bundle not found at $APP_PATH"
    exit 1
fi

echo "✅ App bundle exists"

# Check if executable exists
if [ ! -f "$EXECUTABLE" ]; then
    echo "❌ Error: Executable not found at $EXECUTABLE"
    exit 1
fi

echo "✅ Executable exists"

# Check if icon exists
if [ ! -f "$APP_PATH/Contents/Resources/appicon.icns" ]; then
    echo "⚠️  Warning: Icon file not found"
else
    echo "✅ Icon file exists"
fi

# Check executable permissions
if [ ! -x "$EXECUTABLE" ]; then
    echo "❌ Error: Executable is not marked as executable"
    chmod +x "$EXECUTABLE"
    echo "✅ Fixed executable permissions"
else
    echo "✅ Executable has correct permissions"
fi

# Test if the app can start (will timeout after 5 seconds)
echo "🧪 Testing app startup..."
timeout 5 "$EXECUTABLE" 2>&1 | head -20 || true

# Check for common missing dependencies
echo "📦 Checking for embedded Python libraries..."
if otool -L "$EXECUTABLE" | grep -q "libpython"; then
    echo "✅ Python library is linked"
else
    echo "⚠️  Warning: Python library might not be properly linked"
fi

# Check app size
APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo "📏 App size: $APP_SIZE"

# Check for numpy in the bundle
if find "$APP_PATH" -name "*numpy*" -type f | grep -q numpy; then
    echo "✅ NumPy appears to be bundled"
else
    echo "❌ Error: NumPy not found in bundle"
fi

echo "🎉 Verification complete!"