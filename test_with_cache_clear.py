#!/usr/bin/env python3
"""
Test with cache cleared to ensure we're using the new algorithm
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def main():
    """Test with cache cleared"""

    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Not ready")
        return

    # CLEAR THE CACHE
    print("🧹 Clearing search cache...")
    manager._search_cache.clear()
    manager._cache_access_order.clear()
    manager._cache_hits = 0
    manager._cache_misses = 0
    print("✅ Cache cleared\n")

    test_cases = [
        ("Intruder Alert (feat. Sarah Green)", "Lupe Fiasco", "Lupe Fiasco's The Cool (Deluxe Edition)", "Lupe Fiasco"),
        ("Daydreamin' (feat. Jill Scott)", "Lupe Fiasco", "Lupe Fiasco's Food & Liquor", "Lupe Fiasco"),
        ("Hurt Me Soul", "Lupe Fiasco", "Lupe Fiasco's Food & Liquor", "Lupe Fiasco"),
        ("The Coolest", "Lupe Fiasco", "Lupe Fiasco's The Cool (Deluxe Edition)", "Lupe Fiasco"),
    ]

    print("=" * 80)
    print("🧪 TESTING WITH CLEARED CACHE")
    print("=" * 80)

    passed = 0
    failed = 0

    for i, (track, artist, album, expected) in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {track}")
        print(f"   Artist hint: {artist}")
        print(f"   Album hint: {album}")

        result = manager.search(
            track_name=track,
            artist_hint=artist,
            album_hint=album
        )

        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")

        if result == expected:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            failed += 1

    print(f"\n{'=' * 80}")
    print(f"📊 RESULTS: {passed}/{len(test_cases)} passed ({passed/len(test_cases)*100:.1f}%)")
    print(f"={'=' * 80}\n")


if __name__ == "__main__":
    main()
