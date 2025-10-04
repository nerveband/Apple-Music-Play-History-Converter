#!/usr/bin/env python3
"""
Ultra-Fast CSV Processor Test Script
Tests the optimized batch processor against large CSV files.

Target: 253K rows in <10 minutes (vs 5.3 hours)
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.ultra_fast_csv_processor import UltraFastCSVProcessor

DATA_DIR = str(Path.home() / ".apple_music_converter")
TEST_CSV_DIR = Path(__file__).parent / "_test_csvs"

print("="*80)
print("🚀 ULTRA-FAST CSV PROCESSOR TEST")
print("="*80)
print()

# Test files in order of size
test_files = [
    "Apple Music Play Activity small.csv",  # 17 rows - quick test
    "Apple Music - Play History Daily Tracks.csv",  # Medium test
    "Apple Music Play Activity full.csv",  # 253K rows - the big one!
]

def test_csv_file(csv_file: Path, manager: MusicBrainzManagerV2Optimized):
    """Test processing a single CSV file."""
    if not csv_file.exists():
        print(f"⚠️  Skipping {csv_file.name} (not found)")
        return None

    csv_size = csv_file.stat().st_size / (1024**2)
    print(f"\n{'='*80}")
    print(f"📄 Testing: {csv_file.name}")
    print(f"   Size: {csv_size:.1f} MB")
    print(f"{'='*80}\n")

    # Create processor
    processor = UltraFastCSVProcessor(manager)

    # Process with timing
    start_time = time.time()

    try:
        result_df = processor.process_csv(str(csv_file))
        total_time = time.time() - start_time

        # Results
        stats = processor.get_stats()

        print(f"\n{'='*80}")
        print(f"✅ SUCCESS: {csv_file.name}")
        print(f"{'='*80}")
        print(f"Total rows:          {stats['total_rows']:,}")
        print(f"Unique tracks:       {stats['unique_tracks']:,}")
        print(f"Dedup saves:         {stats['dedup_saves']:,}")
        print(f"HOT hits:            {stats['hot_hits']:,}")
        print(f"COLD hits:           {stats['cold_hits']:,}")
        print(f"Not found:           {stats['not_found']:,}")
        print(f"Total time:          {_format_time(total_time)}")
        print(f"Throughput:          {stats['total_rows']/total_time:.1f} rows/sec")

        # Calculate speedup vs old method (77ms per row)
        old_time = stats['total_rows'] * 0.077
        speedup = old_time / total_time
        print(f"Speedup vs old:      🚀 {speedup:.1f}x faster!")

        # Calculate projected time for 253K rows
        if stats['total_rows'] < 100000:
            projected_253k = (253525 / stats['total_rows']) * total_time
            print(f"Projected for 253K:  {_format_time(projected_253k)}")

        print(f"{'='*80}\n")

        return {
            'file': csv_file.name,
            'rows': stats['total_rows'],
            'time': total_time,
            'throughput': stats['total_rows']/total_time,
            'speedup': speedup,
            'stats': stats
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

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

def main():
    """Run all tests."""
    # Initialize manager
    print("Initializing MusicBrainz manager...")
    manager = MusicBrainzManagerV2Optimized(DATA_DIR)

    if not manager.is_ready():
        print("❌ MusicBrainz not optimized!")
        print("   Run: python test_optimization_performance.py")
        return

    print("✅ MusicBrainz ready")
    print()

    # Run tests
    results = []

    for filename in test_files:
        csv_file = TEST_CSV_DIR / filename
        result = test_csv_file(csv_file, manager)
        if result:
            results.append(result)

    # Summary
    if results:
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)

        for result in results:
            print(f"\n{result['file']}:")
            print(f"  Rows:       {result['rows']:,}")
            print(f"  Time:       {_format_time(result['time'])}")
            print(f"  Throughput: {result['throughput']:.1f} rows/sec")
            print(f"  Speedup:    🚀 {result['speedup']:.1f}x")

        # Overall stats
        total_rows = sum(r['rows'] for r in results)
        total_time = sum(r['time'] for r in results)
        avg_throughput = total_rows / total_time
        avg_speedup = sum(r['speedup'] for r in results) / len(results)

        print(f"\n{'='*80}")
        print(f"OVERALL:")
        print(f"  Total rows:       {total_rows:,}")
        print(f"  Total time:       {_format_time(total_time)}")
        print(f"  Avg throughput:   {avg_throughput:.1f} rows/sec")
        print(f"  Avg speedup:      🚀 {avg_speedup:.1f}x")
        print(f"{'='*80}")

    print("\n✅ All tests complete!")

if __name__ == "__main__":
    main()