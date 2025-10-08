#!/usr/bin/env python3
"""
Comprehensive comparison test across all three search providers.
Tests 100 diverse tracks and analyzes patterns in successes/failures.
"""

import sys
import os
import asyncio
import pandas as pd
import random
from pathlib import Path
from collections import defaultdict
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2
from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized

# CSV file path
CSV_PATH = "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Desktop/Apple Music Play Activity full_Converted_20251006_201637.csv"

def print_separator(title=""):
    """Print a visual separator."""
    print("\n" + "=" * 100)
    if title:
        print(f"  {title}")
        print("=" * 100)

def has_unicode(text):
    """Check if text contains non-ASCII Unicode characters."""
    if not text or not isinstance(text, str):
        return False
    return any(ord(c) > 127 for c in text)

def is_likely_cover_or_remix(artist_str, track_str=""):
    """Detect if this is likely a cover/remix version."""
    if not isinstance(artist_str, str):
        return False

    artist_lower = artist_str.lower()
    track_lower = track_str.lower() if track_str else ""

    cover_keywords = [
        'dj ', 'remix', 'cover', 'tribute', 'karaoke',
        '8-bit', 'acoustic', 'piano', 'orchestra',
        'vs ', 'ft ', 'feat.', 'featuring',
        'lounge', 'jazz', 'version'
    ]

    for keyword in cover_keywords:
        if keyword in artist_lower or keyword in track_lower:
            return True

    return False

def select_strategic_sample(df, sample_size=100):
    """
    Select a strategic sample for comprehensive testing:
    - 20% Unicode characters
    - 30% likely covers/remixes (to test this challenging case)
    - 30% with clean album info (canonical tracks)
    - 20% random diverse tracks
    """
    samples = []

    # 1. Unicode tracks (20%)
    unicode_tracks = df[df['Track'].apply(has_unicode) | df['Artist'].apply(has_unicode)]
    if len(unicode_tracks) > 0:
        n = min(20, len(unicode_tracks))
        unicode_sample = unicode_tracks.sample(n=n)
        samples.append(unicode_sample)
        print(f"   📝 Selected {len(unicode_sample)} tracks with Unicode")

    # 2. Likely covers/remixes (30%) - the challenging cases
    df['is_cover'] = df.apply(lambda row: is_likely_cover_or_remix(
        str(row['Artist']) if pd.notna(row['Artist']) else "",
        str(row['Track']) if pd.notna(row['Track']) else ""
    ), axis=1)
    cover_tracks = df[df['is_cover']]
    if len(cover_tracks) > 0:
        n = min(30, len(cover_tracks))
        cover_sample = cover_tracks.sample(n=n)
        samples.append(cover_sample)
        print(f"   📝 Selected {len(cover_sample)} likely covers/remixes")

    # 3. Clean canonical tracks with album info (30%)
    canonical_tracks = df[
        (df['Album'].notna()) &
        (df['Album'] != '') &
        (~df['is_cover'])
    ]
    if len(canonical_tracks) > 0:
        n = min(30, len(canonical_tracks))
        canonical_sample = canonical_tracks.sample(n=n)
        samples.append(canonical_sample)
        print(f"   📝 Selected {len(canonical_sample)} canonical tracks with albums")

    # 4. Random diverse (20%)
    remaining = sample_size - sum(len(s) for s in samples)
    if remaining > 0:
        random_sample = df.sample(n=min(remaining, len(df)))
        samples.append(random_sample)
        print(f"   📝 Selected {len(random_sample)} random tracks")

    # Combine and deduplicate
    combined = pd.concat(samples).drop_duplicates(subset=['Track', 'Artist', 'Album'])

    # If we have more than needed, sample down
    if len(combined) > sample_size:
        combined = combined.sample(n=sample_size)

    return combined

def artists_match(csv_artist, found_artist):
    """
    Check if artists match using improved flexible matching.

    Uses MusicBrainzManagerV2Optimized.artists_match_flexible() which handles:
    - Unicode normalization (en-dash vs hyphen, etc.)
    - Featured artist detection
    - Main artist extraction
    - Partial matches
    """
    if pd.isna(csv_artist):
        return True  # No artist to compare

    # Use the new flexible matching from musicbrainz_manager
    matches, match_type = MusicBrainzManagerV2Optimized.artists_match_flexible(
        str(csv_artist), str(found_artist)
    )

    return matches

async def test_all_providers(service, track, csv_artist, album):
    """Test a track against all three providers."""
    results = {}

    for provider in ["musicbrainz", "musicbrainz_api", "itunes"]:
        service.set_search_provider(provider)

        try:
            result = await service.search_song(
                song_name=track,
                artist_name=None,
                album_name=album if pd.notna(album) else None
            )

            if result['success']:
                results[provider] = {
                    'success': True,
                    'artist': result['artist'],
                    'match': artists_match(csv_artist, result['artist'])
                }
            else:
                results[provider] = {
                    'success': False,
                    'error': result.get('error', 'Unknown')
                }

        except Exception as e:
            results[provider] = {
                'success': False,
                'error': str(e)
            }

        # Rate limiting for APIs
        if provider in ["musicbrainz_api", "itunes"]:
            await asyncio.sleep(1.2)

    return results

async def run_comprehensive_test():
    """Run comprehensive comparison test."""
    print_separator("COMPREHENSIVE 3-PROVIDER COMPARISON - 100 TRACKS")

    # Load CSV
    print(f"\n📂 Loading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    print(f"   Total rows: {len(df):,}")

    # Select strategic sample
    print("\n🎲 Selecting strategic sample of 100 tracks:")
    sample_df = select_strategic_sample(df, sample_size=100)
    print(f"\n   ✅ Selected {len(sample_df)} unique tracks")

    # Statistics
    unicode_count = sum(1 for _, row in sample_df.iterrows()
                       if has_unicode(row['Track']) or has_unicode(str(row['Artist'])))
    cover_count = sum(1 for _, row in sample_df.iterrows()
                     if is_likely_cover_or_remix(str(row['Artist']) if pd.notna(row['Artist']) else "",
                                                 str(row['Track'])))
    album_count = sum(1 for _, row in sample_df.iterrows()
                     if pd.notna(row.get('Album')) and row.get('Album') != '')

    print(f"\n📊 Sample Statistics:")
    print(f"   🌐 Unicode tracks: {unicode_count}/{len(sample_df)}")
    print(f"   🎸 Cover/Remix tracks: {cover_count}/{len(sample_df)}")
    print(f"   📀 Tracks with album: {album_count}/{len(sample_df)}")
    print(f"   🎵 Unique artists: {sample_df['Artist'].nunique()}")

    # Initialize service
    print("\n🚀 Initializing MusicSearchServiceV2...")
    service = MusicSearchServiceV2()

    if not service.musicbrainz_manager.is_ready():
        print("❌ MusicBrainz database not ready")
        return

    print("   ✅ All providers ready")

    # Test each track
    print_separator("TESTING TRACKS AGAINST ALL PROVIDERS")

    all_results = []
    total = len(sample_df)

    start_time = time.time()

    for idx, (_, row) in enumerate(sample_df.iterrows(), 1):
        track = row['Track']
        artist = row['Artist']
        album = row.get('Album', None)

        print(f"\n[{idx}/{total}] {track}")
        print(f"   CSV Artist: {artist}")
        if album and pd.notna(album):
            print(f"   Album: {album}")

        # Test all providers
        provider_results = await test_all_providers(service, track, artist, album)

        # Show results
        for provider, result in provider_results.items():
            if result['success']:
                match_icon = "✅" if result['match'] else "❌"
                print(f"   {match_icon} {provider:15} → {result['artist']}")
            else:
                print(f"   💥 {provider:15} → FAILED: {result.get('error', 'Unknown')}")

        # Store
        all_results.append({
            'track': track,
            'csv_artist': artist,
            'album': album,
            'is_unicode': has_unicode(track) or has_unicode(str(artist)),
            'is_cover': is_likely_cover_or_remix(str(artist) if pd.notna(artist) else "", str(track)),
            'has_album': pd.notna(album) and album != '',
            'results': provider_results
        })

    elapsed = time.time() - start_time

    # Analysis
    print_separator("COMPREHENSIVE ANALYSIS")

    # Overall stats per provider
    provider_stats = {
        'musicbrainz': {'matches': 0, 'mismatches': 0, 'failures': 0},
        'musicbrainz_api': {'matches': 0, 'mismatches': 0, 'failures': 0},
        'itunes': {'matches': 0, 'mismatches': 0, 'failures': 0}
    }

    for result in all_results:
        for provider, prov_result in result['results'].items():
            if prov_result['success']:
                if prov_result['match']:
                    provider_stats[provider]['matches'] += 1
                else:
                    provider_stats[provider]['mismatches'] += 1
            else:
                provider_stats[provider]['failures'] += 1

    # Print overall stats
    print(f"\n📊 Overall Results ({len(all_results)} tracks, {elapsed:.1f}s):\n")

    for provider in ['musicbrainz', 'musicbrainz_api', 'itunes']:
        stats = provider_stats[provider]
        total_success = stats['matches'] + stats['mismatches']
        total_tests = sum(stats.values())
        accuracy = (stats['matches'] / total_tests * 100) if total_tests > 0 else 0
        success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0

        print(f"{provider.upper().replace('_', ' '):20}")
        print(f"   ✅ Matches:    {stats['matches']:3}/{total_tests} ({accuracy:.1f}%)")
        print(f"   ❌ Mismatches: {stats['mismatches']:3}/{total_tests}")
        print(f"   💥 Failures:   {stats['failures']:3}/{total_tests}")
        print(f"   📈 Success:    {total_success:3}/{total_tests} ({success_rate:.1f}%)")
        print()

    # Category-specific analysis
    print_separator("CATEGORY ANALYSIS")

    categories = {
        'Unicode': lambda r: r['is_unicode'],
        'Covers/Remixes': lambda r: r['is_cover'],
        'With Album': lambda r: r['has_album'],
        'Clean/Canonical': lambda r: r['has_album'] and not r['is_cover']
    }

    for cat_name, cat_filter in categories.items():
        cat_results = [r for r in all_results if cat_filter(r)]

        if not cat_results:
            continue

        print(f"\n📋 {cat_name} ({len(cat_results)} tracks):")

        for provider in ['musicbrainz', 'musicbrainz_api', 'itunes']:
            matches = sum(1 for r in cat_results
                         if r['results'][provider]['success'] and r['results'][provider]['match'])
            total = len(cat_results)
            accuracy = (matches / total * 100) if total > 0 else 0

            print(f"   {provider:20} {matches:3}/{total} ({accuracy:.1f}%)")

    # Provider agreement analysis
    print_separator("PROVIDER AGREEMENT")

    agreement_stats = {
        'all_agree': 0,
        'mb_api_agree': 0,
        'mb_itunes_agree': 0,
        'api_itunes_agree': 0,
        'all_different': 0
    }

    for result in all_results:
        mb = result['results']['musicbrainz'].get('artist', '').lower() if result['results']['musicbrainz']['success'] else None
        api = result['results']['musicbrainz_api'].get('artist', '').lower() if result['results']['musicbrainz_api']['success'] else None
        itunes = result['results']['itunes'].get('artist', '').lower() if result['results']['itunes']['success'] else None

        if mb and api and itunes:
            if mb == api == itunes:
                agreement_stats['all_agree'] += 1
            elif mb == api:
                agreement_stats['mb_api_agree'] += 1
            elif mb == itunes:
                agreement_stats['mb_itunes_agree'] += 1
            elif api == itunes:
                agreement_stats['api_itunes_agree'] += 1
            else:
                agreement_stats['all_different'] += 1

    print(f"\n🤝 Provider Agreement:")
    print(f"   All 3 agree:        {agreement_stats['all_agree']}")
    print(f"   MB DB + API agree:  {agreement_stats['mb_api_agree']}")
    print(f"   MB DB + iTunes:     {agreement_stats['mb_itunes_agree']}")
    print(f"   API + iTunes:       {agreement_stats['api_itunes_agree']}")
    print(f"   All different:      {agreement_stats['all_different']}")

    # Best performer examples
    print_separator("KEY INSIGHTS")

    # Find tracks where one provider excelled
    mb_wins = [r for r in all_results if
               r['results']['musicbrainz']['success'] and r['results']['musicbrainz']['match'] and
               (not r['results']['musicbrainz_api'].get('match', False) or not r['results']['itunes'].get('match', False))]

    api_wins = [r for r in all_results if
                r['results']['musicbrainz_api']['success'] and r['results']['musicbrainz_api']['match'] and
                (not r['results']['musicbrainz'].get('match', False) or not r['results']['itunes'].get('match', False))]

    itunes_wins = [r for r in all_results if
                   r['results']['itunes']['success'] and r['results']['itunes']['match'] and
                   (not r['results']['musicbrainz'].get('match', False) or not r['results']['musicbrainz_api'].get('match', False))]

    print(f"\n🏆 Provider Strengths:")
    print(f"   MusicBrainz DB unique wins:  {len(mb_wins)}")
    print(f"   MusicBrainz API unique wins: {len(api_wins)}")
    print(f"   iTunes unique wins:          {len(itunes_wins)}")

    if mb_wins:
        print(f"\n   MusicBrainz DB excelled at:")
        for r in mb_wins[:3]:
            print(f"      • {r['track']} - {r['csv_artist']}")

    if api_wins:
        print(f"\n   MusicBrainz API excelled at:")
        for r in api_wins[:3]:
            print(f"      • {r['track']} - {r['csv_artist']}")

    if itunes_wins:
        print(f"\n   iTunes excelled at:")
        for r in itunes_wins[:3]:
            print(f"      • {r['track']} - {r['csv_artist']}")

    # Export detailed results
    output_file = "comprehensive_test_results.csv"
    export_data = []
    for r in all_results:
        export_data.append({
            'Track': r['track'],
            'CSV_Artist': r['csv_artist'],
            'Album': r['album'],
            'Is_Unicode': r['is_unicode'],
            'Is_Cover': r['is_cover'],
            'MB_Artist': r['results']['musicbrainz'].get('artist', 'FAILED'),
            'MB_Match': r['results']['musicbrainz'].get('match', False),
            'API_Artist': r['results']['musicbrainz_api'].get('artist', 'FAILED'),
            'API_Match': r['results']['musicbrainz_api'].get('match', False),
            'iTunes_Artist': r['results']['itunes'].get('artist', 'FAILED'),
            'iTunes_Match': r['results']['itunes'].get('match', False),
        })

    export_df = pd.DataFrame(export_data)
    export_df.to_csv(output_file, index=False)
    print(f"\n💾 Detailed results exported to: {output_file}")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
