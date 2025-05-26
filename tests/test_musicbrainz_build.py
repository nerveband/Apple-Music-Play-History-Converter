#!/usr/bin/env python3

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from musicbrainz_manager import MusicBrainzManager

def test_build_database():
    """Test the MusicBrainz database functionality."""
    
    # Check if canonical tar file exists
    docs_path = Path(__file__).parent.parent / "docs"
    canonical_files = list(docs_path.glob("musicbrainz-canonical-dump-*.tar.zst"))
    
    if not canonical_files:
        print("No canonical dump files found in docs/. Skipping test.")
        return True
    
    tar_file = canonical_files[0]
    print(f"Testing with canonical file: {tar_file.name}")
    print(f"File size: {tar_file.stat().st_size / (1024*1024):.1f} MB")
    
    # Initialize MusicBrainz manager
    manager = MusicBrainzManager()
    
    def progress_callback(message, progress, extra=None):
        print(f"[{progress:3.0f}%] {message}")
    
    print("\nTesting import...")
    success = manager.import_database_file(str(tar_file), progress_callback)
    
    if success:
        print("\n✅ Database build successful!")
        
        # Test the database
        print("\nTesting database queries...")
        
        # Test searches
        test_queries = [
            ("Yesterday", "Beatles"),
            ("Billie Jean", "Michael Jackson"),
            ("Bohemian Rhapsody", "Queen"),
            ("Hotel California", "Eagles"),
            ("Smells Like Teen Spirit", "Nirvana")
        ]
        
        for song, artist in test_queries:
            print(f"\nSearching for: '{song}' by '{artist}'")
            results = manager.search(song, artist)
            
            if results:
                print(f"  Found {len(results)} results:")
                for i, result in enumerate(results[:3]):  # Show top 3 results
                    print(f"    {i+1}. {result['artistName']} - {result['trackName']}")
                    if result.get('collectionName'):
                        print(f"       Album: {result['collectionName']}")
                    if result.get('matchScore'):
                        print(f"       Score: {result['matchScore']}")
            else:
                print("  No results found")
        
        # Get database info
        info = manager.get_database_info()
        print(f"\nDatabase Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        return True
    else:
        print("\n❌ Database build failed!")
        return False

if __name__ == "__main__":
    success = test_build_database()
    sys.exit(0 if success else 1)
