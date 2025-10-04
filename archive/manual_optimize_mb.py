#!/usr/bin/env python3
"""
Manually run MusicBrainz optimization to see any errors
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2 import MusicBrainzManagerV2

def progress_callback(message: str, percent: float, start_time: float):
    print(f"[{percent:5.1f}%] {message}")

print("="*80)
print("MANUAL MUSICBRAINZ OPTIMIZATION")
print("="*80)

data_dir = str(Path.home() / ".apple_music_converter")
manager = MusicBrainzManagerV2(data_dir)

print(f"\nStatus before optimization:")
print(f"  CSV available: {manager.is_database_available()}")
print(f"  DuckDB exists: {manager.duckdb_file.exists()}")
print(f"  Is ready: {manager.is_ready()}")
print(f"  CSV path: {manager.csv_file}")
print(f"  DuckDB path: {manager.duckdb_file}")

print(f"\nStarting optimization...")
print("-"*80)

try:
    # Start optimization with progress callback
    success = manager.start_optimization_if_needed(progress_callback=progress_callback)
    print(f"\n✅ start_optimization_if_needed returned: {success}")

    if success:
        # Wait for completion
        print("\nWaiting for optimization to complete...")
        ready = manager.wait_until_ready(timeout=600.0)
        print(f"✅ wait_until_ready returned: {ready}")

    print(f"\nStatus after optimization:")
    print(f"  Is ready: {manager.is_ready()}")
    print(f"  Optimization complete: {manager._optimization_complete}")
    print(f"  Optimization in progress: {manager._optimization_in_progress}")

    # Check tables
    if manager._conn:
        print(f"\n  Tables in database:")
        tables = manager._conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        for table in tables:
            count = manager._conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"    - {table[0]}: {count:,} rows")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("OPTIMIZATION COMPLETE")
print("="*80)