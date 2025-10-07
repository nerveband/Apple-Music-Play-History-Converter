#!/usr/bin/env python3
"""
Comprehensive test script for all search providers.
Tests MusicBrainz DB, MusicBrainz API, and iTunes API with real data.
"""

import sys
import os
import asyncio
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2
from apple_music_history_converter.app_directories import get_database_dir

# Test cases from the "808s & Heartbreak" album
TEST_CASES = [
    {
        "track": "Say You Will",
        "artist": "Kanye West",  # Expected correct artist
        "album": "808s & Heartbreak",
        "description": "First track from 808s & Heartbreak (was matching to Mike Candys)"
    },
    {
        "track": "Welcome To Heartbreak",
        "artist": "Kanye West",  # Expected correct artist
        "album": "808s & Heartbreak",
        "description": "Track with (feat. Kid Cudi) (was matching to KIDS SEE GHOSTS)"
    },
    {
        "track": "Heartless",
        "artist": "Kanye West",  # Expected correct artist
        "album": "808s & Heartbreak",
        "description": "Popular track from 808s & Heartbreak"
    },
    {
        "track": "Amazing",
        "artist": "Kanye West",  # Expected correct artist
        "album": "808s & Heartbreak",
        "description": "Track with (feat. Young Jeezy) (was matching to Yosshie 4onthefloor)"
    },
    {
        "track": "Street Lights",
        "artist": "Kanye West",  # Expected correct artist
        "album": "808s & Heartbreak",
        "description": "Track from 808s & Heartbreak (was matching to Saint Pé)"
    }
]

def print_separator(title=""):
    """Print a visual separator."""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)
    print()

async def test_provider(service, provider_name, test_case):
    """Test a single provider with a test case."""
    print(f"🔍 Testing: {provider_name}")
    print(f"   Track: {test_case['track']}")
    print(f"   Album: {test_case['album']}")
    print(f"   Expected: {test_case['artist']}")
    print(f"   Description: {test_case['description']}")

    try:
        result = await service.search_song(
            song_name=test_case['track'],
            artist_name=None,  # Don't provide artist hint - let it discover
            album_name=test_case['album']
        )

        if result['success']:
            found_artist = result['artist']
            # Accept partial match: "Kanye West feat. Kid Cudi" matches "Kanye West"
            expected_artist = test_case['artist'].lower().strip()
            found_lower = found_artist.lower().strip()
            is_correct = (found_lower == expected_artist or
                         expected_artist in found_lower or
                         found_lower.startswith(expected_artist + " feat"))

            if is_correct:
                print(f"   ✅ CORRECT: Found '{found_artist}'")
            else:
                print(f"   ❌ WRONG: Found '{found_artist}' (expected '{test_case['artist']}')")

            return {
                "success": True,
                "found_artist": found_artist,
                "correct": is_correct,
                "source": result['source']
            }
        else:
            error = result.get('error', 'Unknown error')
            print(f"   ❌ FAILED: {error}")
            return {
                "success": False,
                "error": error
            }

    except Exception as e:
        print(f"   💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

async def test_all_providers():
    """Test all providers with all test cases."""
    print_separator("COMPREHENSIVE SEARCH PROVIDER TEST")

    # Initialize service
    print("🚀 Initializing MusicSearchServiceV2...")
    service = MusicSearchServiceV2()

    # Check if MusicBrainz DB is ready
    mb_ready = service.musicbrainz_manager.is_ready()
    print(f"   MusicBrainz DB Ready: {mb_ready}")

    if not mb_ready:
        print("   ⚠️  MusicBrainz database not optimized - will skip DB tests")

    results = {
        "musicbrainz": [],
        "musicbrainz_api": [],
        "itunes": []
    }

    # Test each provider
    for provider in ["musicbrainz", "musicbrainz_api", "itunes"]:
        if provider == "musicbrainz" and not mb_ready:
            print(f"\n⏭️  Skipping MusicBrainz DB (not ready)")
            continue

        print_separator(f"TESTING: {provider.upper().replace('_', ' ')}")

        service.set_search_provider(provider)

        for i, test_case in enumerate(TEST_CASES, 1):
            print(f"\n📋 Test Case {i}/{len(TEST_CASES)}")
            result = await test_provider(service, provider, test_case)
            results[provider].append({
                "test_case": test_case,
                "result": result
            })

            # Small delay between requests for MusicBrainz API
            if provider == "musicbrainz_api":
                await asyncio.sleep(1.2)  # Respect 1 req/sec limit

    # Print summary
    print_separator("SUMMARY")

    for provider, tests in results.items():
        if not tests:
            continue

        total = len(tests)
        correct = sum(1 for t in tests if t['result'].get('correct', False))
        failed = sum(1 for t in tests if not t['result'].get('success', False))

        print(f"\n{provider.upper().replace('_', ' ')}:")
        print(f"   Total Tests: {total}")
        print(f"   ✅ Correct: {correct}/{total} ({correct/total*100:.1f}%)")
        print(f"   ❌ Wrong: {total - correct - failed}/{total}")
        print(f"   💥 Failed: {failed}/{total}")

        # Show which tests failed
        if correct < total:
            print(f"\n   Failed Tests:")
            for test in tests:
                if not test['result'].get('correct', False):
                    tc = test['test_case']
                    res = test['result']
                    if res.get('success'):
                        print(f"      • {tc['track']}: Got '{res['found_artist']}' (expected '{tc['artist']}')")
                    else:
                        print(f"      • {tc['track']}: {res.get('error', 'Unknown error')}")

    # Compare providers
    if results["musicbrainz"] and results["musicbrainz_api"]:
        print_separator("COMPARISON: MusicBrainz DB vs API")

        for i, (db_test, api_test) in enumerate(zip(results["musicbrainz"], results["musicbrainz_api"])):
            tc = db_test['test_case']
            db_artist = db_test['result'].get('found_artist', 'N/A')
            api_artist = api_test['result'].get('found_artist', 'N/A')

            match = db_artist == api_artist
            symbol = "✅" if match else "⚠️"

            print(f"\n{symbol} {tc['track']}:")
            print(f"   DB:  {db_artist}")
            print(f"   API: {api_artist}")
            if not match:
                print(f"   ❌ MISMATCH!")

async def test_with_csv():
    """Test with actual CSV file to find problematic tracks."""
    csv_path = "/Users/nerveband/Desktop/Apple Music Play Activity full_Converted_20251006_201637.csv"

    if not os.path.exists(csv_path):
        print(f"⚠️  CSV file not found: {csv_path}")
        return

    print_separator("TESTING WITH REAL CSV DATA")

    print(f"📂 Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    # Find 808s & Heartbreak tracks
    album_filter = df['Album'].str.contains('808', case=False, na=False)
    tracks_808s = df[album_filter].head(10)

    print(f"\n🎵 Found {len(tracks_808s)} tracks from 808s & Heartbreak album:")
    print(tracks_808s[['Artist', 'Track', 'Album']].to_string(index=False))

    # Test with MusicBrainz DB
    service = MusicSearchServiceV2()
    service.set_search_provider("musicbrainz")

    if not service.musicbrainz_manager.is_ready():
        print("\n⚠️  MusicBrainz DB not ready - cannot test")
        return

    print_separator("TESTING CSV TRACKS WITH MUSICBRAINZ DB")

    mismatches = []

    for idx, row in tracks_808s.iterrows():
        current_artist = row['Artist']
        track_name = row['Track']
        album_name = row['Album']

        print(f"\n🔍 Testing: {track_name}")
        print(f"   Current: {current_artist}")
        print(f"   Album: {album_name}")

        result = await service.search_song(
            song_name=track_name,
            artist_name=None,
            album_name=album_name
        )

        if result['success']:
            found_artist = result['artist']
            if found_artist.lower().strip() != current_artist.lower().strip():
                print(f"   ❌ MISMATCH: MusicBrainz found '{found_artist}'")
                mismatches.append({
                    "track": track_name,
                    "csv_artist": current_artist,
                    "mb_artist": found_artist,
                    "album": album_name
                })
            else:
                print(f"   ✅ MATCH: {found_artist}")
        else:
            print(f"   ❌ FAILED: {result.get('error', 'Unknown')}")

    if mismatches:
        print_separator("MISMATCHES FOUND")
        print(f"\n🚨 Found {len(mismatches)} mismatches:")
        for m in mismatches:
            print(f"\n   Track: {m['track']}")
            print(f"   CSV says: {m['csv_artist']}")
            print(f"   MB found: {m['mb_artist']}")
            print(f"   Album: {m['album']}")

async def debug_musicbrainz_query():
    """Debug MusicBrainz queries with detailed logging."""
    print_separator("DEBUG: MusicBrainz Query Details")

    service = MusicSearchServiceV2()

    # Enable detailed logging
    import logging
    logging.basicConfig(level=logging.DEBUG)

    test_track = "Say You Will"
    test_album = "808s & Heartbreak"

    print(f"🔍 Debugging search for:")
    print(f"   Track: {test_track}")
    print(f"   Album: {test_album}")
    print(f"   Artist Hint: None (let it discover)")

    # Test with MusicBrainz DB
    if service.musicbrainz_manager.is_ready():
        print("\n📊 Testing with MusicBrainz DB:")
        service.set_search_provider("musicbrainz")

        result = await service.search_song(
            song_name=test_track,
            artist_name=None,
            album_name=test_album
        )

        print(f"\n   Result: {result}")

    # Test with MusicBrainz API
    print("\n📊 Testing with MusicBrainz API:")
    service.set_search_provider("musicbrainz_api")

    result = await service.search_song(
        song_name=test_track,
        artist_name=None,
        album_name=test_album
    )

    print(f"\n   Result: {result}")

if __name__ == "__main__":
    print("🧪 Search Provider Test Suite\n")

    # Run all tests
    asyncio.run(test_all_providers())

    # Test with CSV if available
    asyncio.run(test_with_csv())

    # Debug mode
    print_separator("DEBUG MODE")
    asyncio.run(debug_musicbrainz_query())

    print_separator("TESTS COMPLETE")
