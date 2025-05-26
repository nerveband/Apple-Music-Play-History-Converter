#!/usr/bin/env python3
"""
Test the import function with proper progress tracking.
"""

import sys
sys.path.insert(0, '.')

def progress_callback(message, progress):
    """Enhanced progress callback that shows a visual progress bar."""
    # Create a visual progress bar
    bar_length = 40
    filled_length = int(bar_length * progress / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    print(f"\r[{bar}] {progress:3.0f}% {message}", end='', flush=True)
    if progress == 100 or progress == 0:
        print()  # New line when complete or error

def test_import_with_clean_slate():
    """Test importing after cleaning up existing data."""
    
    print("🔧 TESTING IMPORT WITH PROGRESS BAR")
    print("=" * 60)
    
    from musicbrainz_manager import MusicBrainzManager
    from pathlib import Path
    import shutil
    
    # Clean up existing data first
    data_dir = Path("data/musicbrainz")
    if data_dir.exists():
        print("🧹 Cleaning up existing data...")
        shutil.rmtree(data_dir, ignore_errors=True)
    
    # Initialize manager
    manager = MusicBrainzManager()
    
    # Test file path
    test_file = "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/docs/musicbrainz-canonical-dump-20250517-080003.tar.zst"
    
    print(f"Testing import of: {test_file}")
    
    # Check if file exists
    file_path = Path(test_file)
    if not file_path.exists():
        print(f"❌ File not found: {test_file}")
        return
    
    print(f"✅ File exists, size: {file_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Test the import with progress tracking
    print("\n🚀 Starting import with progress tracking...")
    try:
        result = manager.import_database_file(test_file, progress_callback)
        
        if result:
            print("✅ Import successful!")
            
            # Test if we can search
            print("\n🔍 Testing search functionality...")
            search_results = manager.search("bohemian", "queen")
            print(f"✅ Search test: Found {len(search_results)} results")
            
            if search_results:
                print(f"\n📋 Top 3 results:")
                for i, result in enumerate(search_results[:3]):
                    print(f"   {i+1}. {result['artistName']} - {result['trackName']} ({result['score']} score)")
                    
        else:
            print("❌ Import failed!")
            
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_import_with_clean_slate()
