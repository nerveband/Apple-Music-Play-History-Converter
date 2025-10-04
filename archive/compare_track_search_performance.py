#!/usr/bin/env python3
"""
Compare track search performance: Current strategy vs potential optimizations.
Uses real track+artist data from CSV files for fair comparison.
"""

import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized


def load_track_data_from_csv(csv_dir: Path = Path("./_test_csvs"), limit: Optional[int] = 100) -> List[Tuple[str, str]]:
    """Load track+artist pairs from test CSV files."""
    tracks = []
    csv_files = list(csv_dir.glob("*.csv"))

    print(f"📂 Loading track+artist pairs from {csv_dir}...")

    for csv_file in csv_files:
        try:
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'windows-1252']:
                try:
                    df = pd.read_csv(csv_file, encoding=encoding, low_memory=False)
                    break
                except UnicodeDecodeError:
                    continue

            # Find track and artist columns
            track_col = None
            artist_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'song' in col_lower or 'title' in col_lower or ('track' in col_lower and 'count' not in col_lower):
                    track_col = col
                if 'artist' in col_lower:
                    artist_col = col

            if track_col and artist_col:
                pairs = df[[track_col, artist_col]].dropna()
                track_artist_pairs = [(row[track_col], row[artist_col]) for _, row in pairs.iterrows()]
                tracks.extend(track_artist_pairs)
                print(f"   ✓ {csv_file.name}: {len(track_artist_pairs):,} track+artist pairs")

        except Exception as e:
            print(f"   ✗ {csv_file.name}: {e}")

    # Remove duplicates while preserving order
    seen = set()
    unique_tracks = []
    for track, artist in tracks:
        key = (track, artist)
        if key not in seen:
            seen.add(key)
            unique_tracks.append((track, artist))

    if limit and len(unique_tracks) > limit:
        unique_tracks = unique_tracks[:limit]
        print(f"\n✓ Loaded {len(unique_tracks):,} unique track+artist pairs (limited to {limit})\n")
    else:
        print(f"\n✓ Loaded {len(unique_tracks):,} unique track+artist pairs\n")

    return unique_tracks


def benchmark_current_strategy(track_data: List[Tuple[str, str]]) -> Dict:
    """Benchmark the current MusicBrainzManagerV2Optimized strategy."""
    print("=" * 80)
    print("🔵 CURRENT STRATEGY: MusicBrainzManagerV2Optimized")
    print("   (Track-based search with hot/cold/fuzzy tables)")
    print("=" * 80)

    data_dir = Path.home() / ".apple_music_converter" / "musicbrainz"
    mb_manager = MusicBrainzManagerV2Optimized(str(data_dir))

    if not mb_manager.is_database_available():
        print("❌ MusicBrainz database not available")
        return None

    is_ready = mb_manager.is_ready()
    print(f"📊 Database status: Ready={is_ready}")

    if not is_ready:
        print("⚠️  Database not optimized. Run optimization first for best performance.")
        print("   Continuing with unoptimized database...\n")

    # Warm-up
    mb_manager.search("Test Track", "Test Artist")

    print(f"\n⚡ Benchmarking {len(track_data):,} track searches...")

    start_time = time.time()
    results = []
    hits = 0
    misses = 0

    for track_name, artist_name in track_data:
        result = mb_manager.search(track_name, artist_hint=artist_name)
        results.append(result)
        if result:
            hits += 1
        else:
            misses += 1

    elapsed = time.time() - start_time

    print(f"\n✅ Benchmark completed in {elapsed:.3f}s")
    print(f"   ⚡ Speed: {len(track_data) / elapsed:,.1f} queries/sec")
    print(f"   ✓ Hits: {hits:,} ({hits/len(track_data)*100:.1f}%)")
    print(f"   ✗ Misses: {misses:,} ({misses/len(track_data)*100:.1f}%)")

    # Estimate for 253k queries
    queries_per_sec = len(track_data) / elapsed
    time_for_253k = 253000 / queries_per_sec

    print(f"\n📈 Projected performance for 253,000 queries:")
    print(f"   Estimated time: {time_for_253k:.1f}s ({time_for_253k/60:.1f} minutes)")

    return {
        'name': 'Current Strategy (Track Search)',
        'elapsed': elapsed,
        'queries_per_sec': queries_per_sec,
        'hits': hits,
        'misses': misses,
        'hit_rate': hits / len(track_data) * 100,
        'time_for_253k': time_for_253k,
        'is_optimized': is_ready,
    }


def print_summary(current: Dict, num_queries: int):
    """Print performance summary."""
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 80)

    print(f"\n🔵 Current Strategy (MusicBrainzManagerV2Optimized):")
    print(f"   Database optimized:  {current['is_optimized']}")
    print(f"   Test queries:        {num_queries:,}")
    print(f"   Total time:          {current['elapsed']:.3f}s")
    print(f"   Speed:               {current['queries_per_sec']:,.1f} queries/sec")
    print(f"   Hit rate:            {current['hit_rate']:.1f}%")
    print(f"   Storage:             ~14,229 MB (full MusicBrainz DB)")

    print(f"\n📈 PROJECTED FOR LARGE CSV (253,000 queries):")
    print(f"   Estimated time:      {current['time_for_253k']/60:.1f} minutes")
    print(f"   Hit rate:            ~{current['hit_rate']:.1f}%")

    print(f"\n💡 COMPARISON WITH FTS5 ARTIST-ONLY:")
    print(f"   ⚠️  Not directly comparable - different search types:")
    print(f"   - Current: Track search (track + artist hint)")
    print(f"   - FTS5: Artist-only search")
    print(f"   - FTS5 would need track data added for fair comparison")

    print(f"\n🎯 KEY INSIGHTS:")
    print(f"   ✓ Current strategy: Searches full track+artist+album records")
    print(f"   ✓ Storage: 14GB for comprehensive metadata")
    print(f"   ✓ Speed: {current['queries_per_sec']:,.0f} queries/sec")

    if current['is_optimized']:
        print(f"   ✓ Database IS optimized (hot/cold/fuzzy tables)")
    else:
        print(f"   ⚠️  Database NOT optimized - run optimization for better performance")

    print(f"\n📊 FTS5 Alternative (from previous test):")
    print(f"   - Artist-only searches: ~487 queries/sec")
    print(f"   - Storage: ~769 MB (94.6% smaller)")
    print(f"   - Trade-off: Less metadata, artist names only")

    print("=" * 80)


def main():
    """Run performance benchmark."""
    print("=" * 80)
    print("🏁 TRACK SEARCH PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    # Load track data (limit to 100 for quick test)
    track_data = load_track_data_from_csv(limit=100)

    if not track_data:
        print("❌ No track data found. Add CSV files with track+artist columns to _test_csvs/")
        return

    # Benchmark current strategy
    current_results = benchmark_current_strategy(track_data)

    if not current_results:
        print("❌ Benchmark failed")
        return

    # Print summary
    print_summary(current_results, len(track_data))


if __name__ == "__main__":
    main()