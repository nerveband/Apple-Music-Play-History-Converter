#!/usr/bin/env python3
"""Test script to debug path issues."""

from pathlib import Path
import tempfile
import os

def test_paths():
    """Test path creation and resolution."""
    print("Testing path handling...")
    
    # Test 1: Basic path creation
    data_dir = Path("app_data/musicbrainz")
    print(f"\n1. Basic path: {data_dir}")
    print(f"   Absolute: {data_dir.resolve()}")
    print(f"   Exists: {data_dir.exists()}")
    
    # Test 2: Create temp directory
    temp_dir = data_dir / "temp"
    print(f"\n2. Temp dir: {temp_dir}")
    print(f"   Absolute: {temp_dir.resolve()}")
    
    # Create the directory
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Created: {temp_dir.exists()}")
    
    # Test 3: Create a test file
    test_file = temp_dir / "test.txt"
    print(f"\n3. Test file: {test_file}")
    print(f"   Absolute: {test_file.resolve()}")
    
    # Write to file
    with open(test_file, 'w') as f:
        f.write("test content")
    
    print(f"   Created: {test_file.exists()}")
    print(f"   Size: {test_file.stat().st_size} bytes")
    
    # Test 4: List directory contents
    print(f"\n4. Directory contents:")
    for item in temp_dir.iterdir():
        print(f"   - {item.name}")
    
    # Test 5: Check working directory
    print(f"\n5. Working directory: {os.getcwd()}")
    print(f"   Script location: {Path(__file__).resolve()}")

if __name__ == "__main__":
    test_paths()
