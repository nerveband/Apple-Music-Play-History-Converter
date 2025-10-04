# Fuzzy Table Optimization Analysis

## Current Problem
The fuzzy table building process is frozen/extremely slow due to Python UDF being called millions of times.

## Three Approaches Analyzed

### Approach A: Simple `lower(trim())` (from v2.py)
```sql
lower(trim(recording_name)) AS recording_clean
```
**Pros:**
- ✅ Builds instantly (native SQL)
- ✅ No Python context switching
- ✅ Simple and maintainable

**Cons:**
- ❌ Search code cleans terms aggressively, DB only has simple cleaning
- ❌ Exact matches (`WHERE recording_clean = ?`) will FAIL
- ❌ Only works with LIKE queries (contains/prefix)

**Example mismatch:**
- DB stores: "song (remix)"
- Search term cleaned to: "song remix"
- Exact match query fails ❌

### Approach B: Python UDF Aggressive Cleaning (current v2_optimized)
```python
self._conn.create_function("clean_aggressive", self.clean_text_aggressive)
# Then: clean_aggressive(recording_name) AS recording_clean
```

**Pros:**
- ✅ Perfect match with search term cleaning
- ✅ Exact matches work correctly
- ✅ Handles Unicode normalization (NFKC)

**Cons:**
- ❌ **EXTREMELY SLOW** - Python called for every row (millions of times)
- ❌ Causes app to freeze during optimization
- ❌ Estimated 10-20+ minutes for 6.44 GB database

**Cleaning steps:**
1. Unicode normalize (NFKC): "café" → "cafe"
2. Remove parens: `r'\s*[\(\[].*?[\)\]]'`
3. Remove feat: `r'feat(?:\.|uring)?.*'` (case-insensitive)
4. Lowercase
5. Remove punctuation: `r'[^\w\s]'` (UNICODE)
6. Normalize whitespace

### Approach C: SQL regexp Aggressive Cleaning (my proposal)
```sql
trim(
    regexp_replace(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    lower(recording_name),
                    '\([^)]*\)|\[[^\]]*\]', '', 'g'
                ),
                '\s+(feat\.|featuring|ft\.|with)\s+.*', '', 'gi'
            ),
            '[^\w\s]', '', 'g'
        ),
        '\s+', ' ', 'g'
    )
) AS recording_clean
```

**Pros:**
- ✅ FAST - native SQL (100x faster than Python UDF)
- ✅ No context switching
- ✅ Builds in seconds instead of minutes

**Cons:**
- ❌ **Missing Unicode normalization** (CRITICAL BUG!)
- ⚠️ Slightly different feat pattern
- ❌ Will cause search mismatches for Unicode characters

**Unicode normalization bug:**
- Python: "Beyoncé" → "beyonce"
- SQL: "Beyoncé" → "beyoncé"
- Search term (Python): "beyonce"
- Match: FAIL ❌

## How Search Actually Works

### Search Flow (v2_optimized):
1. User searches: "Café Tacvba"
2. Python cleans search term: `clean_text_aggressive("Café Tacvba")` → "cafe tacvba"
3. Queries: `WHERE recording_clean = "cafe tacvba"`
4. Expects DB to have: "cafe tacvba" (also aggressively cleaned)

### Why Both Must Match:
The search cascade tries:
1. **Exact match**: `WHERE recording_clean = ?` (requires identical cleaning)
2. **Prefix match**: `WHERE recording_clean LIKE ? || '%'` (requires similar cleaning)
3. **Contains match**: `WHERE recording_clean LIKE '%' || ? || '%'` (more flexible)

For performance, exact matches are tried FIRST. They only work if both sides are cleaned identically.

## Critical Dependencies

### All code that depends on `recording_clean` and `artist_clean`:

1. **Fuzzy exact search** (line 1097, 1108):
   ```sql
   WHERE recording_clean = ?
   ```

2. **Fuzzy prefix search** (line 1129, 1141):
   ```sql
   WHERE recording_clean LIKE ? || '%'
   ```

3. **Fuzzy contains search** (line 1164, 1176):
   ```sql
   WHERE recording_clean LIKE '%' || ? || '%'
   ```

4. **Reverse contains search** (line 1197, 1212):
   ```sql
   WHERE length(recording_clean) >= 3
     AND ? LIKE '%' || recording_clean || '%'
   ```

5. **HOT/COLD table indexes** (line 939-948):
   ```sql
   CREATE INDEX idx_hot_rec_clean ON musicbrainz_hot(recording_clean)
   CREATE INDEX idx_cold_rec_clean ON musicbrainz_cold(recording_clean)
   ```

6. **Composite indexes** (line 987, 994):
   ```sql
   CREATE INDEX idx_hot_rec_album ON musicbrainz_hot(recording_clean, release_name)
   CREATE INDEX idx_hot_rec_artist ON musicbrainz_hot(recording_clean, artist_clean)
   ```

**ALL of these expect `recording_clean` to match `clean_text_aggressive()` output!**

## Impact Analysis

### If we use simple `lower(trim())`:
- ❌ **Breaks exact matches** - search cleaned "song remix", DB has "song (remix)"
- ❌ **Breaks prefix matches** - same issue
- ⚠️ **Contains might work** - if cleaned term is substring of DB value
- ❌ **Performance degrades** - falls back to slower query methods

### If we use SQL regexp (my approach):
- ✅ **Exact matches work** - for ASCII text
- ❌ **Unicode bugs** - "Beyoncé" fails to match "beyonce"
- ❌ **International artists broken** - Björk, Måneskin, etc.
- ⚠️ **Subtle feat pattern differences** - may miss some variants

### If we keep Python UDF:
- ✅ **Everything works correctly**
- ❌ **Unbearably slow** - 10-20+ minutes optimization time
- ❌ **App appears frozen** - poor user experience

## Recommendation

**Option 1: Fix SQL regexp with Unicode normalization**
Check if DuckDB has Unicode normalization functions. If so, add to SQL.

**Option 2: Hybrid approach**
- Pre-compute in separate async step (show progress)
- Use threading to not block UI
- Still use Python UDF but make it non-blocking

**Option 3: Revert to v2.py architecture**
- Use simple `lower(trim())` in fuzzy table
- Adjust search cascade to not rely on exact matches
- Use more LIKE queries (slower but works)

**Option 4: Keep current freeze (document it)**
- Add progress updates during Python UDF execution
- Inform user it takes 10-20 minutes
- Only runs once per database

## Testing Required Before Any Change

1. **Test Unicode handling**: Songs with accents, umlauts, special chars
2. **Test feat patterns**: "feat.", "featuring", "ft.", various cases
3. **Test punctuation**: Apostrophes, hyphens, special chars
4. **Test search accuracy**: Hit rate before/after change
5. **Performance benchmarks**: Build time and search speed

## Questions to Answer

1. Does DuckDB have Unicode normalization functions?
2. Can we make Python UDF non-blocking with progress?
3. What's the actual hit rate impact of approach C vs B?
4. How many songs have Unicode characters in dataset?
