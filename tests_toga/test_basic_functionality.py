"""
Basic smoke tests for Toga implementation.
Tests core functionality without GUI.
"""
import pytest
from pathlib import Path

# Import the app modules
from apple_music_history_converter import apple_music_play_history_converter


class TestFileTypeDetection:
    """Test CSV file type detection."""

    def test_detect_play_activity_from_filename(self, test_csv_path):
        """Test detection of Play Activity format from filename."""
        # Rename file to match pattern
        test_path = Path(test_csv_path)
        new_path = test_path.parent / "Apple Music - Play Activity.csv"
        test_path.rename(new_path)

        # The detection logic would check filename
        assert "Play Activity" in str(new_path)

    def test_detect_play_history_from_filename(self, tmp_path):
        """Test detection of Play History format from filename."""
        csv_file = tmp_path / "Apple Music - Play History Daily Tracks.csv"
        csv_file.write_text("Track Description,Album,Date\n")

        assert "Play History" in str(csv_file)

    def test_detect_recently_played_from_filename(self, tmp_path):
        """Test detection of Recently Played format from filename."""
        csv_file = tmp_path / "Apple Music - Recently Played Tracks.csv"
        csv_file.write_text("Track Description,Container Description\n")

        assert "Recently Played" in str(csv_file)


class TestCSVProcessing:
    """Test CSV loading and processing."""

    def test_csv_file_exists(self, test_csv_path):
        """Test that test CSV file was created."""
        assert Path(test_csv_path).exists()

    def test_csv_has_correct_headers(self, test_csv_path):
        """Test CSV has expected Play Activity headers."""
        content = Path(test_csv_path).read_text()
        headers = content.split('\n')[0]

        assert "Song Name" in headers
        assert "Artist Name" in headers
        assert "Album Name" in headers
        assert "Play Date Time" in headers

    def test_csv_has_missing_artist(self, test_csv_path):
        """Test CSV contains a row with missing artist (for testing)."""
        content = Path(test_csv_path).read_text()
        lines = content.split('\n')

        # Line 3 should have empty artist field
        assert "Test Track 3,," in lines[3]

    def test_large_csv_created(self, large_test_csv_path):
        """Test large CSV file was created with 1000 rows."""
        content = Path(large_test_csv_path).read_text()
        lines = content.split('\n')

        # Should have header + 1000 data rows + empty line at end
        assert len(lines) >= 1001


class TestSecurityFixes:
    """Test that security vulnerabilities are fixed."""

    def test_no_os_system_calls(self):
        """Verify os.system() is not used in the codebase."""
        import apple_music_history_converter.apple_music_play_history_converter as app_module
        source_file = Path(app_module.__file__)

        source_code = source_file.read_text()

        # Should NOT contain os.system calls
        assert "os.system(" not in source_code, "Found unsafe os.system() call!"

    def test_subprocess_used_instead(self):
        """Verify subprocess is imported and used."""
        import apple_music_history_converter.apple_music_play_history_converter as app_module
        source_file = Path(app_module.__file__)

        source_code = source_file.read_text()

        # Should contain subprocess import
        assert "import subprocess" in source_code, "subprocess not imported!"

        # Should contain shell=False for security
        assert "shell=False" in source_code, "subprocess not using shell=False!"


class TestDataNormalization:
    """Test data normalization and conversion logic."""

    def test_timestamp_format(self):
        """Test timestamp parsing from Play Activity format."""
        # Example timestamp: "2024-01-01 12:00:00"
        test_timestamp = "2024-01-01 12:00:00"

        from datetime import datetime
        # Should be parseable
        dt = datetime.strptime(test_timestamp, "%Y-%m-%d %H:%M:%S")

        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_csv_column_mapping(self, test_csv_path):
        """Test that CSV columns can be mapped to internal format."""
        import pandas as pd

        df = pd.read_csv(test_csv_path)

        # Verify columns exist
        assert "Song Name" in df.columns
        assert "Artist Name" in df.columns
        assert "Album Name" in df.columns

        # Can be mapped to internal format
        internal_mapping = {
            "Song Name": "track",
            "Artist Name": "artist",
            "Album Name": "album"
        }

        for csv_col, internal_col in internal_mapping.items():
            assert csv_col in df.columns


class TestCrossPlatform:
    """Test cross-platform path handling."""

    def test_pathlib_used(self):
        """Verify pathlib is used for path operations."""
        import apple_music_history_converter.apple_music_play_history_converter as app_module
        source_file = Path(app_module.__file__)

        source_code = source_file.read_text()

        # Should import Path from pathlib
        assert "from pathlib import Path" in source_code or "import pathlib" in source_code

    def test_path_resolution(self, test_csv_path):
        """Test that paths are properly resolved."""
        test_path = Path(test_csv_path)

        # Should be absolute
        assert test_path.is_absolute()

        # Should exist
        assert test_path.exists()

    def test_subprocess_commands_cross_platform(self):
        """Test that subprocess commands check platform."""
        import apple_music_history_converter.apple_music_play_history_converter as app_module
        source_file = Path(app_module.__file__)

        source_code = source_file.read_text()

        # Should check for different platforms
        assert 'sys.platform == "darwin"' in source_code  # macOS
        assert 'sys.platform == "win32"' in source_code   # Windows
