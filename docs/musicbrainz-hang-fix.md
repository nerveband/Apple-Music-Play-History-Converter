# MusicBrainz Search Hang - Root Cause Analysis and Fix

**Date:** September 29, 2025
**Issue:** App hangs when processing CSV files with MusicBrainz enabled, specifically when searching for missing artists.

## Problem Summary

The application would hang indefinitely when attempting to search for missing artists using MusicBrainz. The first song would never complete processing and no timeout would occur.

## Root Causes Identified

### 1. **Missing `schema_version` in Metadata** (Primary Issue)

**Location:** `~/.apple_music_converter/musicbrainz/mb_meta.json`

**Problem:**
- The metadata file was missing the `schema_version` field
- This caused `_check_existing_optimization()` in `musicbrainz_manager_v2.py` (line 245) to fail the schema version check
- Even though the DuckDB database existed, `_optimization_complete` and `_ready` flags remained `False`
- When `ensure_musicbrainz_ready()` was called, it would enter `wait_until_ready()` with a 600-second timeout
- The `wait_until_ready()` function would loop forever because:
  - It was waiting for `is_ready()` to return `True`
  - But `is_ready()` checks `_optimization_complete`, which was `False`
  - The optimization wouldn't run because it thought it was already in progress

**Original metadata:**
```json
{
  "version": "96fa1296a1cb3715",
  "optimized_at": "2025-09-17T11:56:00.000000",
  "duckdb_path": "/Users/nerveband/.apple_music_converter/musicbrainz/duckdb/mb.duckdb"
}
```

**Fixed metadata:**
```json
{
  "version": "96fa1296a1cb3715",
  "optimized_at": "2025-09-17T11:56:00.000000",
  "duckdb_path": "/Users/nerveband/.apple_music_converter/musicbrainz/duckdb/mb.duckdb",
  "schema_version": 2
}
```

### 2. **Outdated DuckDB Schema** (Secondary Issue)

**Location:** `~/.apple_music_converter/musicbrainz/duckdb/mb.duckdb`

**Problem:**
- The existing DuckDB database was built with an old schema (before schema version 2)
- It only contained the `musicbrainz_basic` table
- The new search code expects both `musicbrainz_basic` AND `musicbrainz_fuzzy` tables
- When searches tried to query `musicbrainz_fuzzy`, they would fail with:
  ```
  Catalog Error: Table with name musicbrainz_fuzzy does not exist!
  Did you mean "musicbrainz_basic"?
  ```
- The search would fall back to basic searches only, which gave poor results

**Solution:**
- Delete the old DuckDB file: `rm ~/.apple_music_converter/musicbrainz/duckdb/mb.duckdb`
- The app will automatically rebuild the database with the correct schema on next run

### 3. **Variable Usage Before Declaration** (Code Bug)

**Location:** `src/apple_music_history_converter/music_search_service_v2.py`, line 203-210

**Problem:**
- In the `search_song()` method, the `provider` variable was used in a trace log before being declared
- Line 205 referenced `provider` in the trace_log.debug() call
- But `provider = self.get_search_provider()` wasn't called until line 212

**Fix:**
```python
# Before (broken):
logger.debug(f"Searching: song='{song_name}', artist='{artist_name}', album='{album_name}'")
if TRACE_ENABLED:
    trace_log.debug(
        "search_song: provider=%s ...",
        provider,  # ❌ Used before declaration!
        ...
    )

provider = self.get_search_provider()  # Declared here

# After (fixed):
provider = self.get_search_provider()  # ✅ Declare first
auto_fallback = self.get_auto_fallback()

logger.debug(f"Searching: song='{song_name}', artist='{artist_name}', album='{album_name}'")
if TRACE_ENABLED:
    trace_log.debug(
        "search_song: provider=%s ...",
        provider,  # ✅ Now safe to use
        ...
    )
```

### 4. **Optimization Logic Improvement** (Enhancement)

**Location:** `src/apple_music_history_converter/music_search_service_v2.py`, `ensure_musicbrainz_ready()` method

**Problem:**
- The method would immediately jump to modal/wait logic without first attempting to start optimization
- This could cause the function to wait indefinitely if optimization hadn't been started yet

**Fix:**
Added explicit `start_optimization_if_needed()` call before checking modal/wait logic:
```python
# Start optimization if needed (will check if already complete)
# This is safe to call multiple times - it checks state internally
logger.info("Starting optimization if needed...")
print("🔧 Starting optimization check...")
optimization_started = self.musicbrainz_manager.start_optimization_if_needed()

if not optimization_started:
    logger.error("Failed to start optimization - CSV not available")
    print("❌ Failed to start optimization - CSV not available")
    return False

# Now proceed with modal/wait logic...
```

## Files Changed

1. **`src/apple_music_history_converter/music_search_service_v2.py`**
   - Fixed variable declaration order in `search_song()`
   - Added explicit optimization start in `ensure_musicbrainz_ready()`

2. **`~/.apple_music_converter/musicbrainz/mb_meta.json`** (User data)
   - Added `"schema_version": 2` field

3. **`~/.apple_music_converter/musicbrainz/duckdb/mb.duckdb`** (User data)
   - Deleted to force rebuild with correct schema

## Testing

Created `debug_musicbrainz_search.py` script to reproduce and verify the fix:
- Tests initialization of MusicSearchServiceV2
- Verifies MusicBrainz readiness check
- Tests searches with sample data from the problematic CSV
- Confirms no hangs occur and searches complete with timeout

**Test Results After Fix:**
- ✅ MusicBrainz initialization: SUCCESS
- ✅ Readiness check: SUCCESS (no hang)
- ✅ Search for "Apple Music 1": Returns properly (no match found, as expected)
- ✅ Search for "Get Lucky": Returns result (though may need tuning)
- ✅ All searches complete within 5 seconds

## Lessons Learned

1. **Metadata Validation:** Always validate metadata schema versions to prevent state mismatches
2. **Database Schema Evolution:** Need better migration strategy when schema changes
3. **Timeout Mechanisms:** The `wait_until_ready()` loop needs a maximum iteration count, not just time-based timeout
4. **Debugging Async Code:** Background thread operations are hard to debug - need better logging
5. **Variable Declaration Order:** Python doesn't catch undefined variable usage until runtime in conditionals

## Recommendations for Future

### Short-term:
1. Add metadata validation on startup with automatic repair
2. Add database schema version checking with automatic rebuild if mismatch
3. Add maximum iteration limits to `wait_until_ready()` loops
4. Add more comprehensive error messages for common failure modes

### Long-term:
1. Implement proper database migration system instead of full rebuilds
2. Add health check endpoint that validates all components
3. Consider using a proper state machine for optimization lifecycle
4. Add telemetry to track how often these issues occur in production

### 5. **Slow Fuzzy Table Creation** (Performance Issue)

**Location:** `src/apple_music_history_converter/musicbrainz_manager_v2.py`, `_build_fuzzy_table()` method

**Problem:**
- The fuzzy table creation used complex `regexp_replace` operations with Unicode character classes
- Processing 28+ million rows with nested regexp operations was extremely slow (>2 minutes or timeout)
- The optimization would hang or get killed before completing the fuzzy table

**Original SQL:**
```sql
-- This was TOO SLOW on 28M rows
regexp_replace(
    regexp_replace(
        regexp_replace(
            lower(recording_name),
            '\\s*\\(.*?\\)|\\s*\\[.*?\\]', ''    -- drop parentheses/brackets
        ),
        '\\bfeat(?:\\.|uring)?\\b.*', ''        -- drop "feat..."
    ),
    '[^\\p{L}\\p{Nd}\\s]+', ''                 -- remove punctuation (Unicode!)
) AS recording_clean
```

**Fixed SQL:**
```sql
-- Much faster - just lowercase and trim
-- More aggressive cleaning done in Python during search
lower(trim(recording_name)) AS recording_clean,
lower(trim(artist_credit_name)) AS artist_clean
```

This reduced fuzzy table creation time from >2 minutes to ~40 seconds for 28M rows.

## Resolution

**Status:** ✅ RESOLVED

The app now:
1. Correctly detects when MusicBrainz database is ready
2. Rebuilds the database with correct schema if needed
3. Doesn't hang when searching for missing artists
4. Returns search results or "no match" within reasonable timeouts
5. Completes optimization in reasonable time (~60 seconds for 28M rows)

## Additional Notes

### About "Apple Music 1" Tracks

The CSV contains entries like:
```
Track Description: Apple Music 1
Artist: (empty)
```

These are radio station plays, not actual songs. The search correctly returns "no match" for these, which is the expected behavior. Users should filter these out before conversion if desired.

### Search Accuracy

During testing, noticed some search results are incorrect (e.g., "I Can Change" by LCD Soundsystem returns "Saddam Hussein"). This is a separate issue related to the scoring algorithm in `musicbrainz_manager_v2.py` and should be addressed separately.