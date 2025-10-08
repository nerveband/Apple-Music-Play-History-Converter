#!/usr/bin/env python3
"""
Debug Daydreamin' search with detailed scoring
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Debug search"""

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Not ready")
        return

    track = "Daydreamin' (feat. Jill Scott)"
    artist = "Lupe Fiasco"
    album = "Lupe Fiasco's Food & Liquor"

    print("=" * 80)
    print(f"Testing: {track}")
    print(f"Artist hint: {artist}")
    print(f"Album hint: {album}")
    print("=" * 80)

    # Call search
    result = manager.search(
        track_name=track,
        artist_hint=artist,
        album_hint=album
    )

    print(f"\n✅ Result: {result}")

    # Now test with just artist hint (no album)
    print("\n" + "=" * 80)
    print("Testing WITH artist hint but WITHOUT album hint:")
    print("=" * 80)

    result2 = manager.search(
        track_name=track,
        artist_hint=artist,
        album_hint=None
    )

    print(f"\n✅ Result: {result2}")


if __name__ == "__main__":
    main()
