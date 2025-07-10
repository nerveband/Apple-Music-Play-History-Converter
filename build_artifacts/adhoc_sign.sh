#!/bin/bash
# Ad-hoc sign the app (free, but only works on your machine)

set -e

APP_PATH="dist/Apple Music History Converter.app"

echo "🔏 Ad-hoc signing macOS app..."

# Remove any existing signatures
codesign --remove-signature "$APP_PATH" 2>/dev/null || true

# Ad-hoc sign (using "-" means ad-hoc)
codesign --force --deep --sign - "$APP_PATH"

echo "✅ App is ad-hoc signed!"
echo "⚠️  Note: This only removes Gatekeeper warnings on THIS machine."
echo "    Other users will still see the warning."