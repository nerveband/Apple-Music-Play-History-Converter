#!/bin/bash
# Sign and notarize macOS app for distribution

set -e

# Configuration
APP_PATH="dist/Apple Music History Converter.app"
DEVELOPER_ID="Developer ID Application: YOUR_NAME (TEAM_ID)"  # Update this
BUNDLE_ID="com.nerveband.apple-music-history-converter"
ENTITLEMENTS_FILE="entitlements.plist"

echo "🔏 Signing macOS app..."

# Create entitlements file if it doesn't exist
if [ ! -f "$ENTITLEMENTS_FILE" ]; then
    cat > "$ENTITLEMENTS_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
EOF
fi

# Sign the app
echo "Signing with identity: $DEVELOPER_ID"
codesign --deep --force --verify --verbose \
    --sign "$DEVELOPER_ID" \
    --options runtime \
    --entitlements "$ENTITLEMENTS_FILE" \
    "$APP_PATH"

# Verify the signature
echo "🔍 Verifying signature..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "✅ App signed successfully!"

# Create a zip for notarization
echo "📦 Creating zip for notarization..."
ditto -c -k --keepParent "$APP_PATH" "Apple_Music_History_Converter.zip"

# Notarize the app
echo "📝 Notarizing app with Apple..."
xcrun notarytool submit "Apple_Music_History_Converter.zip" \
    --apple-id "your-apple-id@example.com" \
    --password "your-app-specific-password" \
    --team-id "YOUR_TEAM_ID" \
    --wait

# Staple the notarization
echo "📌 Stapling notarization..."
xcrun stapler staple "$APP_PATH"

echo "🎉 App is signed and notarized!"