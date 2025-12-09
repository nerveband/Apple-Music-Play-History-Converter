# MusicBrainz Matching Algorithm

This document describes how the Apple Music History Converter matches tracks to artists using the MusicBrainz database.

## Overview

The converter uses a local MusicBrainz database (~2GB) for offline, instant artist lookups. The matching algorithm operates in two modes based on available system resources:

| Mode | RAM Required | Database Size | Match Quality |
|------|--------------|---------------|---------------|
| **PERFORMANCE** | 8GB+ | ~2GB (optimized) | Best |
| **EFFICIENCY** | <8GB | ~2GB (simple) | Good + Fuzzy |

## How Mode Selection Works

The system automatically detects available RAM at startup:

```
RAM >= 8GB  -->  PERFORMANCE MODE (HOT/COLD tables, pre-cleaned data)
RAM < 8GB   -->  EFFICIENCY MODE (simple schema, runtime fuzzy matching)
```

---

## PERFORMANCE MODE (High-RAM Systems)

### Database Schema

Performance mode builds an optimized database with pre-computed columns:

```sql
-- HOT table: Top 2 million most popular tracks (by MusicBrainz score)
CREATE TABLE musicbrainz_hot (
    recording_clean VARCHAR,    -- Aggressively cleaned track name
    recording_lower VARCHAR,    -- Simple lowercase
    artist_credit_name VARCHAR,
    release_lower VARCHAR,      -- Album name lowercase
    score INTEGER               -- Popularity score (lower = more popular)
);

-- COLD table: Remaining 27 million tracks
CREATE TABLE musicbrainz_cold (...same schema...);
```

### Pre-Computed Cleaning (recording_clean)

The `recording_clean` column applies aggressive normalization at database build time:

1. **Unicode normalization** (NFKC) - Standardizes characters
2. **Remove parenthetical content** - `(feat. X)`, `(live)`, `(remix)`, `[deluxe]`
3. **Remove "feat." patterns** - `feat.`, `featuring`, `ft.`
4. **Lowercase** - Case-insensitive matching
5. **Remove punctuation** - Apostrophes, hyphens, etc.
6. **Collapse whitespace** - Multiple spaces become single space

**Example:**
```
Input:  "Don't Stop Me Now (2011 Remaster)"
Clean:  "dont stop me now"
```

### Search Strategy

```
Phase 1: Search HOT table (2M popular tracks)
    |
    v
Phase 2: Search COLD table for misses (27M tracks)
    |
    v
Done - ~95%+ match rate typical
```

### Why Performance Mode Has Better Matching

Because cleaning is pre-computed in the database:
- `"Bohemian Rhapsody (Muppets Version)"` matches `"bohemian rhapsody"` instantly
- No runtime fuzzy matching needed
- Both user input AND database are cleaned the same way
- Index lookups remain fast

---

## EFFICIENCY MODE (Low-RAM Systems)

### Database Schema

Efficiency mode uses a simpler schema to reduce memory:

```sql
CREATE TABLE musicbrainz (
    recording_lower VARCHAR,    -- Simple lowercase only
    artist_credit_name VARCHAR,
    release_lower VARCHAR,
    score INTEGER
);
```

### Runtime Cleaning

User track names receive only simple cleaning:
```python
track_clean = track.lower().strip()
```

### Three-Phase Search Strategy

```
Phase 1: Exact Match (with apostrophe variants)
    |
    +-- Search for: "i'm not okay (i promise)"
    +-- Also try:   "i'm not okay (i promise)" (curly apostrophe)
    |
    v
Phase 2: Album-Aware Matching
    |
    +-- If multiple artists have same track, prefer album match
    +-- Example: "Yesterday" + album "Help!" --> The Beatles (not any cover)
    |
    v
Phase 3: Fuzzy Matching (for unmatched tracks)
    |
    +-- Strip parenthetical content: "(feat. X)", "(live)", "(remix)"
    +-- Strip "feat." without parentheses
    +-- Retry search with stripped version
    |
    v
Done - ~85%+ match rate typical
```

### Fuzzy Matching Examples

| Original Track | Stripped | Result |
|----------------|----------|--------|
| `cemetery drive (8-bit computer game version)` | `cemetery drive` | My Chemical Romance |
| `1 train (feat. kendrick lamar, joey bada$$...)` | `1 train` | A$AP Rocky |
| `bohemian rhapsody (muppets version)` | `bohemian rhapsody` | Queen |
| `crawlspace messiah (feat. vomit forth)` | `crawlspace messiah` | PSYCHO-FRAME |

---

## Algorithm Limitations

### Unmatchable Track Categories

Even with fuzzy matching, some tracks cannot be matched:

#### 1. Non-Latin Text
```
ektenia ii: blagoslovenie (Russian)
(Japanese kanji tracks)
```
MusicBrainz may have different romanization or script.

#### 2. Typos in Source Data
```
"nazi punks fuckk off"  (extra 'k')
"fools are attacted"    (attacted vs attracted)
```
No algorithm can fix spelling errors without expensive fuzzy string matching.

#### 3. Garbage/Corrupted Data
```
"2xsm4xsa4xsmadkc4xs31xsoo1xsl"
"2xsxdccol2xsx3xsxc1xsdd6xsok303"
```
Corrupted track names from sync errors or encoding issues.

#### 4. Obscure/Independent Releases
```
"we are sex bob-omb"     (Scott Pilgrim soundtrack)
"goblins blade"          (very small artist)
```
Not every release is in MusicBrainz.

#### 5. Medleys/Mashups
```
"day tripper / if i needed someone / i want you"
```
Combined tracks that don't exist as single entries.

#### 6. Classical Music Formatting
```
"seasons (summer): iii. presto"
"symphony no. 5 in c minor, op. 67: i. allegro con brio"
```
Classical naming conventions vary wildly between sources.

#### 7. Unconventional Punctuation
```
"sit down. stand up"     (period in middle)
"eve white/eve black"    (slash separator)
"i'm but a wave to ..."  (trailing ellipsis)
```

#### 8. User-Uploaded Content
Some Apple Music tracks are user uploads that were never commercially released.

### Match Rate Expectations

| Scenario | Expected Match Rate |
|----------|---------------------|
| Performance Mode, mainstream music | 95-99% |
| Performance Mode, indie/obscure | 85-95% |
| Efficiency Mode, mainstream music | 90-95% |
| Efficiency Mode, indie/obscure | 75-90% |
| Previously unmatched "hard cases" | 30-50% |

---

## Performance Characteristics

### Speed Comparison

| Operation | Performance Mode | Efficiency Mode |
|-----------|------------------|-----------------|
| Single track lookup | ~1-2ms | ~2-5ms |
| Batch lookup (5000 tracks) | ~50-100ms | ~100-200ms |
| 100,000 row CSV | ~30-60 seconds | ~60-120 seconds |
| 250,000 row CSV | ~2-3 minutes | ~3-5 minutes |

### Memory Usage

| Mode | Database Memory | Peak Processing |
|------|-----------------|-----------------|
| Performance | ~1.5-2GB | ~2-3GB total |
| Efficiency | ~500MB-1GB | ~1-2GB total |

---

## Apostrophe Handling

A common matching issue is apostrophe character variants:

| Character | Name | Unicode | Common In |
|-----------|------|---------|-----------|
| `'` | Straight apostrophe | U+0027 | Apple Music exports |
| `'` | Right single quote | U+2019 | MusicBrainz data |

The algorithm searches for BOTH variants automatically:
```python
# User has: "i'm not okay"
# DB has:   "i'm not okay" (curly apostrophe)
# Algorithm searches for both --> Match found!
```

---

## Album-Aware Matching

When a track name matches multiple artists, the algorithm uses album information:

```
Track: "Yesterday"
Album: "Help!"

Candidates in DB:
  - "Yesterday" by The Beatles (album: "Help!")      <-- MATCH (album matches)
  - "Yesterday" by En Vogue (album: "Funky Divas")
  - "Yesterday" by Boyz II Men (album: "II")
```

This prevents incorrect matches for common song titles.

---

## iTunes API Fallback

For tracks that fail MusicBrainz matching, the iTunes API can be used as a fallback.

### iTunes API vs MusicBrainz Comparison

| Track Type | MusicBrainz | iTunes API |
|------------|-------------|------------|
| Mainstream tracks | Excellent | Excellent |
| Indie/obscure | Good | Better |
| Typos (e.g., "fuckk" vs "fuck") | Fails | Often works |
| Non-Latin text (Russian, Japanese) | Often fails | Often works |
| Classical with movements | Often fails | Works well |
| Medleys/mashups | Fails | Returns first match |
| Soundtracks (Scott Pilgrim, etc.) | Often missing | Works well |
| Unconventional punctuation | Often fails | Works well |
| User-uploaded content | Fails | Works if on Apple Music |

### Real-World Test Results

We tested 10 "hard case" tracks that failed MusicBrainz matching:

| Track | MusicBrainz | iTunes API |
|-------|-------------|------------|
| `nazi punks fuckk off` (typo) | Failed | Found (Evergreen Terrace cover) |
| `we are sex bob-omb` (soundtrack) | Failed | Found (Sex Bob-Omb) |
| `ektenia ii: blagoslovenie` (Russian) | Failed | Found (Batushka) |
| `seasons (summer): iii. presto` (classical) | Failed | Found (Royal Philharmonic) |
| `day tripper / if i needed someone` (medley) | Failed | Found (The Beatles) |
| `sit down. stand up` (odd punctuation) | Failed | Found (Radiohead) |
| `eve white/eve black` (slash) | Failed | Found (Siouxsie & The Banshees) |
| `bohemian rhapsody` (normal) | Works | Works (Queen) |
| `i'm not okay` (apostrophe) | Works | Works (My Chemical Romance) |
| `cemetery drive` (normal) | Works | Works (My Chemical Romance) |

**Result: iTunes API matched 10/10, MusicBrainz matched 3/10**

### Why iTunes API Has Better Fuzzy Matching

1. **Full-text search** - Apple's servers use sophisticated search algorithms
2. **Phonetic matching** - Handles typos and pronunciation variations
3. **Apple Music catalog** - Contains the exact tracks users are looking up
4. **Flexible punctuation** - Ignores or normalizes special characters
5. **Multi-language support** - Handles romanization of non-Latin text

### iTunes API Limitations

| Limitation | Impact |
|------------|--------|
| **Rate limit: 20 requests/minute** | 44,000 tracks = ~37 hours! |
| **Requires internet** | No offline processing |
| **No batch queries** | Must query one track at a time |
| **403 errors** | Temporary blocks if rate exceeded |
| **May return wrong version** | Cover versions, remixes, etc. |

### Recommended Strategy

```
1. MusicBrainz first (fast, offline, batch processing)
   - Handles 85-99% of mainstream tracks instantly

2. iTunes API for remaining tracks
   - Enable in settings for unmatched tracks
   - Best for obscure/non-English content
   - Use sparingly due to rate limits
```

### Rate Limit Handling

The app tracks 403 errors separately and shows a "Retry rate-limited tracks" button:

- Rate-limited tracks are saved to a separate list
- User can retry after waiting (typically 1-5 minutes)
- Exponential backoff prevents repeated blocks

---

## MusicBrainz API (Not Used)

The app uses a **local MusicBrainz database**, not the MusicBrainz API. Here's why:

### MusicBrainz API Limitations

| Limitation | Impact |
|------------|--------|
| **Rate limit: 1 request/second** | 44,000 tracks = ~12 hours |
| **No batch queries** | Must query one track at a time |
| **Complex XML/JSON responses** | Parsing overhead |
| **Requires internet** | No offline processing |
| **Server reliability** | Occasional downtime |

### Why Local Database is Better

| Feature | Local DB | MusicBrainz API |
|---------|----------|-----------------|
| Speed | ~2ms/query | ~500ms/query |
| Batch queries | Yes (5000+) | No |
| Offline | Yes | No |
| Rate limits | None | 1/second |
| 250K tracks | ~3 minutes | ~70 hours |

### Data Source

The local database is built from MusicBrainz canonical data dumps:
- Updated periodically by MusicBrainz
- Downloaded as compressed archive (~2GB)
- Converted to DuckDB for fast queries
- Contains ~29 million track-artist mappings

---

## Future Improvements

Potential algorithm enhancements (not yet implemented):

1. **Phonetic matching** - Match by pronunciation (computationally expensive)
2. **Levenshtein distance** - Fuzzy string matching for typos (expensive for 29M rows)
3. **N-gram indexing** - Pre-computed substring indexes
4. **Machine learning** - Trained model for similarity scoring

These are not implemented due to performance tradeoffs with a 29-million row database.
