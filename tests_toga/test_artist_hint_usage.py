"""
Test that artist_hint is properly used in MusicBrainz database searches.

This test was created to verify the fix for the bug where artist_hint
was passed to the search function but never used in the actual database queries,
causing wrong artists to be returned for common song names.

Bug symptoms:
- "Stay" by Rihanna returns "fahxrul"
- "Closer" by The Chainsmokers returns "Fuemana"
- "Happy" by Pharrell Williams returns "Towa Tei"
"""
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized
from apple_music_history_converter.app_directories import get_database_dir


class TestArtistHintUsage:
    """Test that artist_hint parameter affects search results."""

    @pytest.fixture
    def manager(self):
        """Get MusicBrainz manager instance."""
        data_dir = str(get_database_dir())
        mgr = MusicBrainzManagerV2Optimized(data_dir)
        if not mgr.is_ready():
            pytest.skip("MusicBrainz database not available")
        return mgr

    def test_artist_hint_affects_search_results(self, manager):
        """
        CRITICAL TEST: When artist_hint is provided, it should influence results.

        This test searches for "Hello" (a common song name) with different artist hints.
        Without using artist_hint, the search might return any artist with a "Hello" song.
        With artist_hint="Adele", it should prioritize Adele's version.

        If this test fails, it means artist_hint is being IGNORED.
        """
        # Search WITHOUT artist hint
        result_no_hint = manager.search(
            track_name="Hello",
            artist_hint=None,
            album_hint=None
        )

        # Search WITH artist hint for Adele
        result_with_adele_hint = manager.search(
            track_name="Hello",
            artist_hint="Adele",
            album_hint=None
        )

        # The artist hint should cause Adele to be prioritized
        # If artist_hint is ignored, both results will be the same
        assert result_with_adele_hint is not None, "Search should return a result"
        assert "adele" in result_with_adele_hint.lower(), \
            f"With artist_hint='Adele', should return Adele, got: {result_with_adele_hint}"

    def test_artist_hint_disambiguates_common_songs(self, manager):
        """
        Test that artist_hint helps disambiguate songs with common names.

        "Stay" is performed by many artists including Rihanna, The Kid LAROI, etc.
        With artist_hint="Rihanna", should return Rihanna's version.
        """
        result = manager.search(
            track_name="Stay",
            artist_hint="Rihanna",
            album_hint=None
        )

        assert result is not None, "Search should return a result"
        # Should contain Rihanna (might be "Rihanna feat. Mikky Ekko")
        assert "rihanna" in result.lower(), \
            f"With artist_hint='Rihanna', should return Rihanna, got: {result}"

    def test_artist_hint_for_pharrell_happy(self, manager):
        """
        Test "Happy" by Pharrell Williams.

        "Happy" is a common song name. With hint, should return Pharrell.
        """
        result = manager.search(
            track_name="Happy",
            artist_hint="Pharrell Williams",
            album_hint=None
        )

        assert result is not None, "Search should return a result"
        assert "pharrell" in result.lower(), \
            f"With artist_hint='Pharrell Williams', should return Pharrell, got: {result}"

    def test_artist_hint_for_cher_believe(self, manager):
        """
        Test "Believe" by Cher.

        "Believe" has versions by many artists. With hint, should return Cher.
        """
        result = manager.search(
            track_name="Believe",
            artist_hint="Cher",
            album_hint=None
        )

        assert result is not None, "Search should return a result"
        assert "cher" in result.lower(), \
            f"With artist_hint='Cher', should return Cher, got: {result}"

    def test_wrong_artist_hint_does_not_match(self, manager):
        """
        Test that a completely wrong artist hint doesn't corrupt results.

        When searching for "Amazing" from "808s & Heartbreak" but with
        artist_hint="NONEXISTENT_ARTIST_12345", it should still find
        the correct track based on album, but ideally not match the wrong artist.
        """
        result = manager.search(
            track_name="Amazing",
            artist_hint="NONEXISTENT_ARTIST_12345",
            album_hint="808s & Heartbreak"
        )

        # Should still find Kanye West based on album match
        # The nonexistent artist shouldn't break the search
        assert result is not None, "Search should return a result even with bad hint"
        # When album is specified, should still work
        assert "kanye" in result.lower(), \
            f"With album hint, should still find Kanye West, got: {result}"


class TestArtistHintWithAlbumHint:
    """Test that artist_hint works alongside album_hint."""

    @pytest.fixture
    def manager(self):
        """Get MusicBrainz manager instance."""
        data_dir = str(get_database_dir())
        mgr = MusicBrainzManagerV2Optimized(data_dir)
        if not mgr.is_ready():
            pytest.skip("MusicBrainz database not available")
        return mgr

    def test_both_hints_work_together(self, manager):
        """
        Test that both artist_hint and album_hint work together.

        Searching for "Amazing" with both artist_hint="Kanye West" and
        album_hint="808s & Heartbreak" should definitely return Kanye West.
        """
        result = manager.search(
            track_name="Amazing",
            artist_hint="Kanye West",
            album_hint="808s & Heartbreak"
        )

        assert result is not None, "Search should return a result"
        assert "kanye" in result.lower(), \
            f"With both hints, should return Kanye West, got: {result}"

    def test_artist_hint_priority_over_popularity(self, manager):
        """
        Test that artist_hint takes priority over general popularity scores.

        Even if another artist's version is more popular, the hint should
        prioritize the specified artist.
        """
        # Search for a common track with a specific artist hint
        result = manager.search(
            track_name="Closer",
            artist_hint="The Chainsmokers",
            album_hint=None
        )

        assert result is not None, "Search should return a result"
        assert "chainsmokers" in result.lower(), \
            f"With artist_hint='The Chainsmokers', should return The Chainsmokers, got: {result}"
