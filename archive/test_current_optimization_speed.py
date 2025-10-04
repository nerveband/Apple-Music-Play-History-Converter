#!/usr/bin/env python3
"""
Direct test of current optimization strategy speed using raw DuckDB queries.
Tests the actual speed of the optimized hot/cold/fuzzy tables.
"""

import time
import pandas as pd
import duckdb
import re
import unicodedata
from pathlib import Path
from typing import List, Tuple, Optional


def normalize_text(text: str) -> str:
    """Conservative normalization matching the manager's approach."""
    if not text:
        return ""
    # Remove diacritics, lowercase, remove punctuation, collapse whitespace
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    clean = re.sub(r'[^\w\s]', ' ', ascii_text.lower())
    return ' '.join(clean.split())


def load_track_data(csv_dir: Path = Path("./_test_csvs"), limit: Optional[int] = 100) -> List[Tuple[str, str]]:
    """Load track+artist pairs from CSV files."""
    tracks = []
    csv_files = list(csv_dir.glob("*.csv"))

    print(f"📂 Loading track data from {csv_dir}...")

    for csv_file in csv_files:
        try:
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'windows-1252']:
                try:
                    df = pd.read_csv(csv_file, encoding=encoding, low_memory=False)
                    break
                except UnicodeDecodeError:
                    continue

            # Find columns
            track_col = None
            artist_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'song' in col_lower or 'title' in col_lower or ('track' in col_lower and 'count' not in col_lower):
                    track_col = col
                if 'artist' in col_lower:
                    artist_col = col

            if track_col and artist_col:
                pairs = df[[track_col, artist_col]].dropna()
                track_artist_pairs = [(row[track_col], row[artist_col]) for _, row in pairs.iterrows()]
                tracks.extend(track_artist_pairs)
                print(f"   ✓ {csv_file.name}: {len(track_artist_pairs):,} pairs")

        except Exception as e:
            print(f"   ✗ {csv_file.name}: {e}")

    # Deduplicate
    seen = set()
    unique_tracks = []
    for track, artist in tracks:
        key = (track, artist)
        if key not in seen:
            seen.add(key)
            unique_tracks.append((track, artist))

    if limit and len(unique_tracks) > limit:
        unique_tracks = unique_tracks[:limit]

    print(f"✓ Loaded {len(unique_tracks):,} unique track+artist pairs\n")
    return unique_tracks


def benchmark_optimized_tables(track_data: List[Tuple[str, str]]):
    """Benchmark the optimized hot/cold/fuzzy table strategy."""
    print("=" * 80)
    print("🔵 CURRENT STRATEGY: Optimized hot/cold/fuzzy Tables")
    print("=" * 80)

    db_path = Path.home() / ".apple_music_converter" / "musicbrainz" / "duckdb" / "mb.duckdb"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return None

    print(f"📂 Database: {db_path}")
    print(f"   Size: {db_path.stat().st_size / (1024**3):.2f} GB")

    conn = duckdb.connect(str(db_path), read_only=True)

    # Check tables
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    print(f"   Tables: {', '.join(table_names)}")

    has_hot = 'musicbrainz_hot' in table_names
    has_cold = 'musicbrainz_cold' in table_names
    has_fuzzy = 'musicbrainz_fuzzy' in table_names
    has_basic = 'musicbrainz_basic' in table_names

    print(f"\n📊 Table Status:")
    print(f"   ✓ Basic: {has_basic}")
    print(f"   ✓ Hot: {has_hot}")
    print(f"   ✓ Cold: {has_cold}")
    print(f"   ✓ Fuzzy: {has_fuzzy}")

    # Configure connection for performance
    conn.execute("SET memory_limit='4GB'")
    conn.execute("SET threads=8")

    print(f"\n⚡ Benchmarking {len(track_data):,} track searches...")
    print("   Strategy: hot → cold → fuzzy → basic fallback")

    start_time = time.time()
    hits = {'hot': 0, 'cold': 0, 'fuzzy': 0, 'basic': 0}
    misses = 0

    for track_name, artist_name in track_data:
        # Normalize inputs
        track_lower = normalize_text(track_name)
        artist_lower = normalize_text(artist_name)

        result = None

        # Try hot table first
        if has_hot and not result:
            query = """
                SELECT recording_mbid
                FROM musicbrainz_hot
                WHERE recording_clean = ?
                  AND artist_clean = ?
                LIMIT 1
            """
            res = conn.execute(query, [track_lower, artist_lower]).fetchone()
            if res and res[0]:
                result = res[0]
                hits['hot'] += 1

        # Try cold table
        if has_cold and not result:
            query = """
                SELECT recording_mbid
                FROM musicbrainz_cold
                WHERE recording_clean = ?
                  AND artist_clean = ?
                LIMIT 1
            """
            res = conn.execute(query, [track_lower, artist_lower]).fetchone()
            if res and res[0]:
                result = res[0]
                hits['cold'] += 1

        # Try fuzzy table with LIKE
        if has_fuzzy and not result:
            query = """
                SELECT recording_mbid
                FROM musicbrainz_fuzzy
                WHERE recording_clean LIKE ?
                  AND artist_clean LIKE ?
                LIMIT 1
            """
            res = conn.execute(query, [f'%{track_lower}%', f'%{artist_lower}%']).fetchone()
            if res and res[0]:
                result = res[0]
                hits['fuzzy'] += 1

        # Fallback to basic
        if has_basic and not result:
            query = """
                SELECT recording_mbid
                FROM musicbrainz_basic
                WHERE recording_lower = ?
                  AND artist_lower = ?
                LIMIT 1
            """
            res = conn.execute(query, [track_lower, artist_lower]).fetchone()
            if res and res[0]:
                result = res[0]
                hits['basic'] += 1

        if not result:
            misses += 1

    elapsed = time.time() - start_time
    conn.close()

    total_hits = sum(hits.values())

    print(f"\n✅ Benchmark completed in {elapsed:.3f}s")
    print(f"   ⚡ Speed: {len(track_data) / elapsed:,.1f} queries/sec")
    print(f"\n📊 Hit Distribution:")
    print(f"   Hot table:   {hits['hot']:3d} hits ({hits['hot']/len(track_data)*100:5.1f}%)")
    print(f"   Cold table:  {hits['cold']:3d} hits ({hits['cold']/len(track_data)*100:5.1f}%)")
    print(f"   Fuzzy table: {hits['fuzzy']:3d} hits ({hits['fuzzy']/len(track_data)*100:5.1f}%)")
    print(f"   Basic table: {hits['basic']:3d} hits ({hits['basic']/len(track_data)*100:5.1f}%)")
    print(f"   ✓ Total hits: {total_hits:,} ({total_hits/len(track_data)*100:.1f}%)")
    print(f"   ✗ Misses: {misses:,} ({misses/len(track_data)*100:.1f}%)")

    # Project to 253k
    queries_per_sec = len(track_data) / elapsed
    time_for_253k = 253000 / queries_per_sec

    print(f"\n📈 Projected for 253,000 queries:")
    print(f"   Estimated time: {time_for_253k/60:.1f} minutes ({time_for_253k:.0f} seconds)")

    return {
        'elapsed': elapsed,
        'queries_per_sec': queries_per_sec,
        'hits': hits,
        'total_hits': total_hits,
        'misses': misses,
        'hit_rate': total_hits / len(track_data) * 100,
        'time_for_253k_sec': time_for_253k,
        'time_for_253k_min': time_for_253k / 60,
    }


def main():
    """Run the benchmark."""
    print("=" * 80)
    print("🏁 CURRENT OPTIMIZATION STRATEGY SPEED TEST")
    print("=" * 80)
    print()

    # Load track data
    track_data = load_track_data(limit=100)

    if not track_data:
        print("❌ No track data found")
        return

    # Benchmark
    results = benchmark_optimized_tables(track_data)

    if results:
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"\nCurrent Strategy (hot/cold/fuzzy tables):")
        print(f"  Speed: {results['queries_per_sec']:,.1f} queries/sec")
        print(f"  Hit rate: {results['hit_rate']:.1f}%")
        print(f"  Storage: 14.23 GB")
        print(f"  253k query estimate: {results['time_for_253k_min']:.1f} minutes")

        print(f"\nFTS5 Alternative (from previous test, artist-only):")
        print(f"  Speed: ~487 queries/sec (artist lookups)")
        print(f"  Storage: 0.77 GB (94.6% smaller)")
        print(f"  Note: Different use case (artists vs tracks)")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()