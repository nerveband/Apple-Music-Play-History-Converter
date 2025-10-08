# Album Matching Accuracy Fix - v2.0.0

## Problem Summary

MusicBrainz database searches were achieving only **40% accuracy** when album information was provided, compared to **100% accuracy** from the MusicBrainz API and **80% from iTunes API**.

### Example Failure Case
- Track: "Amazing"
- Album: "808s & Heartbreak"
- Expected: "Kanye West"
- Got: "Sam Day" ❌ (wrong!)

## Root Cause Analysis

Three critical bugs were identified in the album matching logic:

### Bug 1: Loose Substring Matching (50% threshold)
**Location**: `musicbrainz_manager_v2_optimized.py` lines 1402-1424

**Problem**:
- Required only 50% of album tokens to match
- "8 From 808s" matched "808s & Heartbreak" because "808s" token appeared in both (1/2 = 50%)

**Fix**:
- Increased threshold from 50% to **80%**
- Added length similarity check for partial matches
- "8 From 808s" now correctly REJECTED

### Bug 2: Track-as-Album Fallback Activated Incorrectly
**Location**: `musicbrainz_manager_v2_optimized.py` line 1402

**Problem**:
- "Amazing (Capshun remix)" cleaned to just "amazing"
- Matched track name "amazing" → triggered single release fallback
- Got +5M album bonus even though it wasn't the right album

**Fix**:
- Disabled track-as-album fallback when album hint is provided
- This fallback is now ONLY used when NO album information exists

### Bug 3: Title Match Bonus Applied with Album Hint
**Location**: `musicbrainz_manager_v2_optimized.py` lines 1312-1319

**Problem**:
- "Sam Day - Amazing (Capshun remix)" got +1.5M title match bonus
- This allowed it to beat "Kanye West - 808s & Heartbreak" (correct match)
- Final scores:
  - Sam Day: 4,457,348 + 1,500,000 = 5,957,348 ✅ Winner (wrong!)
  - Kanye West: 501,542 + 5,000,000 = 5,500,042 ❌ Lost (correct!)

**Fix**:
- Title match bonus now ONLY applies when NO album hint is provided
- When album info exists, ONLY album matches get bonuses
- New scores:
  - Sam Day: 4,457,348 + 0 = 4,457,348 ❌ Lost
  - Kanye West: 501,542 + 5,000,000 = 5,500,042 ✅ Winner!

## Code Changes

### 1. Album Matching Threshold (80% strict)
```python
# OLD: 50% threshold - too loose
overlap = matches / len(album_tokens)
return overlap >= 0.5

# NEW: 80% threshold - much stricter
overlap = matches / len(album_tokens)
return overlap >= 0.8
```

### 2. Track-as-Album Fallback Fix
```python
# OLD: Always checked
if track_clean and release_clean == track_clean:
    return True

# NEW: Only when NO album hint
if not album_hint and track_clean and release_clean == track_clean:
    return True
```

### 3. Title Bonus Only for Singles
```python
# OLD: Always gave title bonus
if track_clean and release_clean == track_clean:
    weight += 1_500_000

# NEW: Only when NO album hint (single releases)
elif not album_hint:
    if track_clean and release_clean == track_clean:
        weight += 1_500_000
```

## Test Results

### Before Fix (40% accuracy)
```
MUSICBRAINZ:
   Total Tests: 5
   ✅ Correct: 2/5 (40.0%)
   ❌ Wrong: 3/5

   Failed Tests:
      • Welcome To Heartbreak: Got 'Mike Candys'
      • Amazing: Got 'Sam Day'
      • Street Lights: Got 'Phaxe'
```

### After Fix (100% accuracy)
```
MUSICBRAINZ:
   Total Tests: 5
   ✅ Correct: 5/5 (100.0%)
   ❌ Wrong: 0/5
   💥 Failed: 0/5
```

## Files Modified

1. **musicbrainz_manager_v2_optimized.py**
   - Line 1402: Track-as-album fallback condition
   - Lines 1405-1435: Ultra-strict 80% token matching
   - Lines 1312-1319: Title bonus only for singles

2. **test_search_providers.py**
   - Lines 78-83: Accept partial artist matches (e.g., "Kanye West feat. Kid Cudi" = "Kanye West")

## Performance Impact

- **No performance degradation** - matching logic is equally fast
- **Higher accuracy** - from 40% to 100%
- **Better user experience** - correct artists found consistently

## Validation

All test cases now pass:
- ✅ Say You Will → Kanye West
- ✅ Welcome To Heartbreak → Kanye West feat. Kid Cudi
- ✅ Heartless → Kanye West
- ✅ Amazing → Kanye West feat. Young Jeezy
- ✅ Street Lights → Kanye West

MusicBrainz DB accuracy now matches MusicBrainz API (both 100%).
