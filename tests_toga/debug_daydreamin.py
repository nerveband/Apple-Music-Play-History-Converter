#!/usr/bin/env python3
"""
Debug why Daydreamin' returns wrong artist
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Debug Daydreamin'"""

    print("=" * 80)
    print("🔍 Debug: Daydreamin'")
    print("=" * 80)

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready")
        return

    track_name = "Daydreamin' (feat. Jill Scott)"
    artist_hint = "Lupe Fiasco"
    album_hint = "Lupe Fiasco's Food & Liquor"

    clean_track = manager.clean_text_conservative(track_name)
    print(f"\n📊 Track: {track_name}")
    print(f"   Cleaned: '{clean_track}'")

    # Query both tables
    for table in ["musicbrainz_hot", "musicbrainz_cold"]:
        print(f"\n{'=' * 80}")
        print(f"🔍 {table.upper()}")
        print("=" * 80)

        sql = f"""
            SELECT
                artist_credit_name,
                release_name,
                recording_clean,
                score
            FROM {table}
            WHERE recording_clean = ?
            ORDER BY score DESC
            LIMIT 10
        """

        try:
            rows = manager._conn.execute(sql, [clean_track]).fetchall()

            if not rows:
                print(f"❌ No matches")
                continue

            print(f"✅ Found {len(rows)} matches\n")

            for i, row in enumerate(rows, 1):
                artist_credit, release_name, recording_clean, base_score = row

                print(f"[{i}] Artist: {artist_credit}")
                print(f"    Album: {release_name}")
                print(f"    Base Score: {base_score:,}")

                # Check artist match
                artist_clean = manager.clean_text_conservative(artist_credit)
                artist_hint_clean = manager.clean_text_conservative(artist_hint)

                artist_exact = (artist_clean == artist_hint_clean)
                artist_partial = (artist_clean in artist_hint_clean or artist_hint_clean in artist_clean)

                print(f"    Artist Clean: '{artist_clean}'")
                print(f"    Artist Hint Clean: '{artist_hint_clean}'")
                print(f"    Artist Exact Match: {artist_exact}")
                print(f"    Artist Partial Match: {artist_partial}")

                # Calculate final score with artist bonus
                weight = float(base_score)
                popularity = manager._get_artist_popularity_score(artist_credit)
                weight += popularity

                if artist_exact:
                    weight += 10_000_000
                    print(f"    Artist Exact Bonus: +10,000,000")
                elif artist_partial:
                    weight += 7_000_000
                    print(f"    Artist Partial Bonus: +7,000,000")

                print(f"    FINAL SCORE: {weight:,}\n")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Run actual search
    print("\n" + "=" * 80)
    print("🎯 Actual Search Result")
    print("=" * 80)

    result = manager.search(
        track_name=track_name,
        artist_hint=artist_hint,
        album_hint=album_hint
    )

    print(f"\n📊 Result: {result}")


if __name__ == "__main__":
    main()
