#!/bin/bash
# Sign macOS app with Apple Developer ID for distribution
# This script will be used after setting up your Apple Developer account

set -e

# Configuration
APP_PATH="dist/Apple Music History Converter.app"
APPLE_ID="nerveband@gmail.com"
BUNDLE_ID="com.nerveband.apple-music-history-converter"
ENTITLEMENTS_FILE="entitlements.plist"

echo "🔏 Signing macOS app for distribution..."

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: App not found at $APP_PATH"
    echo "Please run build_macos.sh first to build the app"
    exit 1
fi

# First, let's find the correct signing identity
echo "🔍 Looking for signing identities..."
IDENTITIES=$(security find-identity -v -p codesigning | grep -E "Developer ID Application|Apple Development" || true)

if [ -z "$IDENTITIES" ]; then
    echo "❌ No signing identities found!"
    echo "Please ensure you have:"
    echo "1. Added your Apple ID ($APPLE_ID) to Xcode"
    echo "2. Downloaded your Developer ID Application certificate"
    echo "3. Your certificates are in the Keychain"
    exit 1
fi

echo "Available signing identities:"
echo "$IDENTITIES"

# Try to auto-detect the Developer ID
DEVELOPER_ID=$(echo "$IDENTITIES" | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}' || true)

# If no Developer ID, try Apple Development certificate
if [ -z "$DEVELOPER_ID" ]; then
    DEVELOPER_ID=$(echo "$IDENTITIES" | grep "Apple Development" | head -1 | awk -F'"' '{print $2}' || true)
fi

if [ -z "$DEVELOPER_ID" ]; then
    echo "❌ Could not auto-detect signing identity"
    echo "Please manually set DEVELOPER_ID in this script"
    exit 1
fi

echo "✅ Using signing identity: $DEVELOPER_ID"

# Remove any existing signatures
echo "🧹 Removing existing signatures..."
codesign --remove-signature "$APP_PATH" 2>/dev/null || true

# Sign all frameworks and dylibs first
echo "📝 Signing frameworks and libraries..."
find "$APP_PATH" -name "*.dylib" -o -name "*.so" | while read -r lib; do
    echo "  Signing: $(basename "$lib")"
    codesign --force --sign "$DEVELOPER_ID" "$lib" 2>/dev/null || true
done

# Sign the main app bundle with hardened runtime
echo "📝 Signing main app bundle..."
codesign --deep --force --verify --verbose \
    --sign "$DEVELOPER_ID" \
    --options runtime \
    --entitlements "$ENTITLEMENTS_FILE" \
    --timestamp \
    "$APP_PATH"

# Verify the signature
echo "🔍 Verifying signature..."
if codesign --verify --deep --strict --verbose=2 "$APP_PATH"; then
    echo "✅ Signature verification passed!"
else
    echo "⚠️  Signature verification had warnings (this may be normal)"
fi

# Check if the app will pass Gatekeeper
echo "🔍 Checking Gatekeeper assessment..."
if spctl -a -t exec -vv "$APP_PATH" 2>&1 | grep -q "accepted"; then
    echo "✅ App should pass Gatekeeper!"
else
    echo "⚠️  Gatekeeper assessment unclear - may need notarization"
fi

# Create a zip for distribution
echo "📦 Creating distribution package..."
cd "$(dirname "$APP_PATH")"
APP_NAME="$(basename "$APP_PATH")"
ZIP_NAME="../Apple_Music_History_Converter_Signed.zip"
rm -f "$ZIP_NAME"
ditto -c -k --keepParent "$APP_NAME" "$ZIP_NAME"
cd - > /dev/null

echo ""
echo "🎉 App signing complete!"
echo "📦 Signed app: $APP_PATH"
echo "📦 Distribution package: $(dirname "$APP_PATH")/$ZIP_NAME"
echo ""
echo "Next steps for full distribution:"
echo "1. Test the app on another Mac to ensure it opens without security warnings"
echo "2. For wider distribution, consider notarizing the app with Apple"
echo "   Run: xcrun notarytool submit <zip-file> --apple-id $APPLE_ID --team-id <YOUR-TEAM-ID> --wait"
echo "3. After notarization, staple the ticket:"
echo "   Run: xcrun stapler staple '$APP_PATH'"