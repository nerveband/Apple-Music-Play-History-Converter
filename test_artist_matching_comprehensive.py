#!/usr/bin/env python3
"""
Comprehensive test of artist matching accuracy after fix
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2


async def test_artist_matching():
    """Test various artist/track combinations"""

    test_cases = [
        # Track, Artist, Album (expected artist)
        ("Intruder Alert (feat. Sarah Green)", "Lupe Fiasco", "Lupe Fiasco's The Cool (Deluxe Edition)", "Lupe Fiasco"),
        ("Hurt Me Soul", "Lupe Fiasco", "Lupe Fiasco's Food & Liquor", "Lupe Fiasco"),
        ("The Coolest", "Lupe Fiasco", "Lupe Fiasco's The Cool (Deluxe Edition)", "Lupe Fiasco"),
        ("Daydreamin' (feat. Jill Scott)", "Lupe Fiasco", "Lupe Fiasco's Food & Liquor", "Lupe Fiasco"),
    ]

    print("=" * 80)
    print("🧪 COMPREHENSIVE ARTIST MATCHING TEST")
    print("=" * 80)

    service = MusicSearchServiceV2()

    total_tests = len(test_cases)
    passed = 0
    failed = 0

    for i, (track, artist_hint, album_hint, expected_artist) in enumerate(test_cases, 1):
        print(f"\n[{i}/{total_tests}] Testing: {track} by {artist_hint}")
        print("-" * 80)

        # Test iTunes API (ground truth)
        itunes_result = await service._search_itunes_async(track, artist_hint, album_hint)
        itunes_artist = itunes_result.get('artist') if itunes_result and itunes_result.get('success') else None

        # Test Offline DB (what we're fixing)
        offline_result = service._search_musicbrainz(track, artist_hint, album_hint)
        offline_artist = offline_result.get('artist') if offline_result and offline_result.get('success') else None

        print(f"   iTunes API:   {itunes_artist or 'NOT FOUND'}")
        print(f"   Offline DB:   {offline_artist or 'NOT FOUND'}")
        print(f"   Expected:     {expected_artist}")

        # Check results
        if offline_artist == expected_artist:
            print(f"   ✅ PASS - Offline DB matches expected")
            passed += 1
        else:
            print(f"   ❌ FAIL - Offline DB returned '{offline_artist}', expected '{expected_artist}'")
            failed += 1

        # Also check if iTunes agrees
        if itunes_artist and itunes_artist == offline_artist:
            print(f"   ✅ iTunes API and Offline DB agree")
        elif itunes_artist:
            print(f"   ⚠️  iTunes API returned '{itunes_artist}', Offline DB returned '{offline_artist}'")

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"✅ Passed: {passed} ({passed/total_tests*100:.1f}%)")
    print(f"❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} test(s) failed - please review")


if __name__ == "__main__":
    asyncio.run(test_artist_matching())
