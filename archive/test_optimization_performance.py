#!/usr/bin/env python3
"""
MusicBrainz Optimization Performance Test Script
Tests and benchmarks the ultra-optimized MusicBrainz manager.
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized

print("="*80)
print("🚀 MUSICBRAINZ ULTRA-OPTIMIZATION PERFORMANCE TEST")
print("="*80)
print()

# Configuration
DATA_DIR = str(Path.home() / ".apple_music_converter")
TEST_CSV_DIR = Path(__file__).parent / "_test_csvs"

def format_time(seconds: float) -> str:
    """Format seconds as human-readable string."""
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"

def test_optimization_phase():
    """Test the optimization phase with detailed timing."""
    print("📊 PHASE 1: OPTIMIZATION BENCHMARK")
    print("-" * 80)

    manager = MusicBrainzManagerV2Optimized(DATA_DIR)

    if not manager.is_database_available():
        print("❌ ERROR: MusicBrainz CSV not found!")
        print(f"   Expected at: {manager.csv_file}")
        print()
        print("Please download and place the MusicBrainz CSV file.")
        return None

    print(f"✅ CSV file found: {manager.csv_file}")
    csv_size = manager.csv_file.stat().st_size / (1024**3)
    print(f"   Size: {csv_size:.2f} GB")
    print()

    # Check if already optimized
    if manager.is_ready():
        print("⚠️  Database already optimized!")
        print("   To re-test optimization, delete the DuckDB file:")
        print(f"   rm '{manager.duckdb_file}'")
        print()
        return manager

    # Run optimization with timing
    print("🚀 Starting optimization...")
    print()

    phase_timings = {}
    start_time = time.time()

    def progress_callback(message: str, percent: float, start_t: float):
        """Track progress and phase timings."""
        elapsed = time.time() - start_t
        print(f"[{percent:5.1f}%] {message} (elapsed: {format_time(elapsed)})")

    try:
        manager.run_optimization_synchronously(progress_callback=progress_callback)
        total_time = time.time() - start_time

        print()
        print("=" * 80)
        print(f"✅ OPTIMIZATION COMPLETE: {format_time(total_time)}")
        print("=" * 80)
        print()

        return manager

    except Exception as e:
        print()
        print(f"❌ OPTIMIZATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_search_performance(manager: MusicBrainzManagerV2Optimized):
    """Test search performance with various queries."""
    print("📊 PHASE 2: SEARCH PERFORMANCE BENCHMARK")
    print("-" * 80)

    if not manager or not manager.is_ready():
        print("❌ Manager not ready - skipping search tests")
        return

    # Test queries (track name, album hint) - mix of popular and obscure
    test_queries = [
        # Popular tracks (should be in HOT table)
        ("Bohemian Rhapsody", "A Night at the Opera"),
        ("Billie Jean", "Thriller"),
        ("Hotel California", "Hotel California"),
        ("Stairway to Heaven", "Led Zeppelin IV"),
        ("Smells Like Teen Spirit", "Nevermind"),
        ("Imagine", "Imagine"),
        ("Hey Jude", "Hey Jude"),
        ("Sweet Child O' Mine", "Appetite for Destruction"),
        ("Yesterday", "Help!"),
        ("Purple Rain", "Purple Rain"),

        # Medium popularity (may be in COLD table)
        ("Wonderwall", "What's the Story Morning Glory"),
        ("Come As You Are", "Nevermind"),
        ("Black Hole Sun", "Superunknown"),
        ("November Rain", "Use Your Illusion I"),
        ("Under the Bridge", "Blood Sugar Sex Magik"),

        # Edge cases
        ("Outside (feat. Ellie Goulding)", None),  # Featured artist
        ("Lose Yourself", None),  # No album hint
        ("Thriller", None),  # Ambiguous (track vs album)
    ]

    print(f"Running {len(test_queries)} search queries...")
    print()

    results = []
    total_time = 0

    for i, (track, album) in enumerate(test_queries, 1):
        start = time.time()
        artist = manager.search(track, album_hint=album)
        elapsed = (time.time() - start) * 1000  # ms

        total_time += elapsed

        status = "✅" if artist else "❌"
        print(f"{i:2d}. {status} '{track}' -> '{artist or 'NOT FOUND'}' ({elapsed:.2f}ms)")

        results.append({
            "track": track,
            "album": album,
            "artist": artist,
            "elapsed_ms": elapsed,
            "found": artist is not None
        })

    # Statistics
    print()
    print("-" * 80)
    print("SEARCH STATISTICS:")
    print("-" * 80)

    found_count = sum(1 for r in results if r["found"])
    match_rate = (found_count / len(results)) * 100

    latencies = [r["elapsed_ms"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    p50_latency = sorted(latencies)[len(latencies) // 2]
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]

    print(f"Total Queries:    {len(results)}")
    print(f"Matches Found:    {found_count} ({match_rate:.1f}%)")
    print()
    print(f"Latency Stats:")
    print(f"  Average:        {avg_latency:.2f}ms")
    print(f"  Min:            {min_latency:.2f}ms")
    print(f"  Max:            {max_latency:.2f}ms")
    print(f"  P50 (median):   {p50_latency:.2f}ms")
    print(f"  P95:            {p95_latency:.2f}ms")
    print(f"  P99:            {p99_latency:.2f}ms")
    print()

    # Cache stats
    cache_stats = manager.get_cache_stats()
    print("Cache Statistics:")
    print(f"  Hits:           {cache_stats['cache_hits']}")
    print(f"  Misses:         {cache_stats['cache_misses']}")
    print(f"  Hit Rate:       {cache_stats['hit_rate_percent']:.1f}%")
    print(f"  Cache Size:     {cache_stats['cache_size']}/{cache_stats['cache_max_size']}")
    print()

    return results

def test_cache_effectiveness(manager: MusicBrainzManagerV2Optimized):
    """Test LRU cache effectiveness by repeating searches."""
    print("📊 PHASE 3: CACHE EFFECTIVENESS TEST")
    print("-" * 80)

    if not manager or not manager.is_ready():
        print("❌ Manager not ready - skipping cache tests")
        return

    # Test queries
    test_tracks = [
        ("Bohemian Rhapsody", "A Night at the Opera"),
        ("Billie Jean", "Thriller"),
        ("Hotel California", "Hotel California"),
        ("Imagine", "Imagine"),
        ("Hey Jude", "Hey Jude"),
    ]

    print(f"Testing cache with {len(test_tracks)} queries repeated 3 times...")
    print()

    # First pass (cold cache)
    print("Pass 1 (COLD CACHE):")
    cold_times = []
    for track, album in test_tracks:
        start = time.time()
        artist = manager.search(track, album_hint=album)
        elapsed = (time.time() - start) * 1000
        cold_times.append(elapsed)
        print(f"  '{track}' -> {elapsed:.2f}ms")

    print()

    # Second pass (warm cache)
    print("Pass 2 (WARM CACHE):")
    warm_times = []
    for track, album in test_tracks:
        start = time.time()
        artist = manager.search(track, album_hint=album)
        elapsed = (time.time() - start) * 1000
        warm_times.append(elapsed)
        print(f"  '{track}' -> {elapsed:.2f}ms (🚀 {cold_times[len(warm_times)-1]/elapsed:.0f}x faster)")

    print()

    # Third pass (hot cache)
    print("Pass 3 (HOT CACHE):")
    hot_times = []
    for track, album in test_tracks:
        start = time.time()
        artist = manager.search(track, album_hint=album)
        elapsed = (time.time() - start) * 1000
        hot_times.append(elapsed)
        print(f"  '{track}' -> {elapsed:.2f}ms (🚀 {cold_times[len(hot_times)-1]/elapsed:.0f}x faster)")

    print()
    print("-" * 80)
    print("CACHE PERFORMANCE:")
    print("-" * 80)

    avg_cold = sum(cold_times) / len(cold_times)
    avg_warm = sum(warm_times) / len(warm_times)
    avg_hot = sum(hot_times) / len(hot_times)

    speedup_warm = avg_cold / avg_warm
    speedup_hot = avg_cold / avg_hot

    print(f"Average Latency (cold):  {avg_cold:.2f}ms")
    print(f"Average Latency (warm):  {avg_warm:.2f}ms (🚀 {speedup_warm:.1f}x faster)")
    print(f"Average Latency (hot):   {avg_hot:.2f}ms (🚀 {speedup_hot:.1f}x faster)")
    print()

    cache_stats = manager.get_cache_stats()
    print(f"Final Cache Hit Rate:    {cache_stats['hit_rate_percent']:.1f}%")
    print()

def test_csv_processing(manager: MusicBrainzManagerV2Optimized):
    """Test processing a real CSV file."""
    print("📊 PHASE 4: CSV PROCESSING TEST")
    print("-" * 80)

    if not manager or not manager.is_ready():
        print("❌ Manager not ready - skipping CSV tests")
        return

    # Find a small test CSV
    test_csv = TEST_CSV_DIR / "Apple Music Play Activity small.csv"
    if not test_csv.exists():
        print(f"⚠️  Test CSV not found: {test_csv}")
        print("   Skipping CSV processing test")
        return

    print(f"Processing: {test_csv.name}")
    print()

    # Read CSV
    import pandas as pd
    try:
        df = pd.read_csv(test_csv)
        print(f"Rows: {len(df)}")
        print()
    except Exception as e:
        print(f"❌ Failed to read CSV: {e}")
        return

    # Process each row
    start_time = time.time()
    results = []

    for idx, row in df.iterrows():
        track_name = row.get('Song Name') or row.get('Track Description')
        album_name = row.get('Album')

        if pd.isna(track_name) or not track_name:
            continue

        search_start = time.time()
        artist = manager.search(track_name, album_hint=album_name)
        search_time = (time.time() - search_start) * 1000

        results.append({
            "track": track_name,
            "album": album_name,
            "artist": artist,
            "time_ms": search_time
        })

        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(df)} rows...")

    total_time = time.time() - start_time

    print()
    print("-" * 80)
    print("CSV PROCESSING RESULTS:")
    print("-" * 80)

    matched = sum(1 for r in results if r["artist"])
    match_rate = (matched / len(results)) * 100 if results else 0

    avg_time = sum(r["time_ms"] for r in results) / len(results) if results else 0

    print(f"Total Rows:       {len(results)}")
    print(f"Matched:          {matched} ({match_rate:.1f}%)")
    print(f"Processing Time:  {format_time(total_time)}")
    print(f"Avg Per Row:      {avg_time:.2f}ms")
    print(f"Throughput:       {len(results)/total_time:.1f} rows/sec")
    print()

    # Cache stats
    cache_stats = manager.get_cache_stats()
    print(f"Cache Hit Rate:   {cache_stats['hit_rate_percent']:.1f}%")
    print()

def test_database_size():
    """Check database file sizes."""
    print("📊 PHASE 5: DATABASE SIZE CHECK")
    print("-" * 80)

    data_dir = Path(DATA_DIR) / "musicbrainz"
    csv_file = data_dir / "canonical" / "canonical_musicbrainz_data.csv"
    duckdb_file = data_dir / "duckdb" / "mb.duckdb"

    if csv_file.exists():
        csv_size = csv_file.stat().st_size / (1024**3)
        print(f"CSV File:         {csv_size:.2f} GB")
    else:
        print(f"CSV File:         Not found")

    if duckdb_file.exists():
        db_size = duckdb_file.stat().st_size / (1024**3)
        compression_ratio = (1 - db_size / csv_size) * 100 if csv_file.exists() else 0
        print(f"DuckDB File:      {db_size:.2f} GB")
        if csv_file.exists():
            print(f"Compression:      {compression_ratio:.1f}% smaller than CSV")
    else:
        print(f"DuckDB File:      Not found")

    print()

def main():
    """Run all tests."""
    print("Starting performance tests...")
    print()

    # Test 1: Optimization
    manager = test_optimization_phase()
    if not manager:
        print("❌ Optimization failed - cannot continue tests")
        return

    print()

    # Test 2: Search performance
    test_search_performance(manager)
    print()

    # Test 3: Cache effectiveness
    test_cache_effectiveness(manager)
    print()

    # Test 4: CSV processing
    test_csv_processing(manager)
    print()

    # Test 5: Database size
    test_database_size()

    print("=" * 80)
    print("🎉 ALL TESTS COMPLETE!")
    print("=" * 80)

if __name__ == "__main__":
    main()