# Async Conversion Checklist - Critical Issue #1

**Purpose:** Track conversion from mixed threading/async to pure Toga async
**Date:** 2025-10-04

---

## 🎯 Core Strategy

### From (Bad - Mixed Pattern):
```python
# ❌ Store event loop
self.main_loop = asyncio.get_event_loop()

# ❌ Create threads manually
threading.Thread(target=worker, daemon=True).start()

# ❌ Bridge from thread to UI
asyncio.run_coroutine_threadsafe(ui_update(), self.main_loop)
```

### To (Good - Pure Async):
```python
# ✅ No event loop storage needed
# ✅ Use executor for blocking I/O
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_function, args)

# ✅ Use asyncio.create_task for async work
task = asyncio.create_task(async_worker())

# ✅ Direct async UI updates (no bridge)
await self.update_ui()
```

---

## 📋 Step 1: Remove Event Loop Storage

**File:** `apple_music_play_history_converter.py`

- [ ] Line 55: Remove `self.main_loop = asyncio.get_event_loop()`
- [ ] Remove all references to `self.main_loop` (40+ locations)

**Replacement pattern:**
```python
# Instead of: asyncio.run_coroutine_threadsafe(coro, self.main_loop)
# Use: await coro (from async context)
# Or: asyncio.create_task(coro) (fire and forget)
```

---

## 📋 Step 2: Convert Threading to Async Executors

### 2.1 CSV Processing Thread

**Current (Line 1722):**
```python
def process_csv_two_phase(self):
    # Runs in separate thread
    all_tracks = self.load_entire_csv(...)
```

**Target:**
```python
async def process_csv_two_phase_async(self):
    # Run blocking I/O in executor
    loop = asyncio.get_running_loop()
    all_tracks = await loop.run_in_executor(
        None,
        self._load_csv_blocking,
        file_path, file_type
    )
```

**Tasks:**
- [x] `process_csv_two_phase_async()` already exists (line 1759)
- [ ] Remove sync version `process_csv_two_phase()` (line 1722)
- [ ] Update `load_entire_csv()` → `load_entire_csv_async()` (use executor)
- [ ] Remove thread creation from callers

### 2.2 Missing Artist Reprocessing Thread

**Current (Line 6159):**
```python
self.reprocessing_thread = threading.Thread(
    target=self.reprocess_missing_artists_thread,
    daemon=True
)
```

**Target:**
```python
async def reprocess_missing_artists_async(self, missing_artists, provider):
    # Pure async - no threading
    for track in missing_artists:
        # Search asynchronously
        result = await self.search_artist_for_track(...)

        # Update UI directly (no bridge)
        await self.update_progress(...)

        # Yield to event loop
        if index % 10 == 0:
            await asyncio.sleep(0)
```

**Tasks:**
- [ ] Create `reprocess_missing_artists_async()` method
- [ ] Convert `reprocess_missing_artists_thread()` logic to async
- [ ] Remove thread creation (line 6159)
- [ ] Update caller `reprocess_missing_artists()` to use async version

---

## 📋 Step 3: Convert UI Update Bridging to Direct Async

### Pattern Conversion

**Current Bridge Pattern (Used 40+ times):**
```python
def update_results(self, text):
    self.results_text_buffer.append(text)
    asyncio.run_coroutine_threadsafe(
        self._update_results_ui(),
        self.main_loop
    )

async def _update_results_ui(self):
    self.results_display.value = "\n".join(self.results_text_buffer)
```

**Target Pure Async:**
```python
async def update_results(self, text):
    self.results_text_buffer.append(text)
    self.results_display.value = "\n".join(self.results_text_buffer)
    await asyncio.sleep(0)  # Yield to UI
```

### Methods to Convert

**Progress Updates:**
- [ ] `update_progress()` → async (line 4429)
- [ ] `_update_progress_ui()` → inline into update_progress()
- [ ] Remove bridge calls (line 4436)

**Results Updates:**
- [ ] `update_results()` → async (line 4194)
- [ ] `_update_results_ui()` → inline
- [ ] `append_log()` → async (line 4205)
- [ ] `_append_log_ui()` → inline

**Preview Updates:**
- [ ] `update_preview()` → async (line 4223)
- [ ] `_update_preview_ui()` → inline

**Button State:**
- [ ] `enable_copy_save_buttons()` → async (line 2468)
- [ ] `_enable_copy_save_buttons()` → inline
- [ ] `_enable_reprocess_button()` → inline

**Stats Display:**
- [ ] `update_stats_display()` → async (line 4766)
- [ ] All `_update_*_stats_ui()` methods → inline

**API Status:**
- [ ] `update_api_status()` → async (line 4450)
- [ ] `show_skip_button()` → async (line 4464)
- [ ] `hide_skip_button()` → async (line 4499)
- [ ] `update_rate_limit_timer()` → async (line 4478)

**Database UI:**
- [ ] `update_database_status()` → async (line 6586)
- [ ] `update_musicbrainz_ui_state()` → async (line 6673)
- [ ] `update_itunes_ui_state()` → async (line 6678)

---

## 📋 Step 4: Remove Threading Infrastructure

**State Variables to Remove:**
- [ ] `self.processing_thread` (line 60)
- [ ] `self.reprocessing_thread` (line 6159 assignment)
- [ ] `self.main_loop` (line 55)
- [ ] `self.api_lock = Lock()` (line 72) - replace with async primitives if needed

**Threading Imports to Check:**
- [ ] `import threading` (line 13) - may still need for Lock, evaluate
- [ ] `from threading import Lock` (line 23) - replace with asyncio.Lock if needed

---

## 📋 Step 5: Update Callers to Use Async

**Event Handlers (already async):**
- ✅ `convert_csv()` (line 1670) - already async
- ✅ `browse_file()` (line 1455) - already async
- ✅ `save_results()` (line 5632) - already async

**Event Handlers to Make Async:**
- [ ] Pause/resume handlers
- [ ] Stop handlers
- [ ] Skip wait handlers

**Ensure All Button Callbacks Are Async:**
- Toga supports async event handlers natively
- Just use `async def handler(self, widget)`

---

## 📋 Step 6: Test Critical Functionality

### Must Preserve:
- [ ] **Pause/Resume** - User can pause iTunes searches
- [ ] **Stop** - User can stop processing
- [ ] **Skip Rate Limit** - User can skip wait
- [ ] **Progress Updates** - Real-time progress percentage
- [ ] **Missing Artist Reprocessing** - Background search works
- [ ] **Chunked Processing** - Large files don't crash

### Test Scenarios:
1. [ ] Small CSV (< 1000 rows) - full processing
2. [ ] Large CSV (> 10,000 rows) - chunked processing
3. [ ] iTunes API rate limiting - skip button works
4. [ ] Missing artist reprocessing - MusicBrainz provider
5. [ ] Missing artist reprocessing - iTunes provider
6. [ ] Pause during processing - resume works
7. [ ] Stop during processing - clean shutdown

---

## 📋 Step 7: Build and Verify

- [ ] `briefcase dev` - test in development mode
- [ ] `briefcase build` - verify build succeeds
- [ ] Run on macOS - verify functionality
- [ ] Cross-platform check (Windows/Linux if available)

---

## 🔍 Verification Against Documentation

After all changes, verify against `EXISTING_FUNCTIONALITY_DOCUMENTATION.md`:

- [ ] All 150+ methods documented still work
- [ ] All UI components responsive
- [ ] All settings persist
- [ ] All export formats work
- [ ] All providers functional
- [ ] All error handling intact

---

## 📊 Progress Tracking

**Total Tasks:** 50+
**Completed:** 1 (shell injection fix)
**In Progress:** Async conversion
**Remaining:** Testing, verification

---

**Current Status:** STARTING CONVERSION
**Next Step:** Remove event loop storage and update first UI method
