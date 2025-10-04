# Ultra-Fast CSV Processing Implementation Plan

**Goal:** Reduce CSV processing time from **5.3 hours** to **under 10 minutes** (30-50x speedup)

**Date:** September 29, 2025
**Status:** 🚀 IMPLEMENTATION IN PROGRESS

---

## Problem Analysis

### Current Bottlenecks

**Current Performance:**
- 77ms per row
- 12.9 rows/sec throughput
- 253,525 rows = 5.3 hours

**Root Causes:**
1. ❌ **pandas.iterrows()** - Slowest way to iterate (50ms overhead per row)
2. ❌ **Row-by-row searching** - Individual SQL queries for each track
3. ❌ **No deduplication** - Same track searched multiple times
4. ❌ **No parallelization** - Only using 1 of 8 CPU cores
5. ❌ **Cold cache** - Only 5.1% hit rate on first pass
6. ❌ **Python overhead** - Row-by-row Python function calls

### Performance Target

**Target Performance:**
- 1-2ms per row effective
- 500-1000 rows/sec throughput
- 253,525 rows = **4-8 minutes** (40-80x faster!)

---

## Optimization Strategy

### Phase 1: Batch SQL + Deduplication (20-50x faster) 🚀🚀🚀

**Problem:** Searching "Bohemian Rhapsody" 100 times = 100 individual SQL queries

**Solution:**
1. Extract unique (track, album) pairs
2. Single massive SQL query for ALL unique tracks
3. Map results back to all rows (instant dictionary lookup)

**Algorithm:**
```python
# 1. Read CSV
df = pd.read_csv(file)

# 2. Pre-clean tracks (vectorized, not row-by-row)
df['track_clean'] = df['Song Name'].apply(clean_func)

# 3. Find unique tracks
unique = df[['track_clean', 'Album']].drop_duplicates()

# 4. Single SQL query for ALL tracks
sql = f"SELECT recording_clean, artist_credit_name FROM musicbrainz_hot
        WHERE recording_clean IN ({placeholders})
        ORDER BY recording_clean, score DESC"
results = conn.execute(sql, unique_tracks).fetchall()

# 5. Build lookup dict
track_to_artist = {track: artist for track, artist in results}

# 6. Vectorized mapping (instant)
df['Artist'] = df['track_clean'].map(track_to_artist)
```

**Expected Speedup:**
- CSV with 50% duplicates: **2x faster**
- CSV with 80% duplicates: **5x faster**
- CSV with 90% duplicates: **10x faster**
- Typical Apple Music CSV: **20-30x faster**

### Phase 2: Vectorized Text Cleaning (2-5x faster) 🚀

**Problem:** Calling `clean_text()` Python function 250K times is slow

**Solution:** Use pandas vectorized string operations

**Before:**
```python
# Slow: Python function call per row
df['track_clean'] = df['Song Name'].apply(manager.clean_text_conservative)
```

**After:**
```python
# Fast: Vectorized pandas operations
df['track_clean'] = (
    df['Song Name']
    .str.normalize('NFKC')
    .str.replace(r'\s*[\(\[].*?[\)\]]', '', regex=True)
    .str.replace(r'\bfeat(?:\.|uring)?\b.*', '', regex=True, case=False)
    .str.lower()
    .str.replace(r'[^\w\s]', '', regex=True)
    .str.replace(r'\s+', ' ', regex=True)
    .str.strip()
)
```

**Expected Speedup:** 2-5x faster text cleaning

### Phase 3: Smart Query Batching (5-10x faster) 🚀🚀

**Problem:** DuckDB optimal batch size is ~1000-10000 rows at once

**Solution:** Process in optimal batches

```python
def batch_search(tracks, batch_size=5000):
    """Search in optimal batches."""
    results = {}

    for i in range(0, len(tracks), batch_size):
        batch = tracks[i:i+batch_size]
        placeholders = ','.join(['?' for _ in batch])

        # Single query for entire batch
        sql = f"SELECT DISTINCT ON (recording_clean)
                       recording_clean, artist_credit_name
                FROM musicbrainz_hot
                WHERE recording_clean IN ({placeholders})
                ORDER BY recording_clean, score DESC"

        batch_results = conn.execute(sql, batch).fetchall()
        results.update({track: artist for track, artist in batch_results})

    return results
```

**Expected Speedup:** 5-10x faster than row-by-row

### Phase 4: HOT/COLD Cascade (2-3x faster) 🚀

**Problem:** Searching cold table even for popular tracks

**Solution:** Query HOT table first (covers 80-90% of real-world tracks)

```python
# 1. Try HOT table first (fast, covers most tracks)
hot_results = batch_search_hot(unique_tracks)

# 2. Only query COLD table for misses
missed = [t for t in unique_tracks if t not in hot_results]
if missed:
    cold_results = batch_search_cold(missed)
    hot_results.update(cold_results)
```

**Expected Speedup:** 2-3x faster (most tracks in HOT table)

### Phase 5: Parallel Processing (4-8x faster) 🚀🚀

**Problem:** Using 1 CPU core, wasting 7 others

**Solution:** Split CSV into chunks, process in parallel

```python
from multiprocessing import Pool
import numpy as np

# Split into chunks
chunks = np.array_split(df, num_workers)

# Process in parallel
with Pool(num_workers) as pool:
    results = pool.map(process_chunk, chunks)

# Combine results
final_df = pd.concat(results)
```

**Expected Speedup:** 4-8x on 8-core CPU (not perfect scaling)

### Phase 6: In-Memory Caching (10-100x for repeated CSVs) 🚀🚀🚀

**Problem:** Re-processing same CSV = re-searching same tracks

**Solution:** Already implemented LRU cache in manager

**Expected Speedup:**
- Second pass on same CSV: **10-50x faster**
- Third pass: **50-100x faster**

---

## Combined Implementation

### Ultra-Fast CSV Processor (All Techniques Combined)

**Expected Performance:**
```
Technique                          Speedup    Cumulative
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Batch SQL + Deduplication          20x        20x
Vectorized text cleaning            3x        60x
Smart batching                      2x        120x
HOT/COLD cascade                    2x        240x
Parallel processing (8 cores)       6x        1440x (theoretical max)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Realistic cumulative speedup: 50-100x
```

**Realistic Performance:**
- **Before:** 77ms per row → 5.3 hours for 253K rows
- **After:** 1-2ms per row effective → **5-10 minutes** for 253K rows

---

## Implementation Steps

### Step 1: Create Ultra-Fast Processor Class

```python
class UltraFastCSVProcessor:
    """Ultra-optimized CSV processor using batch SQL and vectorization."""

    def __init__(self, manager):
        self.manager = manager
        self.conn = manager._conn

    def process_csv(self, csv_file, progress_callback=None):
        """Process CSV with all optimizations."""
        # 1. Read CSV efficiently
        # 2. Vectorized text cleaning
        # 3. Deduplication
        # 4. Batch SQL queries
        # 5. HOT/COLD cascade
        # 6. Vectorized mapping
        # 7. Return processed DataFrame
```

### Step 2: Integrate with Main App

```python
# In apple_music_play_history_converter.py
from .ultra_fast_csv_processor import UltraFastCSVProcessor

# In process_csv_async():
processor = UltraFastCSVProcessor(self.music_search_service.musicbrainz_manager)
result_df = processor.process_csv(input_file, progress_callback=update_progress)
```

### Step 3: Test with Large CSV

```bash
# Test script
python test_ultra_fast_csv.py

# Expected output:
# Total rows: 253,525
# Unique tracks: 45,000 (17.8%)
# Deduplication saves: 208,525 searches!
# HOT table hits: 42,000 (93.3%)
# COLD table hits: 2,500 (5.6%)
# Processing time: 4m 23s
# Throughput: 963 rows/sec
# Speedup: 73x faster!
```

### Step 4: Benchmark Results

Target metrics:
- ✅ Processing time: <10 minutes
- ✅ Throughput: >500 rows/sec
- ✅ Speedup: >50x vs current
- ✅ Match rate: 100% (same accuracy)
- ✅ Memory usage: <2GB

---

## Code Architecture

### New Files

1. **`ultra_fast_csv_processor.py`** - Ultra-optimized processor
2. **`test_ultra_fast_csv.py`** - Comprehensive benchmark
3. **`docs/ultra-fast-csv-processing.md`** - This file

### Modified Files

1. **`apple_music_play_history_converter.py`** - Use new processor
2. **`musicbrainz_manager_v2_optimized.py`** - Add batch search methods

---

## Performance Monitoring

### Key Metrics to Track

1. **Total processing time** - Overall CSV processing duration
2. **Throughput** - Rows processed per second
3. **Deduplication rate** - % of duplicate tracks saved
4. **HOT table hit rate** - % found in HOT table
5. **Cache hit rate** - % served from LRU cache
6. **Memory usage** - Peak RAM during processing
7. **Match rate** - % of tracks successfully matched

### Debug Output

```
🚀 ULTRA-FAST CSV PROCESSING
══════════════════════════════════════════════════════════════
Reading CSV...
  ✅ Read 253,525 rows in 2.3s

Vectorized text cleaning...
  ✅ Cleaned 253,525 tracks in 1.1s

Deduplication analysis...
  📊 Total rows: 253,525
  📊 Unique tracks: 45,234 (17.8%)
  💾 Deduplication saves: 208,291 searches (82.2%)!
  🚀 Speedup from dedup: 5.6x

Batch SQL queries...
  🔥 Querying HOT table (batch size: 5,000)
  ✅ HOT table hits: 42,156 (93.2%)

  ❄️  Querying COLD table for misses
  ✅ COLD table hits: 2,543 (5.6%)

  ⚠️  Not found: 535 (1.2%)

Vectorized mapping...
  ✅ Mapped results in 0.4s

Final results...
  ✅ Total matches: 252,990 (99.8%)
  ⏱️  Total time: 4m 23s
  🚀 Throughput: 963 rows/sec
  🎉 Speedup: 73x faster than previous!
══════════════════════════════════════════════════════════════
```

---

## Fallback Strategy

If batch SQL approach has issues:
1. Try smaller batch sizes (1000 instead of 5000)
2. Fall back to parallel row-by-row (still 6-8x faster)
3. Use original method as last resort

---

## Expected Results Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Per-row time | 77ms | 1-2ms | **38-77x** |
| Throughput | 12.9 rows/sec | 500-1000 rows/sec | **40-80x** |
| 253K rows | 5.3 hours | 4-8 minutes | **40-80x** |
| Dedup savings | 0% | 80-90% | **5-10x** |
| SQL queries | 253K | 45-50K | **5-6x** |
| Memory usage | Low | Medium | Acceptable |

---

## Risk Mitigation

### Potential Issues

1. **SQL IN clause limits** - DuckDB supports up to ~32K parameters
   - Mitigation: Batch into 5K chunks

2. **Memory usage** - Loading entire CSV + results
   - Mitigation: Process in chunks if >1GB

3. **Accuracy regression** - Batch queries might miss some matches
   - Mitigation: Extensive testing, fallback to row-by-row for misses

4. **GUI responsiveness** - Long operation might freeze UI
   - Mitigation: Already using background threads + progress updates

---

## Success Criteria

✅ Processing time <10 minutes for 250K rows
✅ Match rate ≥99% (same as current)
✅ Memory usage <2GB
✅ No GUI freezing
✅ Progress updates work correctly
✅ Handles all CSV formats (Play Activity, Recently Played, Daily Tracks)
✅ Works cross-platform (macOS, Windows, Linux)

---

## Implementation Checklist

- [ ] Create `UltraFastCSVProcessor` class
- [ ] Implement vectorized text cleaning
- [ ] Implement batch SQL queries
- [ ] Implement deduplication logic
- [ ] Implement HOT/COLD cascade
- [ ] Add progress reporting
- [ ] Create test script
- [ ] Test with small CSV (17 rows)
- [ ] Test with large CSV (253K rows)
- [ ] Benchmark performance
- [ ] Integrate with GUI
- [ ] Test GUI integration
- [ ] Update documentation
- [ ] Mark complete

---

## Next Steps

1. Implement `UltraFastCSVProcessor` class
2. Test with `test_ultra_fast_csv.py`
3. Benchmark against large CSV
4. Integrate with main app
5. Test GUI mode
6. Celebrate 50-100x speedup! 🎉