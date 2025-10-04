# Existing Functionality Documentation - Before Critical Fixes

**Purpose:** Document all existing functionality and implementation details before applying critical fixes.
**Date:** 2025-10-04
**Branch:** `feature/ui-rewrite`
**Main File:** `apple_music_play_history_converter.py` (7310 lines)

---

## 🎯 Core Application Functionality

### 1. Application Lifecycle

**Current Implementation:**
- **Framework:** Toga (BeeWare)
- **Entry Point:** `AppleMusicConverterApp(toga.App)`
- **Startup:** `def startup(self)` - NOT async (Toga requirement)
- **Event Loop:** Stores `self.main_loop = asyncio.get_event_loop()` for threading bridge
- **Main Window:** Created in startup with size (1200, 900)

**Key Methods:**
```python
def startup(self):                          # Line 50 - Initialize app, create UI
def setup_theme(self):                      # Line 124 - Dark mode detection
def setup_design_language(self):            # Line 137 - Define spacing/colors/typography
def build_ui(self):                         # Line 322 - Construct entire UI
```

**Functionality:**
- ✅ Dark mode detection via `darkdetect` library
- ✅ System theme adaptation (colors, typography)
- ✅ 8pt grid spacing system (Apple HIG compliant)
- ✅ Window size: 1200x900 (HIG compliant)
- ✅ First-time setup check for MusicBrainz database

---

### 2. File Selection & Processing

#### 2.1 File Selection
**Current Implementation:**
```python
async def browse_file(self, widget):        # Line 1455 - File browser dialog
def detect_file_type(self):                 # Line 1625 - Auto-detect CSV format
```

**Supported CSV Formats:**
1. **Play Activity** - Standard Apple Music export
2. **Play History Daily Tracks** - Daily aggregated format
3. **Recently Played Tracks** - Alternative export format
4. **Generic CSV** - Fallback for unknown formats

**Detection Logic:**
- Checks filename for patterns ("Play Activity", "Play History", "Recently Played")
- Falls back to "Play Activity" if pattern not found
- Updates UI with detected file type

**Functionality:**
- ✅ File browser with CSV filter (.csv extension)
- ✅ Automatic file type detection
- ✅ File path validation
- ✅ File size calculation
- ✅ Row count estimation
- ✅ UI updates with file info

#### 2.2 CSV Processing Modes

**Mode 1: Two-Phase Processing (Default)**
```python
def process_csv_two_phase(self):            # Line 1722 - Sync version (threading)
async def process_csv_two_phase_async(self): # Line 1759 - Async version
```

**Process Flow:**
1. Load entire CSV into memory
2. Convert to Last.fm format (no artist search)
3. Display results
4. **Separate step:** User can optionally search for missing artists

**Mode 2: Chunked Processing (Large Files)**
```python
def process_csv_in_chunks(self, encoding, chunk_size, file_type):  # Line 2703
def process_csv_data_chunked(self, file_type):                      # Line 3147
```

**Chunking Logic:**
- Default chunk size: 10,000 rows
- Processes in batches to avoid memory exhaustion
- Updates progress bar between chunks
- Yields control to event loop with `asyncio.sleep(0.001)`

**Mode 3: DuckDB Processing (Ultra-Fast)**
```python
def process_csv_data_with_duckdb(self, file_type):  # Line 2887
```

**DuckDB Features:**
- SQL-based CSV querying without loading into memory
- Direct file reading with `read_csv()` function
- Automatic data type handling
- Cleanup of empty/whitespace values

---

### 3. Music Search Integration

#### 3.1 Dual Provider System

**Providers:**
1. **MusicBrainz** (Offline, ~2GB database)
   - DuckDB-based search
   - 1-5ms average search time
   - Optimized indices for artist/track/album

2. **iTunes API** (Online, rate-limited)
   - 20 requests/minute limit
   - Fallback when MusicBrainz fails
   - Adaptive rate limiting

**Provider Selection:**
```python
def on_musicbrainz_selected(self, widget):  # Line 4862
def on_itunes_selected(self, widget):       # Line 4874
```

**Search Flow:**
```python
async def search_artist_for_track(self, track_name, album_name, strict_provider):  # Line 3757
def search_itunes_api(self, track_name, album_name):  # Line 3787
```

**Functionality:**
- ✅ Provider selection via radio buttons
- ✅ Automatic fallback from MusicBrainz to iTunes
- ✅ Manual provider override option
- ✅ Search statistics tracking (hits, timing, rate limits)

#### 3.2 Rate Limiting (iTunes API)

**Current Implementation:**
```python
def check_api_rate_limit(self):             # Line 3764 - Check if rate limited
def on_rate_limit_hit(self, sleep_time):    # Line 4592 - Handle rate limit
def on_rate_limit_wait(self, total_wait_time):  # Line 4632 - Show countdown
def skip_current_wait(self, widget):        # Line 4752 - Skip wait button
```

**Rate Limit Features:**
- ✅ Tracks last 20 API calls in deque
- ✅ Enforces 20 requests/minute (3-second spacing)
- ✅ Countdown timer in UI showing wait time
- ✅ "Skip Wait" button to bypass (reduces rate to respect limit)
- ✅ Adaptive rate limiting based on server responses
- ✅ Automatic retry on 429 errors

**UI Updates:**
- Progress bar shows "Waiting for rate limit..."
- Timer displays remaining seconds (e.g., "45s remaining")
- Skip button becomes enabled during wait
- Stats panel shows rate limit hit count

#### 3.3 Missing Artist Handling

**Detection:**
```python
def has_missing_artist(self, row, headers):  # Line 7106
def count_missing_artists(self):             # Line 7126
```

**Reprocessing:**
```python
async def reprocess_missing_artists(self, widget, force_provider):  # Line 5906
def reprocess_missing_artists_thread(self, missing_artists_tracks, provider):  # Line 6195
```

**Process Flow:**
1. User completes initial conversion
2. App counts rows with empty artist field
3. Shows dialog: "Found X missing artists - search now?"
4. User chooses provider (MusicBrainz or iTunes)
5. **Threading:** Spawns daemon thread for background search
6. **UI Updates:** Uses `asyncio.run_coroutine_threadsafe()` bridge
7. Results inserted into existing data
8. Auto-saves after completion

**Functionality:**
- ✅ Missing artist count badge in UI
- ✅ Provider selection dialog
- ✅ Time estimate based on provider
- ✅ Pause/resume capability
- ✅ Progress tracking with detailed stats
- ✅ Auto-save on completion

---

### 4. Threading & Async Architecture (⚠️ CRITICAL ISSUE)

#### 4.1 Current Mixed Implementation

**Threading Components:**
```python
self.processing_thread = None               # Line 60 - Main processing thread
self.reprocessing_thread = None             # Line 6159 - Reprocess thread
self.main_loop = asyncio.get_event_loop()   # Line 55 - Stored event loop
```

**Thread Creation Points:**
1. **CSV Processing** (line 1722):
   ```python
   def process_csv_two_phase(self):
       # Sync version - runs in thread
   ```

2. **Missing Artist Reprocessing** (line 6159):
   ```python
   self.reprocessing_thread = threading.Thread(
       target=self.reprocess_missing_artists_thread,
       args=(missing_artists, current_provider),
       daemon=True  # ⚠️ Can be killed during shutdown
   )
   ```

#### 4.2 Thread-to-Async Bridge Pattern

**Bridge Method (Used 40+ times):**
```python
# From sync thread context -> async UI update
asyncio.run_coroutine_threadsafe(
    self._update_progress_ui(),
    self.main_loop
)
```

**Bridge Usage Locations:**
- Line 1714: Reset search button
- Line 1757: Reset buttons after processing
- Line 2466: Reset with parameters
- Line 4046-4186: Multiple progress/UI updates during processing
- Line 4199-4208: Results and log updates
- Line 4229: Preview updates
- Line 4436-4503: Progress bar and timer updates
- Line 4552-4699: Skip button state changes
- Line 6350-7271: Reprocessing UI updates

**Problems with Current Approach:**
- ⚠️ Race conditions if event loop closed early
- ⚠️ Daemon threads can be killed mid-operation
- ⚠️ No guarantee of UI update order
- ⚠️ Complex error handling across thread boundaries
- ⚠️ Difficult to debug deadlocks

#### 4.3 Async Methods (Correct Pattern)

**Pure Async Methods:**
```python
async def browse_file(self, widget):                    # Line 1455
async def convert_csv(self, widget):                    # Line 1670
async def process_csv_two_phase_async(self):            # Line 1759
async def load_entire_csv_async(self, file_path, file_type):  # Line 1803
async def detect_and_handle_converted_csv(self, file_path, df):  # Line 1384
```

**These work correctly** - pure async, no threading needed.

---

### 5. UI Components & Layout

#### 5.1 Main Window Structure

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Header Section (Logo + Title)                          │
├─────────────────┬───────────────────────────────────────┤
│ Settings Panel  │ Main Content Area                     │
│ (Left Sidebar)  │                                       │
│                 │ - File Selection                      │
│ - Provider      │ - Progress Section                    │
│ - Database      │ - Results Display                     │
│ - iTunes API    │ - Preview Section                     │
│ - Statistics    │ - Action Buttons                      │
│                 │                                       │
└─────────────────┴───────────────────────────────────────┘
```

**Creation Methods:**
```python
def create_header_section(self):            # Line 389
def create_content_area(self):              # Line 440
def create_comprehensive_settings_panel(self): # Line 459
def create_provider_section(self):          # Line 507
def create_database_section(self):          # Line 559
def create_itunes_api_section(self):        # Line 778
def create_file_selection_section(self):    # Line 978
def create_results_section(self):           # Line 1056
def create_preview_section(self):           # Line 1245
def create_progress_section(self):          # Line 1301
def create_search_provider_stats(self):     # Line 1365
```

#### 5.2 Key UI Widgets

**File Selection:**
- `self.select_file_button` - Browse button
- `self.file_path_label` - Shows selected file path
- `self.file_type_selection` - Dropdown for format override

**Progress:**
- `self.progress_bar` - Horizontal progress bar (0-1 value)
- `self.progress_label` - Status message
- `self.timer_label` - Rate limit countdown

**Results:**
- `self.results_display` - MultilineTextInput (readonly)
- `self.preview_table` - Table widget for data preview
- `self.missing_artist_badge` - Label showing missing count

**Buttons:**
- `self.convert_button` - Start conversion
- `self.copy_button` - Copy to clipboard (enabled after processing)
- `self.save_button` - Save to file (enabled after processing)
- `self.reprocess_button` - Search for missing artists
- `self.skip_wait_button` - Skip rate limit wait

**Settings:**
- `self.musicbrainz_radio` - MusicBrainz provider radio button
- `self.itunes_radio` - iTunes provider radio button
- `self.database_status_label` - Shows database state
- `self.adaptive_rate_limit_switch` - Toggle adaptive limiting

#### 5.3 UI Update Pattern

**Sync Method → Async UI Update:**
```python
def update_results(self, text):             # Line 4194 - Sync API
    # Appends to results buffer
    self.results_text_buffer.append(text)
    # Triggers async UI update via bridge
    asyncio.run_coroutine_threadsafe(
        self._update_results_ui(),
        self.main_loop
    )

async def _update_results_ui(self):         # Line 4201 - Async implementation
    # Actually updates the Toga widget
    self.results_display.value = "\n".join(self.results_text_buffer)
```

**This pattern is used for:**
- `update_results()` / `_update_results_ui()` - Results display
- `update_progress()` / `_update_progress_ui()` - Progress bar
- `update_preview()` / `_update_preview_ui()` - Preview table
- `append_log()` / `_append_log_ui()` - Log append
- `update_api_status()` / `_update_api_status_ui()` - API status
- `show_skip_button()` / `_show_skip_button_ui()` - Skip button visibility

---

### 6. Database Management

#### 6.1 MusicBrainz Database

**Download:**
```python
async def download_database(self, widget):   # Line 4892
async def run_database_download(self):      # Line 5020
```

**Features:**
- ✅ Downloads canonical MusicBrainz data (~2GB compressed)
- ✅ Auto-detects latest version from exports
- ✅ Shows progress dialog with percentage
- ✅ Cancellable download
- ✅ Automatic decompression (.tar.zst format)
- ✅ Updates UI status on completion

**Manual Import:**
```python
async def manual_import_database(self, widget):  # Line 5346
async def run_database_import(self, file_path):  # Line 5164
```

**Import Features:**
- ✅ File picker for local .tar.zst files
- ✅ Progress tracking
- ✅ Validation of database structure
- ✅ Error handling for corrupt files

**Optimization:**
```python
async def optimize_musicbrainz_async(self):      # Line 1887
async def optimize_musicbrainz_handler(self, widget):  # Line 6735
def start_background_optimization(self):         # Line 7240
```

**Optimization Features:**
- ✅ Rebuilds search indices for faster lookups
- ✅ Background thread execution (⚠️ uses threading)
- ✅ Progress dialog with percentage
- ✅ Can take 5-15 minutes depending on hardware

#### 6.2 Database Status & Management

**Status Checking:**
```python
async def check_database_status(self):       # Line 6582
def update_database_status(self):            # Line 6586
```

**Database States:**
- ✅ **Not Downloaded** - Red indicator, download button enabled
- ✅ **Downloaded** - Green indicator, all features enabled
- ✅ **Optimized** - Shows optimization status
- ✅ **Update Available** - Shows when newer version exists

**Management Actions:**
```python
async def delete_database(self, widget):     # Line 6684 - Delete database
async def reveal_database_location(self, widget):  # Line 6712 - Open in file manager
async def check_for_updates(self, widget):  # Line 5215 - Check for newer version
```

**File Manager Integration (⚠️ SECURITY ISSUE):**
```python
# Line 6719-6723 - Uses os.system() - VULNERABLE
if sys.platform == "darwin":
    os.system(f'open -R "{db_path}"')        # ⚠️ Shell injection risk
elif sys.platform == "win32":
    os.system(f'explorer /select,"{db_path}"')
else:
    os.system(f'xdg-open "{os.path.dirname(db_path)}"')
```

---

### 7. Data Export & Saving

#### 7.1 Save Processed Results

**Main Save:**
```python
async def save_results(self, widget):        # Line 5632
def save_processed_file_to_path(self, df, file_path):  # Line 5726
```

**Save Features:**
- ✅ File save dialog with default name pattern
- ✅ Timestamp-based default filename
- ✅ CSV format with UTF-8 encoding
- ✅ Last.fm compatible column headers
- ✅ Auto-save after missing artist reprocessing
- ✅ Tracks last saved file path for reprocessing

**Export Format:**
```csv
artist,track,album,date
Artist Name,Track Name,Album Name,1234567890
```

**Date Format:** Unix timestamp (seconds since epoch)

#### 7.2 Export Missing Artists List

**Export Function:**
```python
async def save_missing_artists_csv(self, widget):  # Line 5562
```

**Features:**
- ✅ Exports list of tracks with missing artists
- ✅ Includes track name, album name
- ✅ Useful for manual lookups
- ✅ CSV format for spreadsheet import

#### 7.3 Copy to Clipboard

**Copy Function:**
```python
async def copy_results(self, widget):        # Line 5509
```

**Features:**
- ✅ Copies entire processed CSV to clipboard
- ✅ Ready for paste into Last.fm import
- ✅ Uses `pyperclip` library
- ✅ Works cross-platform

---

### 8. Preview System

#### 8.1 Immediate Preview (Post-Selection)

**Preview Loading:**
```python
async def load_immediate_preview(self):      # Line 4279
```

**Features:**
- ✅ Loads first 100 rows of CSV
- ✅ Displays in table widget
- ✅ Shows column headers
- ✅ Auto-detects encoding (UTF-8, Latin-1, Windows-1252)
- ✅ Handles large files gracefully (only reads first 100 rows)

#### 8.2 Play Activity Preview

**Specialized Preview:**
```python
async def load_play_activity_preview(self):  # Line 4367
```

**Features:**
- ✅ Enhanced preview for Play Activity format
- ✅ Shows artist, track, album, play date
- ✅ Formats timestamps for readability
- ✅ Handles missing values gracefully

#### 8.3 Results Preview (Post-Processing)

**Update Preview:**
```python
def update_preview(self, df, total_rows):    # Line 4223
async def _update_preview_ui(self):          # Line 4231
```

**Features:**
- ✅ Updates after conversion
- ✅ Shows first 100 rows of results
- ✅ Displays in Last.fm format
- ✅ Shows total row count
- ✅ Helps user verify conversion accuracy

---

### 9. Error Handling & Validation

#### 9.1 File Validation

**Checks:**
- ✅ File exists and is readable
- ✅ File is a CSV format
- ✅ File has required columns for detected type
- ✅ Encoding is supported
- ✅ File size vs. available RAM check

**RAM Check:**
```python
def check_file_size_and_ram(self, file_path):  # Line 7071
```

**Features:**
- ✅ Uses `psutil` to check available memory
- ✅ Warns if file > 50% of available RAM
- ✅ Recommends chunked processing for large files

#### 9.2 CSV Format Validation

**Detection:**
```python
def detect_file_type(self):                  # Line 1625
```

**Validation Checks:**
- ✅ Checks for expected column headers
- ✅ Validates timestamp formats
- ✅ Handles missing optional columns
- ✅ Falls back to generic processing if format unknown

#### 9.3 Resume Detection

**Converted CSV Detection:**
```python
async def detect_and_handle_converted_csv(self, file_path, df):  # Line 1384
```

**Features:**
- ✅ Detects if CSV is already in Last.fm format
- ✅ Shows dialog asking if user wants to reprocess
- ✅ Prevents accidental re-conversion
- ✅ Allows manual override

---

### 10. Settings & Configuration

#### 10.1 Settings Storage

**Location:** `~/.apple_music_converter/settings.json`

**Stored Settings:**
```json
{
  "search_provider": "musicbrainz",
  "enable_fallback": true,
  "rate_limit": 20,
  "adaptive_rate_limit": true,
  "parallel_mode": false,
  "last_file_path": "/path/to/last/file.csv",
  "window_size": [1200, 900],
  "theme": "auto"
}
```

#### 10.2 Provider Settings

**MusicBrainz:**
- ✅ Database path configuration
- ✅ Optimization status
- ✅ Index rebuild options

**iTunes API:**
- ✅ Rate limit setting (default: 20/min)
- ✅ Adaptive rate limiting toggle
- ✅ Parallel mode (experimental)
- ✅ Fallback behavior configuration

#### 10.3 UI Settings

**Callbacks:**
```python
def on_fallback_changed(self, widget):       # Line 6815
def on_itunes_api_changed(self, widget):     # Line 6819
def on_adaptive_rate_limit_changed(self, widget):  # Line 6824
def on_parallel_mode_changed(self, widget):  # Line 6856
def save_rate_limit(self, widget):           # Line 6869
```

**Features:**
- ✅ Settings persist across sessions
- ✅ Real-time validation of inputs
- ✅ Immediate effect on behavior
- ✅ Reset to defaults option

---

### 11. Statistics & Analytics

#### 11.1 Search Statistics

**Tracking:**
```python
def update_stats_display(self):              # Line 4766, Line 7047
```

**Tracked Metrics:**
- ✅ MusicBrainz hits (count + avg time)
- ✅ iTunes API hits (count + avg time)
- ✅ Rate limit hits (count + last time)
- ✅ Total processing time
- ✅ Tracks processed per second
- ✅ Success rate percentage

**Display Format:**
```
MusicBrainz: 1,234 tracks (avg 2.3ms)
iTunes API: 56 tracks (avg 450ms)
Rate Limits: 3 hits (last: 2:34 PM)
```

#### 11.2 Progress Statistics

**Real-Time Stats:**
- ✅ Current track being processed
- ✅ Percentage complete
- ✅ Estimated time remaining
- ✅ Tracks per second
- ✅ Missing artist count

**Time Estimation:**
```python
def update_time_estimate(self):              # Line 6987
```

**Features:**
- ✅ Calculates based on average processing speed
- ✅ Adjusts for rate limiting delays
- ✅ Updates every few seconds
- ✅ Shows in human-readable format (e.g., "2m 34s remaining")

---

### 12. First-Time Setup

**Setup Flow:**
```python
def check_first_time_setup(self):            # Line 7291
```

**First-Time Experience:**
1. App checks for MusicBrainz database
2. If not found, shows welcome dialog
3. Explains provider options:
   - MusicBrainz: Fast, offline, requires 2GB download
   - iTunes API: Online, rate-limited, no download needed
4. User chooses provider or downloads database
5. Settings saved for future sessions

**Features:**
- ✅ One-time setup wizard
- ✅ Clear explanation of tradeoffs
- ✅ Option to skip and use iTunes only
- ✅ Database download integrated into setup

---

### 13. Cross-Platform Support

#### 13.1 Platform Detection

**Platform-Specific Code:**
```python
if sys.platform == "darwin":      # macOS
    # macOS-specific code
elif sys.platform == "win32":     # Windows
    # Windows-specific code
else:                              # Linux
    # Linux-specific code
```

**Platform Differences:**

**macOS:**
- ✅ Uses `open -R` for file reveal
- ✅ Native Toga/Cocoa widgets
- ✅ Full code signing support
- ✅ Notarization integration

**Windows:**
- ✅ Uses `explorer /select,` for file reveal
- ✅ Native Toga/WinForms widgets
- ✅ Windows-specific path handling

**Linux:**
- ✅ Uses `xdg-open` for file reveal
- ✅ GTK-based widgets
- ✅ System package dependencies

#### 13.2 Path Handling

**Cross-Platform Paths:**
- ✅ Uses `pathlib.Path` for all file operations
- ✅ Automatic path separator handling
- ✅ Home directory expansion (`~` support)
- ✅ UNC path support on Windows

---

## 📋 Method Inventory & Checklist

### ✅ Completed Documentation

- [x] Application Lifecycle (startup, theme, design)
- [x] File Selection & Processing
- [x] Music Search Integration (dual provider)
- [x] Rate Limiting (iTunes API)
- [x] Missing Artist Handling
- [x] Threading & Async Architecture
- [x] UI Components & Layout
- [x] Database Management
- [x] Data Export & Saving
- [x] Preview System
- [x] Error Handling & Validation
- [x] Settings & Configuration
- [x] Statistics & Analytics
- [x] First-Time Setup
- [x] Cross-Platform Support

### Method Categories

**Lifecycle Methods (6):**
- [x] `startup()` - App initialization
- [x] `setup_theme()` - Dark mode
- [x] `setup_design_language()` - Design tokens
- [x] `build_ui()` - UI construction
- [x] `check_first_time_setup()` - Setup wizard
- [x] `check_database_status()` - DB status

**UI Creation Methods (15):**
- [x] `create_header_section()`
- [x] `create_content_area()`
- [x] `create_comprehensive_settings_panel()`
- [x] `create_provider_section()`
- [x] `create_database_section()`
- [x] `create_itunes_api_section()`
- [x] `create_file_selection_section()`
- [x] `create_results_section()`
- [x] `create_preview_section()`
- [x] `create_progress_section()`
- [x] `create_search_provider_stats()`
- [x] `create_section_header()`
- [x] `sidebar_heading()`
- [x] `section_divider()`
- [x] `get_pack_style()` - Helper

**File Processing Methods (25):**
- [x] `browse_file()` - File selection
- [x] `detect_file_type()` - Format detection
- [x] `convert_csv()` - Main conversion
- [x] `process_csv_two_phase()` - Sync version
- [x] `process_csv_two_phase_async()` - Async version
- [x] `load_entire_csv()` - Sync load
- [x] `load_entire_csv_async()` - Async load
- [x] `process_csv_in_chunks()` - Chunked processing
- [x] `process_csv_data()` - Data processor
- [x] `process_csv_data_small()` - Small file processor
- [x] `process_csv_data_chunked()` - Chunked processor
- [x] `process_csv_data_with_duckdb()` - DuckDB processor
- [x] `process_play_activity_data()` - Play Activity
- [x] `process_play_activity_data_small()` - Play Activity (small)
- [x] `process_play_activity_data_with_duckdb()` - Play Activity (DuckDB)
- [x] `process_play_activity_data_chunked()` - Play Activity (chunked)
- [x] `process_play_history_data_small()` - Play History
- [x] `process_recently_played_data_small()` - Recently Played
- [x] `process_generic_csv_data_small()` - Generic CSV
- [x] `normalize_track_data()` - Data normalization
- [x] `normalize_timestamp()` - Timestamp handling
- [x] `convert_to_final_format()` - Final conversion
- [x] `detect_and_handle_converted_csv()` - Resume detection
- [x] `check_file_size_and_ram()` - Memory check
- [x] `analyze_file_comprehensive()` - File analysis

**Music Search Methods (10):**
- [x] `search_artist_for_track()` - Main search
- [x] `search_itunes_api()` - iTunes search
- [x] `process_with_musicbrainz()` - MusicBrainz processing
- [x] `process_with_musicbrainz_async()` - MusicBrainz (async)
- [x] `process_missing_with_itunes()` - iTunes processing
- [x] `process_missing_with_itunes_async()` - iTunes (async)
- [x] `process_missing_with_musicbrainz_async()` - MusicBrainz missing
- [x] `reprocess_missing_artists()` - Reprocess UI
- [x] `reprocess_missing_artists_thread()` - Reprocess worker
- [x] `count_missing_artists()` - Count missing

**Rate Limiting Methods (11):**
- [x] `check_api_rate_limit()` - Check if limited
- [x] `on_rate_limit_hit()` - Handle limit
- [x] `on_rate_limit_wait()` - Wait handler
- [x] `on_actual_rate_limit_detected()` - Detection
- [x] `on_rate_limit_discovered()` - Discovery
- [x] `skip_current_wait()` - Skip wait
- [x] `skip_wait()` - Skip handler
- [x] `update_rate_limit_timer()` - Timer update
- [x] `show_skip_button()` - Show button
- [x] `hide_skip_button()` - Hide button
- [x] `_interruptible_wait()` - Interruptible sleep

**UI Update Methods (30+):**
- [x] `update_results()` / `_update_results_ui()`
- [x] `update_progress()` / `_update_progress_ui()`
- [x] `update_preview()` / `_update_preview_ui()`
- [x] `update_api_status()` / `_update_api_status_ui()`
- [x] `update_database_status()`
- [x] `update_musicbrainz_ui_state()`
- [x] `update_itunes_ui_state()`
- [x] `update_stats_display()`
- [x] `update_search_button_state()`
- [x] `update_missing_artist_count()`
- [x] `update_save_status()`
- [x] `update_time_estimate()`
- [x] `append_log()` / `_append_log_ui()`
- [x] Plus 15+ more UI update helpers

**Database Methods (12):**
- [x] `download_database()` - Download UI
- [x] `run_database_download()` - Download worker
- [x] `download_complete()` - Completion handler
- [x] `download_failed()` - Error handler
- [x] `cancel_download()` - Cancel
- [x] `manual_import_database()` - Import UI
- [x] `run_database_import()` - Import worker
- [x] `import_complete()` - Import success
- [x] `import_failed()` - Import error
- [x] `delete_database()` - Delete DB
- [x] `reveal_database_location()` - Open location
- [x] `optimize_musicbrainz_handler()` - Optimize

**Export Methods (5):**
- [x] `save_results()` - Save CSV
- [x] `save_processed_file_to_path()` - Save helper
- [x] `save_missing_artists_csv()` - Save missing
- [x] `copy_results()` - Copy to clipboard
- [x] `format_file_size()` - Size formatter

**Preview Methods (4):**
- [x] `load_immediate_preview()` - Initial preview
- [x] `load_play_activity_preview()` - Play Activity preview
- [x] `update_preview()` - Preview updater
- [x] `_update_preview_ui()` - Preview UI

**Settings Methods (8):**
- [x] `on_musicbrainz_selected()` - Provider change
- [x] `on_itunes_selected()` - Provider change
- [x] `on_fallback_changed()` - Fallback toggle
- [x] `on_itunes_api_changed()` - API change
- [x] `on_adaptive_rate_limit_changed()` - Rate limit toggle
- [x] `on_parallel_mode_changed()` - Parallel toggle
- [x] `save_rate_limit()` - Save rate limit
- [x] `check_for_updates()` - Update check

**Process Control Methods (6):**
- [x] `toggle_process_pause()` - Pause/resume
- [x] `stop_process()` - Stop processing
- [x] `enable_copy_save_buttons()` - Enable buttons
- [x] `reset_processing_stats()` - Reset stats
- [x] `finalize_processing()` - Finish processing
- [x] `finalize_processing_async()` - Finish (async)

---

## 🔧 Implementation Details

### State Variables

**Processing State:**
```python
self.current_file_path = None               # Selected file
self.detected_file_type = None              # Auto-detected type
self.processed_df = None                    # Processed DataFrame
self.file_size = 0                          # File size in bytes
self.row_count = 0                          # Total rows
```

**Search State:**
```python
self.musicbrainz_found = 0                  # MusicBrainz hits
self.itunes_found = 0                       # iTunes hits
self.musicbrainz_count = 0                  # Total MusicBrainz
self.itunes_count = 0                       # Total iTunes
self.musicbrainz_search_time = 0            # Total MB time
self.itunes_search_time = 0                 # Total iTunes time
self.active_search_provider = None          # Current provider
```

**Rate Limiting State:**
```python
self.api_calls = deque(maxlen=20)           # Call history
self.api_lock = Lock()                      # Thread-safe lock
self.rate_limit_hits = 0                    # Limit hit count
self.last_rate_limit_time = None            # Last hit time
self.wait_duration = 0                      # Current wait
self.skip_wait_requested = False            # Skip flag
```

**Threading State (⚠️ TO BE REMOVED):**
```python
self.processing_thread = None               # Main thread
self.reprocessing_thread = None             # Reprocess thread
self.main_loop = asyncio.get_event_loop()   # Event loop
self.pause_itunes_search_flag = False       # Pause flag
self.stop_itunes_search_flag = False        # Stop flag
```

**UI State:**
```python
self.results_text_buffer = []               # Results buffer
self.last_output_file = None                # Last saved file
self.failed_requests = []                   # Failed iTunes requests
```

### Data Flow

**Main Conversion Flow:**
```
1. User selects CSV file
   ↓
2. File type auto-detected
   ↓
3. Preview loaded (first 100 rows)
   ↓
4. User clicks "Convert"
   ↓
5. CSV loaded into memory OR processed in chunks
   ↓
6. Data normalized to internal format
   ↓
7. Converted to Last.fm format (no artist search yet)
   ↓
8. Results displayed in preview
   ↓
9. Copy/Save buttons enabled
   ↓
10. Missing artist count calculated
    ↓
11. User optionally searches for missing artists
```

**Missing Artist Search Flow:**
```
1. Count rows with empty artist field
   ↓
2. Show dialog with count and provider choice
   ↓
3. User selects provider (MusicBrainz/iTunes)
   ↓
4. ⚠️ Daemon thread spawned
   ↓
5. For each missing artist:
   - Search provider API
   - Update progress via bridge
   - Handle rate limiting
   - Insert found artist into data
   ↓
6. Auto-save results
   ↓
7. Update UI with success count
```

---

## 🎯 Critical Patterns to Preserve

### 1. **Pause/Resume Functionality**
- User can pause iTunes API searches mid-operation
- State flags: `pause_itunes_search_flag`, `stop_itunes_search_flag`
- **MUST PRESERVE** in async refactor

### 2. **Rate Limit Skip**
- User can skip current rate limit wait
- Reduces effective rate to respect overall limit
- **MUST PRESERVE** in async refactor

### 3. **Chunked Processing**
- Large files (>100MB) use chunked processing
- Prevents memory exhaustion
- **MUST PRESERVE** - already working correctly

### 4. **Provider Fallback**
- MusicBrainz → iTunes automatic fallback
- User can force specific provider
- **MUST PRESERVE** - critical feature

### 5. **Auto-Save After Reprocessing**
- Results auto-saved after missing artist search
- Uses timestamp-based filename
- **MUST PRESERVE** - user expectation

### 6. **Resume Detection**
- Detects if CSV already converted
- Prevents accidental re-conversion
- **MUST PRESERVE** - data safety feature

### 7. **Progress Tracking**
- Real-time progress percentage
- Time estimates
- Detailed statistics
- **MUST PRESERVE** - core UX feature

---

## ⚠️ Known Issues to Fix

### Critical Issues (From CRITICAL_FIXES_PLAN.md):

1. **Mixed Threading/Async** - 40+ instances of bridge pattern
2. **Shell Injection** - `os.system()` at lines 6719-6723
3. **Zero Test Coverage** - All tests deleted
4. **Memory Issues** - 2 instances of full CSV loads (skipping per user request)
5. **tkinter Residue** - Comments and patterns from old framework

---

## 📊 Statistics

**Total Methods:** ~150+
**Total Lines:** 7,310
**Async Methods:** ~30
**Sync Methods:** ~120
**Threading Bridges:** 40+
**UI Update Methods:** 30+
**Event Handlers:** 25+

---

**END OF DOCUMENTATION**

This document serves as the source of truth for existing functionality.
All changes must preserve the documented behavior unless explicitly marked for removal.
