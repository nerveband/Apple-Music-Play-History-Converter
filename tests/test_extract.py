#!/usr/bin/env python3
"""Test extraction of existing file."""

from musicbrainz_manager import MusicBrainzManager
from pathlib import Path

def test_extract():
    """Test extraction of existing file."""
    manager = MusicBrainzManager()
    
    compressed_file = Path("app_data/musicbrainz/temp/musicbrainz-dump.tar.zst")
    output_dir = Path("app_data/musicbrainz/temp/extracted")
    
    print(f"Testing extraction of: {compressed_file}")
    print(f"File exists: {compressed_file.exists()}")
    print(f"File size: {compressed_file.stat().st_size / (1024*1024):.2f} MB")
    
    def progress_callback(progress, message):
        print(f"Progress: {progress}% - {message}")
    
    # Try extraction
    print("\nAttempting extraction...")
    success = manager._extract_tar_zst_file(compressed_file, output_dir, progress_callback)
    
    if success:
        print("\nExtraction successful!")
        # List extracted files
        if output_dir.exists():
            print("\nExtracted files:")
            for item in output_dir.iterdir():
                print(f"  - {item.name} ({item.stat().st_size / (1024*1024):.2f} MB)")
    else:
        print("\nExtraction failed!")

if __name__ == "__main__":
    test_extract()
