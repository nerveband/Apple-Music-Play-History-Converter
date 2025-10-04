# MusicBrainz Optimization Plan

## Executive Summary

This document outlines a comprehensive optimization strategy for the Apple Music Play History Converter's MusicBrainz search system. The current implementation processes a ~2GB CSV file with 28M+ rows and creates DuckDB indexes, which takes 2-3 minutes. The goal is to reduce this time by **50-70%** and improve search speeds by **10-100x** through aggressive database, query, and algorithmic optimizations.

## Current Performance Baseline

### Optimization Phase (One-time setup)
- **Total Time**: ~2-3 minutes
- **CSV Size**: ~2GB (28M+ rows)
- **Bottlenecks**:
  - Building basic table: ~30-45s
  - Creating indexes on basic table: ~40-60s
  - Building fuzzy table: ~30-45s
  - Creating indexes on fuzzy table: ~30-45s

### Search Phase (Per-track lookup)
- **Current**: 1-5ms per track (MusicBrainz), 200-500ms (iTunes API)
- **Search Strategy**: Bidirectional cascade with conservative/aggressive text cleaning
- **Hit Rate**: ~80-85% MusicBrainz, ~95% with iTunes fallback

## Architecture Analysis

### Current Implementation Strengths ✅
1. **Smart dual-provider architecture**: MusicBrainz (offline) + iTunes (online fallback)
2. **Persistent DuckDB**: Avoids rebuilding on every run
3. **Bidirectional search cascade**: Conservative → Aggressive → Reverse containment
4. **Text normalization**: Unicode normalization, feature removal, punctuation handling
5. **Album-aware scoring**: Boosts results matching album hints
6. **Proper versioning**: Detects CSV changes and triggers re-optimization

### Current Implementation Weaknesses ⚠️
1. **Single-threaded optimization**: No parallelization of table builds or indexing
2. **Full table scans**: Creates complete fuzzy table with all 28M rows
3. **No tiered indexing**: All tracks treated equally, no priority for popular artists
4. **Redundant text cleaning**: Cleaning happens at query time instead of index time
5. **Memory limits too conservative**: DuckDB set to 2GB, could use more
6. **No compression**: Tables stored uncompressed in DuckDB
7. **Substring matching overhead**: LIKE queries on 28M rows are expensive
8. **No caching layer**: Repeated searches for same track hit database

## Optimization Strategy

### Phase 1: Database & Index Optimization (Expected: 50% speedup) 🚀

#### 1.1 Parallel Index Creation
**Problem**: Indexes created sequentially, one at a time
**Solution**: Create multiple indexes concurrently

```python
def _index_basic_table_parallel(self, progress_callback: Optional[Callable] = None):
    """Create indexes in parallel using DuckDB's thread pool."""
    # DuckDB can run multiple CREATE INDEX commands concurrently
    self._conn.execute("SET threads TO 8")  # Use 8 threads instead of 4

    # Fire all index creations at once - DuckDB handles concurrency
    queries = [
        "CREATE INDEX IF NOT EXISTS idx_basic_rec_lower ON musicbrainz_basic(recording_lower)",
        "CREATE INDEX IF NOT EXISTS idx_basic_art_lower ON musicbrainz_basic(artist_lower)",
        "CREATE INDEX IF NOT EXISTS idx_basic_rel_lower ON musicbrainz_basic(release_lower)"
    ]

    # Execute in parallel using asyncio + thread pool
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(self._conn.execute, query) for query in queries]
        for i, future in enumerate(as_completed(futures)):
            future.result()  # Wait for completion
            if progress_callback:
                progress_callback(f"Index {i+1}/3 complete", (i+1)/3)
```

**Expected Impact**: 30-40% faster index creation

#### 1.2 Increase Memory Allocation
**Problem**: DuckDB limited to 2GB, causing disk spills
**Solution**: Dynamically allocate 25% of system RAM

```python
import psutil

def _connect_to_duckdb(self):
    self._conn = duckdb.connect(str(self.duckdb_file))

    # Allocate 25% of system RAM (but at least 2GB, max 8GB)
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    memory_limit = min(max(int(total_ram_gb * 0.25), 2), 8)

    self._conn.execute(f"SET memory_limit='{memory_limit}GB'")
    self._conn.execute("SET threads TO 8")  # More threads for parallelism
    self._conn.execute("PRAGMA enable_object_cache")
```

**Expected Impact**: 15-20% faster builds, fewer disk I/O operations

#### 1.3 Pre-compute Cleaning in Fuzzy Table
**Problem**: Fuzzy table only does basic lowercase/trim, aggressive cleaning done at query time
**Solution**: Pre-compute aggressive cleaning during table build

```python
def _build_fuzzy_table_optimized(self):
    """Build fuzzy table with pre-computed aggressive cleaning."""
    # Create Python UDF for aggressive cleaning
    self._conn.create_function("clean_aggressive", self.clean_text_aggressive)

    sql = """
        CREATE TABLE musicbrainz_fuzzy AS
        SELECT
            id, artist_credit_id, artist_mbids, artist_credit_name,
            release_mbid, release_name, recording_mbid, recording_name, score,
            clean_aggressive(recording_name) AS recording_clean,
            clean_aggressive(artist_credit_name) AS artist_clean
        FROM musicbrainz_basic
        WHERE recording_name IS NOT NULL
          AND artist_credit_name IS NOT NULL
          AND length(trim(recording_name)) > 0
          AND length(trim(artist_credit_name)) > 0
    """

    self._conn.execute(sql)
```

**Expected Impact**: 20-30% faster queries, moves work from query-time to index-time

#### 1.4 Compressed Storage
**Problem**: Tables stored uncompressed
**Solution**: Enable DuckDB compression

```python
def _connect_to_duckdb(self):
    self._conn = duckdb.connect(str(self.duckdb_file))

    # Enable compression (reduces file size by 50-70%)
    self._conn.execute("PRAGMA enable_compression")
    self._conn.execute("SET compression='auto'")
```

**Expected Impact**: 50-70% smaller database files, faster I/O

### Phase 2: Smart Indexing Strategy (Expected: 30% speedup) 🎯

#### 2.1 Tiered Index Architecture
**Problem**: All 28M tracks indexed equally, even rare/obscure ones
**Solution**: Build separate "hot" and "cold" tables based on popularity

```python
def _build_tiered_tables(self):
    """Build separate tables for popular vs rare tracks."""
    # Hot table: Top 5M most popular tracks (by score)
    self._conn.execute("""
        CREATE TABLE musicbrainz_hot AS
        SELECT * FROM musicbrainz_basic
        WHERE score >= (SELECT PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY score) FROM musicbrainz_basic)
        ORDER BY score DESC
    """)

    # Cold table: Remaining tracks
    self._conn.execute("""
        CREATE TABLE musicbrainz_cold AS
        SELECT * FROM musicbrainz_basic
        WHERE score < (SELECT PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY score) FROM musicbrainz_basic)
    """)

    # Index hot table aggressively
    self._conn.execute("CREATE INDEX idx_hot_rec ON musicbrainz_hot(recording_lower)")
    self._conn.execute("CREATE INDEX idx_hot_art ON musicbrainz_hot(artist_lower)")

    # Index cold table with partial indexes (first 3 chars only)
    self._conn.execute("CREATE INDEX idx_cold_rec_prefix ON musicbrainz_cold(SUBSTRING(recording_lower, 1, 3))")
```

**Search Strategy**:
1. Check hot table first (exact + prefix + contains)
2. Only check cold table if hot table misses
3. 80-90% of real-world searches will hit hot table

**Expected Impact**: 40-60% faster searches for popular tracks, 10-20% faster overall

#### 2.2 Artist Popularity Cache
**Problem**: Artist popularity computed on-demand per search
**Solution**: Pre-compute artist popularity table

```python
def _build_artist_popularity_cache(self):
    """Build artist popularity lookup table."""
    self._conn.execute("""
        CREATE TABLE artist_popularity AS
        SELECT
            artist_credit_name,
            MAX(score) as popularity_score,
            COUNT(*) as track_count
        FROM musicbrainz_basic
        GROUP BY artist_credit_name
    """)

    self._conn.execute("CREATE INDEX idx_artist_pop ON artist_popularity(artist_credit_name)")

def _get_artist_popularity_score(self, artist_credit: str) -> float:
    """Fast lookup from pre-built cache table."""
    if artist_credit in self._artist_score_cache:
        return self._artist_score_cache[artist_credit]

    row = self._conn.execute(
        "SELECT popularity_score FROM artist_popularity WHERE artist_credit_name = ?",
        [artist_credit]
    ).fetchone()

    value = float(row[0]) if row else 0.0
    self._artist_score_cache[artist_credit] = value
    return value
```

**Expected Impact**: 50-80% faster artist scoring, eliminates per-search aggregation

### Phase 3: Query Optimization (Expected: 20% speedup) ⚡

#### 3.1 Reduce Search Row Limit
**Problem**: Fetching 25 rows per query, but only using first match
**Solution**: Reduce to 10 rows, optimize sort order

```python
SEARCH_ROW_LIMIT = 10  # Down from 25
```

**Expected Impact**: 15-20% faster queries (less data transfer)

#### 3.2 Composite Indexes
**Problem**: Queries filter on both recording + album/artist
**Solution**: Create composite indexes for common patterns

```python
def _create_composite_indexes(self):
    """Create composite indexes for multi-column queries."""
    # For queries with album hints
    self._conn.execute("""
        CREATE INDEX idx_rec_album ON musicbrainz_fuzzy(recording_clean, release_name)
    """)

    # For queries with artist hints
    self._conn.execute("""
        CREATE INDEX idx_rec_artist ON musicbrainz_fuzzy(recording_clean, artist_lower)
    """)
```

**Expected Impact**: 25-40% faster searches with album/artist hints

#### 3.3 Early Termination with LIMIT + ORDER BY Optimization
**Problem**: Sorting all results before applying LIMIT
**Solution**: Optimize sort order to enable early termination

```python
def _search_fuzzy_exact(self, clean_track: str, album_hint: Optional[str]) -> Optional[str]:
    """Optimized exact match with early termination."""
    if album_hint:
        # Order by match quality first, then score - DuckDB can terminate early
        sql = f"""
            SELECT artist_credit_name, release_name, score
            FROM musicbrainz_hot  -- Search hot table first
            WHERE recording_clean = ?
            ORDER BY
                (release_name ILIKE ?) DESC,  -- Album match first (0 or 1)
                score DESC
            LIMIT {SEARCH_ROW_LIMIT}
        """
        rows = self._conn.execute(sql, [clean_track, f"%{album_hint}%"]).fetchall()

        if not rows:
            # Fall back to cold table
            rows = self._conn.execute(
                sql.replace("musicbrainz_hot", "musicbrainz_cold"),
                [clean_track, f"%{album_hint}%"]
            ).fetchall()

    return self._choose_candidate(rows, album_hint, clean_track)
```

**Expected Impact**: 10-15% faster searches via early termination

### Phase 4: Algorithmic Improvements (Expected: 40% speedup) 🧠

#### 4.1 Multi-level Search Cache
**Problem**: No caching of search results
**Solution**: Implement LRU cache for recent searches

```python
from functools import lru_cache

class MusicBrainzManagerV2:
    def __init__(self, data_dir: str):
        # ... existing code ...

        # In-memory LRU cache for recent searches (10k entries = ~2MB)
        self._search_cache = {}
        self._cache_max_size = 10000
        self._cache_access_order = deque()

    def search(self, track_name: str, artist_hint: Optional[str] = None, album_hint: Optional[str] = None) -> Optional[str]:
        """Search with LRU caching."""
        # Create cache key
        cache_key = (track_name.lower().strip(),
                     (artist_hint or "").lower().strip(),
                     (album_hint or "").lower().strip())

        # Check cache
        if cache_key in self._search_cache:
            # Move to end (most recently used)
            self._cache_access_order.remove(cache_key)
            self._cache_access_order.append(cache_key)
            return self._search_cache[cache_key]

        # Not in cache - do normal search
        result = self._search_with_cleaning(track_name, album_hint, conservative=True)
        if not result:
            result = self._search_with_cleaning(track_name, album_hint, conservative=False)

        # Add to cache (evict oldest if needed)
        if len(self._search_cache) >= self._cache_max_size:
            oldest_key = self._cache_access_order.popleft()
            del self._search_cache[oldest_key]

        self._search_cache[cache_key] = result
        self._cache_access_order.append(cache_key)

        return result
```

**Expected Impact**: 90-99% cache hit rate on CSV re-processing, instant lookups

#### 4.2 Batch CSV Processing
**Problem**: CSV rows processed one-by-one during conversion
**Solution**: Batch lookups to amortize overhead

```python
async def process_csv_batch(self, tracks: List[Dict]) -> List[Dict]:
    """Process multiple tracks in one batch (future enhancement)."""
    # Prepare all queries at once
    queries = []
    for track in tracks:
        clean_track = self.clean_text_conservative(track['name'])
        queries.append((clean_track, track.get('album')))

    # Execute batch query (DuckDB supports prepared statement reuse)
    results = []
    for clean_track, album_hint in queries:
        result = self._search_fuzzy_exact(clean_track, album_hint)
        results.append(result)

    return results
```

**Expected Impact**: 20-30% faster CSV processing (reduced per-track overhead)

#### 4.3 Phonetic Indexing (Advanced)
**Problem**: Typos and alternate spellings miss exact matches
**Solution**: Add phonetic (Soundex/Metaphone) columns for fuzzy matching

```python
def _build_phonetic_indexes(self):
    """Add phonetic columns for fuzzy matching."""
    # Register phonetic function (using metaphone library)
    import metaphone
    self._conn.create_function("metaphone", metaphone.doublemetaphone)

    # Add phonetic columns
    self._conn.execute("""
        ALTER TABLE musicbrainz_fuzzy
        ADD COLUMN recording_phonetic TEXT,
        ADD COLUMN artist_phonetic TEXT
    """)

    self._conn.execute("""
        UPDATE musicbrainz_fuzzy
        SET
            recording_phonetic = metaphone(recording_clean),
            artist_phonetic = metaphone(artist_clean)
    """)

    self._conn.execute("CREATE INDEX idx_rec_phonetic ON musicbrainz_fuzzy(recording_phonetic)")

def _search_phonetic(self, clean_track: str, album_hint: Optional[str]) -> Optional[str]:
    """Fallback to phonetic search for typos."""
    import metaphone
    track_phonetic = metaphone.doublemetaphone(clean_track)[0]

    sql = f"""
        SELECT artist_credit_name, release_name, score
        FROM musicbrainz_fuzzy
        WHERE recording_phonetic = ?
        ORDER BY score DESC
        LIMIT {SEARCH_ROW_LIMIT}
    """

    rows = self._conn.execute(sql, [track_phonetic]).fetchall()
    return self._choose_candidate(rows, album_hint, clean_track)
```

**Expected Impact**: 5-10% better match rate for typos/variants

### Phase 5: Platform-Specific Optimizations 🖥️

#### 5.1 macOS Optimization
```python
import platform

def _configure_platform_specific(self):
    """Platform-specific optimizations."""
    if platform.system() == "Darwin":  # macOS
        # Use macOS memory allocator (faster than default)
        self._conn.execute("SET allocator='system'")

        # Enable Apple Silicon SIMD if available
        if platform.machine() == "arm64":
            self._conn.execute("SET enable_simd_vectorization=true")
```

#### 5.2 Windows Optimization
```python
if platform.system() == "Windows":
    # Windows benefits from larger page size
    self._conn.execute("SET page_size='16KB'")

    # Disable fsync for faster writes (optimize for speed vs crash recovery)
    self._conn.execute("PRAGMA synchronous=OFF")
```

#### 5.3 Linux Optimization
```python
if platform.system() == "Linux":
    # Linux can handle more aggressive threading
    cpu_count = os.cpu_count() or 4
    self._conn.execute(f"SET threads TO {cpu_count}")

    # Enable mmap for large files
    self._conn.execute("PRAGMA mmap_size=2147483648")  # 2GB mmap
```

**Expected Impact**: 10-20% platform-specific gains

## Implementation Roadmap

### Week 1: Foundation (Quick Wins)
- [x] ~~Read and analyze existing code~~
- [ ] Implement Phase 1.1: Parallel index creation (**30-40% faster**)
- [ ] Implement Phase 1.2: Dynamic memory allocation (**15-20% faster**)
- [ ] Implement Phase 3.1: Reduce search row limit (**15-20% faster**)
- [ ] Test on real CSV file and benchmark improvements

**Expected Total**: **50-60% optimization time reduction** (2-3 min → 1-1.5 min)

### Week 2: Smart Indexing
- [ ] Implement Phase 2.1: Tiered hot/cold tables (**40-60% search speedup**)
- [ ] Implement Phase 2.2: Artist popularity cache (**50-80% scoring speedup**)
- [ ] Implement Phase 4.1: LRU search cache (**90%+ cache hit rate**)
- [ ] Test search accuracy and performance

**Expected Total**: **10-100x search speedup** for common tracks (cache hits), **2-5x** for cache misses

### Week 3: Advanced Optimizations
- [ ] Implement Phase 3.2: Composite indexes (**25-40% query speedup**)
- [ ] Implement Phase 1.3: Pre-computed cleaning (**20-30% query speedup**)
- [ ] Implement Phase 1.4: Compression (**50-70% storage reduction**)
- [ ] Implement Phase 5: Platform-specific optimizations (**10-20% gains**)

**Expected Total**: **Additional 30-50% improvements** across the board

### Week 4: Polish & Advanced Features
- [ ] Implement Phase 4.2: Batch CSV processing (**20-30% CSV speedup**)
- [ ] Implement Phase 4.3: Phonetic indexing (**5-10% match rate improvement**)
- [ ] Comprehensive testing across all platforms
- [ ] Documentation and performance monitoring

## Expected Final Results

### Optimization Time
- **Current**: 2-3 minutes
- **Target**: 0.5-1 minute (**60-75% reduction**)

### Search Performance
- **Current**: 1-5ms per track
- **Target Hot Path** (cached): <0.1ms (**10-100x faster**)
- **Target Cold Path** (cache miss, hot table): 0.2-0.8ms (**2-5x faster**)
- **Target Rare Tracks** (cold table): 1-3ms (**same or slightly better**)

### Storage
- **Current**: ~2GB DuckDB file
- **Target**: ~0.6-1GB (**50-70% reduction** via compression)

### Match Rate
- **Current**: 80-85% (MusicBrainz)
- **Target**: 85-90% (**+5-10%** via phonetic matching)

## Compatibility & Safety

### Backward Compatibility
- All changes maintain V2 API compatibility
- Schema version incremented to trigger re-optimization
- Existing databases gracefully migrate

### Testing Strategy
- Unit tests for each optimization phase
- Benchmark suite with real CSV files
- Platform testing: macOS (Intel + Apple Silicon), Windows, Linux
- Regression testing for search accuracy

### Rollback Plan
- Schema versioning allows reverting to previous implementation
- Feature flags for toggling optimizations
- Performance monitoring to detect regressions

## Monitoring & Metrics

### Key Performance Indicators
1. **Optimization Duration**: Track time for each phase
2. **Search Latency**: P50, P95, P99 percentiles
3. **Cache Hit Rate**: Monitor cache effectiveness
4. **Match Accuracy**: Compare results against baseline
5. **Memory Usage**: Ensure optimizations don't cause OOM
6. **Database Size**: Track storage efficiency

### Instrumentation
```python
class PerformanceMonitor:
    """Track optimization performance metrics."""
    def __init__(self):
        self.metrics = {
            "optimization_time": [],
            "search_latency": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "match_rate": []
        }

    def record_search(self, duration_ms: float, cache_hit: bool, matched: bool):
        self.metrics["search_latency"].append(duration_ms)
        if cache_hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
        self.metrics["match_rate"].append(1 if matched else 0)

    def get_report(self) -> Dict:
        return {
            "avg_search_latency": sum(self.metrics["search_latency"]) / len(self.metrics["search_latency"]),
            "cache_hit_rate": self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"]),
            "match_rate": sum(self.metrics["match_rate"]) / len(self.metrics["match_rate"])
        }
```

## Conclusion

This optimization plan provides a structured approach to dramatically improving MusicBrainz performance while maintaining accuracy and compatibility. The phased approach allows for incremental improvements with measurable results at each stage.

**Total Expected Improvement**:
- **60-75% faster optimization** (2-3 min → 0.5-1 min)
- **10-100x faster searches** (cached hot path)
- **2-5x faster searches** (uncached hot path)
- **50-70% smaller database** (via compression)
- **5-10% better match rate** (via phonetic matching)

The optimization strategy balances immediate wins (Phase 1) with longer-term architectural improvements (Phases 2-4), ensuring steady progress toward the performance goals while maintaining code quality and cross-platform compatibility.