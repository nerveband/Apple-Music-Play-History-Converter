#!/usr/bin/env python3
"""
Compare performance between current optimization strategy and FTS5 approach.
"""

import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized

def load_test_artists_from_csv(csv_dir: Path = Path("./_test_csvs")) -> List[str]:
    """Load unique artist names from test CSV files."""
    artists = set()
    csv_files = list(csv_dir.glob("*.csv"))

    print(f"📂 Loading test artists from {csv_dir}...")

    for csv_file in csv_files:
        try:
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'windows-1252']:
                try:
                    df = pd.read_csv(csv_file, encoding=encoding, low_memory=False)
                    break
                except UnicodeDecodeError:
                    continue

            artist_col = None
            for col in df.columns:
                if 'artist' in col.lower():
                    artist_col = col
                    break

            if artist_col:
                csv_artists = df[artist_col].dropna().unique()
                artists.update(csv_artists)
                print(f"   ✓ {csv_file.name}: {len(csv_artists):,} unique artists")
        except Exception as e:
            print(f"   ✗ {csv_file.name}: {e}")

    artists_list = sorted(list(artists))
    print(f"✓ Loaded {len(artists_list):,} unique artists\n")
    return artists_list


def benchmark_current_strategy(test_artists: List[str]) -> Dict[str, Any]:
    """Benchmark the current MusicBrainzManagerV2 optimization strategy."""
    print("=" * 80)
    print("🔵 CURRENT STRATEGY: MusicBrainzManagerV2Optimized")
    print("=" * 80)

    # Initialize with default data directory
    data_dir = Path.home() / ".apple_music_converter" / "musicbrainz"
    mb_manager = MusicBrainzManagerV2Optimized(str(data_dir))

    # Check if database is available
    if not mb_manager.is_database_available():
        print("❌ MusicBrainz database not available")
        return None

    if not mb_manager.is_ready():
        print("⚠️  Database not optimized yet. This may affect performance.")

    print(f"📊 Database status: Ready={mb_manager.is_ready()}")

    print(f"\n⚠️  Note: MusicBrainzManagerV2Optimized searches for tracks, not artists.")
    print(f"   This compares track search with artist-only search (different use cases).")
    print(f"   For a fair comparison, we'd need track+artist CSV data.\n")

    print(f"   Skipping current strategy benchmark (needs track data).")

    # We can't fairly benchmark this without track data
    # The optimized manager searches for tracks, not standalone artists

    return {
        'name': 'Current Strategy (MusicBrainzManagerV2)',
        'elapsed': elapsed,
        'queries_per_sec': len(test_artists) / elapsed,
        'hits': hits,
        'misses': misses,
        'hit_rate': hits / len(test_artists) * 100,
        'cache_stats': stats,
        'results': results
    }


def benchmark_fts5_strategy(test_artists: List[str]) -> Dict[str, Any]:
    """Benchmark the FTS5 optimization strategy."""
    print("\n" + "=" * 80)
    print("🟢 FTS5 STRATEGY: Artist-Only Optimization")
    print("=" * 80)

    # Import the test class
    from test_artist_only_optimization import ArtistOnlyOptimizationTest

    output_dir = Path("./test_optimization_output")
    exact_map_db = output_dir / "artist_exact_map.duckdb"
    fts_db = output_dir / "artist_fts.sqlite"

    if not exact_map_db.exists() or not fts_db.exists():
        print("❌ FTS5 optimization files not found. Run test_artist_only_optimization.py first.")
        return None

    print(f"📂 Using optimization files from: {output_dir}")

    # Initialize with existing databases
    import duckdb
    import sqlite3

    duck_conn = duckdb.connect(str(exact_map_db), read_only=True)
    sqlite_conn = sqlite3.connect(str(fts_db))

    test = ArtistOnlyOptimizationTest("dummy", str(output_dir))
    test.duck_conn = duck_conn
    test.sqlite_conn = sqlite_conn

    # Warm-up query
    test.benchmark_exact_lookups(["The Beatles"])

    print(f"\n⚡ Benchmarking {len(test_artists):,} artist lookups...")

    # Stage 1: Exact lookups
    start_time = time.time()
    exact_results, exact_time, exact_hits, exact_misses = test.benchmark_exact_lookups(test_artists)

    # Stage 2: Fuzzy lookups for misses
    misses = [test_artists[i] for i, r in enumerate(exact_results) if r[1] is None]
    fts_hits = 0
    fts_time = 0

    if misses:
        print(f"\n🔍 Running FTS5 fuzzy search for {len(misses):,} misses...")
        fts_results, fts_time, fts_hits, fts_final_misses = test.benchmark_fts_lookups(misses)

    total_time = exact_time + fts_time
    total_hits = exact_hits + fts_hits
    total_misses = len(misses) - fts_hits if misses else 0

    print(f"\n✅ FTS5 strategy completed in {total_time:.3f}s")
    print(f"   ⚡ Speed: {len(test_artists) / total_time:,.1f} queries/sec")
    print(f"   ✓ Total hits: {total_hits:,} ({total_hits/len(test_artists)*100:.1f}%)")
    print(f"   ✗ Total misses: {total_misses:,} ({total_misses/len(test_artists)*100:.1f}%)")

    test.close()

    return {
        'name': 'FTS5 Strategy (Artist-Only)',
        'elapsed': total_time,
        'queries_per_sec': len(test_artists) / total_time,
        'hits': total_hits,
        'misses': total_misses,
        'hit_rate': total_hits / len(test_artists) * 100,
        'exact_time': exact_time,
        'exact_hits': exact_hits,
        'fts_time': fts_time,
        'fts_hits': fts_hits,
    }


def print_comparison(current: Dict[str, Any], fts5: Dict[str, Any], num_queries: int):
    """Print side-by-side comparison."""
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE COMPARISON")
    print("=" * 80)

    print(f"\n🔵 Current Strategy (MusicBrainzManagerV2):")
    print(f"   Total time:        {current['elapsed']:.3f}s")
    print(f"   Speed:             {current['queries_per_sec']:,.1f} queries/sec")
    print(f"   Hit rate:          {current['hit_rate']:.1f}%")
    print(f"   Cache efficiency:  {current['cache_stats'].get('cache_hits', 0):,} hits / "
          f"{current['cache_stats'].get('cache_misses', 0):,} misses")

    print(f"\n🟢 FTS5 Strategy (Artist-Only):")
    print(f"   Total time:        {fts5['elapsed']:.3f}s")
    print(f"   - Exact lookups:   {fts5['exact_time']:.3f}s ({fts5['exact_hits']} hits)")
    print(f"   - FTS5 fuzzy:      {fts5['fts_time']:.3f}s ({fts5['fts_hits']} hits)")
    print(f"   Speed:             {fts5['queries_per_sec']:,.1f} queries/sec")
    print(f"   Hit rate:          {fts5['hit_rate']:.1f}%")

    print(f"\n⚡ WINNER:")
    if current['elapsed'] < fts5['elapsed']:
        speedup = fts5['elapsed'] / current['elapsed']
        print(f"   🏆 Current Strategy is {speedup:.2f}x FASTER")
    else:
        speedup = current['elapsed'] / fts5['elapsed']
        print(f"   🏆 FTS5 Strategy is {speedup:.2f}x FASTER")

    print(f"\n💾 STORAGE:")
    print(f"   Current:  ~14,229 MB (full MusicBrainz DB)")
    print(f"   FTS5:     ~769 MB (exact map + FTS5 index)")
    print(f"   Savings:  ~94.6% smaller")

    print(f"\n🎯 RECOMMENDATION:")

    # Calculate projected time for 253k queries
    current_253k = 253000 / current['queries_per_sec']
    fts5_253k = 253000 / fts5['queries_per_sec']

    print(f"   For 253,000 queries (typical large CSV):")
    print(f"   - Current Strategy: ~{current_253k/60:.1f} minutes")
    print(f"   - FTS5 Strategy:    ~{fts5_253k/60:.1f} minutes")

    if current['elapsed'] < fts5['elapsed']:
        print(f"\n   ✓ Current strategy is faster but uses 18.5x more storage")
        print(f"   ✓ Consider FTS5 if storage/distribution size is a priority")
    else:
        print(f"\n   ✓ FTS5 strategy is faster AND uses 94.6% less storage")
        print(f"   ✓ Strong candidate for replacing current approach")

    print("=" * 80)


def main():
    """Run comparison benchmark."""
    print("=" * 80)
    print("🏁 OPTIMIZATION STRATEGY COMPARISON")
    print("=" * 80)
    print()

    # Load test artists
    test_artists = load_test_artists_from_csv()

    if not test_artists:
        print("❌ No test artists found. Add CSV files to _test_csvs/ directory.")
        return

    # Benchmark current strategy
    current_results = benchmark_current_strategy(test_artists)

    if not current_results:
        print("❌ Failed to benchmark current strategy")
        return

    # Benchmark FTS5 strategy
    fts5_results = benchmark_fts5_strategy(test_artists)

    if not fts5_results:
        print("❌ Failed to benchmark FTS5 strategy")
        return

    # Print comparison
    print_comparison(current_results, fts5_results, len(test_artists))


if __name__ == "__main__":
    main()