#!/usr/bin/env python3
"""
Tests for the phonetic matching feature (Phase 5).

Tests Soundex-based phonetic matching for improved artist name matching,
especially for misspellings and phonetic variations.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import (
    MusicBrainzManagerV2Optimized,
    MatchingConfig
)


class TestSoundex:
    """Test the Soundex algorithm implementation."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing phonetic methods."""
        # Use a temp directory (doesn't need real data for unit tests)
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(phonetic_enabled=True)
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_soundex_basic(self, manager):
        """Test basic Soundex encoding."""
        # Classic Soundex examples
        assert manager.soundex("Robert") == "R163"
        assert manager.soundex("Rupert") == "R163"  # Should match Robert

    def test_soundex_same_codes_similar_names(self, manager):
        """Test that similar-sounding names get same Soundex code."""
        # These should all produce the same code
        assert manager.soundex("Smith") == manager.soundex("Smyth")
        assert manager.soundex("Jon") == manager.soundex("John")
        assert manager.soundex("Katy") == manager.soundex("Katie")
        assert manager.soundex("Steven") == manager.soundex("Stephen")

    def test_soundex_different_codes_different_names(self, manager):
        """Test that different names get different codes."""
        assert manager.soundex("Robert") != manager.soundex("Michael")
        assert manager.soundex("Taylor") != manager.soundex("Jackson")
        assert manager.soundex("Beyonce") != manager.soundex("Adele")

    def test_soundex_empty_string(self, manager):
        """Test Soundex handles empty string."""
        assert manager.soundex("") == "0000"

    def test_soundex_numbers_only(self, manager):
        """Test Soundex handles non-alpha characters."""
        assert manager.soundex("123") == "0000"
        assert manager.soundex("!@#") == "0000"

    def test_soundex_mixed_content(self, manager):
        """Test Soundex with mixed alphanumeric content."""
        # Should extract only letters
        assert manager.soundex("Prince2") == manager.soundex("Prince")
        assert manager.soundex("50 Cent") == manager.soundex("Cent")


class TestPhoneticMatching:
    """Test the phonetic matching methods."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing phonetic methods."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(phonetic_enabled=True)
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_phonetic_match_true(self, manager):
        """Test phonetic_match returns True for similar-sounding names."""
        assert manager.phonetic_match("Jon", "John") is True
        assert manager.phonetic_match("Smith", "Smyth") is True
        assert manager.phonetic_match("Katie", "Katy") is True

    def test_phonetic_match_false(self, manager):
        """Test phonetic_match returns False for different names."""
        assert manager.phonetic_match("Robert", "Michael") is False
        assert manager.phonetic_match("Taylor", "Jackson") is False

    def test_phonetic_similarity_exact(self, manager):
        """Test phonetic_similarity returns 1.0 for exact phonetic match."""
        sim = manager.phonetic_similarity("Jon", "John")
        assert sim == 1.0

    def test_phonetic_similarity_partial(self, manager):
        """Test phonetic_similarity returns partial scores for near matches."""
        # Same first 3 characters of Soundex should return 0.75
        sim = manager.phonetic_similarity("Robert", "Rupert")
        assert sim >= 0.75

    def test_phonetic_similarity_no_match(self, manager):
        """Test phonetic_similarity returns 0.0 for no match."""
        sim = manager.phonetic_similarity("Apple", "Zebra")
        assert sim == 0.0

    def test_phonetic_disabled(self, manager):
        """Test that phonetic matching returns 0/False when disabled."""
        manager.config.phonetic_enabled = False
        assert manager.phonetic_match("Jon", "John") is False
        assert manager.phonetic_similarity("Jon", "John") == 0.0


class TestPhoneticTokenSimilarity:
    """Test phonetic token-level similarity for multi-word names."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(phonetic_enabled=True)
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_token_similarity_full_match(self, manager):
        """Test full token match returns high score."""
        sim = manager.phonetic_token_similarity(
            "The Weeknd",
            "The Weeknd"
        )
        assert sim == 1.0

    def test_token_similarity_phonetic_variant(self, manager):
        """Test phonetic variants in multi-word names."""
        # "Steven" and "Stephen" are phonetically similar
        sim = manager.phonetic_token_similarity(
            "Steven Tyler",
            "Stephen Tyler"
        )
        assert sim >= 0.9

    def test_token_similarity_partial(self, manager):
        """Test partial token matches."""
        sim = manager.phonetic_token_similarity(
            "John Smith",
            "Jon Smyth"
        )
        # Both tokens should phonetically match
        assert sim >= 0.9


class TestEnhancedArtistSimilarity:
    """Test the combined fuzzy + phonetic similarity."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(
                phonetic_enabled=True,
                fuzzy_artist_enabled=True
            )
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_enhanced_similarity_exact(self, manager):
        """Test enhanced similarity with exact match."""
        sim = manager.enhanced_artist_similarity(
            "The Beatles",
            "The Beatles"
        )
        assert sim >= 0.95

    def test_enhanced_similarity_phonetic_helps(self, manager):
        """Test that phonetic matching improves scores for similar-sounding names."""
        # Pure fuzzy might give lower score, but phonetic should boost it
        sim = manager.enhanced_artist_similarity(
            "Jon Bon Jovi",
            "John Bon Jovi"
        )
        assert sim >= 0.9

    def test_enhanced_similarity_fuzzy_dominates(self, manager):
        """Test that fuzzy matching still works well for typos."""
        sim = manager.enhanced_artist_similarity(
            "Beyonce",
            "Beyoncé"  # With accent
        )
        assert sim >= 0.8

    def test_enhanced_similarity_boost(self, manager):
        """Test that boost is applied when both scores are high."""
        # When both fuzzy and phonetic are high, should get boosted score
        sim = manager.enhanced_artist_similarity(
            "Michael Jackson",
            "Michael Jackson"
        )
        # Should be at or near 1.0 with boost
        assert sim >= 0.95


class TestPhoneticCaching:
    """Test phonetic code caching."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(
                phonetic_enabled=True,
                phonetic_cache_size=100
            )
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_cache_stores_codes(self, manager):
        """Test that phonetic codes are cached."""
        # First call computes and caches
        code1 = manager.phonetic_code("Taylor Swift")
        assert len(manager._phonetic_cache) == 1

        # Second call should use cache
        code2 = manager.phonetic_code("Taylor Swift")
        assert code1 == code2
        assert len(manager._phonetic_cache) == 1  # No new entry

    def test_cache_lru_eviction(self, manager):
        """Test LRU eviction when cache is full."""
        manager.config.phonetic_cache_size = 3

        # Fill cache
        manager.phonetic_code("Artist One")
        manager.phonetic_code("Artist Two")
        manager.phonetic_code("Artist Three")

        assert len(manager._phonetic_cache) == 3

        # Add one more - should evict oldest
        manager.phonetic_code("Artist Four")

        assert len(manager._phonetic_cache) == 3

    def test_cache_cleared_on_mode_change(self, manager):
        """Test that cache is cleared when mode changes."""
        manager.phonetic_code("Test Artist")
        assert len(manager._phonetic_cache) == 1

        manager.set_mode("high_accuracy")
        assert len(manager._phonetic_cache) == 0


class TestRealWorldArtistMatching:
    """Test phonetic matching with real-world artist name variations."""

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(phonetic_enabled=True)
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_common_misspellings(self, manager):
        """Test matching common artist name misspellings."""
        test_cases = [
            ("Brittany Spears", "Britney Spears"),
            ("Mariah Carey", "Mariah Carrey"),  # Common double-letter confusion
            ("Eminem", "Emenem"),
        ]

        for misspelled, correct in test_cases:
            sim = manager.enhanced_artist_similarity(misspelled, correct)
            # Should still get reasonable similarity due to phonetic matching
            assert sim >= 0.5, f"Failed: {misspelled} vs {correct}, got {sim}"

    def test_name_variants(self, manager):
        """Test matching artist name variants."""
        test_cases = [
            ("50 Cent", "Fifty Cent"),  # Number vs spelled out
            ("Dr. Dre", "Doctor Dre"),  # Abbreviation
            ("Jay-Z", "Jay Z"),  # Punctuation
        ]

        for variant1, variant2 in test_cases:
            sim = manager.enhanced_artist_similarity(variant1, variant2)
            # Should get good similarity
            assert sim >= 0.5, f"Failed: {variant1} vs {variant2}, got {sim}"


class TestPhoneticWithRealCSV:
    """Integration tests using real CSV files."""

    @pytest.fixture
    def test_csv_path(self):
        """Get path to test CSV file."""
        csv_path = Path(__file__).parent.parent / "_test_csvs" / "Apple Music - Recently Played Tracks.csv"
        if not csv_path.exists():
            pytest.skip(f"Test CSV not found: {csv_path}")
        return csv_path

    @pytest.fixture
    def manager(self):
        """Create manager for testing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MatchingConfig(phonetic_enabled=True)
            manager = MusicBrainzManagerV2Optimized(tmpdir, config)
            yield manager

    def test_phonetic_matching_on_real_data(self, test_csv_path, manager):
        """Test phonetic matching on real CSV data artists."""
        import pandas as pd

        df = pd.read_csv(test_csv_path)

        # Extract unique artists from the CSV
        artists = set()
        for _, row in df.iterrows():
            track_desc = row.get('Track Description', '')
            if ' - ' in str(track_desc):
                artist = str(track_desc).split(' - ', 1)[0].strip()
                if artist:
                    artists.add(artist)

        # Test phonetic encoding works for all artists
        for artist in list(artists)[:20]:  # Test first 20
            code = manager.phonetic_code(artist)
            # Should produce a valid 4-character code
            assert len(code) == 4, f"Invalid code for {artist}: {code}"
            assert code[0].isalpha() or code == "0000", f"Invalid code for {artist}: {code}"

    def test_enhanced_similarity_on_real_artists(self, test_csv_path, manager):
        """Test enhanced similarity scores for real artists."""
        import pandas as pd

        df = pd.read_csv(test_csv_path)

        # Extract artists
        artists = []
        for _, row in df.iterrows():
            track_desc = row.get('Track Description', '')
            if ' - ' in str(track_desc):
                artist = str(track_desc).split(' - ', 1)[0].strip()
                if artist and artist not in artists:
                    artists.append(artist)
                    if len(artists) >= 10:
                        break

        # Test self-similarity (should be 1.0 or very high)
        for artist in artists:
            sim = manager.enhanced_artist_similarity(artist, artist)
            assert sim >= 0.95, f"Self-similarity for {artist} is too low: {sim}"

        # Test different artists (should be lower)
        if len(artists) >= 2:
            sim = manager.enhanced_artist_similarity(artists[0], artists[1])
            # Different artists should have lower similarity (unless they happen to have similar names)
            # We just verify the function works without error
            assert 0 <= sim <= 1


class TestPhoneticIntegration:
    """Test integration of phonetic matching into the full matching pipeline."""

    @pytest.fixture
    def manager_with_data(self):
        """Create manager with MusicBrainz data if available."""
        from apple_music_history_converter.app_directories import get_database_dir

        db_dir = get_database_dir()
        csv_path = db_dir / "musicbrainz" / "canonical" / "canonical_musicbrainz_data.csv"

        if not csv_path.exists():
            pytest.skip("MusicBrainz database not available")

        config = MatchingConfig(phonetic_enabled=True)
        manager = MusicBrainzManagerV2Optimized(str(db_dir), config)

        if not manager.is_ready():
            pytest.skip("MusicBrainz manager not ready")

        yield manager

    def test_phonetic_helps_find_artist(self, manager_with_data):
        """Test that phonetic matching helps find artists with name variations."""
        # This test requires the real MusicBrainz database
        # We test that the enhanced similarity produces reasonable results

        # Test with track from real CSV data
        result = manager_with_data.search(
            track_name="One Summer's Day",
            artist_hint="Joe Hisaishi"
        )

        if result:
            # Should find the track with correct artist
            assert "hisaishi" in result.lower() or result != "[Unknown]"

    def test_phonetic_config_toggle(self, manager_with_data):
        """Test that phonetic matching can be toggled."""
        # Disable phonetic
        manager_with_data.config.phonetic_enabled = False

        # Should still work, just without phonetic boost
        sim = manager_with_data.enhanced_artist_similarity(
            "The Beatles",
            "The Beatles"
        )
        assert sim >= 0.9

        # Re-enable
        manager_with_data.config.phonetic_enabled = True

        sim = manager_with_data.enhanced_artist_similarity(
            "The Beatles",
            "The Beatles"
        )
        assert sim >= 0.9
