#!/usr/bin/env python3
"""Test creating fuzzy table"""

import duckdb
import time
from pathlib import Path

db_path = Path.home() / ".apple_music_converter" / "musicbrainz" / "duckdb" / "mb.duckdb"

print(f"Connecting to: {db_path}")
conn = duckdb.connect(str(db_path))

# Set memory limit
conn.execute("SET memory_limit='4GB'")
conn.execute("SET threads=4")

print("Dropping existing fuzzy table...")
conn.execute("DROP TABLE IF EXISTS musicbrainz_fuzzy")

print("Creating fuzzy table (this may take a while)...")
start = time.time()

# Simpler SQL without complex regexp
sql = """
    CREATE TABLE musicbrainz_fuzzy AS
    SELECT
        id,
        artist_credit_id,
        artist_mbids,
        artist_credit_name,
        release_mbid,
        release_name,
        recording_mbid,
        recording_name,
        score,
        lower(trim(recording_name)) AS recording_clean,
        lower(trim(artist_credit_name)) AS artist_clean
    FROM musicbrainz_basic
    WHERE recording_name IS NOT NULL
      AND artist_credit_name IS NOT NULL
    LIMIT 1000000
"""

print(f"Executing SQL (limited to 1M rows for testing)...")
try:
    conn.execute(sql)
    elapsed = time.time() - start
    print(f"✅ Fuzzy table created in {elapsed:.1f} seconds")

    # Check row count
    count = conn.execute("SELECT COUNT(*) FROM musicbrainz_fuzzy").fetchone()[0]
    print(f"Rows in fuzzy table: {count:,}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

conn.close()
print("Done")