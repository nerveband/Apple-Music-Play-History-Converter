#!/usr/bin/env python3
"""
Test ultra-fast processor with LARGE CSV (253K rows).
This is the real performance test!
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.ultra_fast_csv_processor import UltraFastCSVProcessor

DATA_DIR = str(Path.home() / ".apple_music_converter")
TEST_CSV = Path(__file__).parent / "_test_csvs" / "Apple Music Play Activity full.csv"

def _format_time(seconds: float) -> str:
    """Format seconds as human-readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {mins}m {secs:.0f}s"

print("="*80)
print("🚀 ULTRA-FAST CSV PROCESSOR - LARGE FILE TEST (253K ROWS)")
print("="*80)
print()

# Check file exists
if not TEST_CSV.exists():
    print(f"❌ Large test file not found: {TEST_CSV}")
    print("   This test requires the full 268MB CSV file")
    sys.exit(1)

csv_size = TEST_CSV.stat().st_size / (1024**2)
print(f"📄 Test file: {TEST_CSV.name}")
print(f"   Size: {csv_size:.1f} MB")
print()

# Initialize manager
print("Initializing MusicBrainz manager...")
manager = MusicBrainzManagerV2Optimized(DATA_DIR)

if not manager.is_ready():
    print("❌ MusicBrainz not optimized!")
    print("   Run: python test_optimization_performance.py")
    sys.exit(1)

print("✅ MusicBrainz ready")
print()

# Create processor
processor = UltraFastCSVProcessor(manager)

# Process with detailed monitoring
print("Starting ultra-fast processing...")
print("(This should take 5-10 minutes instead of 5+ hours!)")
print()

start_time = time.time()

try:
    result_df = processor.process_csv(str(TEST_CSV))
    total_time = time.time() - start_time

    # Get stats
    stats = processor.get_stats()

    # Calculate metrics
    matched = result_df['Artist'].notna().sum()
    match_rate = (matched / len(result_df)) * 100
    throughput = len(result_df) / total_time

    # Old method comparison (77ms per row)
    old_time = len(result_df) * 0.077
    old_time_hours = old_time / 3600
    speedup = old_time / total_time

    print(f"\n" + "="*80)
    print(f"✅ SUCCESS!")
    print(f"="*80)
    print(f"Total rows:          {len(result_df):,}")
    print(f"Matched:             {matched:,} ({match_rate:.1f}%)")
    print(f"Unique tracks:       {stats['unique_tracks']:,}")
    print(f"Deduplication:       {stats['dedup_saves']:,} saves ({stats['dedup_saves']/len(result_df)*100:.1f}%)")
    print(f"HOT hits:            {stats['hot_hits']:,} ({stats['hot_hits']/stats['unique_tracks']*100:.1f}%)")
    print(f"COLD hits:           {stats['cold_hits']:,} ({stats['cold_hits']/stats['unique_tracks']*100:.1f}%)")
    print(f"Not found:           {stats['not_found']:,} ({stats['not_found']/stats['unique_tracks']*100:.1f}%)")
    print()
    print(f"Processing time:     {_format_time(total_time)}")
    print(f"Throughput:          {throughput:.1f} rows/sec")
    print()
    print(f"Old method time:     {_format_time(old_time)} ({old_time_hours:.1f} hours)")
    print(f"🚀 Speedup:          {speedup:.1f}x FASTER!")
    print(f"="*80)

    # Success criteria
    print(f"\n📊 Success Criteria:")
    print(f"   ✅ Processing time < 10 min: {'✅ PASS' if total_time < 600 else '❌ FAIL'} ({_format_time(total_time)})")
    print(f"   ✅ Throughput > 500 rows/sec: {'✅ PASS' if throughput > 500 else '❌ FAIL'} ({throughput:.1f})")
    print(f"   ✅ Speedup > 50x: {'✅ PASS' if speedup > 50 else '❌ FAIL'} ({speedup:.1f}x)")
    print(f"   ✅ Match rate ≥ 95%: {'✅ PASS' if match_rate >= 95 else '❌ FAIL'} ({match_rate:.1f}%)")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)