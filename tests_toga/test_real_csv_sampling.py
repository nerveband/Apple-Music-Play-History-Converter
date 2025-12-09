#!/usr/bin/env python3
"""
Test MusicBrainz accuracy with real CSV data sampling.
Includes diverse tracks with Unicode characters, various genres, etc.
"""

import sys
import os
import asyncio
import pandas as pd
import random
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

# CSV file path
CSV_PATH = "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Desktop/Apple Music Play Activity full_Converted_20251006_201637.csv"

def print_separator(title=""):
    """Print a visual separator."""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)
    print()

def has_unicode(text):
    """Check if text contains non-ASCII Unicode characters."""
    if not text or not isinstance(text, str):
        return False
    return any(ord(c) > 127 for c in text)

def select_diverse_sample(df, sample_size=50):
    """
    Select a diverse sample of tracks including:
    - Tracks with Unicode characters
    - Various artists
    - Different albums
    - Mix of popular and obscure
    """
    samples = []

    # 1. Get tracks with Unicode characters (20%)
    unicode_tracks = df[df['Track'].apply(has_unicode) | df['Artist'].apply(has_unicode)]
    if len(unicode_tracks) > 0:
        unicode_sample = unicode_tracks.sample(n=min(10, len(unicode_tracks)))
        samples.append(unicode_sample)
        print(f"   [N] Selected {len(unicode_sample)} tracks with Unicode characters")

    # 2. Get tracks with album info (60%)
    album_tracks = df[df['Album'].notna() & (df['Album'] != '')]
    if len(album_tracks) > 0:
        album_sample = album_tracks.sample(n=min(30, len(album_tracks)))
        samples.append(album_sample)
        print(f"   [N] Selected {len(album_sample)} tracks with album info")

    # 3. Random selection to fill remaining (20%)
    remaining = sample_size - sum(len(s) for s in samples)
    if remaining > 0:
        random_sample = df.sample(n=min(remaining, len(df)))
        samples.append(random_sample)
        print(f"   [N] Selected {len(random_sample)} random tracks")

    # Combine and deduplicate
    combined = pd.concat(samples).drop_duplicates(subset=['Track', 'Artist', 'Album'])

    # If we have more than needed, sample down
    if len(combined) > sample_size:
        combined = combined.sample(n=sample_size)

    return combined

async def run_track(service, track, artist, album, index, total):
    """Test a single track with MusicBrainz DB."""
    print(f"\n[{index}/{total}] Testing: {track}")
    print(f"   CSV Artist: {artist}")
    print(f"   Album: {album if album else '(none)'}")

    # Show Unicode indicator
    unicode_indicator = ""
    track_str = str(track) if pd.notna(track) else ""
    artist_str = str(artist) if pd.notna(artist) else ""
    if has_unicode(track_str) or has_unicode(artist_str):
        unicode_chars = [c for c in (track_str + artist_str) if ord(c) > 127]
        unicode_indicator = f" [W] Unicode: {', '.join(set(unicode_chars[:3]))}"
        print(f"   {unicode_indicator}")

    try:
        result = await service.search_song(
            song_name=track,
            artist_name=None,  # Let it discover
            album_name=album if pd.notna(album) else None
        )

        if result['success']:
            found_artist = result['artist']

            # Handle NaN artist
            if pd.isna(artist):
                print(f"   [!]  No CSV artist to compare - accepting MusicBrainz result: {found_artist}")
                return {"status": "match", "found": found_artist, "csv": "(none)"}

            csv_artist_lower = str(artist).lower().strip()
            found_artist_lower = found_artist.lower().strip()

            # Check if match (allow partial match for featured artists)
            is_match = (
                csv_artist_lower == found_artist_lower or
                csv_artist_lower in found_artist_lower or
                found_artist_lower in csv_artist_lower or
                found_artist_lower.startswith(csv_artist_lower + " feat")
            )

            if is_match:
                print(f"   [OK] MATCH: {found_artist}")
                return {"status": "match", "found": found_artist, "csv": artist}
            else:
                print(f"   [X] MISMATCH: Found '{found_artist}'")
                return {"status": "mismatch", "found": found_artist, "csv": artist}
        else:
            error = result.get('error', 'Unknown error')
            print(f"   [X] FAILED: {error}")
            return {"status": "failed", "error": error}

    except Exception as e:
        print(f"   [!] EXCEPTION: {e}")
        return {"status": "exception", "error": str(e)}

async def run_sampling_test():
    """Run sampling test on real CSV data."""
    print_separator("REAL CSV SAMPLING TEST - 50 DIVERSE TRACKS")

    # Load CSV
    print(f"[FOLDER] Loading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    print(f"   Total rows: {len(df):,}")

    # Check for required columns
    if 'Track' not in df.columns or 'Artist' not in df.columns:
        print("[X] CSV missing required columns (Track, Artist)")
        return

    # Select diverse sample
    print("\n[DICE] Selecting diverse sample of 50 tracks:")
    sample_df = select_diverse_sample(df, sample_size=50)
    print(f"\n   [OK] Selected {len(sample_df)} unique tracks")

    # Show sample statistics
    unicode_count = sum(1 for _, row in sample_df.iterrows()
                       if has_unicode(row['Track']) or has_unicode(row['Artist']))
    album_count = sum(1 for _, row in sample_df.iterrows()
                     if pd.notna(row.get('Album')) and row.get('Album') != '')

    print(f"\n[=] Sample Statistics:")
    print(f"   [W] Tracks with Unicode: {unicode_count}/{len(sample_df)}")
    print(f"   [DISC] Tracks with Album: {album_count}/{len(sample_df)}")
    print(f"   [#] Unique Artists: {sample_df['Artist'].nunique()}")

    # Initialize service
    print("\n[>] Initializing MusicSearchServiceV2...")
    service = MusicSearchServiceV2()
    service.set_search_provider("musicbrainz")

    if not service.musicbrainz_manager.is_ready():
        print("[X] MusicBrainz database not ready")
        return

    print("   [OK] MusicBrainz DB ready")

    # Test each track
    print_separator("TESTING TRACKS")

    results = []
    total = len(sample_df)

    for idx, (_, row) in enumerate(sample_df.iterrows(), 1):
        track = row['Track']
        artist = row['Artist']
        album = row.get('Album', None)

        result = await run_track(service, track, artist, album, idx, total)
        result['track'] = track
        result['csv_artist'] = artist
        result['album'] = album
        result['has_unicode'] = has_unicode(track) or has_unicode(artist)
        results.append(result)

    # Summary
    print_separator("RESULTS SUMMARY")

    matches = [r for r in results if r['status'] == 'match']
    mismatches = [r for r in results if r['status'] == 'mismatch']
    failed = [r for r in results if r['status'] in ['failed', 'exception']]

    total_tests = len(results)
    accuracy = (len(matches) / total_tests * 100) if total_tests > 0 else 0

    print(f"\n[=] Overall Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   [OK] Matches: {len(matches)}/{total_tests} ({len(matches)/total_tests*100:.1f}%)")
    print(f"   [X] Mismatches: {len(mismatches)}/{total_tests} ({len(mismatches)/total_tests*100:.1f}%)")
    print(f"   [!] Failed: {len(failed)}/{total_tests} ({len(failed)/total_tests*100:.1f}%)")
    print(f"\n   [*] Accuracy: {accuracy:.1f}%")

    # Unicode-specific results
    unicode_results = [r for r in results if r['has_unicode']]
    if unicode_results:
        unicode_matches = [r for r in unicode_results if r['status'] == 'match']
        unicode_accuracy = (len(unicode_matches) / len(unicode_results) * 100) if unicode_results else 0
        print(f"\n   [W] Unicode Tracks: {len(unicode_matches)}/{len(unicode_results)} matches ({unicode_accuracy:.1f}%)")

    # Album-specific results
    album_results = [r for r in results if r['album'] and pd.notna(r['album'])]
    if album_results:
        album_matches = [r for r in album_results if r['status'] == 'match']
        album_accuracy = (len(album_matches) / len(album_results) * 100) if album_results else 0
        print(f"   [DISC] Album Tracks: {len(album_matches)}/{len(album_results)} matches ({album_accuracy:.1f}%)")

    # Show mismatches
    if mismatches:
        print(f"\n[X] Mismatches ({len(mismatches)}):")
        for r in mismatches[:10]:  # Show first 10
            print(f"\n   Track: {r['track']}")
            print(f"      CSV: {r['csv_artist']}")
            print(f"      Found: {r['found']}")
            if r['album']:
                print(f"      Album: {r['album']}")

        if len(mismatches) > 10:
            print(f"\n   ... and {len(mismatches) - 10} more")

    # Show failures
    if failed:
        print(f"\n[!] Failed Searches ({len(failed)}):")
        for r in failed[:5]:  # Show first 5
            print(f"\n   Track: {r['track']}")
            print(f"      Artist: {r['csv_artist']}")
            print(f"      Error: {r.get('error', 'Unknown')}")

        if len(failed) > 5:
            print(f"\n   ... and {len(failed) - 5} more")

if __name__ == "__main__":
    asyncio.run(run_sampling_test())
