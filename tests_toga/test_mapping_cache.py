#!/usr/bin/env python3
"""
Tests for the per-user track mapping cache (Phase 3).
"""

import pytest
import tempfile
import os
from pathlib import Path

# Skip all tests if DuckDB is not available
duckdb = pytest.importorskip("duckdb")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apple_music_history_converter.track_mapping import TrackMappingCache


class TestTrackMappingCache:
    """Test the TrackMappingCache class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database path (not file - DuckDB creates it)."""
        # Create a temp directory and generate a path (but don't create the file)
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_mappings.duckdb")
            yield db_path
            # Cleanup is automatic when TemporaryDirectory exits

    @pytest.fixture
    def cache(self, temp_db):
        """Create a cache instance with temp database."""
        c = TrackMappingCache(db_path=temp_db)
        yield c
        c.close()

    def test_cache_initialization(self, cache):
        """Test that cache initializes correctly."""
        assert cache.is_enabled
        stats = cache.get_stats()
        assert stats['enabled'] is True
        assert stats['total_mappings'] == 0

    def test_store_and_lookup(self, cache):
        """Test storing and looking up a mapping."""
        # Store a mapping
        result = cache.store(
            apple_song="Blinding Lights",
            apple_album="After Hours",
            apple_artist="The Weeknd",
            mb_artist_credit="The Weeknd",
            mb_release="After Hours",
            confidence="high"
        )
        assert result is True

        # Lookup the mapping
        found = cache.lookup(
            song="Blinding Lights",
            album="After Hours",
            artist="The Weeknd"
        )
        assert found is not None
        assert found['mb_artist_credit_name'] == "The Weeknd"
        assert found['mb_release_name'] == "After Hours"
        assert found['confidence'] == "high"

    def test_case_insensitive_lookup(self, cache):
        """Test that lookups are case-insensitive."""
        cache.store(
            apple_song="Bohemian Rhapsody",
            apple_album="A Night at the Opera",
            apple_artist="Queen",
            mb_artist_credit="Queen",
            confidence="high"
        )

        # Lookup with different case
        found = cache.lookup(
            song="BOHEMIAN RHAPSODY",
            album="a night at the opera",
            artist="QUEEN"
        )
        assert found is not None
        assert found['mb_artist_credit_name'] == "Queen"

    def test_whitespace_normalization(self, cache):
        """Test that whitespace is normalized in lookups."""
        cache.store(
            apple_song="  Hello  ",
            apple_album="  25  ",
            apple_artist="  Adele  ",
            mb_artist_credit="Adele",
            confidence="high"
        )

        found = cache.lookup(song="Hello", album="25", artist="Adele")
        assert found is not None
        assert found['mb_artist_credit_name'] == "Adele"

    def test_low_confidence_not_stored(self, cache):
        """Test that low confidence matches are not stored."""
        result = cache.store(
            apple_song="Test Song",
            apple_album="Test Album",
            apple_artist="Test Artist",
            mb_artist_credit="Some Artist",
            confidence="low"
        )
        assert result is False

        found = cache.lookup(song="Test Song", album="Test Album", artist="Test Artist")
        assert found is None

    def test_use_count_incremented(self, cache):
        """Test that use_count is incremented on lookup."""
        cache.store(
            apple_song="Test",
            apple_album=None,
            apple_artist=None,
            mb_artist_credit="Artist",
            confidence="high"
        )

        # First lookup
        found1 = cache.lookup(song="Test")
        assert found1['use_count'] == 1

        # Second lookup - should have higher use_count now
        found2 = cache.lookup(song="Test")
        assert found2['use_count'] == 2

    def test_user_verified_mapping(self, cache):
        """Test storing user-verified mappings."""
        result = cache.store_user_verified(
            apple_song="Song Name",
            apple_album="Album",
            apple_artist="Artist",
            mb_artist_credit="Corrected Artist"
        )
        assert result is True

        found = cache.lookup(song="Song Name", album="Album", artist="Artist")
        assert found is not None
        assert found['mb_artist_credit_name'] == "Corrected Artist"
        assert found['verified_by'] == "user"
        assert found['confidence'] == "manual"

    def test_get_stats(self, cache):
        """Test getting cache statistics."""
        # Add some mappings
        cache.store("Song1", None, None, "Artist1", confidence="high")
        cache.store("Song2", None, None, "Artist2", confidence="medium")
        cache.store_user_verified("Song3", None, None, "Artist3")

        stats = cache.get_stats()
        assert stats['enabled'] is True
        assert stats['total_mappings'] == 3
        assert 'high' in stats['by_confidence']
        assert 'medium' in stats['by_confidence']
        assert 'manual' in stats['by_confidence']

    def test_clear_all(self, cache):
        """Test clearing all mappings."""
        cache.store("Song1", None, None, "Artist1", confidence="high")
        cache.store("Song2", None, None, "Artist2", confidence="high")

        stats = cache.get_stats()
        assert stats['total_mappings'] == 2

        result = cache.clear_all()
        assert result is True

        stats = cache.get_stats()
        assert stats['total_mappings'] == 0

    def test_lookup_nonexistent(self, cache):
        """Test looking up a mapping that doesn't exist."""
        found = cache.lookup(song="Nonexistent Song", album="No Album", artist="No Artist")
        assert found is None

    def test_optional_fields(self, cache):
        """Test that album and artist are optional."""
        cache.store(
            apple_song="Song Only",
            apple_album=None,
            apple_artist=None,
            mb_artist_credit="Some Artist",
            confidence="high"
        )

        found = cache.lookup(song="Song Only")
        assert found is not None
        assert found['mb_artist_credit_name'] == "Some Artist"


class TestTrackMappingCacheDisabled:
    """Test behavior when DuckDB is not available."""

    def test_disabled_cache_operations(self):
        """Test that disabled cache returns appropriate values."""
        # Create cache in disabled state by forcing it
        cache = TrackMappingCache()
        cache._enabled = False
        cache._conn = None

        assert cache.is_enabled is False
        assert cache.lookup("Song") is None
        assert cache.store("Song", None, None, "Artist", confidence="high") is False
        assert cache.get_stats() == {'enabled': False}
        assert cache.clear_all() is False
