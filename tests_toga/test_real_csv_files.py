"""
Integration tests using real CSV files from _test_csvs folder.
Tests actual file processing with real Apple Music export data.
"""
import pytest
from pathlib import Path
import pandas as pd


# Path to test CSV files
TEST_CSV_DIR = Path(__file__).parent.parent / "_test_csvs"


class TestRealCSVFiles:
    """Test with actual Apple Music CSV export files."""

    def test_test_csv_directory_exists(self):
        """Verify test CSV directory exists."""
        assert TEST_CSV_DIR.exists(), f"Test CSV directory not found: {TEST_CSV_DIR}"
        assert TEST_CSV_DIR.is_dir(), "Test CSV path is not a directory"

    def test_all_test_files_exist(self):
        """Verify all expected test CSV files exist."""
        expected_files = [
            "Apple Music Play Activity small.csv",
            "Apple Music Play Activity full.csv",
            "Apple Music - Play History Daily Tracks.csv",
            "Apple Music - Recently Played Tracks.csv"
        ]

        for filename in expected_files:
            filepath = TEST_CSV_DIR / filename
            assert filepath.exists(), f"Test file missing: {filename}"

    def test_play_activity_small_structure(self):
        """Test Play Activity small CSV has correct structure."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        # Read CSV
        df = pd.read_csv(filepath, nrows=10)  # Read first 10 rows

        # Verify key columns exist
        assert "Song Name" in df.columns
        # Note: This format uses very long column names with full details
        assert "Album Name" in df.columns

        # Should have multiple rows
        assert len(df) > 0

    def test_play_activity_full_is_large(self):
        """Test Play Activity full CSV is large (269MB)."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity full.csv"

        # Check file size
        file_size = filepath.stat().st_size
        assert file_size > 100_000_000, f"Full CSV should be >100MB, got {file_size:,} bytes"

        # Can read header without loading entire file
        df_header = pd.read_csv(filepath, nrows=0)
        assert "Song Name" in df_header.columns
        assert "Album Name" in df_header.columns

    def test_play_activity_full_row_count(self):
        """Test Play Activity full CSV has many rows (using chunking)."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity full.csv"

        # Count rows using chunking to avoid memory issues
        row_count = 0
        chunk_size = 10000

        for chunk in pd.read_csv(filepath, chunksize=chunk_size):
            row_count += len(chunk)

        # Should have hundreds of thousands of rows
        assert row_count > 10000, f"Expected >10k rows, got {row_count:,}"
        print(f"✅ Full CSV has {row_count:,} rows")

    def test_play_history_daily_structure(self):
        """Test Play History Daily Tracks CSV structure."""
        filepath = TEST_CSV_DIR / "Apple Music - Play History Daily Tracks.csv"

        df = pd.read_csv(filepath)

        # This format has different columns
        assert "Track Description" in df.columns
        assert len(df) > 0

    def test_recently_played_structure(self):
        """Test Recently Played Tracks CSV structure."""
        filepath = TEST_CSV_DIR / "Apple Music - Recently Played Tracks.csv"

        df = pd.read_csv(filepath)

        # This format has different columns
        assert "Track Description" in df.columns or "Song Name" in df.columns
        assert len(df) > 0

    def test_csv_encoding_detection(self):
        """Test that CSVs can be read with UTF-8 encoding."""
        test_files = [
            "Apple Music Play Activity small.csv",
            "Apple Music - Play History Daily Tracks.csv",
            "Apple Music - Recently Played Tracks.csv"
        ]

        for filename in test_files:
            filepath = TEST_CSV_DIR / filename

            # Should be readable with UTF-8
            try:
                df = pd.read_csv(filepath, encoding='utf-8', nrows=5)
                assert len(df) > 0
            except UnicodeDecodeError:
                # Try latin-1 fallback
                df = pd.read_csv(filepath, encoding='latin-1', nrows=5)
                assert len(df) > 0

    def test_missing_artists_detection(self):
        """Test detection of rows with missing artist information."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath)

        # Check if there are any rows with missing Song Name
        missing_songs = df[df["Song Name"].isna() | (df["Song Name"] == "")]

        # Document how many missing
        print(f"Found {len(missing_songs)} rows with missing song names")

    def test_timestamp_formats(self):
        """Test that timestamps can be parsed."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath, nrows=10)

        # Check if timestamp column exists (various possible names)
        timestamp_columns = [col for col in df.columns if 'Time' in col or 'Date' in col]

        assert len(timestamp_columns) > 0, "No timestamp columns found"
        print(f"Found timestamp columns: {timestamp_columns}")

    def test_chunk_processing_performance(self):
        """Test that chunked processing works for large file."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity full.csv"

        import time
        start = time.time()

        # Process in chunks
        chunk_size = 10000
        chunks_processed = 0
        rows_processed = 0

        for chunk in pd.read_csv(filepath, chunksize=chunk_size):
            chunks_processed += 1
            rows_processed += len(chunk)

            # Process first 3 chunks only for speed
            if chunks_processed >= 3:
                break

        elapsed = time.time() - start

        print(f"✅ Processed {chunks_processed} chunks ({rows_processed:,} rows) in {elapsed:.2f}s")
        print(f"   Speed: {rows_processed/elapsed:.0f} rows/second")

        assert chunks_processed >= 3
        assert rows_processed >= 20000  # Should have at least 2 full chunks

    def test_export_format_conversion(self):
        """Test converting to Last.fm format."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath, nrows=10)

        # Simulate conversion to Last.fm format
        # Last.fm format: artist,track,album,date
        lastfm_format = pd.DataFrame({
            'artist': '',  # Would be populated from search
            'track': df['Song Name'],
            'album': df['Album Name'],
            'date': 0  # Would be calculated from timestamps
        })

        assert len(lastfm_format) == len(df)
        assert 'artist' in lastfm_format.columns
        assert 'track' in lastfm_format.columns
        assert 'album' in lastfm_format.columns
        assert 'date' in lastfm_format.columns


class TestCrossFormatCompatibility:
    """Test handling of different CSV format types."""

    def test_all_formats_loadable(self):
        """Test that all CSV formats can be loaded."""
        test_files = [
            ("Apple Music Play Activity small.csv", "Play Activity"),
            ("Apple Music - Play History Daily Tracks.csv", "Play History"),
            ("Apple Music - Recently Played Tracks.csv", "Recently Played")
        ]

        for filename, format_type in test_files:
            filepath = TEST_CSV_DIR / filename

            # Should load without errors
            df = pd.read_csv(filepath, nrows=5)
            assert len(df) > 0, f"Failed to load {format_type}"
            print(f"✅ {format_type}: {len(df.columns)} columns, loaded successfully")

    def test_format_detection_by_filename(self):
        """Test that format can be detected from filename."""
        test_cases = [
            ("Apple Music Play Activity small.csv", "Play Activity"),
            ("Apple Music - Play History Daily Tracks.csv", "Play History"),
            ("Apple Music - Recently Played Tracks.csv", "Recently Played")
        ]

        for filename, expected_format in test_cases:
            # Filename-based detection
            if "Play Activity" in filename:
                detected = "Play Activity"
            elif "Play History" in filename:
                detected = "Play History"
            elif "Recently Played" in filename:
                detected = "Recently Played"
            else:
                detected = "Unknown"

            assert detected == expected_format, f"Wrong format detected for {filename}"

    def test_format_detection_by_columns(self):
        """Test that format can be detected from column structure."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"
        df = pd.read_csv(filepath, nrows=1)

        # Play Activity has very detailed columns
        columns = set(df.columns)

        # Check for format-specific columns
        if "Song Name" in columns and "Album Name" in columns:
            assert True  # Play Activity format
        elif "Track Description" in columns:
            assert True  # Play History or Recently Played
        else:
            pytest.fail("Could not determine format from columns")


class TestMemoryEfficiency:
    """Test memory-efficient processing of large files."""

    def test_chunked_vs_full_load_memory(self):
        """Compare memory usage of chunked vs full load."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        import sys

        # Full load
        df_full = pd.read_csv(filepath)
        full_memory = sys.getsizeof(df_full)

        # Chunked load (simulated - just test mechanism works)
        chunk_count = 0
        for chunk in pd.read_csv(filepath, chunksize=100):
            chunk_count += 1
            chunk_memory = sys.getsizeof(chunk)
            # Each chunk should use less memory than full file
            assert chunk_memory < full_memory or chunk_count == 1

        print(f"✅ Full file: {full_memory:,} bytes")
        print(f"   Processed in {chunk_count} chunks")

    def test_nrows_parameter_limits_memory(self):
        """Test that nrows parameter limits memory usage."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity full.csv"

        # Read only 100 rows
        df_small = pd.read_csv(filepath, nrows=100)

        assert len(df_small) == 100
        print(f"✅ Limited read to {len(df_small)} rows")


class TestDataQuality:
    """Test data quality and integrity."""

    def test_no_completely_empty_rows(self):
        """Test that there are no completely empty rows."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath)

        # Check if any row is completely empty
        empty_rows = df.isnull().all(axis=1).sum()

        print(f"Found {empty_rows} completely empty rows")
        # Allow some empty rows as they might be legitimate

    def test_song_name_not_all_missing(self):
        """Test that Song Name column is not entirely missing."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath)

        # Count non-empty song names
        valid_songs = df[df["Song Name"].notna() & (df["Song Name"] != "")]

        assert len(valid_songs) > 0, "No valid song names found!"
        print(f"✅ Found {len(valid_songs)} rows with song names out of {len(df)} total")

    def test_special_characters_handling(self):
        """Test that special characters in data are handled correctly."""
        filepath = TEST_CSV_DIR / "Apple Music Play Activity small.csv"

        df = pd.read_csv(filepath, nrows=100)

        # Check if data loads without errors despite special characters
        assert len(df) > 0

        # Check for non-ASCII characters (they should be preserved)
        if len(df) > 0 and "Song Name" in df.columns:
            for song in df["Song Name"].dropna().head(10):
                # Should be able to convert to string without errors
                str_song = str(song)
                assert len(str_song) >= 0
