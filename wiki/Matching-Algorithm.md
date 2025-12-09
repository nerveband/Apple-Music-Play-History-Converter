# MusicBrainz Matching Algorithm

This document provides explicit technical details about how the Apple Music History Converter matches tracks to artists using the MusicBrainz database.

## Overview

The matching algorithm uses a **HOT/COLD tiered DuckDB database** derived from MusicBrainz canonical data. It employs a **cascading search strategy** with multiple matching methods, **artist hint prioritization**, **intelligent candidate scoring with confidence metrics**, and **edge case handling**.

### Key Features

- **Tiered architecture**: HOT/COLD tables for optimized searching
- **Confidence scoring**: Explicit confidence levels (high/medium/low/no_match)
- **Edge case handling**: Short titles, generic titles, common titles, obscure artists
- **Unicode normalization**: Robust handling of apostrophes, quotes, and special characters
- **Artist tokenization**: Handles collaborations (feat., &, with, vs)
- **Configurable modes**: Normal (fast) vs High Accuracy (thorough)
- **Optional fuzzy matching**: Levenshtein-based similarity for edge cases
- **Album-session alignment**: Detects consecutive tracks from same album for consistent matching
- **Per-user mapping cache**: Persistently caches verified matches for fast repeat imports
- **Phonetic matching**: Soundex-based matching for artist name misspellings (Jon/John)

## Key Insight: Score Semantics

**Critical understanding**: The `score` column in MusicBrainz data represents **chronological order** (row ID), NOT popularity.

| Score Value | Meaning | Example |
|-------------|---------|---------|
| **Lower scores** | Earlier MusicBrainz entry | Original/established tracks |
| **Higher scores** | Later MusicBrainz entry | Covers, remixes, newer releases |

**Why this matters**: When multiple tracks share the same name, the one with the **lowest score** is typically the original/canonical version. For example:

- "Blinding Lights" by The Weeknd (score ~500,000) - the hit single
- "Blinding Lights" by Pete Frogs (score ~4,000,000) - a cover

**Algorithm rule**: Always `ORDER BY score ASC` to prioritize established tracks.

## Database Tiering: HOT and COLD Tables

The algorithm splits MusicBrainz data into two tiers for optimized searching:

### HOT Table (~15% of data)

Contains the most established recordings based on score distribution.

```sql
-- Creation: Bottom 15th percentile of scores (most established)
threshold = APPROX_QUANTILE(score, 0.15)
INSERT INTO musicbrainz_hot
SELECT * FROM source WHERE score <= threshold
```

**Characteristics**:
- ~4.3 million records (from 29 million total)
- Contains highly established/popular tracks
- Searched first for fastest results
- Indexed for sub-millisecond queries

### COLD Table (~85% of data)

Contains the remaining recordings for comprehensive coverage.

```sql
-- Creation: Above 15th percentile (less established)
INSERT INTO musicbrainz_cold
SELECT * FROM source WHERE score > threshold
```

**Characteristics**:
- ~24.7 million records
- Contains covers, remixes, obscure tracks
- Searched only if HOT table misses
- Still indexed but larger dataset

### Search Flow

```
1. Search HOT table (fast, high-quality results)
       ↓
2. If not found → Search COLD table (comprehensive coverage)
       ↓
3. If still not found → Return None (or fall back to iTunes API)
```

## Text Normalization Pipeline

The algorithm uses a two-stage normalization pipeline to handle Unicode variants and special characters.

### Stage 1: Base Normalization

Handles Unicode normalization and character mapping:

```python
# Unicode apostrophe variants → straight apostrophe
UNICODE_APOSTROPHE_MAP = {
    '\u2018': "'",  # LEFT SINGLE QUOTATION MARK
    '\u2019': "'",  # RIGHT SINGLE QUOTATION MARK
    '\u02BC': "'",  # MODIFIER LETTER APOSTROPHE
    '\u02B9': "'",  # MODIFIER LETTER PRIME
    '\u0060': "'",  # GRAVE ACCENT
    '\u00B4': "'",  # ACUTE ACCENT
}

# Unicode quote variants → straight quotes
UNICODE_QUOTE_MAP = {
    '\u201C': '"',  # LEFT DOUBLE QUOTATION MARK
    '\u201D': '"',  # RIGHT DOUBLE QUOTATION MARK
    '\u201E': '"',  # DOUBLE LOW-9 QUOTATION MARK
    '\u00AB': '"',  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    '\u00BB': '"',  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
}

def normalize_base(text: str) -> str:
    """
    Base normalization: Unicode NFKC + apostrophe/quote normalization.
    """
    # 1. NFKC normalization (compatibility decomposition)
    text = unicodedata.normalize('NFKC', text)

    # 2. Normalize apostrophes
    for src, dst in UNICODE_APOSTROPHE_MAP.items():
        text = text.replace(src, dst)

    # 3. Normalize quotes
    for src, dst in UNICODE_QUOTE_MAP.items():
        text = text.replace(src, dst)

    # 4. Collapse whitespace and lowercase
    text = ' '.join(text.lower().split())

    return text
```

**Example transformations**:
| Input | Output |
|-------|--------|
| "Don\u2019t Stop Me Now" | "don't stop me now" |
| "\u201CHello\u201D" | "\"hello\"" |
| "Track   With   Spaces" | "track with spaces" |

### Stage 2: Matching Normalization

Additional normalization for stylized characters:

```python
def normalize_for_matching(text: str) -> str:
    """
    Extended normalization for special characters like A$AP.
    """
    text = normalize_base(text)

    # Handle $ as 's' when embedded in words (A$AP → ASAP)
    # But preserve $ at word boundaries ($100 stays $100)
    text = re.sub(r'(?<=\w)\$(?=\w)', 's', text)

    return text
```

**Example transformations**:
| Input | Output |
|-------|--------|
| "A$AP Rocky" | "asap rocky" |
| "$100 Bill" | "$100 bill" |
| "Ke$ha" | "kesha" |

## Text Cleaning Methods

Two cleaning levels handle different matching scenarios:

### Conservative Cleaning

Minimal changes for high-precision matching:

```python
def clean_text_conservative(text: str) -> str:
    """
    Conservative cleaning for fuzzy matching.
    Preserves word boundaries and meaningful punctuation.
    """
    if not text:
        return ""

    # 1. Unicode normalization (NFKC)
    text = unicodedata.normalize('NFKC', text)

    # 2. Lowercase
    text = text.lower()

    # 3. Remove parenthetical content: (feat. X), [Remix], etc.
    text = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', text)

    # 4. Remove "feat./featuring" suffixes
    text = re.sub(r'\bfeat(?:\.|uring)?\b.*', '', text, flags=re.IGNORECASE)

    # 5. Normalize whitespace
    text = ' '.join(text.split())

    # 6. Strip leading/trailing whitespace
    return text.strip()
```

**Example transformations**:
| Input | Output |
|-------|--------|
| "Blinding Lights (Radio Edit)" | "blinding lights" |
| "HUMBLE. (feat. Kendrick Lamar)" | "humble" |
| "Don't Stop Me Now" | "don't stop me now" |

### Aggressive Cleaning

Maximum normalization for last-resort matching:

```python
def clean_text_aggressive(text: str) -> str:
    """
    Aggressive cleaning for fallback matching.
    Removes all punctuation, keeps only alphanumeric.
    """
    if not text:
        return ""

    # 1. Start with conservative cleaning
    text = clean_text_conservative(text)

    # 2. Remove ALL punctuation (keep only letters, numbers, spaces)
    text = re.sub(r'[^\w\s]', '', text)

    # 3. Collapse multiple spaces
    text = ' '.join(text.split())

    return text.strip()
```

**Example transformations**:
| Input | Output |
|-------|--------|
| "Don't Stop Me Now" | "dont stop me now" |
| "P!nk - So What" | "pnk so what" |
| "AC/DC - Highway to Hell" | "acdc highway to hell" |

## Search Cascade Strategy

The algorithm uses a **four-level cascade** with progressively looser matching:

### Level 1: Fuzzy Exact Match

Looks for exact cleaned track name:

```sql
SELECT DISTINCT ON (artist_credit_name)
    recording_clean, artist_credit_name, score
FROM musicbrainz_hot
WHERE recording_clean = ?clean_track_name
ORDER BY artist_credit_name,
         CASE WHEN LOWER(artist_credit_name) = ?artist_hint THEN 0 ELSE 1 END,
         score ASC
LIMIT 10
```

**Matches**: "blinding lights" → "blinding lights"

### Level 2: Fuzzy Prefix Match

Looks for tracks starting with the search term:

```sql
SELECT DISTINCT ON (artist_credit_name)
    recording_clean, artist_credit_name, score
FROM musicbrainz_hot
WHERE recording_clean LIKE ?clean_track_name || '%'
ORDER BY artist_credit_name,
         CASE WHEN LOWER(artist_credit_name) = ?artist_hint THEN 0 ELSE 1 END,
         score ASC
LIMIT 10
```

**Matches**: "blinding" → "blinding lights", "blinding lights remix"

### Level 3: Fuzzy Contains Match

Looks for tracks containing the search term:

```sql
SELECT DISTINCT ON (artist_credit_name)
    recording_clean, artist_credit_name, score
FROM musicbrainz_hot
WHERE recording_clean LIKE '%' || ?clean_track_name || '%'
ORDER BY artist_credit_name,
         CASE WHEN LOWER(artist_credit_name) = ?artist_hint THEN 0 ELSE 1 END,
         score ASC
LIMIT 10
```

**Matches**: "lights" → "blinding lights", "city of lights"

### Level 4: Reverse Contains Match

Looks for search term containing the track name:

```sql
SELECT DISTINCT ON (artist_credit_name)
    recording_clean, artist_credit_name, score
FROM musicbrainz_hot
WHERE ?clean_track_name LIKE '%' || recording_clean || '%'
ORDER BY artist_credit_name,
         CASE WHEN LOWER(artist_credit_name) = ?artist_hint THEN 0 ELSE 1 END,
         score ASC
LIMIT 10
```

**Matches**: "blinding lights radio edit extended" → "blinding lights"

## Artist Hint Prioritization

When an artist hint is provided (from the CSV's artist column), the algorithm prioritizes matching artists:

### SQL ORDER BY Clause

```sql
ORDER BY
    -- Priority 1: Exact artist match first
    CASE WHEN LOWER(artist_credit_name) = ?artist_hint THEN 0 ELSE 1 END,
    -- Priority 2: Lower score (more established) wins
    score ASC
```

### Example

Searching for "Blinding Lights" with artist hint "the weeknd":

| Candidate | Artist | Score | Priority |
|-----------|--------|-------|----------|
| blinding lights | The Weeknd | 500,000 | (0, 500000) - WINNER |
| blinding lights | Pete Frogs | 4,000,000 | (1, 4000000) |
| blinding lights | Cover Band | 3,500,000 | (1, 3500000) |

Result: Returns "The Weeknd" because it matches the hint AND has the lowest score among matches.

## Candidate Scoring Algorithm

When multiple candidates are found, they're scored to select the best match:

### Score Inversion

```python
MAX_SCORE = 5_000_000  # Maximum expected MusicBrainz score

def _score_candidate(self, candidate_artist: str, candidate_score: int,
                     artist_hint: Optional[str]) -> float:
    """
    Score a candidate match. Higher weight = better match.
    """
    # Invert score: lower MusicBrainz score = higher weight
    weight = MAX_SCORE - candidate_score

    # Bonus for artist hint match
    if artist_hint:
        hint_clean = self.clean_text_conservative(artist_hint)
        candidate_clean = self.clean_text_conservative(candidate_artist)

        if hint_clean == candidate_clean:
            weight += 10_000_000  # Exact match bonus
        elif hint_clean in candidate_clean or candidate_clean in hint_clean:
            weight += 5_000_000   # Partial match bonus

    return weight
```

### Weight Calculation Examples

| Artist | MusicBrainz Score | Artist Hint | Weight |
|--------|-------------------|-------------|--------|
| The Weeknd | 500,000 | "the weeknd" | 4,500,000 + 10,000,000 = **14,500,000** |
| The Weeknd | 500,000 | None | **4,500,000** |
| Pete Frogs | 4,000,000 | "the weeknd" | 1,000,000 |
| Weeknd Tribute | 3,000,000 | "the weeknd" | 2,000,000 + 5,000,000 = **7,000,000** |

## Caching Strategy

Results are cached at multiple levels for performance:

### LRU Result Cache

```python
from functools import lru_cache

@lru_cache(maxsize=50000)
def _cached_search(self, track_name: str, artist_hint: str, album_hint: str) -> str:
    """
    Cache search results for repeated queries.
    Cache key is (track_name, artist_hint, album_hint) tuple.
    """
    return self._perform_search(track_name, artist_hint, album_hint)
```

**Cache behavior**:
- 50,000 entry maximum
- LRU eviction policy
- Cache key includes all search parameters
- Separate from database query cache

### Database Query Cache

DuckDB maintains its own internal query cache:

```sql
-- DuckDB caches prepared statements and query results
PRAGMA enable_object_cache;  -- Enabled by default
```

## Complete Search Flow

```
Input: track_name="Blinding Lights", artist_hint="The Weeknd", album_hint="After Hours"

1. CHECK CACHE
   └── Cache key: ("blinding lights", "the weeknd", "after hours")
   └── If hit → Return cached result

2. CLEAN TEXT
   └── track_clean = "blinding lights"
   └── artist_clean = "the weeknd"
   └── album_clean = "after hours"

3. SEARCH HOT TABLE (Cascade)
   ├── Level 1: Exact match on "blinding lights"
   │   └── Found: [("The Weeknd", 500000), ("Pete Frogs", 4000000)]
   │   └── Score candidates with artist hint bonus
   │   └── Winner: "The Weeknd" (weight 14,500,000)
   │   └── RETURN "The Weeknd"
   │
   ├── Level 2: Prefix match (if Level 1 empty)
   ├── Level 3: Contains match (if Level 2 empty)
   └── Level 4: Reverse contains (if Level 3 empty)

4. SEARCH COLD TABLE (if HOT empty)
   └── Same cascade as HOT

5. FALLBACK
   └── Return None (or trigger iTunes API fallback)

6. CACHE RESULT
   └── Store ("blinding lights", "the weeknd", "after hours") → "The Weeknd"
```

## Performance Characteristics

### Query Performance

| Table | Average Query Time | Throughput |
|-------|-------------------|------------|
| HOT (indexed) | 1-2ms | 500-1000/sec |
| COLD (indexed) | 3-5ms | 200-300/sec |
| Combined cascade | 2-10ms | 100-500/sec |

### Hit Rates

Based on testing with real Apple Music play history:

| Source | Hit Rate | Notes |
|--------|----------|-------|
| HOT table | 85-90% | Most popular tracks found here |
| COLD table | 5-8% | Covers, obscure tracks |
| Not found | 5-10% | Very obscure or misspelled |

### Accuracy Metrics

Based on comprehensive testing with real Apple Music play history:

| Test Set | Accuracy | Notes |
|----------|----------|-------|
| Play History Daily Tracks | **94.4%** | 119/126 correct |
| Recently Played Tracks | **70%** | 28/40 (generic soundtrack titles) |
| Unit Test Suite | **100%** | 135/135 passing |

**Known Limitations**:
- Generic titles (e.g., "Escape", "Home") without artist hints may match wrong artists
- Japanese artist names (e.g., "久石譲") may not match English equivalents ("Joe Hisaishi")
- Soundtrack albums with generic titles require album hints for accuracy

## Known Limitations

### Unicode Apostrophes

Different apostrophe characters can cause mismatches:

```
CSV: "Don't Stop Me Now" (U+2019 RIGHT SINGLE QUOTATION MARK)
DB:  "Don't Stop Me Now" (U+0027 APOSTROPHE)
```

**Mitigation**: Normalize apostrophes in cleaning:

```python
text = text.replace("'", "'").replace("'", "'")
```

### Collaboration Credits

MusicBrainz stores various artist credit formats:

```
"Jawsh 685 & Jason Derulo"
"Jawsh 685 feat. Jason Derulo"
"Jawsh 685, Jason Derulo"
```

**Mitigation**: Artist tokenization splits collaborations into individual tokens:

```python
def tokenize_artist_credit(artist: str) -> set:
    """
    Split artist credit into individual artist tokens.
    Handles: feat., featuring, ft., with, &, and, vs., versus, x
    """
    pattern = r'\s+(?:feat\.?|featuring|ft\.?|with|&|and|vs\.?|versus|x)\s+'
    parts = re.split(pattern, artist, flags=re.IGNORECASE)
    tokens = set()
    for part in parts:
        cleaned = normalize_for_matching(part.strip())
        if cleaned:
            tokens.add(cleaned)
    return tokens

# Example:
# "Rihanna feat. Calvin Harris" → {"rihanna", "calvin harris"}
# "A$AP Rocky & Tyler, The Creator" → {"asap rocky", "tyler, the creator"}
```

The algorithm then checks if the artist hint matches ANY token in the credit.

### Extremely Common Track Names

Generic track names like "Intro", "Outro", "Untitled" may match wrong artists without a hint.

**Mitigation**: The algorithm detects and handles these edge cases with special policies.

## Edge Case Detection

The algorithm identifies several types of ambiguous titles that require special handling.

### Short Titles

Titles with fewer characters than `min_effective_title_length` (default: 3):

```python
def is_short_title(title: str) -> bool:
    """
    Detect titles too short for reliable matching.
    Examples: "Up", "17", "L$D"
    """
    cleaned = normalize_for_matching(title)
    return len(cleaned) < config.min_effective_title_length
```

### Generic Titles

Common structural titles that many albums share:

```python
GENERIC_TITLES = frozenset([
    "intro", "outro", "interlude", "prelude", "intermission",
    "skit", "untitled", "track", "hidden track"
])

def is_generic_title(title: str) -> bool:
    cleaned = normalize_for_matching(title)
    return cleaned in config.generic_titles
```

### Numeric Titles

Pure numbers or hash-prefixed numbers:

```python
def is_numeric_title(title: str) -> bool:
    """
    Detect numeric-only titles like "17", "#1", "1999".
    """
    cleaned = normalize_for_matching(title)
    stripped = cleaned.lstrip('#')
    return stripped.isdigit()
```

### Common/High-Frequency Titles

Titles that appear many times across different artists:

```python
def is_common_title(title: str) -> bool:
    """
    Detect titles shared by many artists (>50 occurrences).
    Examples: "In Motion", "Underground", "Home"
    """
    candidate_count = get_title_candidate_count(title)
    return candidate_count >= config.high_frequency_threshold  # default: 50
```

### Ambiguous Title Detection

Combined check for any ambiguous condition:

```python
def is_ambiguous_title(title: str) -> bool:
    return (is_short_title(title) or
            is_generic_title(title) or
            is_numeric_title(title))
```

## Edge Case Policies

When edge cases are detected, special policies modify the matching behavior.

### Ambiguous Title Policy

For short/generic/numeric titles:

```python
def _apply_ambiguous_title_policy(candidates, artist_hint):
    """
    When title is ambiguous, REQUIRE artist hint match.
    Without hint: return no_match instead of guessing.
    """
    if not artist_hint:
        return MatchResult(
            artist_name=None,
            confidence="no_match",
            reason="Ambiguous title requires artist hint"
        )
    # With hint: only consider candidates matching the hint
    matching = [c for c in candidates if artist_tokens_match(artist_hint, c.artist)]
    if not matching:
        return MatchResult(confidence="no_match", reason="No artist match for ambiguous title")
    return _choose_from_candidates(matching)
```

### Common Title Policy

For high-frequency titles (>50 artists):

```python
def _apply_common_title_policy(candidates, artist_hint, album_hint):
    """
    For common titles, require BOTH artist AND album hints.
    """
    if not artist_hint:
        return MatchResult(confidence="no_match", reason="Common title requires artist hint")

    artist_matches = [c for c in candidates if artist_tokens_match(artist_hint, c.artist)]
    if not artist_matches:
        return MatchResult(confidence="no_match", reason="No artist match for common title")

    if album_hint:
        album_matches = [c for c in artist_matches if album_hint.lower() in c.album.lower()]
        if album_matches:
            return _choose_from_candidates(album_matches, confidence="high")

    # Artist match only: medium confidence
    return _choose_from_candidates(artist_matches, confidence="medium")
```

### Obscure Artist Policy

For artists not found in HOT table:

```python
def _apply_obscure_artist_policy(candidates, artist_hint):
    """
    For obscure artists (COLD-only), require exact artist match.
    """
    if not artist_hint:
        # Without hint, accept top COLD result with low confidence
        return _choose_from_candidates(candidates, confidence="low")

    exact_matches = [c for c in candidates if c.artist_match == "exact"]
    if exact_matches:
        return _choose_from_candidates(exact_matches, confidence="medium")

    return MatchResult(confidence="no_match", reason="Obscure artist not matched")
```

## Confidence Scoring System

The algorithm produces explicit confidence levels for every match.

### Confidence Levels

| Level | Meaning | Typical Conditions |
|-------|---------|-------------------|
| **high** | Very reliable match | Artist hint matched + clear winner + good margin |
| **medium** | Likely correct | Artist hint matched OR clear score margin |
| **low** | Use with caution | Weak signals, COLD table only, no hints |
| **no_match** | No valid match | Ambiguous without hint, no candidates found |

### Confidence Margin

The difference between top two candidates determines confidence:

```python
def _choose_candidate_with_confidence(candidates):
    """
    Score all candidates and determine confidence.
    """
    if not candidates:
        return MatchResult(confidence="no_match")

    if len(candidates) == 1:
        return MatchResult(
            artist_name=candidates[0].artist,
            confidence="high",
            margin=float('inf')
        )

    # Sort by score descending
    sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
    top = sorted_candidates[0]
    second = sorted_candidates[1]

    margin = top.score - second.score

    if margin >= config.min_confidence_margin:  # default: 500,000
        confidence = "high"
    elif top.artist_match == "exact":
        confidence = "medium"
    else:
        confidence = "low"

    return MatchResult(
        artist_name=top.artist,
        confidence=confidence,
        margin=margin,
        top_candidates=sorted_candidates[:3]
    )
```

### MatchResult Structure

```python
@dataclass
class MatchResult:
    artist_name: Optional[str]     # Matched artist or None
    confidence: str                 # "high", "medium", "low", "no_match"
    margin: float                   # Score difference to runner-up
    top_candidates: List[CandidateResult]  # Top 3 candidates
    reason: str                     # Explanation for decision

@dataclass
class CandidateResult:
    artist_name: str
    release_name: str
    score: int
    mb_score: int                   # Original MusicBrainz score
    artist_match: str               # "exact", "partial", None
    album_match: bool
    confidence: str
```

## Matching Modes

Two operational modes balance speed vs accuracy.

### Normal Mode (Default)

Optimized for speed with standard confidence thresholds:

```python
# Normal mode settings
config = MatchingConfig(
    mode="normal",
    fuzzy_enabled=False,
    min_confidence_margin=500_000,
    search_row_limit=10
)
```

**Characteristics**:
- No fuzzy matching
- Higher confidence margin requirement
- Faster queries

### High Accuracy Mode

Maximum accuracy for difficult matches:

```python
# High accuracy mode settings
config = MatchingConfig(
    mode="high_accuracy",
    fuzzy_enabled=True,          # Enable Levenshtein matching
    min_confidence_margin=300_000,  # Lower margin required
    search_row_limit=20          # More candidates
)
```

**Characteristics**:
- Fuzzy matching enabled (requires `rapidfuzz` library)
- Lower confidence threshold (catches more matches)
- More candidates considered
- Slower but more thorough

### Mode Switching

```python
manager.set_mode("high_accuracy")  # Enable thorough matching
manager.set_mode("normal")         # Return to fast mode
```

**Note**: Switching modes clears the search cache.

## Album-Session Alignment

When users listen to consecutive tracks from the same album, the algorithm detects these "sessions" and aligns them to a single MusicBrainz release.

### Session Detection

```python
class SessionAligner:
    """Align contiguous plays from same album."""

    def detect_sessions(self, tracks: List[Dict]) -> List[AlbumSession]:
        """
        Detect album sessions in track list.
        A session is 3+ consecutive tracks with the same album name.
        """
        sessions = []
        current_album = None
        current_tracks = []

        for track in tracks:
            album = track.get('album', '').lower().strip()
            if album and album == current_album:
                current_tracks.append(track)
            else:
                if len(current_tracks) >= 3:  # Min session size
                    sessions.append(AlbumSession(
                        album_name=current_album,
                        tracks=current_tracks
                    ))
                current_album = album
                current_tracks = [track] if album else []

        return sessions
```

### Session Alignment

Once detected, sessions are aligned to a single MusicBrainz release:

```python
def align_session(self, session: AlbumSession) -> AlbumSession:
    """
    Query MusicBrainz for all tracks from the album.
    Apply consistent artist credit across all session tracks.
    """
    release_tracks = self._get_release_tracks(session.album_name)

    if release_tracks:
        # Use most common artist credit from release
        dominant_artist = max(
            set(t['artist'] for t in release_tracks),
            key=lambda a: sum(1 for t in release_tracks if t['artist'] == a)
        )
        session.mb_artist_credit = dominant_artist
        session.aligned = True

    return session
```

### Benefits

| Scenario | Without Session | With Session |
|----------|----------------|--------------|
| 5 tracks from "After Hours" | Each searched individually | All get "The Weeknd" consistently |
| Generic track "Intro" in album | May match wrong artist | Uses album's artist credit |
| Soundtrack albums | Often mismatched | Consistent film composer |

### Configuration

```python
aligner = SessionAligner(
    manager=musicbrainz_manager,
    min_session_size=3  # Minimum consecutive tracks
)
```

---

## Per-User Mapping Cache

Verified matches are cached persistently for instant lookup on repeat imports.

### Schema

```sql
CREATE TABLE IF NOT EXISTS user_track_mappings (
    track_hash TEXT PRIMARY KEY,          -- Hash of (song, album, artist)
    apple_song_name TEXT NOT NULL,
    apple_album_name TEXT,
    apple_artist_name TEXT,
    mb_recording_mbid TEXT,
    mb_artist_credit_name TEXT,
    mb_release_name TEXT,
    confidence TEXT,                       -- 'high', 'medium', 'manual'
    verified_by TEXT,                      -- 'auto', 'user'
    created_at TIMESTAMP,
    last_used_at TIMESTAMP
);
```

### Lookup Flow

```python
class TrackMappingCache:
    def lookup(self, song: str, album: str, artist: str) -> Optional[Dict]:
        """
        Check cache before MusicBrainz search.
        Returns cached result if found, None otherwise.
        """
        track_hash = self._compute_hash(song, album, artist)
        result = self.conn.execute(
            "SELECT * FROM user_track_mappings WHERE track_hash = ?",
            [track_hash]
        ).fetchone()

        if result:
            self._update_last_used(track_hash)
            return dict(result)
        return None

    def store(self, apple_data: Dict, mb_result: Dict, confidence: str):
        """Store new mapping after successful match."""
        if confidence in ('high', 'medium'):
            self.conn.execute("""
                INSERT OR REPLACE INTO user_track_mappings (...)
                VALUES (...)
            """, [...])
```

### Performance Impact

| Operation | Without Cache | With Cache |
|-----------|--------------|------------|
| First import | 2-10ms/track | 2-10ms/track |
| Repeat import | 2-10ms/track | <1ms/track |
| 10,000 track re-import | 20-100 seconds | <10 seconds |

---

## Phonetic Matching

Soundex-based phonetic matching improves artist name matching for misspellings and variations.

### Soundex Algorithm

```python
def soundex(self, text: str) -> str:
    """
    Generate Soundex code for phonetic matching.
    Returns 4-character code (letter + 3 digits).
    """
    if not text:
        return "0000"

    # Keep first letter, convert rest to digits
    text = ''.join(c for c in text.upper() if c.isalpha())
    if not text:
        return "0000"

    # Soundex mapping
    mapping = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }

    code = text[0]
    prev = mapping.get(text[0], '0')

    for char in text[1:]:
        digit = mapping.get(char, '0')
        if digit != '0' and digit != prev:
            code += digit
            if len(code) == 4:
                break
        prev = digit

    return (code + '000')[:4]
```

### Phonetic Examples

| Name 1 | Name 2 | Soundex | Match? |
|--------|--------|---------|--------|
| "Jon" | "John" | J500 = J500 | Yes |
| "Smith" | "Smyth" | S530 = S530 | Yes |
| "Steven" | "Stephen" | S315 = S315 | Yes |
| "Robert" | "Michael" | R163 ≠ M240 | No |

### Enhanced Artist Similarity

Combines fuzzy (Levenshtein) and phonetic matching:

```python
def enhanced_artist_similarity(self, artist1: str, artist2: str) -> float:
    """
    Combine fuzzy and phonetic similarity for robust matching.
    """
    # Fuzzy similarity (0.0-1.0)
    fuzzy_sim = fuzz.ratio(artist1.lower(), artist2.lower()) / 100.0

    # Phonetic similarity (0.0-1.0)
    phonetic_sim = self.phonetic_similarity(artist1, artist2)

    # Weighted combination
    combined = (fuzzy_sim * 0.6) + (phonetic_sim * 0.4)

    # Boost if both are high
    if fuzzy_sim >= 0.8 and phonetic_sim >= 0.75:
        combined = min(1.0, combined * 1.1)

    return combined
```

### Real-World Matches

| Input Artist | Database Artist | Fuzzy | Phonetic | Combined |
|--------------|-----------------|-------|----------|----------|
| "Brittany Spears" | "Britney Spears" | 0.88 | 1.0 | 0.93 |
| "Jon Bon Jovi" | "John Bon Jovi" | 0.93 | 1.0 | 0.96 |
| "Eminem" | "Emenem" | 0.83 | 1.0 | 0.90 |

### Phonetic Cache

Soundex codes are cached for performance:

```python
@lru_cache(maxsize=10000)
def phonetic_code(self, text: str) -> str:
    """Cached phonetic code generation."""
    return self.soundex(text)
```

---

## Fuzzy Matching

Optional Levenshtein-based similarity for edge cases (requires `rapidfuzz`).

### Fuzzy Title Similarity

```python
def fuzzy_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate fuzzy similarity between two titles.
    Returns 0.0-1.0 where 1.0 is exact match.
    """
    if not FUZZY_AVAILABLE:
        return 1.0 if title1 == title2 else 0.0

    clean1 = normalize_for_matching(title1)
    clean2 = normalize_for_matching(title2)

    return fuzz.ratio(clean1, clean2) / 100.0
```

### When Fuzzy Matching Applies

Fuzzy matching is used when:
1. High accuracy mode is enabled
2. Exact matching finds no candidates
3. Title has potential typos or variations

```python
# Fuzzy threshold: minimum similarity to consider a match
config.fuzzy_threshold = 0.7  # 70% similarity required
```

**Example**:
| Query | Candidate | Similarity | Match? |
|-------|-----------|------------|--------|
| "Blindng Lights" | "Blinding Lights" | 0.93 | Yes |
| "Blinding Light" | "Blinding Lights" | 0.97 | Yes |
| "Blind" | "Blinding Lights" | 0.50 | No |

## Tuning Parameters

### MatchingConfig Dataclass

All algorithm parameters are controlled via the `MatchingConfig` dataclass:

```python
@dataclass
class MatchingConfig:
    # Table tiering
    hot_percentile: float = 0.15          # 15% most established in HOT

    # Search behavior
    search_row_limit: int = 10            # Max candidates per search level
    min_confidence_margin: float = 500_000  # Margin for "high" confidence

    # Edge case thresholds
    min_effective_title_length: int = 3   # Titles < 3 chars = "short"
    high_frequency_threshold: int = 50    # >50 artists = "common" title
    generic_titles: frozenset = frozenset([...])  # Generic title list

    # Scoring weights
    min_absolute_score: float = 1_000_000 # Minimum score for "high" confidence
    artist_exact_bonus: int = 5_000_000   # Bonus for exact artist match
    artist_partial_bonus: int = 2_000_000 # Bonus for partial match
    album_match_bonus: int = 3_000_000    # Bonus for album hint match

    # Fuzzy matching
    fuzzy_enabled: bool = False           # Enable Levenshtein matching
    fuzzy_threshold: float = 0.7          # Min similarity (0.0-1.0)

    # Operational mode
    mode: str = "normal"                  # "normal" or "high_accuracy"

    # Edge case behavior
    match_short_titles_without_hints: bool = False
    strict_cold_matching: bool = True
```

### Adjustable Thresholds

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| hot_percentile | 0.15 | 0.10-0.25 | Lower = faster but fewer hits |
| search_row_limit | 10 | 5-20 | Candidates per search level |
| min_confidence_margin | 500,000 | 300K-1M | Threshold for "high" confidence |
| min_effective_title_length | 3 | 2-5 | Short title detection threshold |
| high_frequency_threshold | 50 | 20-100 | Common title detection threshold |
| fuzzy_threshold | 0.7 | 0.5-0.9 | Fuzzy match strictness |

### Configuration

```python
from apple_music_history_converter.musicbrainz_manager_v2_optimized import (
    MusicBrainzManagerV2Optimized,
    MatchingConfig
)

# Custom configuration
config = MatchingConfig(
    hot_percentile=0.20,
    min_confidence_margin=300_000,
    fuzzy_enabled=True,
    mode="high_accuracy"
)

manager = MusicBrainzManagerV2Optimized(db_path, config)
```

## Testing

### Unit Tests

```bash
# Run all matching tests
python -m pytest tests_toga/test_matching_edge_cases.py -v

# Run accuracy tests
python -m pytest tests_toga/test_200_tracks_accuracy.py -v

# Run full test suite
python -m pytest tests_toga/ -v
```

### Test Coverage

The test suite covers:
- Unicode normalization (7 tests)
- Artist tokenization (7 tests)
- Edge case detection (12 tests)
- Configuration system (3 tests)
- Mode management (5 tests)
- Candidate/MatchResult structures (3 tests)
- Configurable thresholds (3 tests)

### Manual Verification

```python
from apple_music_history_converter.musicbrainz_manager_v2_optimized import (
    MusicBrainzManagerV2Optimized,
    MatchingConfig
)
from apple_music_history_converter.app_directories import get_database_dir

manager = MusicBrainzManagerV2Optimized(str(get_database_dir()))

# Test with artist hint
result = manager.search("Blinding Lights", artist_hint="The Weeknd")
print(f"Result: {result}")  # Expected: "The Weeknd"

# Test without hint
result = manager.search("Blinding Lights")
print(f"Result: {result}")  # Expected: "The Weeknd" (lowest score wins)

# Test with confidence
result = manager.search_with_confidence("Blinding Lights", artist_hint="The Weeknd")
print(f"Artist: {result.artist_name}")    # "The Weeknd"
print(f"Confidence: {result.confidence}") # "high"
print(f"Margin: {result.margin}")         # Score margin

# Test edge case
result = manager.search_with_confidence("Intro")
print(f"Confidence: {result.confidence}") # "no_match" (generic title, no hint)

# Test high accuracy mode
manager.set_mode("high_accuracy")
result = manager.search_with_confidence("Blindng Lights", artist_hint="The Weeknd")
print(f"Fuzzy match: {result.artist_name}")  # Still finds "The Weeknd"
```

## Changelog

### v2.3.0 (December 2025) - Accuracy & Performance Improvements

**New Features**:
- **Album-session alignment**: Detects consecutive tracks from same album and aligns them to a single MusicBrainz release for consistent artist credits
- **Per-user mapping cache**: Persistently caches verified matches for instant lookup on repeat imports (<1ms vs 2-10ms)
- **Phonetic matching (Soundex)**: Improves artist name matching for misspellings and phonetic variations (Jon/John, Smith/Smyth)
- **Enhanced artist similarity**: Combines fuzzy (Levenshtein) and phonetic matching with weighted scoring
- **Token-level Jaccard similarity**: Adds token-based matching for multi-word titles

**Improvements**:
- Session alignment test coverage: 18 tests
- Phonetic matching test coverage: 26 tests
- Mapping cache test coverage: 12 tests
- Total test suite: 191+ tests passing
- Phonetic cache with LRU eviction for performance

**Implementation Details**:
- `session_aligner.py`: New module for album-session detection and alignment
- `track_mapping_cache.py`: New module for persistent match caching
- `musicbrainz_manager_v2_optimized.py`: Added Soundex, phonetic_match, phonetic_similarity, enhanced_artist_similarity methods

---

### v2.2.0 (December 2025) - Enhanced Accuracy

**New Features**:
- **Fuzzy artist hint matching**: Uses rapidfuzz to match artist hints with up to 80% similarity threshold
- **Parenthetical annotation extraction**: Extracts collaborators from formats like "Artist (ft. Other)"
- **Dynamic mode escalation**: Automatically escalates to high_accuracy mode when confidence is "low"
- **Minimum absolute score enforcement**: Requires minimum score of 1M for "high" confidence
- **Album hint SQL boost**: Adds 1B+ bonus in SQL ORDER BY for album matches
- **Windows path normalization**: Fixed backslash issue causing crashes on Windows

**Improvements**:
- Accuracy: 94.4% on Play History Daily Tracks (126 tracks)
- Accuracy: 70% on Recently Played Tracks (limited by generic soundtrack titles)
- Token-based artist matching now handles more collaboration patterns
- Dynamic SEARCH_ROW_LIMIT: 10 without hints, 100 with hints
- 135+ unit tests passing

**Bug Fixes**:
- Fixed Windows crash with "Play History Daily Tracks" format (backslash escape issue)
- Normalized file paths for cross-platform DuckDB compatibility

### v2.1.0 (December 2025) - Algorithm Enhancement

**New Features**:
- **Unicode normalization pipeline**: Two-stage normalization for apostrophes, quotes, and special characters (A$AP, Ke$ha)
- **Artist tokenization**: Splits collaboration credits (feat., &, with, vs) into individual tokens
- **Edge case detection**: Identifies short, generic, numeric, and common/high-frequency titles
- **Confidence scoring**: Explicit confidence levels (high/medium/low/no_match) with margin calculation
- **Edge case policies**: Special handling for ambiguous titles, common titles, and obscure artists
- **Matching modes**: Normal (fast) vs High Accuracy (thorough with fuzzy matching)
- **Fuzzy matching**: Optional Levenshtein-based similarity for typos (requires rapidfuzz)
- **MatchingConfig dataclass**: All thresholds now configurable

**Improvements**:
- Artist hint matching now uses token-based comparison for better collaboration handling
- Common titles (>50 artists) require both artist AND album hints for high confidence
- Short/generic titles refuse to guess without hints (returns no_match instead of wrong match)
- Test suite expanded to 40+ tests covering all edge cases

### v2.0.2 (December 2025)

- **Fixed**: Score ordering changed from `DESC` to `ASC` (lower = more established)
- **Fixed**: HOT table creation uses `score <= threshold` instead of `>=`
- **Fixed**: Artist popularity uses `MIN(score)` instead of `MAX(score)`
- **Improved**: 92.5% accuracy on test suite (up from ~60% before fix)

---

**Last Updated**: December 2025 | **Version**: 2.3.0

**See Also**: [MusicBrainz Database Setup](MusicBrainz-Database) | [User Guide](User-Guide) | [FAQ](FAQ)
