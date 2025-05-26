#!/usr/bin/env python3
"""
Quick test of a single search to check performance.
"""

import time
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from musicbrainz_manager import MusicBrainzManager

def quick_test():
    """Test a single search for immediate performance feedback."""
    
    print("🎵 Quick MusicBrainz Search Test")
    print("=" * 40)
    
    # Initialize manager
    print("Initializing MusicBrainz manager...")
    manager = MusicBrainzManager()
    
    # Check if database is available
    if not manager.is_database_available():
        print("❌ MusicBrainz database not available. Please download or import data first.")
        return
    
    print("Testing search for 'bohemian rhapsody' by 'queen'...")
    
    start_time = time.time()
    results = manager.search("bohemian rhapsody", "queen")
    search_time = time.time() - start_time
    
    print(f"⏱️  Search completed in {search_time*1000:.2f}ms")
    
    if results:
        print(f"✅ Found {len(results)} results")
        print(f"🎵 Best match: '{results[0]['trackName']}' by '{results[0]['artistName']}'")
    else:
        print("❌ No results found")
    
    # Test a second search to see if it's faster (should be cached)
    print("\nTesting second search for 'imagine' by 'john lennon'...")
    
    start_time = time.time()
    results2 = manager.search("imagine", "john lennon")
    search_time2 = time.time() - start_time
    
    print(f"⏱️  Second search completed in {search_time2*1000:.2f}ms")
    
    if results2:
        print(f"✅ Found {len(results2)} results")
        print(f"🎵 Best match: '{results2[0]['trackName']}' by '{results2[0]['artistName']}'")

if __name__ == "__main__":
    quick_test()
