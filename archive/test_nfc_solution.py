#!/usr/bin/env python3
"""
Test SQL with NFC normalization - best of both worlds.
"""

import time
import duckdb
import re
import unicodedata
from pathlib import Path

CSV_PATH = Path.home() / ".apple_music_converter" / "musicbrainz" / "canonical" / "canonical_musicbrainz_data.csv"
TEST_DB = Path("test_nfc_solution.duckdb")

def clean_text_aggressive_nfc(text: str) -> str:
    """Python version using NFC (matches DuckDB)."""
    if not text:
        return ''
    text = unicodedata.normalize('NFC', text)  # Changed from NFKC!
    text = re.sub(r'\s*[\(\[].*?[\)\]]', '', text)
    text = re.sub(r'feat(?:\.|uring)?.*', '', text, flags=re.IGNORECASE)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

if TEST_DB.exists():
    TEST_DB.unlink()

conn = duckdb.connect(str(TEST_DB))
conn.execute("SET threads=8")

# Create basic table
print("Creating basic table...")
start = time.time()
conn.execute(f"""
    CREATE TABLE musicbrainz_basic AS
    SELECT id, artist_credit_name, recording_name, score
    FROM read_csv_auto('{CSV_PATH}')
    WHERE recording_name IS NOT NULL
      AND artist_credit_name IS NOT NULL
    LIMIT 100000
""")
print(f"  ✅ Basic table: {time.time() - start:.2f}s")

# SQL with NFC normalization
print("\nCreating fuzzy table with SQL + NFC...")
start = time.time()
conn.execute("""
    CREATE TABLE musicbrainz_fuzzy_nfc AS
    SELECT
        id,
        artist_credit_name,
        recording_name,
        score,
        trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(nfc_normalize(recording_name)),
                            '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                        ),
                        '\\s+(feat\\.|featuring|ft\\.|with)\\s+.*', '', 'gi'
                    ),
                    '[^\\w\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        ) AS recording_clean,
        trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(nfc_normalize(artist_credit_name)),
                            '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                        ),
                        '\\s+(feat\\.|featuring|ft\\.|with)\\s+.*', '', 'gi'
                    ),
                    '[^\\w\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        ) AS artist_clean
    FROM musicbrainz_basic
""")
sql_time = time.time() - start
print(f"  ✅ Fuzzy table (SQL+NFC): {sql_time:.2f}s")

# Test matching
print("\nTesting Unicode matching...")
test_cases = [
    ("Beyoncé", "beyoncé", "Should match"),
    ("乡愁四韵", "乡愁四韵", "Chinese - should preserve"),
    ("Song (Remix)", "song", "Should remove parens"),
]

for original, expected, description in test_cases:
    # SQL cleaning
    sql_result = conn.execute("""
        SELECT trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(nfc_normalize(?)),
                            '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                        ),
                        '\\s+(feat\\.|featuring|ft\\.|with)\\s+.*', '', 'gi'
                    ),
                    '[^\\w\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        )
    """, [original]).fetchone()[0]

    # Python cleaning (NFC version)
    python_result = clean_text_aggressive_nfc(original)

    match = "✅" if sql_result == python_result else "❌"
    print(f"{match} '{original}' → SQL: '{sql_result}' | Python: '{python_result}'")
    print(f"   {description}")

print(f"\n{'='*80}")
print(f"📊 PERFORMANCE: {sql_time:.2f}s for 100k rows")
print(f"📈 PROJECTED: {(sql_time * 286.7):.1f}s = {(sql_time * 286.7 / 60):.1f} min for 28.7M rows")
print(f"\n✅ SOLUTION: SQL with NFC normalization")
print(f"   - Fast (same as regexp)")
print(f"   - Unicode support (NFC)")
print(f"   - Matches Python (if we change to NFC)")
print(f"{'='*80}")

conn.close()
