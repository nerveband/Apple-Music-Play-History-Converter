#!/usr/bin/env python3
"""
Test different fuzzy table creation strategies to determine fastest approach.
"""

import time
import duckdb
import re
import unicodedata
from pathlib import Path

# Path to MusicBrainz canonical CSV
CSV_PATH = Path.home() / ".apple_music_converter" / "musicbrainz" / "canonical" / "canonical_musicbrainz_data.csv"
TEST_DB = Path("test_fuzzy_strategies.duckdb")

def clean_text_aggressive(text: str) -> str:
    """Python UDF version - exact match to manager code."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s*[\(\[].*?[\)\]]', '', text)  # Remove parens/brackets
    text = re.sub(r'feat(?:\.|uring)?.*', '', text, flags=re.IGNORECASE)  # Remove feat
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text


def test_strategy_1_python_udf(conn):
    """Strategy 1: Python UDF (CURRENT - SLOW)"""
    print("\n" + "="*80)
    print("STRATEGY 1: Python UDF (current implementation)")
    print("="*80)

    # Register UDF
    conn.create_function("clean_aggressive", clean_text_aggressive)

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
    basic_time = time.time() - start
    print(f"  ✅ Basic table: {basic_time:.2f}s")

    print("Creating fuzzy table with Python UDF...")
    start = time.time()
    conn.execute("""
        CREATE TABLE musicbrainz_fuzzy_udf AS
        SELECT
            id,
            artist_credit_name,
            recording_name,
            score,
            clean_aggressive(recording_name) AS recording_clean,
            clean_aggressive(artist_credit_name) AS artist_clean
        FROM musicbrainz_basic
    """)
    udf_time = time.time() - start
    print(f"  ✅ Fuzzy table (UDF): {udf_time:.2f}s")

    count = conn.execute("SELECT COUNT(*) FROM musicbrainz_fuzzy_udf").fetchone()[0]
    print(f"  📊 Rows: {count:,}")

    return udf_time


def test_strategy_2_sql_regexp(conn):
    """Strategy 2: Pure SQL with REGEXP_REPLACE (FAST but missing NFKC)"""
    print("\n" + "="*80)
    print("STRATEGY 2: Pure SQL REGEXP_REPLACE")
    print("="*80)

    print("Creating fuzzy table with SQL regexp...")
    start = time.time()
    conn.execute("""
        CREATE TABLE musicbrainz_fuzzy_sql AS
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
                                lower(recording_name),
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
                                lower(artist_credit_name),
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
    print(f"  ✅ Fuzzy table (SQL): {sql_time:.2f}s")

    count = conn.execute("SELECT COUNT(*) FROM musicbrainz_fuzzy_sql").fetchone()[0]
    print(f"  📊 Rows: {count:,}")

    return sql_time


def test_strategy_3_simple_lower(conn):
    """Strategy 3: Simple LOWER/TRIM (FASTEST, but requires search code changes)"""
    print("\n" + "="*80)
    print("STRATEGY 3: Simple LOWER/TRIM (v2.py approach)")
    print("="*80)

    print("Creating fuzzy table with simple lower/trim...")
    start = time.time()
    conn.execute("""
        CREATE TABLE musicbrainz_fuzzy_simple AS
        SELECT
            id,
            artist_credit_name,
            recording_name,
            score,
            lower(trim(recording_name)) AS recording_clean,
            lower(trim(artist_credit_name)) AS artist_clean
        FROM musicbrainz_basic
    """)
    simple_time = time.time() - start
    print(f"  ✅ Fuzzy table (simple): {simple_time:.2f}s")

    count = conn.execute("SELECT COUNT(*) FROM musicbrainz_fuzzy_simple").fetchone()[0]
    print(f"  📊 Rows: {count:,}")

    return simple_time


def compare_outputs(conn):
    """Compare the cleaned output between strategies."""
    print("\n" + "="*80)
    print("OUTPUT COMPARISON (first 10 rows)")
    print("="*80)

    # Get sample data
    samples = conn.execute("""
        SELECT
            u.recording_name as original,
            u.recording_clean as udf_clean,
            s.recording_clean as sql_clean,
            l.recording_clean as simple_clean
        FROM musicbrainz_fuzzy_udf u
        JOIN musicbrainz_fuzzy_sql s ON u.id = s.id
        JOIN musicbrainz_fuzzy_simple l ON u.id = l.id
        WHERE u.recording_clean != s.recording_clean
           OR u.recording_clean != l.recording_clean
        LIMIT 10
    """).fetchall()

    if samples:
        print("\n⚠️  DIFFERENCES FOUND:")
        for i, (orig, udf, sql, simple) in enumerate(samples, 1):
            print(f"\n{i}. Original: '{orig}'")
            print(f"   UDF:     '{udf}'")
            print(f"   SQL:     '{sql}'")
            print(f"   Simple:  '{simple}'")
    else:
        print("✅ All strategies produce identical output!")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("🧪 FUZZY TABLE STRATEGY PERFORMANCE TEST")
    print("="*80)

    if not CSV_PATH.exists():
        print(f"❌ CSV not found: {CSV_PATH}")
        return

    print(f"\n📂 Testing with: {CSV_PATH}")
    print(f"   Size: {CSV_PATH.stat().st_size / (1024**3):.2f} GB")
    print(f"   Sample: First 100,000 rows")

    # Clean up old test db
    if TEST_DB.exists():
        TEST_DB.unlink()

    conn = duckdb.connect(str(TEST_DB))
    conn.execute("SET threads=8")
    conn.execute("SET memory_limit='6GB'")

    # Test all strategies
    udf_time = test_strategy_1_python_udf(conn)
    sql_time = test_strategy_2_sql_regexp(conn)
    simple_time = test_strategy_3_simple_lower(conn)

    # Compare outputs
    compare_outputs(conn)

    # Summary
    print("\n" + "="*80)
    print("📊 PERFORMANCE SUMMARY (100k rows)")
    print("="*80)

    print(f"\n1. Python UDF:        {udf_time:.2f}s")
    print(f"2. SQL REGEXP:        {sql_time:.2f}s  ({udf_time/sql_time:.1f}x faster than UDF)")
    print(f"3. Simple LOWER/TRIM: {simple_time:.2f}s  ({udf_time/simple_time:.1f}x faster than UDF)")

    print(f"\n🏆 WINNER: {'SQL REGEXP' if sql_time < simple_time else 'Simple LOWER/TRIM'}")

    # Extrapolate to full dataset (28M rows)
    scale_factor = 28_669_871 / 100_000
    print(f"\n📈 PROJECTED for FULL 28.7M rows:")
    print(f"   Python UDF:        {(udf_time * scale_factor)/60:.1f} minutes")
    print(f"   SQL REGEXP:        {(sql_time * scale_factor)/60:.1f} minutes")
    print(f"   Simple LOWER/TRIM: {(simple_time * scale_factor)/60:.1f} minutes")

    print(f"\n💡 RECOMMENDATION:")
    if sql_time < 5 and simple_time < 1:
        print("   ✅ SQL REGEXP is fast enough (~{sql_time*scale_factor/60:.0f} min for full dataset)")
        print("   ⚠️  BUT missing Unicode normalization (NFKC)")
        print("   ✅ Simple LOWER/TRIM is fastest but requires search code adjustments")

    conn.close()

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
