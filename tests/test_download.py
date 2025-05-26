#!/usr/bin/env python3
"""Test script to debug MusicBrainz download functionality."""

from musicbrainz_manager import MusicBrainzManager

def test_download():
    """Test the download process with detailed output."""
    print("Testing MusicBrainz download functionality...")
    
    # Create manager instance
    manager = MusicBrainzManager()
    
    # Test URL discovery
    print("\n1. Testing URL discovery...")
    url = manager._get_latest_dump_url()
    if url:
        print(f"   ✓ Found latest dump URL: {url}")
    else:
        print("   ✗ Failed to find dump URL")
        return
    
    # Test download with progress callback
    print("\n2. Testing download process...")
    
    def progress_callback(progress, message):
        print(f"   Progress: {progress}% - {message}")
    
    success = manager.download_database(progress_callback)
    
    if success:
        print("\n✓ Download completed successfully!")
        
        # Check database info
        info = manager.get_database_info()
        print(f"\nDatabase info:")
        print(f"  - Exists: {info['exists']}")
        print(f"  - Size: {info['size_mb']}MB")
        print(f"  - Tracks: {info.get('track_count', 'Unknown')}")
        print(f"  - Updated: {info.get('last_updated', 'Unknown')}")
    else:
        print("\n✗ Download failed!")

if __name__ == "__main__":
    test_download()
