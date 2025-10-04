#!/usr/bin/env python3
"""
Test with large CSV file to verify performance at scale.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized

DATA_DIR = str(Path.home() / ".apple_music_converter")
TEST_CSV = Path(__file__).parent / "_test_csvs" / "Apple Music Play Activity full.csv"

print("="*80)
print("🚀 LARGE CSV PROCESSING TEST")
print("="*80)
print()

if not TEST_CSV.exists():
    print(f"❌ Large CSV not found: {TEST_CSV}")
    print("Skipping large CSV test")
    sys.exit(0)

csv_size = TEST_CSV.stat().st_size / (1024**2)
print(f"Test File: {TEST_CSV.name}")
print(f"Size: {csv_size:.1f} MB")
print()

# Initialize manager (should already be optimized)
manager = MusicBrainzManagerV2Optimized(DATA_DIR)

if not manager.is_ready():
    print("⚠️  MusicBrainz not optimized yet - run test_optimization_performance.py first")
    sys.exit(1)

print("✅ MusicBrainz ready")
print()

# Read and process CSV
import pandas as pd

print("Reading CSV file...")
start_read = time.time()
df = pd.read_csv(TEST_CSV)
read_time = time.time() - start_read
print(f"✅ Read {len(df)} rows in {read_time:.1f}s")
print()

# Process sample of rows
sample_size = min(100, len(df))
print(f"Processing {sample_size} sample rows...")
print()

start_process = time.time()
results = []

for idx in range(sample_size):
    row = df.iloc[idx]
    track_name = row.get('Song Name') or row.get('Track Description')
    album_name = row.get('Album')

    if pd.isna(track_name) or not track_name:
        continue

    search_start = time.time()
    artist = manager.search(track_name, album_hint=album_name)
    search_time = (time.time() - search_start) * 1000

    results.append({
        "track": track_name,
        "artist": artist,
        "time_ms": search_time
    })

    if (idx + 1) % 10 == 0:
        print(f"  Processed {idx + 1}/{sample_size}...")

total_time = time.time() - start_process

print()
print("="*80)
print("LARGE CSV PROCESSING RESULTS")
print("="*80)

matched = sum(1 for r in results if r["artist"])
match_rate = (matched / len(results)) * 100 if results else 0

latencies = [r["time_ms"] for r in results]
avg_time = sum(latencies) / len(latencies) if latencies else 0
min_time = min(latencies) if latencies else 0
max_time = max(latencies) if latencies else 0

print(f"Sample Size:       {len(results)}")
print(f"Matched:           {matched} ({match_rate:.1f}%)")
print(f"Total Time:        {total_time:.1f}s")
print(f"Avg Per Row:       {avg_time:.2f}ms")
print(f"Min Latency:       {min_time:.2f}ms")
print(f"Max Latency:       {max_time:.2f}ms")
print(f"Throughput:        {len(results)/total_time:.1f} rows/sec")
print()

# Cache stats
cache_stats = manager.get_cache_stats()
print(f"Cache Hit Rate:    {cache_stats['hit_rate_percent']:.1f}%")
print(f"Cache Size:        {cache_stats['cache_size']}/{cache_stats['cache_max_size']}")
print()

# Extrapolate to full file
estimated_total_time = (total_time / sample_size) * len(df)
estimated_minutes = int(estimated_total_time // 60)
estimated_seconds = int(estimated_total_time % 60)

print(f"Estimated Full File Time: {estimated_minutes}m {estimated_seconds}s")
print(f"Estimated Throughput: {len(df)/estimated_total_time:.1f} rows/sec")
print()

print("="*80)
print("✅ Large CSV test complete!")
print("="*80)