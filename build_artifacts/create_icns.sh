#!/bin/bash
# Create .icns file from PNG for macOS

set -e

cd "$(dirname "$0")/.."

echo "Creating .icns file from PNG..."

# Create temporary iconset directory
mkdir -p images/appicon.iconset

# Generate different sizes (macOS requires specific sizes)
sips -z 16 16     images/appicon.png --out images/appicon.iconset/icon_16x16.png
sips -z 32 32     images/appicon.png --out images/appicon.iconset/icon_16x16@2x.png
sips -z 32 32     images/appicon.png --out images/appicon.iconset/icon_32x32.png
sips -z 64 64     images/appicon.png --out images/appicon.iconset/icon_32x32@2x.png
sips -z 128 128   images/appicon.png --out images/appicon.iconset/icon_128x128.png
sips -z 256 256   images/appicon.png --out images/appicon.iconset/icon_128x128@2x.png
sips -z 256 256   images/appicon.png --out images/appicon.iconset/icon_256x256.png
sips -z 512 512   images/appicon.png --out images/appicon.iconset/icon_256x256@2x.png
sips -z 512 512   images/appicon.png --out images/appicon.iconset/icon_512x512.png
sips -z 1024 1024 images/appicon.png --out images/appicon.iconset/icon_512x512@2x.png

# Create .icns file
iconutil -c icns images/appicon.iconset -o images/appicon.icns

# Clean up
rm -rf images/appicon.iconset

echo "Created images/appicon.icns"