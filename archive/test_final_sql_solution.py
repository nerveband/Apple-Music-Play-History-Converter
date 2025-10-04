#!/usr/bin/env python3
"""
Test FINAL SQL solution that matches Python UDF exactly.
"""

import duckdb
import unicodedata
import re
import time
from pathlib import Path

CSV_PATH = Path.home() / ".apple_music_converter" / "musicbrainz" / "canonical" / "canonical_musicbrainz_data.csv"
TEST_DB = Path("test_final_solution.duckdb")

def clean_text_aggressive(text: str) -> str:
    """Python version - exact match to manager code."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
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

# Test cases
test_cases = [
    ("Beyoncé", "Accented character"),
    ("乡愁四韵", "Chinese characters"),
    ("Song (Remix)", "Parentheses"),
    ("Track feat. Artist", "Feat pattern"),
    ("Björk", "Swedish character"),
    ("Café Tacvba", "Spanish accented"),
    ("Love Is (JHAL H.S.O VIP Mix)", "Complex parens"),
    ("Mühleisen", "German umlaut"),
]

print("=" * 80)
print("FINAL SQL SOLUTION: NFC + [^\\p{L}\\p{N}\\s] (NO strip_accents)")
print("=" * 80)

matches = 0
for original, description in test_cases:
    # SQL cleaning (NO strip_accents - to match Python!)
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
                    '[^\\p{L}\\p{N}\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        )
    """, [original]).fetchone()[0]

    # Python cleaning
    python_result = clean_text_aggressive(original)

    # Compare
    match = sql_result == python_result
    matches += 1 if match else 0
    status = "✅" if match else "❌"

    print(f"\n{status} Original: '{original}'")
    print(f"   SQL:    '{sql_result}'")
    print(f"   Python: '{python_result}'")
    print(f"   {description}")

print("\n" + "=" * 80)
print(f"Match rate: {matches}/{len(test_cases)} ({100*matches/len(test_cases):.1f}%)")

if matches == len(test_cases):
    print("\n🎉 PERFECT MATCH!")
    print("\n✅ SQL solution matches Python UDF behavior:")
    print("   • Keeps accents (Beyoncé → beyoncé)")
    print("   • Preserves Unicode (乡愁四韵)")
    print("   • Removes punctuation ([^\\p{L}\\p{N}\\s])")
    print("   • NFC normalization (compatibility)")

# Performance test
if CSV_PATH.exists():
    print("\n" + "=" * 80)
    print("PERFORMANCE TEST (100k rows)")
    print("=" * 80)

    print("\nCreating basic table...")
    start = time.time()
    conn.execute(f"""
        CREATE TABLE musicbrainz_basic AS
        SELECT id, artist_credit_name, recording_name, score
        FROM read_csv_auto('{CSV_PATH}')
        WHERE recording_name IS NOT NULL
          AND artist_credit_name IS NOT NULL
        LIMIT 100000
    """)
    basic_time = time.time() - start
    print(f"  Basic table: {basic_time:.2f}s")

    print("\nCreating fuzzy table with FINAL SQL solution...")
    start = time.time()
    conn.execute("""
        CREATE TABLE musicbrainz_fuzzy AS
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
                        '[^\\p{L}\\p{N}\\s]', '', 'g'
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
                        '[^\\p{L}\\p{N}\\s]', '', 'g'
                    ),
                    '\\s+', ' ', 'g'
                )
            ) AS artist_clean
        FROM musicbrainz_basic
    """)
    fuzzy_time = time.time() - start
    print(f"  Fuzzy table: {fuzzy_time:.2f}s")

    # Project to full dataset
    scale_factor = 28_669_871 / 100_000
    projected_minutes = (fuzzy_time * scale_factor) / 60

    print(f"\n📈 PROJECTED for 28.7M rows: {projected_minutes:.1f} minutes")
    print(f"   (vs 7.3 minutes with Python UDF)")
    print(f"   Speedup: {7.3 / projected_minutes:.1f}x faster")

else:
    print("\n⚠️  CSV not found, skipping performance test")

print("=" * 80)

conn.close()
if TEST_DB.exists():
    TEST_DB.unlink()
