#!/usr/bin/env python3
"""
Test iTunes API functionality with test CSVs.
"""
import sys
import asyncio
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

async def test_itunes_search():
    """Test iTunes API search with sample tracks."""

    print("=" * 70)
    print("iTunes API Test")
    print("=" * 70)

    # Initialize service
    print("\n1. Initializing Music Search Service...")
    service = MusicSearchServiceV2()
    service.set_search_provider('itunes')
    print("✅ Service initialized with iTunes provider")

    # Test tracks
    test_tracks = [
        {'track': 'Waves: Tropical Waves', 'album': 'Ocean Waves'},
        {'track': 'The Sixteenth Six-Tooth Son of Fourteen Four Regional Dimensions', 'album': 'Nespithe'},
        {'track': 'Where Ghosts Fall Silent', 'album': 'Quietus'},
    ]

    print(f"\n2. Testing {len(test_tracks)} sample tracks...")
    results = []

    for i, track_data in enumerate(test_tracks, 1):
        track = track_data['track']
        album = track_data['album']

        print(f"\n   Track {i}/{len(test_tracks)}: '{track}'")
        print(f"   Album: '{album}'")

        try:
            result = await service.search_song(track, '', album)

            if result and result.get('success'):
                artist = result.get('artist')
                print(f"   ✅ Found: {artist}")
                results.append({
                    'track': track,
                    'album': album,
                    'artist': artist,
                    'success': True
                })
            else:
                print(f"   ❌ Not found")
                results.append({
                    'track': track,
                    'album': album,
                    'artist': None,
                    'success': False
                })
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            results.append({
                'track': track,
                'album': album,
                'artist': None,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    successful = sum(1 for r in results if r.get('success'))
    print(f"✅ Successful searches: {successful}/{len(results)}")
    print(f"❌ Failed searches: {len(results) - successful}/{len(results)}")

    print("\nDetailed Results:")
    for i, result in enumerate(results, 1):
        status = "✅" if result.get('success') else "❌"
        artist = result.get('artist', 'Not found')
        print(f"  {status} Track {i}: {result['track'][:50]}... → {artist}")

    return results

if __name__ == '__main__':
    print("Testing iTunes API with sample tracks...\n")
    results = asyncio.run(test_itunes_search())
    print("\n✅ Test complete!")