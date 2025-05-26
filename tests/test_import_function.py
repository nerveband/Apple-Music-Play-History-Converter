#!/usr/bin/env python3
"""
Test the import function with the actual tar.zst file.
"""

import sys
sys.path.insert(0, '.')

def progress_callback(message, progress):
    """Simple progress callback for testing."""
    print(f"[{progress:3.0f}%] {message}")

def test_import_function():
    """Test importing the actual tar.zst file."""
    
    print("🔧 TESTING IMPORT FUNCTION")
    print("=" * 50)
    
    from musicbrainz_manager import MusicBrainzManager
    
    # Initialize manager
    manager = MusicBrainzManager()
    
    # Test file path
    test_file = "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/docs/musicbrainz-canonical-dump-20250517-080003.tar.zst"
    
    print(f"Testing import of: {test_file}")
    
    # Check if file exists
    from pathlib import Path
    file_path = Path(test_file)
    if not file_path.exists():
        print(f"❌ File not found: {test_file}")
        return
    
    print(f"✅ File exists, size: {file_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Test the import
    print("\n🚀 Starting import...")
    try:
        result = manager.import_database_file(test_file, progress_callback)
        
        if result:
            print("✅ Import successful!")
            
            # Test if we can search
            search_results = manager.search("bohemian", "queen")
            print(f"✅ Search test: Found {len(search_results)} results")
            
            if search_results:
                print(f"   First result: {search_results[0]}")
        else:
            print("❌ Import failed!")
            
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_import_function()
