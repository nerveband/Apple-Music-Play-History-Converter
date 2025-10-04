#!/usr/bin/env python3
"""Check if DuckDB tables exist and have data"""

import duckdb
from pathlib import Path

db_path = Path.home() / ".apple_music_converter" / "musicbrainz" / "duckdb" / "mb.duckdb"

print(f"Checking DuckDB at: {db_path}")
print(f"File exists: {db_path.exists()}")
print(f"File size: {db_path.stat().st_size / (1024**3):.1f} GB\n")

try:
    conn = duckdb.connect(str(db_path))

    # List all tables
    print("=== Tables in database ===")
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
    for table in tables:
        print(f"  - {table[0]}")

    print("\n=== Row counts ===")
    for table in tables:
        table_name = table[0]
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"  {table_name}: {count:,} rows")

            # Show sample row
            if count > 0:
                sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 1").fetchone()
                print(f"    Sample: {sample[:5]}...")  # First 5 columns
        except Exception as e:
            print(f"  {table_name}: ERROR - {e}")

    conn.close()
    print("\n✅ Database check complete")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()