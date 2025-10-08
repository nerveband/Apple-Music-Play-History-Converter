#!/usr/bin/env python3
"""
Test script to reproduce MusicBrainz API rate limiting issue.

This script will:
1. Initialize MusicSearchServiceV2 with musicbrainz_api provider
2. Search for 10 songs sequentially
3. Show detailed logging to diagnose why iTunes rate limiting is being applied

Expected behavior:
- Should see 🟢 _search_musicbrainz_api() CALLED for each request
- Should see 1-second waits between requests (MusicBrainz API policy)
- Should NOT see 🔴 _search_itunes() CALLED
- Should NOT see ⏸️ iTunes API RATE LIMIT HIT

Actual buggy behavior (if bug exists):
- Might see 🔴 _search_itunes() CALLED despite provider='musicbrainz_api'
- Might see ⏸️ iTunes API RATE LIMIT HIT after 4 requests with 60-second wait
"""

import sys
import os
import time
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

async def main():
    print("=" * 80)
    print("🔬 MusicBrainz API Rate Limiting Test")
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
    print()

    if current_provider != "musicbrainz_api":
        print(f"❌ ERROR: Provider is '{current_provider}' instead of 'musicbrainz_api'!")
        return 1

    print("=" * 80)
    print("🔍 Starting searches...")
    print("=" * 80)
    print()

    # Search each song
    start_time = time.time()
    results = []

    for idx, song in enumerate(test_songs, 1):
        print(f"\n{'─' * 80}")
        print(f"[{idx}/{len(test_songs)}] Searching: {song}")
        print(f"{'─' * 80}")

        search_start = time.time()
        result = await service.search_song(song_name=song)
        search_time = time.time() - search_start

        results.append({
            "song": song,
            "result": result,
            "time": search_time
        })

        if result['success']:
            print(f"✅ Found: {result.get('artist', 'Unknown')} - {result.get('song', 'Unknown')}")
        else:
            print(f"❌ Not found: {result.get('error', 'Unknown error')}")

        print(f"⏱️  Search time: {search_time:.2f}s")

    total_time = time.time() - start_time

    # Summary
    print()
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print()

    successful = sum(1 for r in results if r['result']['success'])
    failed = len(results) - successful
    avg_time = sum(r['time'] for r in results) / len(results) if results else 0

    print(f"Total searches: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per search: {avg_time:.2f}s")
    print()

    # Check for issues
    print("🔍 Diagnostic checks:")
    print()

    # Check 1: Were there any 60-second waits?
    max_time = max(r['time'] for r in results) if results else 0
    if max_time > 10:
        print(f"⚠️  WARNING: Detected a search that took {max_time:.1f}s")
        print(f"   This suggests a 60-second iTunes rate limit wait occurred!")
        print(f"   MusicBrainz API should only wait 1 second between requests.")
    else:
        print(f"✅ All searches completed quickly (max: {max_time:.2f}s)")

    # Check 2: Average time should be ~1 second per request
    expected_avg = 1.0
    if avg_time > 2.0:
        print(f"⚠️  WARNING: Average search time is {avg_time:.2f}s (expected ~{expected_avg:.1f}s)")
        print(f"   This suggests rate limiting issues.")
    else:
        print(f"✅ Average search time is reasonable: {avg_time:.2f}s")

    print()
    print("=" * 80)
    print("🔍 Check the logs above for:")
    print("   - 🔀 ROUTING REQUEST messages showing provider='musicbrainz_api'")
    print("   - 🟢 _search_musicbrainz_api() CALLED (GREEN = correct)")
    print("   - 🔴 _search_itunes() CALLED (RED = bug!)")
    print("   - ⏸️  iTunes API RATE LIMIT HIT (should NOT appear)")
    print("=" * 80)

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code if exit_code is not None else 0)
