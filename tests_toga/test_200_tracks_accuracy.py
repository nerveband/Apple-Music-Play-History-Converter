#!/usr/bin/env python3
"""
200-track accuracy test with ground truth validation.

This test uses the actual CSV data (which comes from Apple Music API)
as ground truth, since that's what users actually have in their play history.
"""

import sys
import pandas as pd
import random
from pathlib import Path
from collections import defaultdict

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


def parse_track_description(desc: str) -> tuple:
    """Parse 'Artist - Track' format from Track Description field."""
    if not desc or pd.isna(desc):
        return None, None

    # Handle special cases
    if desc == "Apple Music 1":
        return None, None

    # Split on first ' - '
    if ' - ' in desc:
        parts = desc.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    return None, None


def load_sample_tracks_from_daily(csv_path: Path, sample_size: int = 200) -> list:
    """Load sample tracks from Play History Daily Tracks CSV."""
    print(f"📂 Loading tracks from: {csv_path.name}")

    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    # Parse Track Description field
    tracks = []
    for _, row in df.iterrows():
        desc = row.get('Track Description', '')
        artist, track = parse_track_description(desc)

        if artist and track:
            tracks.append({
                'track': track,
                'artist': artist,
                'album': None  # Daily Tracks doesn't have album info
            })

    print(f"✅ Loaded {len(tracks)} tracks with artist/track info")

    if len(tracks) > sample_size:
        tracks = random.sample(tracks, sample_size)
        print(f"   Sampled {sample_size} tracks\n")

    return tracks


def load_sample_tracks_from_full(csv_path: Path, sample_size: int = 200) -> list:
    """Load sample tracks from full Play Activity CSV."""
    print(f"📂 Loading tracks from: {csv_path.name}")

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
    except:
        df = pd.read_csv(csv_path, encoding='latin-1', low_memory=False)

    # Find columns
    track_col = 'Song Name'
    artist_col = 'Container Artist Name'
    album_col = 'Album Name'

    # Filter valid rows
    df = df[df[track_col].notna() & (df[track_col] != '')]
    df = df[df[artist_col].notna() & (df[artist_col] != '')]

    # Sample first
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    tracks = []
    for _, row in df.iterrows():
        tracks.append({
            'track': str(row[track_col]),
            'artist': str(row[artist_col]),
            'album': str(row[album_col]) if pd.notna(row.get(album_col)) else None
        })

    print(f"✅ Loaded {len(tracks)} tracks")
    print(f"   {sum(1 for t in tracks if t['album']) / max(len(tracks), 1) * 100:.0f}% have album info\n")

    return tracks


def test_track_matching(manager, track_data: dict, verbose: bool = False) -> dict:
    """Test matching for a single track."""
    result = {
        'track': track_data['track'],
        'artist_expected': track_data['artist'],
        'album_expected': track_data['album'],
        'artist_found': None,
        'match_type': None,
        'correct': False,
        'artist_match': False
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

    # Exact match
    if expected_clean == found_clean:
        result['artist_match'] = True
        result['correct'] = True
        result['match_type'] = 'EXACT_ARTIST'
        return result

    # Substring match (handles "feat" variations)
    if expected_clean in found_clean or found_clean in expected_clean:
        result['artist_match'] = True
        result['correct'] = True
        result['match_type'] = 'PARTIAL_ARTIST'
        return result

    # Token-based matching (for collaborations)
    expected_tokens = set(expected_clean.split())
    found_tokens = set(found_clean.split())
    common_tokens = expected_tokens & found_tokens

    # Require at least 70% token overlap or minimum 2 tokens
    min_tokens = min(len(expected_tokens), len(found_tokens))
    required_match = max(2, int(min_tokens * 0.7))

    if len(common_tokens) >= required_match:
        result['artist_match'] = True
        result['correct'] = True
        result['match_type'] = 'TOKEN_MATCH'
        return result

    result['match_type'] = 'WRONG_ARTIST'
    return result


def main():
    """Run 200-track accuracy test."""
    print("=" * 100)
    print("🧪 200-TRACK COMPREHENSIVE ACCURACY TEST")
    print("=" * 100)
    print()

    # Initialize manager
    data_dir = str(get_database_dir())
    manager = MusicBrainzManagerV2Optimized(data_dir)

    if not manager.is_ready():
        print("❌ Manager not ready - run optimization first")
        return

    print("✅ Manager ready\n")

    # Try to load 200 tracks from available CSVs
    all_tracks = []

    # Try Play History Daily Tracks first (cleaner format)
    daily_csv = Path(__file__).parent / "_test_csvs" / "Apple Music - Play History Daily Tracks.csv"
    if daily_csv.exists():
        daily_tracks = load_sample_tracks_from_daily(daily_csv, sample_size=100)
        all_tracks.extend(daily_tracks)

    # Add from full CSV if we need more
    if len(all_tracks) < 200:
        full_csv = Path(__file__).parent / "_test_csvs" / "Apple Music Play Activity full.csv"
        if full_csv.exists():
            needed = 200 - len(all_tracks)
            full_tracks = load_sample_tracks_from_full(full_csv, sample_size=needed)
            all_tracks.extend(full_tracks)

    if not all_tracks:
        print("❌ No tracks loaded from CSV files")
        return

    print(f"📊 Total tracks to test: {len(all_tracks)}\n")

    # Test all tracks
    print("🔍 Testing track matching...")
    print("-" * 100)

    results = []
    correct_count = 0

    for i, track_data in enumerate(all_tracks, 1):
        result = test_track_matching(manager, track_data)
        results.append(result)

        if result['correct']:
            correct_count += 1

        # Progress indicator
        if i % 25 == 0:
            accuracy = (correct_count / i) * 100
            print(f"   [{i:3d}/{len(all_tracks)}] Accuracy: {accuracy:.1f}%")

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

    # Analyze failures by pattern
    failures = [r for r in results if not r['correct']]
    if failures:
        print(f"\n🔍 Failure Analysis ({len(failures)} failures):")
        print("-" * 100)

        # Group by failure type
        not_found_cases = [f for f in failures if f['match_type'] == 'NOT_FOUND']
        wrong_artist_cases = [f for f in failures if f['match_type'] == 'WRONG_ARTIST']

        if not_found_cases:
            print(f"\n❌ NOT FOUND ({len(not_found_cases)} cases):")
            for i, r in enumerate(not_found_cases[:5], 1):
                print(f"   [{i}] '{r['track']}' by '{r['artist_expected']}'")
                if r['album_expected']:
                    print(f"       Album: {r['album_expected']}")

        if wrong_artist_cases:
            print(f"\n❌ WRONG ARTIST ({len(wrong_artist_cases)} cases):")
            for i, r in enumerate(wrong_artist_cases[:10], 1):
                print(f"   [{i}] Track: {r['track']}")
                print(f"       Expected: {r['artist_expected']}")
                print(f"       Found: {r['artist_found']}")
                if r['album_expected']:
                    print(f"       Album: {r['album_expected']}")
                print()

    # Show sample successes
    successes = [r for r in results if r['correct']]
    if successes:
        print(f"✅ Sample Successes (random 10 of {len(successes)}):")
        print("-" * 100)
        sample_successes = random.sample(successes, min(10, len(successes)))
        for i, r in enumerate(sample_successes, 1):
            print(f"   [{i}] '{r['track']}' by '{r['artist_expected']}' → {r['artist_found']} ({r['match_type']})")

    print("\n" + "=" * 100)
    print(f"🎯 FINAL ACCURACY: {accuracy:.1f}%")
    print("=" * 100)


if __name__ == "__main__":
    main()
