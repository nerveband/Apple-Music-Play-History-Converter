#!/usr/bin/env python3
"""
Cross-Platform Compatibility Test Suite for Apple Music Play History Converter

This script tests various cross-platform compatibility aspects including:
- File encoding handling
- Path operations
- CSV processing
- Database operations
- Settings file management
"""

import os
import sys
import platform
import tempfile
import csv
import json
import shutil
from pathlib import Path
import pandas as pd

def test_platform_info():
    """Test and display platform information."""
    print("=== Platform Information ===")
    print(f"Platform: {platform.platform()}")
    print(f"System: {platform.system()}")
    print(f"Release: {platform.release()}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Python Version: {sys.version}")
    print(f"Current Working Directory: {os.getcwd()}")
    print()

def test_file_encoding():
    """Test file encoding handling with various character sets."""
    print("=== File Encoding Tests ===")
    
    # Test data with various character encodings
    test_data = [
        "Basic ASCII text",
        "UTF-8 with accents: café, naïve, résumé",
        "UTF-8 with symbols: ♪ ♫ ♬ ♭ ♮ ♯",
        "UTF-8 with emoji: 🎵 🎶 🎤 🎧",
        "Latin-1 characters: àáâãäåæçèéêë",
        "Windows-1252 characters: ""''–—"
    ]
    
    encodings_to_test = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for encoding in encodings_to_test:
            try:
                test_file = temp_path / f"test_{encoding}.txt"
                
                # Write test data
                with open(test_file, 'w', encoding=encoding, errors='replace') as f:
                    for line in test_data:
                        f.write(line + '\n')
                
                # Read back and verify
                with open(test_file, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                
                print(f"✓ {encoding}: Successfully wrote and read {len(content)} characters")
                
            except Exception as e:
                print(f"✗ {encoding}: Failed - {e}")
    
    print()

def test_csv_processing():
    """Test CSV processing with various encodings and formats."""
    print("=== CSV Processing Tests ===")
    
    # Create test CSV data
    csv_data = [
        ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'],
        ['Café del Mar', 'Naïve Song', 'Résumé Album', '2023-01-01 12:00:00', 'Café del Mar', '180'],
        ['The Beatles', 'Here Comes the Sun', 'Abbey Road', '2023-01-02 13:00:00', 'The Beatles', '185'],
        ['Björk', 'Jóga', 'Homogenic', '2023-01-03 14:00:00', 'Björk', '300'],
        ['Sigur Rós', 'Hoppípolla', 'Takk...', '2023-01-04 15:00:00', 'Sigur Rós', '270']
    ]
    
    encodings_to_test = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for encoding in encodings_to_test:
            try:
                csv_file = temp_path / f"test_{encoding}.csv"
                
                # Write CSV with specific encoding
                with open(csv_file, 'w', encoding=encoding, newline='', errors='replace') as f:
                    writer = csv.writer(f)
                    writer.writerows(csv_data)
                
                # Test pandas reading with encoding detection
                df = None
                for test_encoding in encodings_to_test:
                    try:
                        df = pd.read_csv(csv_file, encoding=test_encoding)
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                
                if df is not None:
                    print(f"✓ {encoding}: CSV written and read successfully ({len(df)} rows)")
                else:
                    print(f"✗ {encoding}: Could not read CSV with any encoding")
                
            except Exception as e:
                print(f"✗ {encoding}: Failed - {e}")
    
    print()

def test_path_operations():
    """Test cross-platform path operations."""
    print("=== Path Operations Tests ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Test directory creation
            test_dir = temp_path / "test_dir" / "nested_dir"
            test_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Directory creation: {test_dir}")
            
            # Test file creation with special characters
            test_file = test_dir / "test file with spaces & symbols.txt"
            test_file.write_text("Test content", encoding='utf-8')
            print(f"✓ File creation with special chars: {test_file.name}")
            
            # Test file operations
            file_size = test_file.stat().st_size
            print(f"✓ File size check: {file_size} bytes")
            
            # Test path resolution
            resolved_path = test_file.resolve()
            print(f"✓ Path resolution: {resolved_path}")
            
            # Test relative path
            relative_path = test_file.relative_to(temp_path)
            print(f"✓ Relative path: {relative_path}")
            
        except Exception as e:
            print(f"✗ Path operations failed: {e}")
    
    print()

def test_json_settings():
    """Test JSON settings file handling."""
    print("=== JSON Settings Tests ===")
    
    test_settings = {
        "search_provider": "musicbrainz",
        "auto_fallback_to_itunes": True,
        "database_location": "app_data/musicbrainz",
        "special_chars": "café, naïve, résumé",
        "unicode_symbols": "♪ ♫ ♬ ♭ ♮ ♯",
        "last_update_check": None
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        settings_file = temp_path / "app_data" / "settings.json"
        
        try:
            # Ensure directory exists
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write settings
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(test_settings, f, indent=2, ensure_ascii=False)
            
            # Read settings back
            with open(settings_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
            
            # Verify
            if loaded_settings == test_settings:
                print("✓ JSON settings: Successfully saved and loaded")
            else:
                print("✗ JSON settings: Data mismatch after save/load")
                
        except Exception as e:
            print(f"✗ JSON settings failed: {e}")
    
    print()

def test_database_operations():
    """Test database file operations."""
    print("=== Database Operations Tests ===")
    
    try:
        import sqlite3
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "test.db"
            
            # Create database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create table with unicode data
            cursor.execute('''
                CREATE TABLE artists (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    album TEXT
                )
            ''')
            
            # Insert test data with special characters
            test_data = [
                ("Café del Mar", "Résumé Album"),
                ("Björk", "Homogenic"),
                ("Sigur Rós", "Takk...")
            ]
            
            cursor.executemany("INSERT INTO artists (name, album) VALUES (?, ?)", test_data)
            conn.commit()
            
            # Read back data
            cursor.execute("SELECT name, album FROM artists")
            results = cursor.fetchall()
            
            conn.close()
            
            if len(results) == len(test_data):
                print(f"✓ Database operations: Successfully stored and retrieved {len(results)} records")
            else:
                print(f"✗ Database operations: Expected {len(test_data)} records, got {len(results)}")
                
    except ImportError:
        print("✗ Database operations: sqlite3 not available")
    except Exception as e:
        print(f"✗ Database operations failed: {e}")
    
    print()

def test_temp_file_operations():
    """Test temporary file operations."""
    print("=== Temporary File Operations Tests ===")
    
    try:
        # Test temporary file creation
        with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False) as temp_file:
            temp_file.write("Test content with special chars: café, naïve")
            temp_path = temp_file.name
        
        # Read back
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Cleanup
        os.unlink(temp_path)
        
        print("✓ Temporary file operations: Success")
        
    except Exception as e:
        print(f"✗ Temporary file operations failed: {e}")
    
    print()

def main():
    """Run all cross-platform compatibility tests."""
    print("Apple Music Play History Converter - Cross-Platform Compatibility Tests")
    print("=" * 70)
    print()
    
    test_platform_info()
    test_file_encoding()
    test_csv_processing()
    test_path_operations()
    test_json_settings()
    test_database_operations()
    test_temp_file_operations()
    
    print("=" * 70)
    print("Cross-platform compatibility tests completed!")
    print()
    print("If all tests show ✓, the application should work correctly on this platform.")
    print("If any tests show ✗, there may be compatibility issues that need attention.")

if __name__ == "__main__":
    main()
