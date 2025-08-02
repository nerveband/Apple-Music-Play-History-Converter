#!/bin/bash
# Get Apple Developer Team ID

echo "🔍 Looking for Apple Developer Team ID..."

# Method 1: From security tool
echo "Method 1: Checking certificates..."
CERT_INFO=$(security find-identity -v -p codesigning | grep -E "Developer ID Application|Apple Development" | head -1)
if [ ! -z "$CERT_INFO" ]; then
    TEAM_ID=$(echo "$CERT_INFO" | grep -o '([A-Z0-9]\{10\})' | tr -d '()')
    if [ ! -z "$TEAM_ID" ]; then
        echo "✅ Team ID found: $TEAM_ID"
    fi
fi

# Method 2: From Xcode
echo ""
echo "Method 2: From Xcode preferences..."
echo "In Xcode:"
echo "1. Go to Xcode → Settings → Accounts"
echo "2. Select your Apple ID (nerveband@gmail.com)"
echo "3. Your Team ID is shown in parentheses next to your name"
echo "   Example: Your Name (ABCDEF1234)"

# Method 3: From Apple Developer website
echo ""
echo "Method 3: From Apple Developer website..."
echo "1. Go to https://developer.apple.com/account"
echo "2. Sign in with nerveband@gmail.com"
echo "3. Your Team ID is shown in the membership section"

echo ""
echo "Once you have your Team ID, update it in:"
echo "- sign_app_developer.sh (for notarization commands)"
echo "- Any build configuration files"