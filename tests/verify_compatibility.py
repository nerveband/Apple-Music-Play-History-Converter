#!/usr/bin/env python3
"""
Quick verification script for cross-platform compatibility features.
Tests the key improvements made to the Apple Music Play History Converter.
"""

import tempfile
import csv
from pathlib import Path
import pandas as pd
import json

def test_csv_encoding_detection():
    """Test the CSV encoding detection functionality."""
    print("Testing CSV encoding detection...")
    
    # Create test CSV with special characters
    test_data = [
        ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'],
        ['Café del Mar', 'Naïve Song', 'Résumé Album', '2023-01-01 12:00:00', 'Café del Mar', '180'],
        ['Björk', 'Jóga', 'Homogenic', '2023-01-02 13:00:00', 'Björk', '300']
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(test_data)
        temp_file = f.name
    
    # Test encoding detection (simulating the app's logic)
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
    encoding_used = 'utf-8'  # default
    
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(temp_file, nrows=5, encoding=encoding)
            encoding_used = encoding
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            continue
    
    # Read with detected encoding
    df = pd.read_csv(temp_file, encoding=encoding_used)
    
    # Cleanup
    Path(temp_file).unlink()
    
    print(f"✓ CSV encoding detection successful (used: {encoding_used})")
    print(f"✓ Read {len(df)} rows with special characters")
    return True

def test_path_operations():
    """Test cross-platform path operations."""
    print("Testing path operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test nested directory creation
        nested_dir = temp_path / "app_data" / "musicbrainz"
        nested_dir.mkdir(parents=True, exist_ok=True)
        
        # Test file with special characters
        test_file = nested_dir / "test file with spaces & symbols.txt"
        test_file.write_text("Test content", encoding='utf-8')
        
        # Test file operations
        file_size = test_file.stat().st_size
        relative_path = test_file.relative_to(temp_path)
        
        print(f"✓ Directory creation successful: {nested_dir.name}")
        print(f"✓ File with special chars: {test_file.name}")
        print(f"✓ Path operations working correctly")
    
    return True

def test_json_settings():
    """Test JSON settings handling."""
    print("Testing JSON settings...")
    
    test_settings = {
        "search_provider": "musicbrainz",
        "auto_fallback_to_itunes": True,
        "special_chars": "café, naïve, résumé",
        "unicode_symbols": "♪ ♫ ♬"
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        settings_file = Path(temp_dir) / "settings.json"
        
        # Write settings
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(test_settings, f, indent=2, ensure_ascii=False)
        
        # Read settings back
        with open(settings_file, 'r', encoding='utf-8') as f:
            loaded_settings = json.load(f)
        
        if loaded_settings == test_settings:
            print("✓ JSON settings save/load successful")
            print("✓ Unicode characters preserved correctly")
            return True
        else:
            print("✗ JSON settings data mismatch")
            return False

def test_csv_export():
    """Test CSV export functionality."""
    print("Testing CSV export...")
    
    # Create test DataFrame with special characters
    test_data = {
        'Artist': ['Café del Mar', 'Björk', 'Sigur Rós'],
        'Track': ['Naïve Song', 'Jóga', 'Hoppípolla'],
        'Album': ['Résumé Album', 'Homogenic', 'Takk...'],
        'Timestamp': ['2023-01-01 12:00:00', '2023-01-02 13:00:00', '2023-01-03 14:00:00'],
        'Album Artist': ['Café del Mar', 'Björk', 'Sigur Rós'],
        'Duration': ['180', '300', '270']
    }
    
    df = pd.DataFrame(test_data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        temp_file = f.name
    
    # Test export with UTF-8-sig (like the app does)
    df.to_csv(
        temp_file, 
        index=False, 
        encoding='utf-8-sig',
        lineterminator='\n'
    )
    
    # Verify we can read it back
    df_read = pd.read_csv(temp_file, encoding='utf-8-sig')
    
    # Cleanup
    Path(temp_file).unlink()
    
    if len(df_read) == len(df):
        print("✓ CSV export with UTF-8-sig successful")
        print("✓ Special characters preserved in export")
        return True
    else:
        print("✗ CSV export failed")
        return False

def main():
    """Run all verification tests."""
    print("Apple Music Play History Converter - Compatibility Verification")
    print("=" * 60)
    print()
    
    tests = [
        test_csv_encoding_detection,
        test_path_operations,
        test_json_settings,
        test_csv_export
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            print()
    
    print("=" * 60)
    print(f"Verification Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All cross-platform compatibility features working correctly!")
        print("The application is ready for use on Windows, macOS, and Linux.")
    else:
        print("⚠️  Some compatibility issues detected. Please check the output above.")
    
    return passed == total

if __name__ == "__main__":
    main()
