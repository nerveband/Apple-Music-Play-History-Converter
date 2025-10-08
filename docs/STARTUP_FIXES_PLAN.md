# Startup Performance & Bug Fixes Plan

## ✅ Completed
1. **Splash Screen Module** - Created `splash_screen.py` with cross-platform Toga implementation
2. **Path Separator Fix** - Fixed mixed `/` and `\` in iTunes debug log path (line 6278)

## 🔄 In Progress

### 1. Splash Screen Integration
**Location**: `apple_music_play_history_converter.py` startup() method

**Changes Needed**:
```python
def startup(self):
    # STEP 1: Show splash screen FIRST
    from .splash_screen import SplashScreen
    self.splash = SplashScreen(self)
    self.splash.create()

    # STEP 2: Load components with progress updates
    await self.splash.update_progress("Initializing services...", 1)
    self._toga_event_loop = asyncio.get_running_loop()

    await self.splash.update_progress("Loading search service...", 2)
    self.music_search_service = MusicSearchService()

    await self.splash.update_progress("Building interface...", 3)
    self.build_ui()

    await self.splash.update_progress("Checking database...", 4)
    # Move to background (non-blocking)
    asyncio.create_task(self._background_startup_checks())

    await self.splash.update_progress("Ready!", 5)
    self.main_window.show()

    # STEP 3: Close splash
    self.splash.close()
```

### 2. Background Database Checks
**Problem**: `update_database_status()` and `check_first_time_setup()` block startup

**Solution**: Create async background task
```python
async def _background_startup_checks(self):
    """Run database checks in background after window shows."""
    await asyncio.sleep(0.1)  # Let window render first
    self.check_first_time_setup()
    self.update_database_status()
```

### 3. iTunes API Rate Limiting on Windows
**Problem**: Adaptive rate limit settings might not persist or work on Windows

**Investigation Needed**:
- Check if settings.json is being read/written correctly on Windows
- Verify threading model works with rate limit callbacks
- Test parallel vs sequential mode on Windows

**Files to Check**:
- `music_search_service_v2.py` - rate limiting logic
- `app_directories.py` - settings path on Windows
- iTunes API callback mechanism

### 4. MusicBrainz "No Internet" Error
**Problem**: iTunes API works but MusicBrainz download fails with "no internet"

**Likely Causes**:
1. Different network test mechanism
2. Firewall blocks different ports/protocols
3. SSL/TLS certificate issues
4. Timeout too short for slower connections

**Files to Check**:
- `musicbrainz_manager_v2_optimized.py` - download logic
- `music_search_service_v2.py` - network diagnostics
- Compare iTunes vs MusicBrainz network checks

**Fix Strategy**:
- Use same network test as iTunes (successful test means internet works)
- Skip redundant network checks if iTunes already succeeded
- Better error messages (distinguish "no internet" from "download failed")

## 📊 Expected Impact

| Fix | Startup Reduction | User Experience |
|-----|------------------|-----------------|
| Splash Screen | -60% perceived | User sees progress immediately |
| Background DB Check | -0.5s real | Window appears instantly |
| Path Separators | N/A | Fixes confusion on Windows |
| iTunes Rate Limit | N/A | Fixes search functionality |
| MusicBrainz Download | N/A | Fixes offline database setup |

## 🎯 Implementation Order

1. ✅ Path separator fix (done)
2. Splash screen integration
3. Background database checks
4. Test Windows builds
5. Investigate & fix iTunes rate limiting
6. Investigate & fix MusicBrainz connectivity

## 🧪 Testing Required

- [ ] macOS: Splash screen displays correctly
- [ ] macOS: Database checks don't block window
- [ ] macOS: Paths use `/` consistently
- [ ] Windows: Splash screen displays correctly
- [ ] Windows: Database checks don't block window
- [ ] Windows: Paths use `\` consistently (no mixed separators)
- [ ] Windows: iTunes API rate limiting works
- [ ] Windows: iTunes API parallel mode works
- [ ] Windows: MusicBrainz download succeeds
- [ ] Slow hardware: App feels responsive throughout startup
