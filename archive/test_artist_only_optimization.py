#!/usr/bin/env python3
"""
Test script to evaluate artist-only optimization strategy.
Creates a minimal exact+FTS5 index from existing MusicBrainz DB and benchmarks performance.
"""

import re
import time
import unicodedata
import sqlite3
from pathlib import Path
from typing import Optional
import duckdb

class ArtistOnlyOptimizationTest:
    def __init__(self, mb_db_path: str, output_dir: str = "./test_optimization_output"):
        self.mb_db_path = Path(mb_db_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Output files
        self.exact_map_db = self.output_dir / "artist_exact_map.duckdb"
        self.fts_db = self.output_dir / "artist_fts.sqlite"

        self.duck_conn: Optional[duckdb.DuckDBPyConnection] = None
        self.sqlite_conn: Optional[sqlite3.Connection] = None

    def normalize_conservative(self, text: str) -> str:
        """Conservative normalization for exact matching."""
        if not text:
            return ""
        # NFKC normalize, lowercase, remove punctuation, collapse whitespace
        normalized = unicodedata.normalize('NFKC', text).lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def build_exact_map(self):
        """Build exact artist map using DuckDB from existing MusicBrainz database."""
        print("🔨 Building exact artist map from MusicBrainz database...")
        start_time = time.time()

        # Connect to source MusicBrainz DB
        source_conn = duckdb.connect(str(self.mb_db_path), read_only=True)

        # Create output DuckDB
        if self.exact_map_db.exists():
            self.exact_map_db.unlink()
        self.duck_conn = duckdb.connect(str(self.exact_map_db))
        self.duck_conn.execute("PRAGMA threads=8;")

        print("  📊 Extracting artist names from musicbrainz_basic table...")

        # This database has a different structure - extract unique artist names and MBIDs
        query = """
        SELECT DISTINCT
            artist_credit_name as display_name,
            artist_mbids as mbid,
            'primary' as name_type,
            '' as type,
            '' as area,
            '' as begin_year,
            '' as disambiguation,
            artist_credit_id
        FROM musicbrainz_basic
        WHERE artist_credit_name IS NOT NULL
          AND artist_mbids IS NOT NULL
        ORDER BY artist_credit_id
        """

        result = source_conn.execute(query).fetchdf()
        print(f"  ✓ Extracted {len(result):,} artist name records from musicbrainz_basic")

        # Split artist_mbids if they contain multiple MBIDs (separated by semicolons)
        # For simplicity, we'll use the first MBID in cases of multiple artists
        def get_first_mbid(mbids_str):
            if not mbids_str:
                return mbids_str
            return mbids_str.split(';')[0] if ';' in mbids_str else mbids_str

        result['mbid'] = result['mbid'].apply(get_first_mbid)

        # Create normalized version for exact matching
        print("  🔧 Normalizing artist names...")
        result['norm_name'] = result['display_name'].apply(self.normalize_conservative)

        # Remove empty normalized names
        result = result[result['norm_name'] != '']
        print(f"  ✓ {len(result):,} valid normalized names")

        # Create exact map table
        print("  💾 Creating exact map table...")
        self.duck_conn.execute("""
            CREATE TABLE artist_exact_map AS
            SELECT
                norm_name,
                mbid,
                display_name,
                name_type,
                type,
                area,
                begin_year,
                disambiguation
            FROM result
        """)

        # Create index on normalized name
        self.duck_conn.execute("CREATE INDEX idx_norm_name ON artist_exact_map(norm_name)")

        # Get statistics
        stats = self.duck_conn.execute("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT norm_name) as unique_norm_names,
                COUNT(DISTINCT mbid) as unique_artists,
                SUM(CASE WHEN name_type = 'primary' THEN 1 ELSE 0 END) as primary_names,
                SUM(CASE WHEN name_type = 'alias' THEN 1 ELSE 0 END) as alias_names
            FROM artist_exact_map
        """).fetchone()

        elapsed = time.time() - start_time

        print(f"\n✅ Exact map built in {elapsed:.2f}s")
        print(f"   📊 Total rows: {stats[0]:,}")
        print(f"   🔑 Unique normalized names: {stats[1]:,}")
        print(f"   👤 Unique artists: {stats[2]:,}")
        print(f"   📝 Primary names: {stats[3]:,}")
        print(f"   🏷️  Alias names: {stats[4]:,}")

        # Get file size
        size_mb = self.exact_map_db.stat().st_size / (1024 * 1024)
        print(f"   💾 File size: {size_mb:.2f} MB")

        source_conn.close()
        return stats, size_mb

    def build_fts_index(self):
        """Build SQLite FTS5 index for fuzzy fallback."""
        print("\n🔍 Building FTS5 fuzzy index...")
        start_time = time.time()

        # Remove existing FTS database
        if self.fts_db.exists():
            self.fts_db.unlink()

        self.sqlite_conn = sqlite3.connect(str(self.fts_db))
        cur = self.sqlite_conn.cursor()

        # Configure SQLite for performance
        cur.execute("PRAGMA journal_mode=OFF;")
        cur.execute("PRAGMA synchronous=OFF;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap

        print("  🏗️  Creating FTS5 virtual table...")
        # Create FTS5 table with unicode61 tokenizer
        cur.execute("""
            CREATE VIRTUAL TABLE artist_fts USING fts5(
                display_name,
                disambiguation,
                type,
                area,
                begin_year,
                mbid UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            );
        """)

        print("  📥 Loading data from exact map...")
        # Load data from DuckDB exact map
        rows = self.duck_conn.execute("""
            SELECT DISTINCT
                display_name,
                COALESCE(disambiguation, '') as disambiguation,
                COALESCE(CAST(type AS TEXT), '') as type,
                COALESCE(CAST(area AS TEXT), '') as area,
                COALESCE(begin_year, '') as begin_year,
                mbid
            FROM artist_exact_map
        """).fetchall()

        print(f"  💾 Inserting {len(rows):,} rows into FTS5...")
        cur.executemany(
            "INSERT INTO artist_fts VALUES (?, ?, ?, ?, ?, ?)",
            rows
        )

        # Optimize
        print("  ⚡ Optimizing FTS5 index...")
        cur.execute("INSERT INTO artist_fts(artist_fts) VALUES('optimize');")

        self.sqlite_conn.commit()

        elapsed = time.time() - start_time
        size_mb = self.fts_db.stat().st_size / (1024 * 1024)

        print(f"\n✅ FTS5 index built in {elapsed:.2f}s")
        print(f"   💾 File size: {size_mb:.2f} MB")

        return size_mb

    def benchmark_exact_lookups(self, test_names: list[str]):
        """Benchmark exact lookups."""
        print(f"\n⚡ Benchmarking exact lookups ({len(test_names):,} queries)...")
        start_time = time.time()

        # Normalize all test names
        norm_names = [self.normalize_conservative(name) for name in test_names]

        # Batch query using DuckDB
        query = """
        WITH test_names(original, norm_name) AS (
            SELECT * FROM (VALUES {})
        )
        SELECT
            t.original,
            m.mbid,
            m.display_name,
            m.name_type
        FROM test_names t
        LEFT JOIN artist_exact_map m ON t.norm_name = m.norm_name
        """.format(','.join(f"('{name}', '{norm}')" for name, norm in zip(test_names, norm_names)))

        results = self.duck_conn.execute(query).fetchall()

        elapsed = time.time() - start_time

        # Count hits
        hits = sum(1 for r in results if r[1] is not None)
        misses = len(test_names) - hits

        print(f"✅ Exact lookup completed in {elapsed:.3f}s")
        print(f"   ⚡ Speed: {len(test_names) / elapsed:,.0f} queries/sec")
        print(f"   ✓ Hits: {hits:,} ({hits/len(test_names)*100:.1f}%)")
        print(f"   ✗ Misses: {misses:,} ({misses/len(test_names)*100:.1f}%)")

        return results, elapsed, hits, misses

    def benchmark_fts_lookups(self, test_names: list[str], limit: int = 5):
        """Benchmark FTS5 fuzzy lookups."""
        print(f"\n🔍 Benchmarking FTS5 fuzzy lookups ({len(test_names):,} queries)...")
        start_time = time.time()

        cur = self.sqlite_conn.cursor()
        results = []

        for name in test_names:
            # Build FTS query
            tokens = [t for t in re.split(r'\W+', name) if t]
            if not tokens:
                results.append([])
                continue

            query_str = ' '.join(tokens[:6])  # Cap at 6 tokens

            cur.execute("""
                SELECT mbid, display_name, bm25(artist_fts) as rank
                FROM artist_fts
                WHERE artist_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query_str, limit))

            results.append(cur.fetchall())

        elapsed = time.time() - start_time

        # Count hits (queries that returned at least one result)
        hits = sum(1 for r in results if r)
        misses = len(test_names) - hits

        print(f"✅ FTS lookup completed in {elapsed:.3f}s")
        print(f"   ⚡ Speed: {len(test_names) / elapsed:,.0f} queries/sec")
        print(f"   ✓ Hits: {hits:,} ({hits/len(test_names)*100:.1f}%)")
        print(f"   ✗ Misses: {misses:,} ({misses/len(test_names)*100:.1f}%)")

        return results, elapsed, hits, misses

    def close(self):
        """Close database connections."""
        if self.duck_conn:
            self.duck_conn.close()
        if self.sqlite_conn:
            self.sqlite_conn.close()

def load_test_artists_from_csv(csv_dir: Path = Path("./_test_csvs")) -> list[str]:
    """Load unique artist names from test CSV files."""
    import pandas as pd

    artists = set()
    csv_files = list(csv_dir.glob("*.csv"))

    print(f"📂 Loading artist names from test CSVs in {csv_dir}...")

    for csv_file in csv_files:
        try:
            # Try different encodings
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'windows-1252']:
                try:
                    df = pd.read_csv(csv_file, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            # Look for artist column (could be 'Artist' or 'Artist Name')
            artist_col = None
            for col in df.columns:
                if 'artist' in col.lower():
                    artist_col = col
                    break

            if artist_col:
                csv_artists = df[artist_col].dropna().unique()
                artists.update(csv_artists)
                print(f"   ✓ {csv_file.name}: {len(csv_artists):,} unique artists")
        except Exception as e:
            print(f"   ✗ Failed to read {csv_file.name}: {e}")

    artists_list = sorted(list(artists))
    print(f"\n✓ Loaded {len(artists_list):,} unique artists from CSV files\n")
    return artists_list

def main():
    """Run the optimization test."""
    print("=" * 80)
    print("🚀 Artist-Only Optimization Test")
    print("=" * 80)

    # Find MusicBrainz database (try different locations)
    mb_db_paths = [
        Path.home() / ".apple_music_converter" / "musicbrainz" / "duckdb" / "mb.duckdb",
        Path.home() / ".apple_music_converter" / "musicbrainz" / "musicbrainz_basic.duckdb",
    ]

    mb_db_path = None
    for path in mb_db_paths:
        if path.exists():
            mb_db_path = path
            break

    if not mb_db_path:
        print(f"❌ MusicBrainz database not found. Tried:")
        for path in mb_db_paths:
            print(f"   - {path}")
        print("   Please run the app and download the MusicBrainz database first.")
        return

    print(f"📂 Using MusicBrainz database: {mb_db_path}")
    original_size_mb = mb_db_path.stat().st_size / (1024 * 1024)
    print(f"   💾 Original size: {original_size_mb:.2f} MB\n")

    # Initialize test
    test = ArtistOnlyOptimizationTest(str(mb_db_path))

    try:
        # Build exact map
        exact_stats, exact_size_mb = test.build_exact_map()

        # Build FTS index
        fts_size_mb = test.build_fts_index()

        # Load test artists from CSV files
        test_names = load_test_artists_from_csv()

        if not test_names:
            print("⚠️  No artists found in CSV files, using default test set...")
            test_names = [
                "The Beatles", "Taylor Swift", "Drake", "Ed Sheeran", "Beyoncé",
                "Ariana Grande", "Post Malone", "Billie Eilish", "The Weeknd",
                "Justin Bieber", "Kanye West", "Eminem", "Rihanna", "Adele",
                "Bruno Mars", "Dua Lipa", "Lady Gaga", "Coldplay", "Imagine Dragons",
                "Maroon 5", "Radiohead", "Pink Floyd", "Led Zeppelin", "Queen",
                "David Bowie", "Prince", "Michael Jackson", "Madonna", "U2", "Metallica",
            ]

        # Benchmark exact lookups
        exact_results, exact_time, exact_hits, exact_misses = test.benchmark_exact_lookups(test_names)

        # Get misses for FTS testing
        misses = [test_names[i] for i, r in enumerate(exact_results) if r[1] is None]

        if misses:
            # Benchmark FTS lookups on misses
            fts_results, fts_time, fts_hits, fts_misses = test.benchmark_fts_lookups(misses)
        else:
            print("\n✓ All queries matched in exact lookup! No fuzzy search needed.")
            fts_hits = 0
            fts_misses = 0

        # Summary
        print("\n" + "=" * 80)
        print("📊 OPTIMIZATION SUMMARY")
        print("=" * 80)

        total_size_mb = exact_size_mb + fts_size_mb
        size_reduction_pct = (1 - total_size_mb / original_size_mb) * 100

        print(f"\n💾 SIZE COMPARISON:")
        print(f"   Original MusicBrainz DB: {original_size_mb:,.2f} MB")
        print(f"   Exact map (DuckDB):      {exact_size_mb:,.2f} MB")
        print(f"   FTS5 index (SQLite):     {fts_size_mb:,.2f} MB")
        print(f"   Total optimized size:    {total_size_mb:,.2f} MB")
        print(f"   📉 Size reduction:        {size_reduction_pct:.1f}%")

        print(f"\n⚡ PERFORMANCE:")
        print(f"   Exact lookups:  {len(test_names) / exact_time:,.0f} queries/sec")
        if misses:
            print(f"   FTS5 lookups:   {len(misses) / fts_time:,.0f} queries/sec")

        print(f"\n✓ COVERAGE:")
        total_hits = exact_hits + fts_hits
        total_misses = fts_misses if misses else exact_misses
        print(f"   Total queries:    {len(test_names):,}")
        print(f"   Exact matches:    {exact_hits:,} ({exact_hits/len(test_names)*100:.1f}%)")
        if misses:
            print(f"   Fuzzy matches:    {fts_hits:,} ({fts_hits/len(test_names)*100:.1f}%)")
        print(f"   Total coverage:   {total_hits:,} ({total_hits/len(test_names)*100:.1f}%)")
        print(f"   Not found:        {total_misses:,} ({total_misses/len(test_names)*100:.1f}%)")

        print(f"\n📁 Output files saved to: {test.output_dir}")
        print("=" * 80)

    finally:
        test.close()

if __name__ == "__main__":
    main()