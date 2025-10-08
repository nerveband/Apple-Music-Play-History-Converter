#!/usr/bin/env python3
"""
Test script to reproduce MusicBrainz API rate limiting issue in BATCH mode.

This tests the batch search path (search_batch_api) which is what
the main app uses during CSV processing.
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

def main():
    print("=" * 80)
    print("🔬 MusicBrainz API BATCH Rate Limiting Test")
    print("=" * 80)
    print()

    # Test songs (simple names that should exist)
    test_songs = [
        "Bohemian Rhapsody",
        "Imagine",
        "Hey Jude",
        "Stairway to Heaven",
        "Like a Rolling Stone",
        "Smells Like Teen Spirit",
        "Hotel California",
        "Sweet Child O' Mine",
        "Billie Jean",
        "Purple Rain"
    ]

    print(f"📊 Test configuration:")
    print(f"   Songs to search: {len(test_songs)}")
    print(f"   Expected provider: musicbrainz_api")
    print(f"   Method: search_batch_api (BATCH MODE)")
    print(f"   Expected rate limit: 1 request/second (no 60-second waits)")
    print()

    # Initialize service
    print("🚀 Initializing MusicSearchServiceV2...")
    service = MusicSearchServiceV2()

    # Set provider to musicbrainz_api
    print("🔧 Setting provider to 'musicbrainz_api'...")
    service.set_search_provider("musicbrainz_api")

    # Verify provider
    current_provider = service.get_search_provider()
    print(f"✅ Current provider: {current_provider}")

    # Check settings
    settings = service.settings
    print(f"📊 Settings:")
    print(f"   use_parallel_requests: {settings.get('use_parallel_requests', 'NOT SET')}")
    print(f"   parallel_workers: {settings.get('parallel_workers', 'NOT SET')}")
    print()

    if current_provider != "musicbrainz_api":
        print(f"❌ ERROR: Provider is '{current_provider}' instead of 'musicbrainz_api'!")
        return 1

    print("=" * 80)
    print("🔍 Starting BATCH search...")
    print("=" * 80)
    print()

    # Search using batch method (this is what the main app uses!)
    start_time = time.time()

    def progress_callback(idx, song_name, result, completed, total):
        """Progress callback to show what's happening."""
        print(f"📊 Progress: {completed}/{total} | Song: {song_name}")
        if result['success']:
            print(f"   ✅ Found: {result.get('artist', 'Unknown')}")
        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown')}")

    print(f"🚀 Calling search_batch_api with {len(test_songs)} songs...")
    print(f"   (This is the EXACT method the main app uses)")
    print()

    results = service.search_batch_api(
        test_songs,
        progress_callback=progress_callback,
        interrupt_check=None
    )

    total_time = time.time() - start_time

    # Summary
    print()
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print()

    successful = sum(1 for r in results if r and r.get('success', False))
    failed = len(results) - successful

    print(f"Total searches: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per search: {total_time/len(results) if results else 0:.2f}s")
    print()

    # Check for issues
    print("🔍 Diagnostic checks:")
    print()

    # Check 1: Total time for 10 songs should be ~10-15 seconds (1 sec/song)
    expected_time = len(test_songs) * 1.5  # ~1.5s per song with MusicBrainz API
    if total_time > expected_time + 60:  # More than 60s extra suggests rate limit issue
        print(f"⚠️  WARNING: Total time is {total_time:.1f}s (expected ~{expected_time:.1f}s)")
        print(f"   This suggests a 60-second iTunes rate limit wait occurred!")
        print(f"   MusicBrainz API should only wait 1 second between requests.")
    else:
        print(f"✅ Total time is reasonable: {total_time:.2f}s (expected ~{expected_time:.1f}s)")

    print()
    print("=" * 80)
    print("🔍 Check the logs above for:")
    print("   - 🔀 ROUTING REQUEST messages showing provider='musicbrainz_api'")
    print("   - ➡️  Calling _search_musicbrainz_api() (correct routing)")
    print("   - 🟢 _search_musicbrainz_api() CALLED (GREEN = correct)")
    print("   - 🔴 _search_itunes() CALLED (RED = bug!)")
    print("   - ⏸️  iTunes API RATE LIMIT HIT (should NOT appear)")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
