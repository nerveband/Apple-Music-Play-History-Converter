#!/usr/bin/env python3
"""
Reset the MusicBrainz cache to force recreation of the optimized table.
"""

import sys
import os
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from musicbrainz_manager import MusicBrainzManager

def reset_cache():
    """Reset the MusicBrainz cache to force table recreation."""
    
    print("🔄 Resetting MusicBrainz cache...")
    
    # Initialize manager
    manager = MusicBrainzManager()
    
    try:
        # Drop existing table if it exists
        manager.conn.execute("DROP TABLE IF EXISTS musicbrainz_data")
        manager.conn.execute("DROP VIEW IF EXISTS musicbrainz_data")
        print("✅ Existing table/view dropped")
        
        # Reset the flag
        manager._view_created = False
        
        print("✅ Cache reset complete!")
        print("   Next search will recreate the optimized table with indexes")
        
    except Exception as e:
        print(f"❌ Error resetting cache: {e}")

if __name__ == "__main__":
    reset_cache()
