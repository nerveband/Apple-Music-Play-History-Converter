#!/usr/bin/env python3
"""
Debug script to test MusicBrainz database download functionality.
This will help identify exactly where the download process is failing.
"""

import sys
import os
from pathlib import Path
from musicbrainz_manager import MusicBrainzManager

def test_database_download():
    """Test the database download process with detailed debugging."""
    print("Testing MusicBrainz Database Download")
    print("=" * 50)
    
    # Initialize manager
    manager = MusicBrainzManager()
    
    print(f"Database path: {manager.db_path}")
    print(f"Temp directory: {manager.temp_dir}")
    print(f"Metadata file: {manager.metadata_file}")
    print()
    
    # Check initial state
    print("Initial State:")
    db_info = manager.get_database_info()
    print(f"Database exists: {db_info['exists']}")
    if db_info['exists']:
        print(f"Database size: {db_info['size_mb']} MB")
        print(f"Track count: {db_info.get('track_count', 'Unknown')}")
    print()
    
    # Test download
    print("Starting download test...")
    print("This will download a small sample to test the process.")
    
    def progress_callback(percent, message):
        print(f"Progress: {percent}% - {message}")
    
    try:
        success = manager.download_database(progress_callback)
        print(f"\nDownload result: {'SUCCESS' if success else 'FAILED'}")
        
        # Check final state
        print("\nFinal State:")
        db_info = manager.get_database_info()
        print(f"Database exists: {db_info['exists']}")
        if db_info['exists']:
            print(f"Database size: {db_info['size_mb']} MB")
            print(f"Track count: {db_info.get('track_count', 'Unknown')}")
            
            # Test a quick search
            print("\nTesting search functionality...")
            results = manager.search("Yesterday", "The Beatles")
            print(f"Search results for 'Yesterday' by 'The Beatles': {len(results)} found")
            if results:
                print(f"First result: {results[0]}")
        else:
            print("Database was not created successfully")
            
    except Exception as e:
        print(f"Error during download: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database_download()
