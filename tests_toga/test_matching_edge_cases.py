"""Tests for MusicBrainz matching algorithm edge cases.

Tests the enhanced matching algorithm including:
- Unicode and apostrophe normalization
- Short/generic title handling
- Common/high-frequency title handling
- Obscure artist handling
- Special character handling (A$AP Rocky style)
- Confidence margin behavior
"""

import pytest
from src.apple_music_history_converter.musicbrainz_manager_v2_optimized import (
    MusicBrainzManagerV2Optimized,
    MatchingConfig,
    CandidateResult,
    MatchResult,
    UNICODE_APOSTROPHE_MAP,
    UNICODE_QUOTE_MAP,
)


class TestUnicodeNormalization:
    """Test Unicode and apostrophe/quote handling."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance for testing normalization methods."""
        config = MatchingConfig()
        manager = MusicBrainzManagerV2Optimized(str(tmp_path), config)
        return manager

    def test_normalize_base_curly_apostrophe(self, manager):
        """Curly apostrophe should normalize to straight apostrophe."""
        text_with_curly = "Don\u2019t Stop Me Now"
        normalized = manager.normalize_base(text_with_curly)
        assert "'" in normalized
        assert "\u2019" not in normalized

    def test_normalize_base_left_single_quote(self, manager):
        """Left single quotation mark should normalize to straight apostrophe."""
        text = "\u2018quote\u2019"
        normalized = manager.normalize_base(text)
        assert normalized == "'quote'"

    def test_normalize_base_curly_double_quotes(self, manager):
        """Curly double quotes should normalize to straight quotes."""
        text = "\u201CQuoted\u201D"
        normalized = manager.normalize_base(text)
        assert normalized == '"quoted"'

    def test_normalize_base_whitespace_collapse(self, manager):
        """Multiple spaces should collapse to single space."""
        text = "Track   With    Spaces"
        normalized = manager.normalize_base(text)
        assert normalized == "track with spaces"

    def test_normalize_for_matching_dollar_sign(self, manager):
        """Dollar sign in word context should become 's'."""
        text = "A$AP Rocky"
        normalized = manager.normalize_for_matching(text)
        assert normalized == "asap rocky"

    def test_normalize_for_matching_dollar_sign_start(self, manager):
        """Dollar sign at start should not be normalized."""
        text = "$100 Bill"
        normalized = manager.normalize_for_matching(text)
        assert "$" in normalized  # Dollar at start is not converted

    def test_clean_text_conservative_preserves_unicode(self, manager):
        """Conservative cleaning should preserve unicode letters."""
        text = "Bjork - It's Oh So Quiet"
        cleaned = manager.clean_text_conservative(text)
        assert "bjork" in cleaned
        assert "its" in cleaned or "it s" in cleaned


class TestArtistTokenization:
    """Test artist credit tokenization and matching."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance for testing."""
        config = MatchingConfig()
        manager = MusicBrainzManagerV2Optimized(str(tmp_path), config)
        return manager

    def test_tokenize_simple_artist(self, manager):
        """Simple artist name should produce single token."""
        tokens = manager.tokenize_artist_credit("Rihanna")
        assert tokens == {"rihanna"}

    def test_tokenize_feat_artist(self, manager):
        """Featuring should split into tokens."""
        tokens = manager.tokenize_artist_credit("Rihanna feat. Calvin Harris")
        assert "rihanna" in tokens
        assert "calvin harris" in tokens

    def test_tokenize_ampersand_artist(self, manager):
        """Ampersand should split into tokens."""
        tokens = manager.tokenize_artist_credit("Hall & Oates")
        assert "hall" in tokens
        assert "oates" in tokens

    def test_tokenize_asap_style(self, manager):
        """A$AP style names should be normalized."""
        tokens = manager.tokenize_artist_credit("A$AP Rocky & Tyler, The Creator")
        assert "asap rocky" in tokens
        # Tyler, The Creator keeps the comma and "the" prefix is removed
        assert any("tyler" in t for t in tokens)

    def test_artist_tokens_match_exact(self, manager):
        """Exact artist match should return 'exact'."""
        match_type, token = manager.artist_tokens_match("Rihanna", "Rihanna feat. Calvin Harris")
        assert match_type == "exact"
        assert token == "rihanna"

    def test_artist_tokens_match_partial(self, manager):
        """Partial artist match should return 'partial'."""
        match_type, token = manager.artist_tokens_match("Calvin", "Rihanna feat. Calvin Harris")
        assert match_type == "partial"

    def test_artist_tokens_match_none(self, manager):
        """Non-matching artist should return None."""
        match_type, token = manager.artist_tokens_match("Drake", "Rihanna feat. Calvin Harris")
        assert match_type is None


class TestEdgeCaseDetection:
    """Test detection of short/generic/numeric titles."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance for testing."""
        config = MatchingConfig(min_effective_title_length=3)
        manager = MusicBrainzManagerV2Optimized(str(tmp_path), config)
        return manager

    def test_is_short_title_two_chars(self, manager):
        """Two character titles should be detected as short."""
        assert manager.is_short_title("Up") is True

    def test_is_short_title_three_chars(self, manager):
        """Three character titles should NOT be detected as short (at threshold)."""
        assert manager.is_short_title("Hey") is False

    def test_is_generic_title_intro(self, manager):
        """'Intro' should be detected as generic."""
        assert manager.is_generic_title("Intro") is True

    def test_is_generic_title_interlude(self, manager):
        """'Interlude' should be detected as generic."""
        assert manager.is_generic_title("Interlude") is True

    def test_is_generic_title_normal(self, manager):
        """Normal titles should not be detected as generic."""
        assert manager.is_generic_title("Blinding Lights") is False

    def test_is_numeric_title_pure_number(self, manager):
        """Pure number should be detected as numeric."""
        assert manager.is_numeric_title("17") is True

    def test_is_numeric_title_with_hash(self, manager):
        """Number with hash should be detected as numeric."""
        assert manager.is_numeric_title("#1") is True

    def test_is_numeric_title_mixed(self, manager):
        """Mixed alphanumeric should not be detected as numeric."""
        assert manager.is_numeric_title("Track 17") is False

    def test_is_ambiguous_short(self, manager):
        """Short titles should be ambiguous."""
        assert manager.is_ambiguous_title("Up") is True

    def test_is_ambiguous_generic(self, manager):
        """Generic titles should be ambiguous."""
        assert manager.is_ambiguous_title("Outro") is True

    def test_is_ambiguous_numeric(self, manager):
        """Numeric titles should be ambiguous."""
        assert manager.is_ambiguous_title("17") is True

    def test_is_ambiguous_normal(self, manager):
        """Normal titles should not be ambiguous."""
        assert manager.is_ambiguous_title("Blinding Lights") is False


class TestMatchingConfig:
    """Test configuration system."""

    def test_default_config_values(self):
        """Default config should have expected values."""
        config = MatchingConfig()
        assert config.hot_percentile == 0.15
        assert config.search_row_limit == 10
        assert config.min_confidence_margin == 500_000
        assert config.fuzzy_enabled is False
        assert config.mode == "normal"

    def test_custom_config_values(self):
        """Custom config values should be respected."""
        config = MatchingConfig(
            hot_percentile=0.20,
            min_confidence_margin=1_000_000,
            fuzzy_enabled=True,
            mode="high_accuracy"
        )
        assert config.hot_percentile == 0.20
        assert config.min_confidence_margin == 1_000_000
        assert config.fuzzy_enabled is True
        assert config.mode == "high_accuracy"

    def test_generic_titles_customizable(self):
        """Generic titles list should be customizable."""
        custom_generic = frozenset(["intro", "outro", "skit"])
        config = MatchingConfig(generic_titles=custom_generic)
        assert "intro" in config.generic_titles
        assert "interlude" not in config.generic_titles


class TestCandidateResult:
    """Test CandidateResult dataclass."""

    def test_candidate_result_creation(self):
        """CandidateResult should be creatable with all fields."""
        candidate = CandidateResult(
            artist_name="The Weeknd",
            release_name="After Hours",
            score=10_000_000,
            mb_score=100,
            artist_match="exact",
            album_match=True,
            confidence="high"
        )
        assert candidate.artist_name == "The Weeknd"
        assert candidate.score == 10_000_000
        assert candidate.confidence == "high"


class TestMatchResult:
    """Test MatchResult dataclass."""

    def test_match_result_creation(self):
        """MatchResult should be creatable with all fields."""
        result = MatchResult(
            artist_name="The Weeknd",
            confidence="high",
            margin=5_000_000,
            top_candidates=[],
            reason="Clear winner"
        )
        assert result.artist_name == "The Weeknd"
        assert result.confidence == "high"
        assert result.margin == 5_000_000

    def test_match_result_no_match(self):
        """MatchResult can represent no match."""
        result = MatchResult(
            artist_name=None,
            confidence="no_match",
            margin=0,
            top_candidates=[],
            reason="No candidates found"
        )
        assert result.artist_name is None
        assert result.confidence == "no_match"


class TestModeManagement:
    """Test accuracy/speed mode switching."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager instance for testing."""
        config = MatchingConfig()
        manager = MusicBrainzManagerV2Optimized(str(tmp_path), config)
        return manager

    def test_default_mode_is_normal(self, manager):
        """Default mode should be normal."""
        assert manager.config.mode == "normal"
        assert manager.config.fuzzy_enabled is False

    def test_set_mode_high_accuracy(self, manager):
        """Setting high_accuracy mode should enable fuzzy matching."""
        manager.set_mode("high_accuracy")
        assert manager.config.mode == "high_accuracy"
        assert manager.config.fuzzy_enabled is True
        assert manager.config.min_confidence_margin == 300_000

    def test_set_mode_normal(self, manager):
        """Setting normal mode should disable fuzzy matching."""
        manager.set_mode("high_accuracy")  # First enable
        manager.set_mode("normal")  # Then disable
        assert manager.config.mode == "normal"
        assert manager.config.fuzzy_enabled is False
        assert manager.config.min_confidence_margin == 500_000

    def test_set_mode_invalid_raises(self, manager):
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError):
            manager.set_mode("turbo")

    def test_set_mode_clears_cache(self, manager):
        """Setting mode should clear the search cache."""
        manager._search_cache["test"] = "value"
        manager._cache_hits = 100
        manager.set_mode("high_accuracy")
        assert len(manager._search_cache) == 0
        assert manager._cache_hits == 0


class TestUnicodeMappings:
    """Test that Unicode mappings are complete."""

    def test_apostrophe_map_has_common_variants(self):
        """Apostrophe map should include common Unicode variants."""
        assert '\u2018' in UNICODE_APOSTROPHE_MAP  # LEFT SINGLE QUOTATION MARK
        assert '\u2019' in UNICODE_APOSTROPHE_MAP  # RIGHT SINGLE QUOTATION MARK
        assert '\u02BC' in UNICODE_APOSTROPHE_MAP  # MODIFIER LETTER APOSTROPHE

    def test_quote_map_has_common_variants(self):
        """Quote map should include common Unicode variants."""
        assert '\u201C' in UNICODE_QUOTE_MAP  # LEFT DOUBLE QUOTATION MARK
        assert '\u201D' in UNICODE_QUOTE_MAP  # RIGHT DOUBLE QUOTATION MARK


class TestConfigurableThresholds:
    """Test that thresholds are configurable and work correctly."""

    def test_min_effective_title_length_affects_detection(self):
        """Changing min_effective_title_length should affect short title detection."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_path:
            # Default threshold of 3
            config1 = MatchingConfig(min_effective_title_length=3)
            manager1 = MusicBrainzManagerV2Optimized(tmp_path, config1)
            assert manager1.is_short_title("Hey") is False  # 3 chars = not short

            # Higher threshold of 5
            config2 = MatchingConfig(min_effective_title_length=5)
            manager2 = MusicBrainzManagerV2Optimized(tmp_path, config2)
            assert manager2.is_short_title("Hey") is True  # 3 chars < 5 = short
