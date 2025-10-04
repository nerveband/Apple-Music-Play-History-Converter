#!/usr/bin/env python3
"""
Test ultra-fast processor with SMALL CSV only.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.ultra_fast_csv_processor import UltraFastCSVProcessor

DATA_DIR = str(Path.home() / ".apple_music_converter")
TEST_CSV = Path(__file__).parent / "_test_csvs" / "Apple Music Play Activity small.csv"

print("="*80)
print("🚀 ULTRA-FAST CSV PROCESSOR - SMALL FILE TEST")
print("="*80)
print()

# Initialize manager
print("Initializing MusicBrainz manager...")
manager = MusicBrainzManagerV2Optimized(DATA_DIR)

if not manager.is_ready():
    print("❌ MusicBrainz not optimized!")
    sys.exit(1)

print("✅ MusicBrainz ready")
print()

# Test small file
if not TEST_CSV.exists():
    print(f"❌ Test file not found: {TEST_CSV}")
    sys.exit(1)

print(f"📄 Processing: {TEST_CSV.name}")
print(f"   Size: {TEST_CSV.stat().st_size} bytes")
print()

# Create processor
processor = UltraFastCSVProcessor(manager)

# Process
try:
    start = time.time()
    result_df = processor.process_csv(str(TEST_CSV))
    elapsed = time.time() - start

    print(f"\n✅ Complete in {elapsed:.2f}s")
    print(f"   Rows: {len(result_df)}")
    print(f"   Matched: {result_df['Artist'].notna().sum()}")
    print(f"   Throughput: {len(result_df)/elapsed:.1f} rows/sec")

    # Show first few results
    print(f"\nFirst 5 results:")
    for idx in range(min(5, len(result_df))):
        row = result_df.iloc[idx]
        track = row.get('Song Name') or row.get('Track Description')
        artist = row.get('Artist')
        print(f"  {idx+1}. '{track}' -> '{artist}'")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Test passed!")