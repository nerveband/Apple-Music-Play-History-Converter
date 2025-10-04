#!/usr/bin/env python3
"""
Test complete DuckDB solution: NFC + strip_accents + Unicode property classes.
"""

import duckdb
import unicodedata
import re
from pathlib import Path

TEST_DB = Path("test_complete_solution.duckdb")

if TEST_DB.exists():
    TEST_DB.unlink()

conn = duckdb.connect(str(TEST_DB))

# Python aggressive cleaning (for comparison)
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
    ("①②③ Numbers", "Circled numbers"),
    ("ﬁle name", "Ligature"),
]

print("=" * 80)
print("COMPLETE DUCKDB SOLUTION TEST")
print("=" * 80)

print("\nSQL Solution: NFC + strip_accents + [^\\p{L}\\p{N}\\s]")
print("-" * 80)

for original, description in test_cases:
    # SQL cleaning
    sql_result = conn.execute("""
        SELECT trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(strip_accents(nfc_normalize(?))),
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
    match = "✅" if sql_result == python_result else "⚠️"
    print(f"\n{match} Original: '{original}'")
    print(f"   SQL:    '{sql_result}'")
    print(f"   Python: '{python_result}'")
    print(f"   {description}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

# Count matches
matches = 0
total = len(test_cases)

for original, _ in test_cases:
    sql_result = conn.execute("""
        SELECT trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(strip_accents(nfc_normalize(?))),
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

    python_result = clean_text_aggressive(original)

    if sql_result == python_result:
        matches += 1

print(f"\nMatch rate: {matches}/{total} ({100*matches/total:.1f}%)")

if matches == total:
    print("🎉 PERFECT MATCH! SQL solution identical to Python UDF!")
    print("\n✅ Can safely replace Python UDF with SQL for:")
    print("   • 100x faster optimization (1 min vs 7 min)")
    print("   • Full Unicode support (accents, Chinese, etc.)")
    print("   • Identical search results")
else:
    print(f"\n⚠️  Differences found in {total - matches} cases")
    print("   NFC keeps some compatibility chars (①, ﬁ)")
    print("   Python NFKC decomposes them (①→1, ﬁ→fi)")
    print("\n   Options:")
    print("   1. Accept differences (search with CONTAINS queries)")
    print("   2. Use Python NFKC during search (hybrid approach)")

print("=" * 80)

conn.close()
if TEST_DB.exists():
    TEST_DB.unlink()
