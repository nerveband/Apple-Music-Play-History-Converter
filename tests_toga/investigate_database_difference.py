#!/usr/bin/env python3
"""
Investigate why offline DB and MusicBrainz API return different results
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2
from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


async def investigate():
    """Investigate the difference"""

    print("=" * 80)
    print("🔍 INVESTIGATING OFFLINE DB vs MUSICBRAINZ API")
    print("=" * 80)

    # Initialize
    service = MusicSearchServiceV2()
    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    # Test case: Daydreamin' by Lupe Fiasco
    track_name = "Daydreamin' (feat. Jill Scott)"
    artist_hint = "Lupe Fiasco"
    album_hint = "Lupe Fiasco's Food & Liquor"

    print(f"\n📊 Test Case:")
    print(f"   Track: {track_name}")
    print(f"   Artist: {artist_hint}")
    print(f"   Album: {album_hint}")

    # 1. Check MusicBrainz API
    print(f"\n{'=' * 80}")
    print("📡 MUSICBRAINZ API (online)")
    print("=" * 80)

    mb_api_result = await service._search_musicbrainz_api_async(track_name, artist_hint, album_hint)

    if mb_api_result and mb_api_result.get('success'):
        print(f"✅ Found: {mb_api_result.get('artist')}")
        print(f"   Full result: {mb_api_result}")
    else:
        print(f"❌ Not found")
        print(f"   Result: {mb_api_result}")

    # 2. Check iTunes API
    print(f"\n{'=' * 80}")
    print("🍎 ITUNES API")
    print("=" * 80)

    itunes_result = await service._search_itunes_async(track_name, artist_hint, album_hint)

    if itunes_result and itunes_result.get('success'):
        print(f"✅ Found: {itunes_result.get('artist')}")
        print(f"   Full result: {itunes_result}")
    else:
        print(f"❌ Not found")

    # 3. Check offline database structure
    print(f"\n{'=' * 80}")
    print("💾 OFFLINE DATABASE STRUCTURE")
    print("=" * 80)

    # Check what tables exist
    print("\n📊 Available tables:")
    tables_query = "SHOW TABLES"
    tables = manager._conn.execute(tables_query).fetchall()
    for table in tables:
        print(f"   - {table[0]}")

    # Check database metadata
    print(f"\n📊 Database metadata:")
    if manager._metadata:
        print(f"   Version: {manager._metadata.get('version', 'N/A')}")
        print(f"   Download date: {manager._metadata.get('download_date', 'N/A')}")
        print(f"   Source: {manager._metadata.get('source', 'N/A')}")

    # 4. Search offline database with detailed logging
    print(f"\n{'=' * 80}")
    print("💾 OFFLINE DATABASE SEARCH (detailed)")
    print("=" * 80)

    clean_track = manager.clean_text_conservative(track_name)
    print(f"\nCleaned track name: '{clean_track}'")

    # Search for any "daydreamin" by any artist
    print(f"\n🔍 Searching for ANY 'daydreamin' tracks:")
    sql = """
        SELECT DISTINCT
            artist_credit_name,
            release_name,
            recording_clean,
            COUNT(*) as count
        FROM musicbrainz_hot
        WHERE recording_clean LIKE '%daydreamin%'
        GROUP BY artist_credit_name, release_name, recording_clean
        ORDER BY count DESC
        LIMIT 20
    """

    rows = manager._conn.execute(sql).fetchall()
    print(f"Found {len(rows)} unique artist/album combinations:")
    for i, row in enumerate(rows, 1):
        artist, album, recording, count = row
        print(f"   [{i}] {artist} - {album}")
        print(f"       Recording: '{recording}' (appears {count} times)")

    # Specifically search for Lupe Fiasco
    print(f"\n🔍 Searching for Lupe Fiasco + daydreamin:")
    sql = """
        SELECT
            artist_credit_name,
            release_name,
            recording_clean,
            artist_clean,
            score
        FROM musicbrainz_hot
        WHERE recording_clean LIKE '%daydreamin%'
          AND artist_clean LIKE '%lupe%'
        LIMIT 10
    """

    rows = manager._conn.execute(sql).fetchall()
    if rows:
        print(f"✅ Found {len(rows)} matches:")
        for i, row in enumerate(rows, 1):
            artist, album, recording, artist_clean, score = row
            print(f"   [{i}] {artist} - {album}")
            print(f"       Recording: '{recording}'")
            print(f"       Artist clean: '{artist_clean}'")
            print(f"       Score: {score:,}")
    else:
        print(f"❌ No matches found in offline database")

    # Try COLD table too
    print(f"\n🔍 Searching COLD table for Lupe Fiasco + daydreamin:")
    sql = """
        SELECT
            artist_credit_name,
            release_name,
            recording_clean,
            artist_clean,
            score
        FROM musicbrainz_cold
        WHERE recording_clean LIKE '%daydreamin%'
          AND artist_clean LIKE '%lupe%'
        LIMIT 10
    """

    rows = manager._conn.execute(sql).fetchall()
    if rows:
        print(f"✅ Found {len(rows)} matches:")
        for i, row in enumerate(rows, 1):
            artist, album, recording, artist_clean, score = row
            print(f"   [{i}] {artist} - {album}")
            print(f"       Recording: '{recording}'")
            print(f"       Artist clean: '{artist_clean}'")
            print(f"       Score: {score:,}")
    else:
        print(f"❌ No matches found in COLD table")

    # 5. Check the source CSV files
    print(f"\n{'=' * 80}")
    print("📁 SOURCE CSV FILES")
    print("=" * 80)

    csv_dir = Path(data_dir) / "musicbrainz" / "canonical"
    if csv_dir.exists():
        csv_files = list(csv_dir.glob("*.csv"))
        print(f"\nFound {len(csv_files)} CSV files:")
        for csv_file in csv_files:
            size_mb = csv_file.stat().st_size / 1024 / 1024
            print(f"   - {csv_file.name} ({size_mb:.1f} MB)")
    else:
        print(f"❌ CSV directory not found: {csv_dir}")

    # 6. Summary
    print(f"\n{'=' * 80}")
    print("📊 SUMMARY")
    print("=" * 80)

    print(f"\n🔍 Key Questions:")
    print(f"   1. Does MusicBrainz API have this track? {mb_api_result.get('success') if mb_api_result else False}")
    print(f"   2. Does iTunes API have this track? {itunes_result.get('success') if itunes_result else False}")
    print(f"   3. Does offline DB have Lupe Fiasco + Daydreamin? [see above]")
    print(f"   4. Are we using the latest MusicBrainz data? [check metadata above]")


if __name__ == "__main__":
    asyncio.run(investigate())
