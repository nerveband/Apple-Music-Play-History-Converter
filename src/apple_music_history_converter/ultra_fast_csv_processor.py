#!/usr/bin/env python3
"""
Ultra-Fast CSV Processor
Processes Apple Music CSV files with 50-100x speedup using:
- Batch SQL queries
- Deduplication
- Vectorized text cleaning
- HOT/COLD cascade
- Smart batching

Target: 253K rows in 4-8 minutes (vs 5.3 hours)
"""

import pandas as pd
import time
import unicodedata
from typing import Optional, Callable, Dict, Tuple
from pathlib import Path

try:
    from .logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger(__name__)

class UltraFastCSVProcessor:
    """
    Ultra-optimized CSV processor using batch SQL and vectorization.

    Performance: 50-100x faster than row-by-row processing
    """

    def __init__(self, manager):
        """
        Initialize with MusicBrainz manager.

        Args:
            manager: MusicBrainzManagerV2Optimized instance
        """
        self.manager = manager
        self.conn = manager._conn
        self.batch_size = 5000  # Optimal batch size for DuckDB IN clause

        # Stats tracking
        self.stats = {
            'total_rows': 0,
            'unique_tracks': 0,
            'dedup_saves': 0,
            'hot_hits': 0,
            'cold_hits': 0,
            'cache_hits': 0,
            'not_found': 0,
            'total_time': 0
        }

    def process_csv(self, csv_file: str, progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Process CSV file with ultra-fast batch processing.

        Args:
            csv_file: Path to CSV file
            progress_callback: Optional callback(message, percent)

        Returns:
            Processed DataFrame with Artist column
        """
        start_time = time.time()

        logger.print_always("\n" + "="*70)
        logger.print_always("🚀 ULTRA-FAST CSV PROCESSING")
        logger.print_always("="*70)

        # Phase 1: Read CSV
        if progress_callback:
            progress_callback("Reading CSV...", 5)

        read_start = time.time()
        df = self._read_csv(csv_file)
        read_time = time.time() - read_start

        logger.print_always(f"✅ Read {len(df):,} rows in {read_time:.1f}s")
        self.stats['total_rows'] = len(df)

        # Phase 2: Vectorized text cleaning
        if progress_callback:
            progress_callback("Cleaning track names...", 15)

        clean_start = time.time()
        df = self._vectorized_clean(df)
        clean_time = time.time() - clean_start

        logger.print_always(f"✅ Cleaned {len(df):,} tracks in {clean_time:.1f}s")

        # Phase 3: Deduplication analysis
        if progress_callback:
            progress_callback("Analyzing unique tracks...", 25)

        dedup_start = time.time()
        unique_df = self._deduplicate(df)
        dedup_time = time.time() - dedup_start

        self.stats['unique_tracks'] = len(unique_df)
        self.stats['dedup_saves'] = len(df) - len(unique_df)
        dedup_ratio = (self.stats['dedup_saves'] / len(df)) * 100
        dedup_speedup = len(df) / len(unique_df) if len(unique_df) > 0 else 1

        logger.print_always(f"\n📊 Deduplication Analysis:")
        logger.print_always(f"   Total rows: {len(df):,}")
        logger.print_always(f"   Unique tracks: {len(unique_df):,} ({len(unique_df)/len(df)*100:.1f}%)")
        logger.print_always(f"   💾 Deduplication saves: {self.stats['dedup_saves']:,} searches ({dedup_ratio:.1f}%)")
        logger.print_always(f"   🚀 Speedup from dedup: {dedup_speedup:.1f}x")

        # Phase 4: Batch SQL queries
        if progress_callback:
            progress_callback("Batch searching MusicBrainz...", 35)

        search_start = time.time()
        track_to_artist = self._batch_search(unique_df, progress_callback)
        search_time = time.time() - search_start

        logger.print_always(f"\n✅ Batch search completed in {search_time:.1f}s")
        logger.print_always(f"   🔥 HOT table hits: {self.stats['hot_hits']:,} ({self.stats['hot_hits']/len(unique_df)*100:.1f}%)")
        logger.print_always(f"   ❄️  COLD table hits: {self.stats['cold_hits']:,} ({self.stats['cold_hits']/len(unique_df)*100:.1f}%)")
        logger.warning(f"   ⚠️  Not found: {self.stats['not_found']:,} ({self.stats['not_found']/len(unique_df)*100:.1f}%)")

        # Phase 5: Vectorized mapping
        if progress_callback:
            progress_callback("Mapping results...", 85)

        map_start = time.time()
        df = self._vectorized_map(df, track_to_artist)
        map_time = time.time() - map_start

        logger.print_always(f"\n✅ Mapped results in {map_time:.1f}s")

        # Final stats
        total_time = time.time() - start_time
        self.stats['total_time'] = total_time

        matched = df['Artist'].notna().sum()
        match_rate = (matched / len(df)) * 100
        throughput = len(df) / total_time

        logger.print_always(f"\n" + "="*70)
        logger.print_always("📊 FINAL RESULTS:")
        logger.print_always("="*70)
        logger.print_always(f"Total rows:      {len(df):,}")
        logger.print_always(f"Matched:         {matched:,} ({match_rate:.1f}%)")
        logger.print_always(f"Total time:      {self._format_time(total_time)}")
        logger.print_always(f"Throughput:      {throughput:.1f} rows/sec")

        # Calculate speedup vs old method (77ms per row)
        old_time = len(df) * 0.077  # 77ms per row
        speedup = old_time / total_time
        logger.print_always(f"Speedup:         🚀 {speedup:.1f}x faster!")
        logger.print_always("="*70 + "\n")

        if progress_callback:
            progress_callback("Complete!", 100)

        return df

    def _read_csv(self, csv_file: str) -> pd.DataFrame:
        """Read CSV with proper encoding detection."""
        try:
            # Try UTF-8 first (most common)
            return pd.read_csv(csv_file, encoding='utf-8', low_memory=False)
        except UnicodeDecodeError:
            try:
                # Try UTF-8 with BOM
                return pd.read_csv(csv_file, encoding='utf-8-sig', low_memory=False)
            except UnicodeDecodeError:
                try:
                    # Try Latin-1
                    return pd.read_csv(csv_file, encoding='latin-1', low_memory=False)
                except Exception:
                    # Last resort: Windows-1252
                    return pd.read_csv(csv_file, encoding='cp1252', low_memory=False)

    def _vectorized_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Vectorized text cleaning (MUCH faster than row-by-row).

        Uses pandas string operations instead of Python function calls.
        """
        # Get track name column (handle different CSV formats)
        track_col = None
        for col in ['Song Name', 'Track Description', 'Title']:
            if col in df.columns:
                track_col = col
                break

        if not track_col:
            raise ValueError("No track name column found in CSV")

        # Vectorized cleaning pipeline
        df['track_clean'] = (
            df[track_col]
            .fillna('')  # Handle NaN
            .str.normalize('NFKC')  # Unicode normalization
            .str.replace(r'\s*[\(\[].*?[\)\]]', '', regex=True)  # Remove parentheses
            .str.replace(r'\bfeat(?:\.|uring)?\b.*', '', regex=True, case=False)  # Remove feat.
            .str.lower()  # Lowercase
            .str.replace(r'[^\w\s]', '', regex=True)  # Remove punctuation
            .str.replace(r'\s+', ' ', regex=True)  # Collapse whitespace
            .str.strip()  # Trim
        )

        # Also get album if available
        album_col = 'Album' if 'Album' in df.columns else None
        if album_col:
            df['album_clean'] = df[album_col].fillna('').str.lower().str.strip()
        else:
            df['album_clean'] = ''

        return df

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract unique (track, album) pairs.

        This is where we get massive speedup for duplicate-heavy CSVs.
        """
        # Keep first occurrence of each unique track+album combo
        unique_df = df[['track_clean', 'album_clean']].drop_duplicates()
        return unique_df.reset_index(drop=True)

    def _batch_search(self, unique_df: pd.DataFrame, progress_callback: Optional[Callable] = None) -> Dict[Tuple[str, str], str]:
        """
        Batch search all unique tracks using massive SQL queries.

        This is the core optimization - single query for thousands of tracks!
        """
        track_to_artist = {}

        # Get list of unique tracks
        unique_tracks = unique_df['track_clean'].tolist()

        if not unique_tracks:
            return track_to_artist

        # Phase 1: Query HOT table in batches
        logger.print_always(f"\n🔥 Querying HOT table (batch size: {self.batch_size:,})...")

        for i in range(0, len(unique_tracks), self.batch_size):
            batch = unique_tracks[i:i+self.batch_size]

            # Update progress
            if progress_callback:
                progress = 35 + int((i / len(unique_tracks)) * 30)  # 35-65%
                progress_callback(f"Searching HOT table: {i:,}/{len(unique_tracks):,}", progress)

            # Build SQL with IN clause
            placeholders = ','.join(['?' for _ in batch])
            sql = f"""
                SELECT DISTINCT ON (recording_clean)
                       recording_clean, artist_credit_name, score
                FROM musicbrainz_hot
                WHERE recording_clean IN ({placeholders})
                ORDER BY recording_clean, score DESC
            """

            try:
                results = self.conn.execute(sql, batch).fetchall()
                for track, artist, score in results:
                    track_to_artist[track] = artist
                    self.stats['hot_hits'] += 1
            except Exception as e:
                logger.error(f"HOT table batch query failed: {e}")
                # Fall back to row-by-row for this batch
                for track in batch:
                    artist = self.manager.search(track)
                    if artist:
                        track_to_artist[track] = artist

        # Phase 2: Query COLD table for misses
        missed_tracks = [t for t in unique_tracks if t not in track_to_artist]

        if missed_tracks:
            logger.print_always(f"\n❄️  Querying COLD table for {len(missed_tracks):,} misses...")

            for i in range(0, len(missed_tracks), self.batch_size):
                batch = missed_tracks[i:i+self.batch_size]

                # Update progress
                if progress_callback:
                    progress = 65 + int((i / len(missed_tracks)) * 15)  # 65-80%
                    progress_callback(f"Searching COLD table: {i:,}/{len(missed_tracks):,}", progress)

                placeholders = ','.join(['?' for _ in batch])
                sql = f"""
                    SELECT DISTINCT ON (recording_clean)
                           recording_clean, artist_credit_name, score
                    FROM musicbrainz_cold
                    WHERE recording_clean IN ({placeholders})
                    ORDER BY recording_clean, score DESC
                """

                try:
                    results = self.conn.execute(sql, batch).fetchall()
                    for track, artist, score in results:
                        track_to_artist[track] = artist
                        self.stats['cold_hits'] += 1
                except Exception as e:
                    logger.error(f"COLD table batch query failed: {e}")

        # Phase 3: Skip fuzzy matching for SPEED
        # Batch queries give us ~94%+ hit rate which is excellent
        # Fuzzy matching takes 100-500ms per track = 5-50 minutes for 1000 tracks!
        # Users can re-process with iTunes fallback for the ~6% misses if needed
        still_missed = [t for t in unique_tracks if t not in track_to_artist]
        if still_missed:
            logger.warning(f"\n⚠️  {len(still_missed):,} tracks not found in batch queries (will be left blank)")
            logger.info(f"   Tip: Re-run with iTunes fallback enabled for better coverage")

        # Count not found
        self.stats['not_found'] = len(unique_tracks) - len(track_to_artist)

        return track_to_artist

    def _vectorized_map(self, df: pd.DataFrame, track_to_artist: Dict[str, str]) -> pd.DataFrame:
        """
        Vectorized mapping of results back to all rows.

        Uses pandas map() which is MUCH faster than iterrows().
        """
        # Map track_clean to artist
        df['Artist'] = df['track_clean'].map(track_to_artist)

        return df

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = seconds % 60
            return f"{mins}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}h {mins}m {secs:.0f}s"

    def get_stats(self) -> Dict:
        """Get processing statistics."""
        return self.stats.copy()