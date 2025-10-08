#!/usr/bin/env python3
"""
Test Daydreamin' scoring to understand why Lupe Fiasco isn't winning
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Test scoring"""

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Not ready")
        return

    track = "Daydreamin' (feat. Jill Scott)"
    artist_hint = "Lupe Fiasco"
    album_hint = "Lupe Fiasco's Food & Liquor"

    clean_track = manager.clean_text_conservative(track)
    artist_hint_clean = manager.clean_text_conservative(artist_hint)

    print("=" * 80)
    print(f"Track: {track}")
    print(f"Clean track: '{clean_track}'")
    print(f"Artist hint: '{artist_hint}'")
    print(f"Artist hint clean: '{artist_hint_clean}'")
    print(f"Album hint: '{album_hint}'")
    print("=" * 80)

    # Manually get candidates from both tables
    print("\n🔍 QUERYING HOT TABLE:")
    hot_sql = f"""
        SELECT artist_credit_name, release_name, score
        FROM musicbrainz_hot
        WHERE recording_clean = ?
        ORDER BY score DESC
        LIMIT 5
    """
    hot_rows = manager._conn.execute(hot_sql, [clean_track]).fetchall()

    print(f"Found {len(hot_rows)} candidates:")
    for i, row in enumerate(hot_rows, 1):
        artist_credit, release_name, base_score = row
        artist_clean = manager.clean_text_conservative(artist_credit)

        # Calculate score with artist bonus
        final_score = float(base_score)
        popularity = manager._get_artist_popularity_score(artist_credit)
        final_score += popularity

        # Check artist match
        artist_exact = (artist_clean == artist_hint_clean)
        if artist_exact:
            final_score += 10_000_000

        print(f"\n[{i}] {artist_credit}")
        print(f"    Release: {release_name}")
        print(f"    Base score: {base_score:,}")
        print(f"    Artist clean: '{artist_clean}'")
        print(f"    Artist match: {artist_exact}")
        print(f"    Popularity: +{popularity:,}")
        if artist_exact:
            print(f"    Artist bonus: +10,000,000")
        print(f"    FINAL SCORE: {final_score:,}")

    print("\n🔍 QUERYING COLD TABLE:")
    cold_sql = f"""
        SELECT artist_credit_name, release_name, score
        FROM musicbrainz_cold
        WHERE recording_clean = ?
        ORDER BY score DESC
        LIMIT 10
    """
    cold_rows = manager._conn.execute(cold_sql, [clean_track]).fetchall()

    print(f"Found {len(cold_rows)} candidates:")
    for i, row in enumerate(cold_rows, 1):
        artist_credit, release_name, base_score = row
        artist_clean = manager.clean_text_conservative(artist_credit)

        # Calculate score with artist bonus
        final_score = float(base_score)
        popularity = manager._get_artist_popularity_score(artist_credit)
        final_score += popularity

        # Check artist match
        artist_exact = (artist_clean == artist_hint_clean)
        if artist_exact:
            final_score += 10_000_000

        print(f"\n[{i}] {artist_credit}")
        print(f"    Release: {release_name}")
        print(f"    Base score: {base_score:,}")
        print(f"    Artist clean: '{artist_clean}'")
        print(f"    Artist match: {artist_exact}")
        print(f"    Popularity: +{popularity:,}")
        if artist_exact:
            print(f"    Artist bonus: +10,000,000")
        print(f"    FINAL SCORE: {final_score:,}")

    # Now run actual search
    print("\n" + "=" * 80)
    print("🎯 ACTUAL SEARCH RESULT:")
    print("=" * 80)

    manager._search_cache.clear()
    manager._cache_access_order.clear()

    result = manager.search(
        track_name=track,
        artist_hint=artist_hint,
        album_hint=album_hint
    )

    print(f"\n✅ Result: {result}")


if __name__ == "__main__":
    main()
