#!/usr/bin/env python3
"""
Analyze the 21 failure cases to identify patterns.
"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir

# The 21 failure cases from the test
failures = [
    ("#1", "Aphex Twin", None),
    ("Passion", "Nightmares On Wax", None),
    ("Freedom", "Pharrell Williams", None),
    ("Sea Spray", "Loné", None),
    ("damned", "Miguel", None),
    ("L$D", "A$AP Rocky", None),
    ("With You", "Chris Brown", None),
    ("the valley", "Miguel", None),
    ("Underground", "John Carpenter & Alan Howarth", None),
    ("Hangin", "FRMTN", None),
]

def main():
    print("=" * 100)
    print("🔍 FAILURE PATTERN ANALYSIS")
    print("=" * 100)
    print()

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready")
        return

    print("Analyzing failure patterns...\n")

    for track, artist, album in failures:
        print(f"{'=' * 100}")
        print(f"Track: {track}")
        print(f"Artist: {artist}")
        print(f"Album: {album}")
        print()

        # Clean inputs
        track_clean = manager.clean_text_conservative(track)
        artist_clean = manager.clean_text_conservative(artist)

        print(f"Cleaned track: '{track_clean}'")
        print(f"Cleaned artist: '{artist_clean}'")
        print()

        # Check if track exists in database
        sql_check = f"""
            SELECT DISTINCT
                artist_credit_name,
                release_name,
                recording_name,
                score
            FROM musicbrainz_basic
            WHERE recording_name ILIKE ?
              AND artist_credit_name ILIKE ?
            ORDER BY score DESC
            LIMIT 5
        """

        try:
            rows = manager._conn.execute(sql_check, [f"%{track}%", f"%{artist}%"]).fetchall()

            if rows:
                print(f"✅ Found {len(rows)} potential matches in database:")
                for i, row in enumerate(rows, 1):
                    print(f"   [{i}] {row[0]} - {row[2]}")
                    print(f"       Album: {row[1]}")
                    print(f"       Score: {row[3]:,}")
            else:
                print(f"❌ No matches found in database for this artist/track combo")

                # Try just the track
                rows_track = manager._conn.execute(
                    "SELECT DISTINCT artist_credit_name, recording_name, score FROM musicbrainz_basic WHERE recording_name ILIKE ? ORDER BY score DESC LIMIT 5",
                    [f"%{track}%"]
                ).fetchall()

                if rows_track:
                    print(f"\n   Tracks with similar names exist:")
                    for i, row in enumerate(rows_track, 1):
                        print(f"   [{i}] {row[0]} - {row[1]} (score: {row[2]:,})")
                else:
                    print(f"\n   Track name '{track}' not found in database at all")

        except Exception as e:
            print(f"❌ Error: {e}")

        print()

if __name__ == "__main__":
    main()
