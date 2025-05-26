#!/usr/bin/env python3
"""
Performance test script for MusicBrainz search optimization.
Tests search speed improvements before and after optimizations.
"""

import time
import sys
import os
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from musicbrainz_manager import MusicBrainzManager

def test_search_performance():
    """Test search performance with various queries."""
    
    print("🎵 MusicBrainz Search Performance Test")
    print("=" * 50)
    
    # Initialize manager
    print("Initializing MusicBrainz manager...")
    manager = MusicBrainzManager()
    
    # Check if database is available
    if not manager.is_database_available():
        print("❌ MusicBrainz database not available. Please download or import data first.")
        return
    
    # Test queries (mix of popular and less common songs)
    test_queries = [
        ("bohemian rhapsody", "queen"),
        ("imagine", "john lennon"),
        ("stairway to heaven", "led zeppelin"),
        ("hotel california", "eagles"),
        ("thriller", "michael jackson"),
        ("billie jean", "michael jackson"),
        ("sweet child o mine", "guns n roses"),
        ("smells like teen spirit", "nirvana"),
        ("purple rain", "prince"),
        ("like a rolling stone", "bob dylan"),
        ("fools", None),  # Test query from user's CSV
        ("talk me down", None),
        ("outside", "calvin harris"),
    ]
    
    print(f"Testing {len(test_queries)} search queries...")
    print()
    
    total_time = 0
    successful_searches = 0
    
    for i, (song, artist) in enumerate(test_queries, 1):
        print(f"Test {i:2d}: Searching for '{song}'" + (f" by '{artist}'" if artist else ""))
        
        start_time = time.time()
        results = manager.search(song, artist)
        search_time = time.time() - start_time
        
        total_time += search_time
        
        if results:
            successful_searches += 1
            print(f"         ✅ Found {len(results)} results in {search_time*1000:.2f}ms")
            # Show best result
            best_result = results[0]
            print(f"         🎵 Best match: '{best_result['trackName']}' by '{best_result['artistName']}'")
        else:
            print(f"         ❌ No results found in {search_time*1000:.2f}ms")
        
        print()
    
    # Calculate statistics
    avg_time = total_time / len(test_queries)
    searches_per_second = len(test_queries) / total_time
    success_rate = (successful_searches / len(test_queries)) * 100
    
    print("📊 Performance Summary")
    print("=" * 50)
    print(f"Total searches:      {len(test_queries)}")
    print(f"Successful searches: {successful_searches}")
    print(f"Success rate:        {success_rate:.1f}%")
    print(f"Total time:          {total_time:.3f} seconds")
    print(f"Average time:        {avg_time*1000:.2f}ms per search")
    print(f"Search rate:         {searches_per_second:.1f} searches/second")
    print()
    
    if searches_per_second > 100:
        print("🚀 EXCELLENT performance! Searches are lightning fast.")
    elif searches_per_second > 50:
        print("✅ GOOD performance! Searches are reasonably fast.")
    elif searches_per_second > 10:
        print("⚠️  MODERATE performance. Could be improved.")
    else:
        print("🐌 SLOW performance. Optimization needed.")
    
    print()
    print("🔧 Performance Tips:")
    print("• First search may be slower due to CSV view creation")
    print("• Subsequent searches should be much faster")
    print("• Consider using SSD storage for best performance")
    print("• Ensure sufficient RAM (2GB+ recommended)")

def test_view_creation():
    """Test the CSV view creation performance."""
    print("🔧 Testing CSV View Creation")
    print("=" * 30)
    
    manager = MusicBrainzManager()
    
    # Force view recreation by clearing the flag
    manager._view_created = False
    
    print("Creating CSV view...")
    start_time = time.time()
    
    # This should trigger view creation
    manager._ensure_csv_view()
    
    creation_time = time.time() - start_time
    print(f"View creation time: {creation_time:.3f} seconds")
    
    # Test that subsequent calls are instant
    start_time = time.time()
    manager._ensure_csv_view()
    second_call_time = time.time() - start_time
    
    print(f"Second call time: {second_call_time*1000:.2f}ms (should be ~0ms)")
    print()

if __name__ == "__main__":
    try:
        test_view_creation()
        test_search_performance()
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
