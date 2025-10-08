#!/usr/bin/env python3
"""
Debug script to understand why offline DB returns Matrixxman instead of Lupe Fiasco
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Investigate the offline database data"""

    print("=" * 80)
    print("🔍 Investigating Offline Database for 'Intruder Alert'")
    print("=" * 80)

    # Initialize manager
    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready - please run optimization first")
        return

    # Search parameters
    track_name = "Intruder Alert (feat. Sarah Green)"
    artist_hint = "Lupe Fiasco"
    album_hint = "Lupe Fiasco's The Cool (Deluxe Edition)"

    print(f"\n📊 Search Parameters:")
    print(f"   Track: {track_name}")
    print(f"   Artist hint: {artist_hint}")
    print(f"   Album hint: {album_hint}")

    # Query the database directly to see all matches
    print(f"\n💾 Querying database for tracks matching 'Intruder Alert'...")
    print("-" * 80)

    # Try different variations
    queries = [
        "Intruder Alert",
        "intruder alert",
        "%Intruder Alert%",
    ]

    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        try:
            # Query using DuckDB
            sql = f"""
                SELECT DISTINCT
                    t.name as track_name,
                    a.name as artist_name,
                    r.name as album_name,
                    t.gid as track_mbid,
                    r.gid as album_mbid
                FROM recording t
                JOIN artist_credit ac ON t.artist_credit = ac.id
                JOIN artist_credit_name acn ON ac.id = acn.artist_credit
                JOIN artist a ON acn.artist = a.id
                LEFT JOIN release r ON EXISTS (
                    SELECT 1 FROM track tr
                    JOIN medium m ON tr.medium = m.id
                    WHERE tr.recording = t.id AND m.release = r.id
                )
                WHERE LOWER(t.name) LIKE LOWER('%{query}%')
                LIMIT 20
            """

            results = manager._conn.execute(sql).fetchall()

            if results:
                print(f"   Found {len(results)} results:")
                for i, row in enumerate(results, 1):
                    print(f"\n   [{i}] Track: {row[0]}")
                    print(f"       Artist: {row[1]}")
                    print(f"       Album: {row[2]}")
                    print(f"       Track MBID: {row[3]}")
            else:
                print(f"   ❌ No results found")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Now test the actual search method with debugging
    print(f"\n" + "=" * 80)
    print(f"🔍 Testing manager.search() method:")
    print("=" * 80)

    result = manager.search(
        track_name=track_name,
        artist_hint=artist_hint,
        album_hint=album_hint
    )

    print(f"\n📊 Result: {result}")


if __name__ == "__main__":
    main()
