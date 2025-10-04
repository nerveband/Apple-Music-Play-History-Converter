#!/usr/bin/env python3
"""
Test DuckDB Unicode property classes for text cleaning.
"""

import duckdb
from pathlib import Path

TEST_DB = Path("test_unicode_properties.duckdb")

if TEST_DB.exists():
    TEST_DB.unlink()

conn = duckdb.connect(str(TEST_DB))

# Test cases with Unicode characters
test_cases = [
    ("Beyoncé", "beyonce", "Accented character"),
    ("乡愁四韵", "乡愁四韵", "Chinese characters"),
    ("Song (Remix)", "song remix", "Remove parentheses"),
    ("Track - Extended", "track extended", "Remove hyphen"),
    ("Björk", "björk", "Swedish character"),
    ("Café Tacvba", "cafe tacvba", "Spanish accented"),
    ("ﬁle", "file", "Ligature (if NFKC used)"),
    ("①②③", "123", "Circled numbers (if NFKC used)"),
]

print("=" * 80)
print("Testing Unicode Property Classes in DuckDB")
print("=" * 80)

# Test Pattern 1: Old ASCII-only approach [^\w\s]
print("\n1. OLD PATTERN: [^\\w\\s] (ASCII-only)")
print("-" * 80)

for original, expected, description in test_cases:
    result = conn.execute("""
        SELECT regexp_replace(
            regexp_replace(
                lower(?),
                '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
            ),
            '[^\\w\\s]', '', 'g'
        )
    """, [original]).fetchone()[0]

    status = "✅" if result == expected else "❌"
    print(f"{status} '{original}' → '{result}' (expected: '{expected}')")
    print(f"   {description}")

# Test Pattern 2: Unicode property classes [^\p{L}\p{N}\s]
print("\n\n2. NEW PATTERN: [^\\p{L}\\p{N}\\s] (Unicode-aware)")
print("-" * 80)

for original, expected, description in test_cases:
    result = conn.execute("""
        SELECT trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        lower(?),
                        '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                    ),
                    '[^\\p{L}\\p{N}\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        )
    """, [original]).fetchone()[0]

    status = "✅" if result == expected else "⚠️"
    print(f"{status} '{original}' → '{result}' (expected: '{expected}')")
    print(f"   {description}")

# Test Pattern 3: With NFC normalization
print("\n\n3. FULL SOLUTION: NFC + [^\\p{L}\\p{N}\\s] (Unicode + Normalized)")
print("-" * 80)

for original, expected, description in test_cases:
    result = conn.execute("""
        SELECT trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        lower(nfc_normalize(?)),
                        '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                    ),
                    '[^\\p{L}\\p{N}\\s]', '', 'g'
                ),
                '\\s+', ' ', 'g'
            )
        )
    """, [original]).fetchone()[0]

    status = "✅" if result == expected else "⚠️"
    print(f"{status} '{original}' → '{result}' (expected: '{expected}')")
    print(f"   {description}")

print("\n" + "=" * 80)
print("KEY FINDINGS:")
print("=" * 80)
print("• [^\\w\\s] strips Unicode (é → '', 乡 → '') ❌")
print("• [^\\p{L}\\p{N}\\s] preserves Unicode letters and numbers ✅")
print("• NFC normalization keeps accents (é stays é)")
print("• For NFKC behavior (é→e, ①→1), use Python during search")
print("=" * 80)

conn.close()
if TEST_DB.exists():
    TEST_DB.unlink()
