#!/usr/bin/env python3
"""
Comprehensive matching accuracy test with 100-200 real tracks.

Tests the three critical fixes:
1. Unicode normalization (curly quotes → straight quotes)
2. Dynamic SEARCH_ROW_LIMIT (10 vs 100 based on hints)
3. SQL ORDER BY boost (1B+ for album matches)
"""

import sys
import pandas as pd
import random
from pathlib import Path
from collections import defaultdict

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def load_sample_tracks(csv_path: Path, sample_size: int = 200) -> list:
    """Load sample tracks from CSV file."""
    print(f"📂 Loading tracks from: {csv_path.name}")

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(csv_path, encoding='latin-1')
        except:
            df = pd.read_csv(csv_path, encoding='windows-1252')

    # Detect columns
    track_col = None
    artist_col = None
    album_col = None

    for col in df.columns:
        col_lower = col.lower()
        if 'track' in col_lower or 'song' in col_lower or 'title' in col_lower:
            if not track_col:
                track_col = col
        if 'artist' in col_lower:
            if not artist_col:
                artist_col = col
        if 'album' in col_lower or 'release' in col_lower:
            if not album_col:
                album_col = col

    if not track_col or not artist_col:
        print(f"❌ Could not detect track/artist columns")
        return []

    # Filter out null values for required fields only
    df = df.dropna(subset=[track_col, artist_col])

    # Sample tracks FIRST
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    tracks = []
    for _, row in df.iterrows():
        track = {
            'track': str(row[track_col]),
            'artist': str(row[artist_col]),
            'album': str(row[album_col]) if album_col and pd.notna(row[album_col]) else None
        }
        tracks.append(track)

    print(f"✅ Loaded {len(tracks)} tracks")
    print(f"   {sum(1 for t in tracks if t['album']) / len(tracks) * 100:.0f}% have album info\n")

    return tracks


def run_track_matching(manager, track_data: dict) -> dict:
    """Test matching for a single track."""
    result = {
        'track': track_data['track'],
        'artist_expected': track_data['artist'],
        'album_expected': track_data['album'],
        'artist_found': None,
        'match_type': None,
        'correct': False,
        'artist_match': False,
        'album_match': False
    }

    # Search with all available context
    artist_found = manager.search(
        track_name=track_data['track'],
        artist_hint=track_data['artist'],
        album_hint=track_data['album']
    )

    result['artist_found'] = artist_found

    if not artist_found:
        result['match_type'] = 'NOT_FOUND'
        return result

    # Normalize for comparison
    expected_clean = manager.clean_text_conservative(track_data['artist'])
    found_clean = manager.clean_text_conservative(artist_found)

    # Check if artist matches
    if expected_clean == found_clean:
        result['artist_match'] = True
        result['correct'] = True
        result['match_type'] = 'EXACT_ARTIST'
    elif expected_clean in found_clean or found_clean in expected_clean:
        result['artist_match'] = True
        result['correct'] = True
        result['match_type'] = 'PARTIAL_ARTIST'
    else:
        # Check for featuring/collaboration variations
        expected_tokens = set(expected_clean.split())
        found_tokens = set(found_clean.split())
        common_tokens = expected_tokens & found_tokens

        if len(common_tokens) >= min(len(expected_tokens), 3):
            result['artist_match'] = True
            result['correct'] = True
            result['match_type'] = 'TOKEN_MATCH'
        else:
            result['match_type'] = 'WRONG_ARTIST'

    return result


def main():
    """Run comprehensive accuracy test."""
    print("=" * 100)
    print("🧪 COMPREHENSIVE MATCHING ACCURACY TEST")
    print("=" * 100)
    print()

    # Initialize manager
    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready - run optimization first")
        return

    print("✅ Manager ready\n")

    # Try multiple CSVs to get enough tracks
    csv_files = [
        Path(__file__).parent / "_test_csvs" / "Apple Music - Recently Played Tracks.csv",
        Path(__file__).parent / "_test_csvs" / "Apple Music - Play History Daily Tracks.csv",
        Path(__file__).parent / "_test_csvs" / "Apple Music Play Activity full.csv",
    ]

    csv_path = None
    for path in csv_files:
        if path.exists():
            csv_path = path
            break

    if not csv_path:
        print(f"❌ No CSV found in _test_csvs/")
        return

    tracks = load_sample_tracks(csv_path, sample_size=200)

    if not tracks:
        print("❌ No tracks loaded")
        return

    # Test all tracks
    print("🔍 Testing track matching...")
    print("-" * 100)

    results = []
    correct_count = 0

    for i, track_data in enumerate(tracks, 1):
        result = run_track_matching(manager, track_data)
        results.append(result)

        if result['correct']:
            correct_count += 1

        # Progress indicator
        if i % 20 == 0:
            accuracy = (correct_count / i) * 100
            print(f"   [{i:3d}/{len(tracks)}] Accuracy: {accuracy:.1f}%")

    # Final statistics
    print()
    print("=" * 100)
    print("📊 RESULTS")
    print("=" * 100)

    total = len(results)
    correct = sum(1 for r in results if r['correct'])
    not_found = sum(1 for r in results if r['match_type'] == 'NOT_FOUND')
    wrong_artist = sum(1 for r in results if r['match_type'] == 'WRONG_ARTIST')

    accuracy = (correct / total) * 100

    print(f"\n✅ OVERALL ACCURACY: {accuracy:.1f}% ({correct}/{total})")
    print(f"   📊 Correct matches: {correct}")
    print(f"   ❌ Wrong artist: {wrong_artist}")
    print(f"   ⚠️  Not found: {not_found}")

    # Match type breakdown
    print("\n📋 Match Type Breakdown:")
    match_types = defaultdict(int)
    for r in results:
        match_types[r['match_type']] += 1

    for match_type, count in sorted(match_types.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        print(f"   {match_type:20s}: {count:3d} ({pct:5.1f}%)")

    # Show some failures for analysis
    failures = [r for r in results if not r['correct']]
    if failures:
        print(f"\n❌ Sample Failures (showing first 10 of {len(failures)}):")
        print("-" * 100)
        for i, r in enumerate(failures[:10], 1):
            print(f"\n[{i}] Track: {r['track']}")
            print(f"    Expected: {r['artist_expected']}")
            print(f"    Found: {r['artist_found']}")
            if r['album_expected']:
                print(f"    Album: {r['album_expected']}")
            print(f"    Type: {r['match_type']}")

    # Show some successes for confirmation
    successes = [r for r in results if r['correct']]
    if successes:
        print(f"\n✅ Sample Successes (showing random 10):")
        print("-" * 100)
        sample_successes = random.sample(successes, min(10, len(successes)))
        for i, r in enumerate(sample_successes, 1):
            print(f"\n[{i}] Track: {r['track']}")
            print(f"    Expected: {r['artist_expected']}")
            print(f"    Found: {r['artist_found']}")
            if r['album_expected']:
                print(f"    Album: {r['album_expected']}")
            print(f"    Type: {r['match_type']}")

    print("\n" + "=" * 100)
    print(f"🎯 FINAL ACCURACY: {accuracy:.1f}%")
    print("=" * 100)


if __name__ == "__main__":
    main()
