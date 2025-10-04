"""
Pytest configuration for Toga tests.
"""
import pytest
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def test_csv_path(tmp_path):
    """Create a test CSV file with Play Activity format."""
    csv_file = tmp_path / "test_play_activity.csv"
    csv_file.write_text(
        "Song Name,Artist Name,Album Name,Play Date Time\n"
        "Test Track 1,Test Artist 1,Test Album 1,2024-01-01 12:00:00\n"
        "Test Track 2,Test Artist 2,Test Album 2,2024-01-02 13:00:00\n"
        "Test Track 3,,Test Album 3,2024-01-03 14:00:00\n"  # Missing artist
    )
    return str(csv_file)


@pytest.fixture
def large_test_csv_path(tmp_path):
    """Create a large test CSV file for chunking tests."""
    csv_file = tmp_path / "test_large.csv"
    lines = ["Song Name,Artist Name,Album Name,Play Date Time\n"]
    for i in range(1000):
        lines.append(f"Track {i},Artist {i},Album {i},2024-01-01 12:{i % 60}:00\n")
    csv_file.write_text("".join(lines))
    return str(csv_file)
