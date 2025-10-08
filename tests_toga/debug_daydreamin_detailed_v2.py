#!/usr/bin/env python3
"""
Detailed debug of Daydreamin' search with full logging
"""

import sys
import logging
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Enable DEBUG logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Debug Daydreamin' with full logging"""

    print("=" * 80)
    print("🔍 DETAILED Debug: Daydreamin'")
    print("=" * 80)

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready")
        return

    track_name = "Daydreamin' (feat. Jill Scott)"
    artist_hint = "Lupe Fiasco"
    album_hint = "Lupe Fiasco's Food & Liquor"

    print(f"\n📊 Input:")
    print(f"   Track: {track_name}")
    print(f"   Artist: {artist_hint}")
    print(f"   Album: {album_hint}")

    clean_track = manager.clean_text_conservative(track_name)
    print(f"\n   Cleaned track: '{clean_track}'")

    # Manually test the combined search
    print("\n" + "=" * 80)
    print("🔍 Testing _search_fuzzy_exact_combined manually")
    print("=" * 80)

    # Query hot table
    hot_rows = manager._query_fuzzy_exact(clean_track, album_hint, use_hot=True)
    print(f"\n✅ HOT table: {len(hot_rows)} rows")
    for i, row in enumerate(hot_rows[:5], 1):
        artist_credit, release_name, score = row
        print(f"   [{i}] {artist_credit} - {release_name} - Score: {score:,}")

    # Query cold table
    cold_rows = manager._query_fuzzy_exact(clean_track, album_hint, use_hot=False)
    print(f"\n✅ COLD table: {len(cold_rows)} rows")
    for i, row in enumerate(cold_rows[:10], 1):
        artist_credit, release_name, score = row
        print(f"   [{i}] {artist_credit} - {release_name} - Score: {score:,}")

    # Combine and score
    all_rows = list(hot_rows) + list(cold_rows)
    print(f"\n📊 COMBINED: {len(all_rows)} total rows")

    print("\n" + "=" * 80)
    print("🎯 Running full search")
    print("=" * 80)

    result = manager.search(
        track_name=track_name,
        artist_hint=artist_hint,
        album_hint=album_hint
    )

    print(f"\n📊 Final Result: {result}")


if __name__ == "__main__":
    main()
