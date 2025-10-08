# iTunes Rate Limit - Final Clean Fix

## Problem: iTunes Search Stopped After 4 Requests

**Root Causes:**
1. **Parallel requests trigger instant 403** - iTunes API blocks all parallel requests from same IP
2. **Confusing queue-filling workaround** - Complex hack to force 60s wait was hard to understand

## Clean Solution

### Fix 1: Simple 60-Second Sleep (No Queue Hacks)

**Before (Complex):**
```python
# Fill queue with fake timestamps from 60s ago (confusing!)
self.itunes_requests.clear()
oldest_timestamp = current_time - 60
for i in range(rate_limit):
    self.itunes_requests.append(oldest_timestamp + (i * 0.001))
```

**After (Simple):**
```python
# Just sleep for 60 seconds - simple and clear!
logger.print_always(f"⏸️  iTunes rate limit hit (403) - waiting 60 seconds...")
time.sleep(60)
self.itunes_requests.clear()
```

**Why this is better:**
- ✅ Clear and obvious what it does
- ✅ No confusing timestamp manipulation
- ✅ Same result, simpler code

### Fix 2: Remove Parallel Requests Entirely

**Before:**
- Had `use_parallel_requests` setting
- Had `parallel_workers` setting
- Had complex ThreadPoolExecutor code
- Had logic to detect and disable parallel mode
- Imported `ThreadPoolExecutor, as_completed` (unused after fix)

**After:**
- Removed all parallel request code
- Function renamed to `search_batch_api()` for clarity
- Clear docstring: "Search API (iTunes or MusicBrainz) for multiple songs sequentially"
- Removed unused imports
- ~100 lines of dead code eliminated

**Code simplified from:**
```python
# 140+ lines of parallel/sequential branching logic
use_parallel = self.settings.get("use_parallel_requests", False)
if not use_parallel:
    # Sequential code
elif current_provider in ["musicbrainz_api", "itunes"]:
    # Force sequential
else:
    # Parallel code with ThreadPoolExecutor
```

**To:**
```python
# 20 lines of simple sequential loop
for idx, song in enumerate(song_names):
    if interrupt_check and interrupt_check():
        break
    result = self._search_itunes(song) if provider == "itunes" else self._search_musicbrainz_api(song)
    results.append(result)
    if progress_callback:
        progress_callback(idx, song, result, idx + 1, len(song_names))
return results
```

## Changes Made

### `src/apple_music_history_converter/music_search_service_v2.py`

**Lines 17-19**: Removed unused imports
```python
# Before:
from concurrent.futures import ThreadPoolExecutor, as_completed

# After:
# (removed - not needed)
```

**Lines 598-615**: Simple 60-second sleep instead of queue filling
```python
# Wait 60 seconds before returning (allow cooldown)
logger.print_always(f"⏸️  iTunes rate limit hit (403) - waiting 60 seconds...")
time.sleep(60)
self.itunes_requests.clear()
```

**Lines 852-905**: Removed all parallel request code, simplified to sequential only
```python
def search_batch_api(self, song_names, progress_callback=None, interrupt_check=None):
    """
    Search API (iTunes or MusicBrainz) for multiple songs sequentially.
    Both APIs require sequential requests to avoid rate limiting.
    """
    # ALWAYS use sequential mode
    results = []
    for idx, song in enumerate(song_names):
        # ... simple loop ...
    return results
```

## Test Results

✅ **All 69 tests passing**

```bash
python -m pytest tests_toga/ -v
# ======================= 69 passed, 28 warnings in 4.24s ========================
```

## Code Quality Improvements

**Before:**
- 140+ lines of parallel/sequential branching
- Complex queue-filling hack
- Unused imports and settings
- Hard to understand flow

**After:**
- 20 lines of simple sequential loop
- Clear 60-second sleep
- No unused code
- Easy to understand

**Lines of code removed:** ~120 lines

## How It Works Now

1. **Sequential Requests**: One request at a time, properly rate-limited
2. **403 Handling**: Sleep 60 seconds, clear queue, continue
3. **Adaptive Rate Limit**: Discovers actual limit and adjusts
4. **Smart Reordering**: Defers previously-failed tracks to end of queue

## User Experience

**Before:**
- Search stopped after 4 requests
- Confusing behavior
- No clear error message

**After:**
- All tracks processed sequentially
- Clear message: "⏸️ iTunes rate limit hit (403) - waiting 60 seconds..."
- Continues after cooldown
- Works reliably

## Files Modified

1. `src/apple_music_history_converter/music_search_service_v2.py`
   - Removed parallel request code (~120 lines)
   - Simplified 403 handling (queue hack → simple sleep)
   - Removed unused imports

## Migration Notes

**Breaking Changes:**
- Function renamed: `search_itunes_batch_parallel()` → `search_batch_api()`
- Removes confusing "itunes" and "parallel" from name
- All call sites updated throughout codebase
- Settings like `use_parallel_requests` removed entirely

## Key Takeaways

1. **Parallel requests don't work** - iTunes blocks them instantly with 403
2. **Simple is better** - `time.sleep(60)` beats complex queue manipulation
3. **Remove dead code** - If it doesn't work, delete it
4. **Clear naming matters** - Function name should reflect actual behavior, not legacy compatibility
