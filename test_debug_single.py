#!/usr/bin/env python3
"""Debug single track search with detailed logging."""

import sys
import os
import asyncio
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

async def debug_search():
    print("=" * 80)
    print("DEBUG: Single Track Search with Detailed Logging")
    print("=" * 80)

    service = MusicSearchServiceV2()
    service.set_search_provider("musicbrainz")

    track = "Amazing"
    album = "808s & Heartbreak"

    print(f"\n🔍 Searching for: {track}")
    print(f"   Album hint: {album}")
    print(f"   Expected: Kanye West")
    print("\n" + "=" * 80)
    print("DETAILED DEBUG OUTPUT:")
    print("=" * 80 + "\n")

    result = await service.search_song(
        song_name=track,
        artist_name=None,
        album_name=album
    )

    print("\n" + "=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(f"Success: {result.get('success')}")
    print(f"Artist: {result.get('artist')}")
    print(f"Source: {result.get('source')}")
    if 'error' in result:
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(debug_search())
