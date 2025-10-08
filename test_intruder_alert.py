#!/usr/bin/env python3
"""
Test script to compare MusicBrainz API, iTunes API, and offline DB results
for "Intruder Alert" by Lupe Fiasco to identify offline DB inaccuracies.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2


async def test_intruder_alert():
    """Test all three sources for Intruder Alert"""

    # Test case from CSV
    artist = "Lupe Fiasco"
    track_name = "Intruder Alert (feat. Sarah Green)"
    album_hint = "Lupe Fiasco's The Cool (Deluxe Edition)"

    print("=" * 80)
    print(f"🎯 Testing: {track_name}")
    print(f"   Artist: {artist}")
    print(f"   Album hint: {album_hint}")
    print("=" * 80)

    # Initialize service
    service = MusicSearchServiceV2()

    # Test 1: MusicBrainz API (GROUND TRUTH)
    print("\n📡 1. MusicBrainz API (GROUND TRUTH):")
    print("-" * 80)
    mb_api_result = await service._search_musicbrainz_api_async(track_name, artist, album_hint)
    if mb_api_result and mb_api_result.get('success'):
        print(f"✅ Found: {mb_api_result.get('artist', 'N/A')}")
        print(f"   Track: {track_name}")
        print(f"   Album: {mb_api_result.get('album', 'N/A')}")
        print(f"   Full result: {mb_api_result}")
    else:
        print(f"❌ Not found in MusicBrainz API: {mb_api_result}")

    # Test 2: iTunes API (GROUND TRUTH)
    print("\n🍎 2. iTunes API (GROUND TRUTH):")
    print("-" * 80)
    itunes_result = await service._search_itunes_async(track_name, artist, album_hint)
    if itunes_result and itunes_result.get('success'):
        print(f"✅ Found: {itunes_result.get('artist', 'N/A')}")
        print(f"   Track: {track_name}")
        print(f"   Album: {itunes_result.get('album', 'N/A')}")
        print(f"   Full result: {itunes_result}")
    else:
        print(f"❌ Not found in iTunes API: {itunes_result}")

    # Test 3: Offline DuckDB Database (WHAT WE'RE TESTING)
    print("\n💾 3. Offline DuckDB Database (CURRENT IMPLEMENTATION):")
    print("-" * 80)

    # Check if database is available
    if not service.musicbrainz_manager:
        print("❌ MusicBrainz database not initialized")
        print("\nℹ️  To run offline DB tests, please ensure MusicBrainz database is set up.")
        return

    if not service.musicbrainz_manager.is_ready():
        print("❌ MusicBrainz manager not ready (needs optimization)")
        print("\nℹ️  Please run MusicBrainz optimization first.")
        return

    # Test offline database search
    offline_result = service._search_musicbrainz(track_name, artist, album_hint)
    if offline_result and offline_result.get('success'):
        print(f"✅ Found: {offline_result.get('artist', 'N/A')}")
        print(f"   Track: {track_name}")
        print(f"   Full result: {offline_result}")
    else:
        print(f"❌ Not found in offline database: {offline_result}")

    # Comparison Analysis
    print("\n" + "=" * 80)
    print("📊 COMPARISON ANALYSIS:")
    print("=" * 80)

    mb_success = mb_api_result and mb_api_result.get('success')
    itunes_success = itunes_result and itunes_result.get('success')
    offline_success = offline_result and offline_result.get('success')

    if mb_success and offline_success:
        print("\n🔍 Comparing MusicBrainz API vs Offline DB:")

        # Compare artists
        api_artist = mb_api_result.get('artist', '')
        offline_artist = offline_result.get('artist', '')

        if api_artist == offline_artist:
            print(f"  ✅ Artist Match: {api_artist}")
        else:
            print(f"  ❌ ARTIST MISMATCH!")
            print(f"     API Artist (CORRECT):     {api_artist}")
            print(f"     Offline Artist (WRONG):   {offline_artist}")

    if itunes_success and offline_success:
        print("\n🔍 Comparing iTunes API vs Offline DB:")

        # Compare artists
        itunes_artist = itunes_result.get('artist', '')
        offline_artist = offline_result.get('artist', '')

        if itunes_artist == offline_artist:
            print(f"  ✅ Artist Match: {itunes_artist}")
        else:
            print(f"  ❌ ARTIST MISMATCH!")
            print(f"     iTunes Artist (CORRECT):  {itunes_artist}")
            print(f"     Offline Artist (WRONG):   {offline_artist}")

    # Final verdict
    print("\n" + "=" * 80)
    print("🎯 FINAL VERDICT:")
    print("=" * 80)

    if mb_success and offline_success:
        api_artist = mb_api_result.get('artist', '')
        offline_artist = offline_result.get('artist', '')

        if api_artist == offline_artist:
            print("✅ Offline database is CORRECT - matches MusicBrainz API ground truth")
        else:
            print("❌ Offline database is INCORRECT - does NOT match MusicBrainz API ground truth")
            print("\n🔧 REQUIRED FIX:")
            print("   The offline database search algorithm needs to be updated to prioritize")
            print("   the same results that the MusicBrainz API returns.")
            print(f"\n   Expected (API):  {api_artist}")
            print(f"   Got (Offline):   {offline_artist}")
    elif not mb_success:
        print("⚠️  Cannot verify - MusicBrainz API did not return a result")
    elif not offline_success:
        print("❌ Offline database FAILED - did not find a match (but API did)")

    if itunes_success and offline_success:
        itunes_artist = itunes_result.get('artist', '')
        offline_artist = offline_result.get('artist', '')

        if itunes_artist != offline_artist:
            print(f"\n⚠️  iTunes API also disagrees with offline DB:")
            print(f"   iTunes:  {itunes_artist}")
            print(f"   Offline: {offline_artist}")


if __name__ == "__main__":
    asyncio.run(test_intruder_alert())
