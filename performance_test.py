#!/usr/bin/env python3
"""
Test multiple searches to measure consistent performance improvements.
"""

import time
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from musicbrainz_manager import MusicBrainzManager

def performance_test():
    """Test multiple searches to measure performance consistency."""
    
    print("🎵 MusicBrainz Performance Test")
    print("=" * 40)
    
    # Initialize manager
    print("Initializing MusicBrainz manager...")
    manager = MusicBrainzManager()
    
    # Check if database is available
    if not manager.is_database_available():
        print("❌ MusicBrainz database not available. Please download or import data first.")
        return
    
    # Test searches
    test_queries = [
        ("hey jude", "beatles"),
        ("stairway to heaven", "led zeppelin"),
        ("hotel california", "eagles"),
        ("sweet child o mine", "guns n roses"),
        ("piano man", "billy joel"),
        ("purple rain", "prince"),
        ("smells like teen spirit", "nirvana"),
        ("thriller", "michael jackson"),
        ("dancing queen", "abba"),
        ("under pressure", "queen")
    ]
    
    print(f"\nTesting {len(test_queries)} different searches...")
    
    times = []
    for i, (song, artist) in enumerate(test_queries, 1):
        print(f"\n{i:2d}. Searching '{song}' by '{artist}'...")
        
        start_time = time.time()
        results = manager.search(song, artist)
        search_time = time.time() - start_time
        times.append(search_time)
        
        if results:
            print(f"    ✅ {search_time*1000:.0f}ms -> {len(results)} results")
            print(f"    🎵 Best: '{results[0]['trackName']}' by '{results[0]['artistName']}'")
        else:
            print(f"    ❌ {search_time*1000:.0f}ms -> No results")
    
    # Performance summary
    print("\n" + "=" * 40)
    print("📊 Performance Summary")
    print("=" * 40)
    
    avg_time = sum(times) * 1000 / len(times)
    min_time = min(times) * 1000
    max_time = max(times) * 1000
    
    print(f"Average search time: {avg_time:.0f}ms")
    print(f"Fastest search:      {min_time:.0f}ms")
    print(f"Slowest search:      {max_time:.0f}ms")
    print(f"Searches per second: {1000/avg_time:.1f}")
    
    if avg_time < 1000:
        print("🚀 Excellent performance - under 1 second per search!")
    elif avg_time < 3000:
        print("👍 Good performance - under 3 seconds per search")
    else:
        print("⚠️  Performance could be improved - over 3 seconds per search")

if __name__ == "__main__":
    performance_test()
