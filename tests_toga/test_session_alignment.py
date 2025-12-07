#!/usr/bin/env python3
"""
Tests for the album-session alignment feature (Phase 2).
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apple_music_history_converter.session_aligner import SessionAligner, AlbumSession


class MockMusicBrainzManager:
    """Mock manager for testing without database.

    Uses real data from test CSVs (Spirited Away, Howl's Moving Castle soundtracks).
    """

    def __init__(self):
        self._conn = MagicMock()

        # Set up mock release data from real test CSV files
        # These tracks are from _test_csvs/Apple Music - Recently Played Tracks.csv
        self.mock_releases = {
            'spirited away': [
                ('Joe Hisaishi', 'Spirited Away (Original Soundtrack)', 'One Summer\'s Day', 100),
                ('Joe Hisaishi', 'Spirited Away (Original Soundtrack)', 'The Dragon Boy', 100),
                ('Joe Hisaishi', 'Spirited Away (Original Soundtrack)', 'Sootballs', 100),
                ('Joe Hisaishi', 'Spirited Away (Original Soundtrack)', 'Procession of Gods', 100),
            ],
            'howl\'s moving castle': [
                ('Joe Hisaishi', 'Howl\'s Moving Castle (Original Soundtrack)', 'The Flower Garden', 100),
                ('Joe Hisaishi', 'Howl\'s Moving Castle (Original Soundtrack)', 'Sophie\'s Castle', 100),
                ('Joe Hisaishi', 'Howl\'s Moving Castle (Original Soundtrack)', 'In the Rain', 100),
                ('Joe Hisaishi', 'Howl\'s Moving Castle (Original Soundtrack)', 'Run!', 100),
            ]
        }

        # Configure mock connection
        self._conn.execute = self._mock_execute

    def _mock_execute(self, sql, params=None):
        """Mock execute that returns release tracks."""
        result = MagicMock()

        if params:
            # Extract album name from LIKE query
            album_search = params[0].strip('%').lower()
            for album_key, tracks in self.mock_releases.items():
                if album_key in album_search or album_search in album_key:
                    result.fetchall.return_value = tracks
                    return result

        result.fetchall.return_value = []
        return result

    def clean_text_conservative(self, text: str) -> str:
        """Mock text cleaning."""
        return text.lower().strip()


class TestSessionDetection:
    """Test session detection logic."""

    @pytest.fixture
    def aligner(self):
        """Create aligner with mock manager."""
        manager = MockMusicBrainzManager()
        return SessionAligner(manager, min_session_size=3)

    def test_detect_single_session(self, aligner):
        """Test detecting a single album session using real test CSV data."""
        # Tracks from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            {'track': 'One Summer\'s Day', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'The Dragon Boy', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Sootballs', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Procession of Gods', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 1
        assert 'spirited away' in sessions[0].album_name.lower()
        assert sessions[0].track_count == 4
        assert sessions[0].start_index == 0

    def test_detect_multiple_sessions(self, aligner):
        """Test detecting multiple album sessions using real test CSV data."""
        # Tracks from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            # Session 1: Spirited Away
            {'track': 'One Summer\'s Day', 'album': 'Spirited Away (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            {'track': 'The Dragon Boy', 'album': 'Spirited Away (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            {'track': 'Sootballs', 'album': 'Spirited Away (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            # Different album (not enough for session)
            {'track': 'Random Song', 'album': 'Some Album', 'artist': 'Someone'},
            {'track': 'Another Song', 'album': 'Some Album', 'artist': 'Someone'},
            # Session 2: Howl's Moving Castle
            {'track': 'The Flower Garden', 'album': 'Howl\'s Moving Castle (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            {'track': 'Sophie\'s Castle', 'album': 'Howl\'s Moving Castle (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            {'track': 'In the Rain', 'album': 'Howl\'s Moving Castle (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
            {'track': 'Run!', 'album': 'Howl\'s Moving Castle (Original Soundtrack)', 'artist': 'Joe Hisaishi'},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 2
        assert 'spirited away' in sessions[0].album_name.lower()
        assert sessions[0].track_count == 3
        assert 'howl' in sessions[1].album_name.lower()
        assert sessions[1].track_count == 4

    def test_no_session_below_minimum(self, aligner):
        """Test that sessions below minimum size are not detected."""
        tracks = [
            {'track': 'Track 1', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 2', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 3', 'album': 'Album B', 'artist': ''},
            {'track': 'Track 4', 'album': 'Album C', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 0

    def test_empty_albums_break_sessions(self, aligner):
        """Test that tracks without albums break session detection."""
        tracks = [
            {'track': 'Track 1', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 2', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 3', 'album': '', 'artist': ''},  # Breaks session
            {'track': 'Track 4', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 5', 'album': 'Album A', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 0  # Neither part is big enough

    def test_empty_track_list(self, aligner):
        """Test handling of empty track list."""
        sessions = aligner.detect_sessions([])
        assert len(sessions) == 0


class TestSessionAlignment:
    """Test session alignment to MusicBrainz."""

    @pytest.fixture
    def aligner(self):
        """Create aligner with mock manager."""
        manager = MockMusicBrainzManager()
        return SessionAligner(manager, min_session_size=3)

    def test_align_session_sets_artist(self, aligner):
        """Test that alignment sets the correct artist credit using real test CSV data."""
        # Data from _test_csvs/Apple Music - Recently Played Tracks.csv
        session = AlbumSession(
            album_name='spirited away',
            artist_hint='Joe Hisaishi',
            tracks=[
                {'track': 'One Summer\'s Day', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
                {'track': 'The Dragon Boy', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
                {'track': 'Sootballs', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            ],
            start_index=0
        )

        aligned = aligner.align_session(session)

        assert aligned.aligned is True
        assert aligned.mb_artist_credit == 'Joe Hisaishi'
        assert 'Spirited Away' in aligned.mb_release_name

    def test_align_all_sessions_updates_tracks(self, aligner):
        """Test that align_all_sessions updates track dictionaries using real test CSV data."""
        # Data from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            {'track': 'One Summer\'s Day', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'The Dragon Boy', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Sootballs', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)
        updated_tracks = aligner.align_all_sessions(sessions, tracks)

        assert len(updated_tracks) == 3
        for track in updated_tracks:
            assert track['artist'] == 'Joe Hisaishi'
            assert track['match_source'] == 'session_aligned'
            assert track['match_confidence'] == 'high_session'

    def test_alignment_preserves_existing_artists(self, aligner):
        """Test that alignment doesn't overwrite existing artist matches using real test CSV data."""
        # Data from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            {'track': 'One Summer\'s Day', 'album': 'Spirited Away (Original Soundtrack)', 'artist': 'Existing Artist'},
            {'track': 'The Dragon Boy', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Sootballs', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)
        updated_tracks = aligner.align_all_sessions(sessions, tracks)

        # First track should keep its existing artist
        assert updated_tracks[0]['artist'] == 'Existing Artist'
        # Others should get session-aligned artist
        assert updated_tracks[1]['artist'] == 'Joe Hisaishi'
        assert updated_tracks[2]['artist'] == 'Joe Hisaishi'


class TestAlbumSession:
    """Test AlbumSession dataclass."""

    def test_track_count(self):
        """Test track_count property."""
        session = AlbumSession(
            album_name='Test Album',
            artist_hint='Test Artist',
            tracks=[{'track': 't1'}, {'track': 't2'}, {'track': 't3'}]
        )
        assert session.track_count == 3

    def test_repr(self):
        """Test string representation."""
        session = AlbumSession(
            album_name='Test Album',
            artist_hint='Test Artist',
            tracks=[{'track': 't1'}]
        )
        assert 'Test Album' in repr(session)
        assert '1 tracks' in repr(session)


class TestSessionAlignerStats:
    """Test statistics tracking."""

    @pytest.fixture
    def aligner(self):
        """Create aligner with mock manager."""
        manager = MockMusicBrainzManager()
        return SessionAligner(manager, min_session_size=3)

    def test_stats_after_detection(self, aligner):
        """Test stats are updated after session detection."""
        tracks = [
            {'track': 'Track 1', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 2', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 3', 'album': 'Album A', 'artist': ''},
        ]

        aligner.detect_sessions(tracks)
        stats = aligner.get_stats()

        assert stats['sessions_detected'] == 1
        assert stats['tracks_in_sessions'] == 3

    def test_reset_stats(self, aligner):
        """Test stats reset."""
        tracks = [
            {'track': 'Track 1', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 2', 'album': 'Album A', 'artist': ''},
            {'track': 'Track 3', 'album': 'Album A', 'artist': ''},
        ]

        aligner.detect_sessions(tracks)
        aligner.reset_stats()
        stats = aligner.get_stats()

        assert stats['sessions_detected'] == 0
        assert stats['tracks_in_sessions'] == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def aligner(self):
        """Create aligner with mock manager."""
        manager = MockMusicBrainzManager()
        return SessionAligner(manager, min_session_size=3)

    def test_case_insensitive_album_matching(self, aligner):
        """Test that album matching is case-insensitive using real test CSV data."""
        # Album from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            {'track': 'Track 1', 'album': 'SPIRITED AWAY (ORIGINAL SOUNDTRACK)', 'artist': ''},
            {'track': 'Track 2', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Track 3', 'album': 'spirited away (original soundtrack)', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 1
        assert sessions[0].track_count == 3

    def test_whitespace_handling(self, aligner):
        """Test that whitespace is handled properly using real test CSV data."""
        # Album from _test_csvs/Apple Music - Recently Played Tracks.csv
        tracks = [
            {'track': 'Track 1', 'album': '  Spirited Away (Original Soundtrack)  ', 'artist': ''},
            {'track': 'Track 2', 'album': 'Spirited Away (Original Soundtrack)', 'artist': ''},
            {'track': 'Track 3', 'album': 'Spirited Away (Original Soundtrack) ', 'artist': ''},
        ]

        sessions = aligner.detect_sessions(tracks)

        assert len(sessions) == 1
        assert sessions[0].track_count == 3

    def test_null_manager_connection(self, aligner):
        """Test handling when manager connection is None."""
        aligner.manager._conn = None

        session = AlbumSession(
            album_name='Test Album',
            artist_hint='Test Artist',
            tracks=[{'track': 't1'}, {'track': 't2'}, {'track': 't3'}]
        )

        # Should not raise, just return unaligned
        aligned = aligner.align_session(session)
        assert aligned.aligned is False

    def test_minimum_session_size_customization(self):
        """Test that minimum session size can be customized."""
        manager = MockMusicBrainzManager()
        aligner = SessionAligner(manager, min_session_size=5)

        tracks = [
            {'track': f'Track {i}', 'album': 'Album A', 'artist': ''}
            for i in range(4)  # Only 4 tracks
        ]

        sessions = aligner.detect_sessions(tracks)
        assert len(sessions) == 0  # Not enough for session of 5


class TestRealCSVIntegration:
    """Integration tests using real test CSV files."""

    @pytest.fixture
    def test_csv_path(self):
        """Get path to Recently Played Tracks test CSV."""
        csv_path = Path(__file__).parent.parent / "_test_csvs" / "Apple Music - Recently Played Tracks.csv"
        if not csv_path.exists():
            pytest.skip(f"Test CSV not found: {csv_path}")
        return csv_path

    def test_detect_sessions_from_real_csv(self, test_csv_path):
        """Test session detection using real CSV data with album sessions."""
        import pandas as pd

        # Load CSV and extract tracks
        df = pd.read_csv(test_csv_path)

        # Convert to track format used by SessionAligner
        tracks = []
        for _, row in df.iterrows():
            container_desc = row.get('Container Description', '')
            track_desc = row.get('Track Description', '')

            # Parse "Artist - Track" format
            if ' - ' in str(track_desc):
                parts = str(track_desc).split(' - ', 1)
                artist = parts[0].strip()
                track_name = parts[1].strip()
            else:
                artist = ''
                track_name = str(track_desc).strip()

            tracks.append({
                'track': track_name,
                'album': str(container_desc) if pd.notna(container_desc) else '',
                'artist': artist
            })

        # Create aligner with mock manager (just for session detection)
        manager = MockMusicBrainzManager()
        aligner = SessionAligner(manager, min_session_size=3)

        # Detect sessions
        sessions = aligner.detect_sessions(tracks)

        # The test CSV has consecutive tracks from Spirited Away and Howl's Moving Castle
        # We should detect at least 2 sessions (one for each soundtrack)
        assert len(sessions) >= 2

        # Check that Spirited Away session was detected
        spirited_away_sessions = [s for s in sessions if 'spirited away' in s.album_name.lower()]
        assert len(spirited_away_sessions) >= 1
        assert spirited_away_sessions[0].track_count >= 3

        # Check that Howl's Moving Castle session was detected
        howls_sessions = [s for s in sessions if "howl" in s.album_name.lower()]
        assert len(howls_sessions) >= 1
        assert howls_sessions[0].track_count >= 3

    def test_stats_with_real_csv(self, test_csv_path):
        """Test that stats are correctly calculated for real CSV data."""
        import pandas as pd

        df = pd.read_csv(test_csv_path)

        tracks = []
        for _, row in df.iterrows():
            container_desc = row.get('Container Description', '')
            track_desc = row.get('Track Description', '')

            if ' - ' in str(track_desc):
                parts = str(track_desc).split(' - ', 1)
                track_name = parts[1].strip()
            else:
                track_name = str(track_desc).strip()

            tracks.append({
                'track': track_name,
                'album': str(container_desc) if pd.notna(container_desc) else '',
                'artist': ''
            })

        manager = MockMusicBrainzManager()
        aligner = SessionAligner(manager, min_session_size=3)

        sessions = aligner.detect_sessions(tracks)
        stats = aligner.get_stats()

        assert stats['sessions_detected'] == len(sessions)
        assert stats['tracks_in_sessions'] > 0
        # The CSV has many tracks from the same albums, so we should have many tracks in sessions
        assert stats['tracks_in_sessions'] >= 10  # At least 10 tracks should be in sessions
