#!/usr/bin/env python3
"""
Detailed debugging to understand why Matrixxman is chosen over Lupe Fiasco
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Investigate database candidates"""

    print("=" * 80)
    print("🔍 Detailed Investigation: Intruder Alert")
    print("=" * 80)

    # Initialize manager
    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready")
        return

    # Clean the track name the same way the search does
    track_name = "Intruder Alert (feat. Sarah Green)"
    clean_track = manager.clean_text_conservative(track_name)

    print(f"\n📊 Track: {track_name}")
    print(f"   Cleaned: '{clean_track}'")

    album_hint = "Lupe Fiasco's The Cool (Deluxe Edition)"
    clean_album = manager.clean_text_conservative(album_hint)
    print(f"\n📊 Album hint: {album_hint}")
    print(f"   Cleaned: '{clean_album}'")

    # Query both HOT and COLD tables
    for table in ["musicbrainz_hot", "musicbrainz_cold"]:
        print(f"\n" + "=" * 80)
        print(f"🔍 Querying {table.upper()} table")
        print("=" * 80)

        sql = f"""
            SELECT
                artist_credit_name,
                release_name,
                recording_clean,
                artist_clean,
                score
            FROM {table}
            WHERE recording_clean = ?
            ORDER BY score DESC
            LIMIT 20
        """

        try:
            rows = manager._conn.execute(sql, [clean_track]).fetchall()

            if not rows:
                print(f"❌ No exact matches found for '{clean_track}'")
                continue

            print(f"✅ Found {len(rows)} matches")
            print()

            for i, row in enumerate(rows, 1):
                artist_credit, release_name, recording_clean, artist_clean, base_score = row

                print(f"[{i}] Artist: {artist_credit}")
                print(f"    Album: {release_name}")
                print(f"    Base Score: {base_score:,}")

                # Calculate score the same way the manager does
                release_clean = manager.clean_text_conservative(release_name) if release_name else ''

                # Check album match
                album_exact_match = (clean_album == release_clean)
                album_partial_match = (clean_album in release_clean or release_clean in clean_album)

                print(f"    Release Clean: '{release_clean}'")
                print(f"    Album Exact Match: {album_exact_match}")
                print(f"    Album Partial Match: {album_partial_match}")

                # Calculate final score
                weight = float(base_score)

                # Get popularity score
                popularity = manager._get_artist_popularity_score(artist_credit)
                weight += popularity

                if popularity > 0:
                    print(f"    Popularity Bonus: +{popularity:,}")

                # Album bonuses
                if album_exact_match:
                    weight += 5_000_000
                    print(f"    Album Exact Bonus: +5,000,000")
                elif album_partial_match:
                    weight += 3_000_000
                    print(f"    Album Partial Bonus: +3,000,000")

                print(f"    FINAL SCORE: {weight:,}")
                print()

        except Exception as e:
            print(f"❌ Error querying {table}: {e}")

    # Now run the actual search to see what gets chosen
    print("\n" + "=" * 80)
    print("🎯 Running actual manager.search()")
    print("=" * 80)

    result = manager.search(
        track_name=track_name,
        artist_hint="Lupe Fiasco",
        album_hint=album_hint
    )

    print(f"\n📊 Search Result: {result}")


if __name__ == "__main__":
    main()
