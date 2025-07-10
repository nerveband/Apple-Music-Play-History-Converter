#!/usr/bin/env python3
"""Create Windows .ico file from PNG in GitHub Actions."""

from PIL import Image
import os

# Read the PNG file
png_path = 'images/appicon.png'
ico_path = 'images/appicon.ico'

if os.path.exists(png_path):
    img = Image.open(png_path)
    
    # Create multiple sizes for Windows .ico
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    # Save as .ico with multiple sizes
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"Created {ico_path}")
else:
    print(f"Error: {png_path} not found")