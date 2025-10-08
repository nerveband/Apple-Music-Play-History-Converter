# Toga/Rubicon GIL Crash Workaround Documentation

## Problem Summary

When quitting the app on macOS, a GIL (Global Interpreter Lock) crash occurs during Toga's event loop shutdown:

```
Fatal Python error: PyEval_SaveThread: the function must be called with the GIL held
File "rubicon/objc/eventloop.py", line 816 in stop
  self._application.terminate(None)
```

## Root Cause

The crash occurs in **Rubicon's Objective-C bridge** during NSApplication termination. This is a known limitation of Toga/Rubicon's macOS integration where the GIL state management conflicts with Python's finalization sequence.

**Crash Location**: `rubicon/objc/eventloop.py:816` → `NSApplication.terminate(None)`

## Research Findings

### Versions Affected
- **rubicon-objc**: 0.5.2 (latest as of January 2025)
- **toga**: 0.5.2 (latest as of January 2025)
- **Python**: 3.12.4
- **Platform**: macOS (Darwin 25.0.0)

### BeeWare/Toga Known Limitations
From [Toga Discussion #2717](https://github.com/beeware/toga/discussions/2717):
- Toga currently lacks comprehensive signal handling support
- `on_exit()` doesn't run for SIGINT/SIGTERM
- Community acknowledges need for "cleanup that runs no matter what"
- This is an area under active discussion for future improvements

### Rubicon Release History
Checked releases 0.4.1 through 0.5.2:
- 0.4.3: Fixed race conditions and event loop issues on secondary threads
- 0.5.0-0.5.2: No specific fixes for NSApplication.terminate() GIL crash
- Issue persists in latest release

## Solution: `os._exit()` Workaround

### Implementation

```python
def on_exit(self, widget: Optional[toga.Widget] = None, **kwargs) -> bool:
    """Clean up resources when app exits to prevent crashes."""

    # 1. Set interrupt flags
    self.is_search_interrupted = True
    self.stop_itunes_search_flag = True
    # ... other flags

    # 2. Shut down ThreadPoolExecutors
    if hasattr(self, '_default_executor') and self._default_executor:
        self._default_executor.shutdown(wait=True, cancel_futures=True)

    # 3. Close database connections (CRITICAL)
    if hasattr(self, 'music_search_service') and self.music_search_service:
        self.music_search_service.close()  # Closes DuckDB connections

    # 4. Flush output streams
    import sys
    sys.stdout.flush()
    sys.stderr.flush()

    # 5. Exit immediately to bypass Toga's buggy shutdown
    import os
    os._exit(0)  # Skip Python finalization and NSApplication.terminate()
```

### Why This is Safe

**Resources Cleaned Up BEFORE os._exit():**
- ✅ DuckDB connections closed explicitly
- ✅ ThreadPoolExecutors shut down with `wait=True`
- ✅ All async tasks canceled
- ✅ Event loops properly signaled
- ✅ Output streams flushed

**What os._exit() Skips:**
- ❌ `atexit` handlers (not needed - cleanup done)
- ❌ Python finalization (not needed - resources closed)
- ❌ Toga event loop shutdown (**THIS IS WHERE THE BUG IS**)

### Exit Code
`os._exit(0)` returns exit code 0 (success) to the operating system, identical to normal Python exit.

## Alternative Solutions Considered

### 1. Return False from on_exit()
**Status**: ❌ Not viable
**Reason**: Would prevent app from ever exiting

### 2. Upgrade rubicon-objc/toga
**Status**: ❌ Already on latest
**Versions**: Both at 0.5.2 (no newer fix available)

### 3. Fix threading/executor issues
**Status**: ❌ Not the root cause
**Reason**: Crash is in NSApplication.terminate(), not threading code

### 4. Use atexit handlers
**Status**: ❌ Doesn't help
**Reason**: Crash occurs before atexit runs, during Toga's event loop stop

### 5. Custom event loop policy
**Status**: ❌ Too invasive
**Reason**: Would require forking Rubicon to modify CocoaLifecycle.stop()

## Testing Results

**Scenario**: Immediate quit after app startup
**Before fix**: Crash with abort trap 6 (GIL error)
**After fix**: Clean exit with code 0, no crash

**Output**:
```
✅ Exit handler complete
   ℹ️  Using os._exit() to bypass Toga/Rubicon GIL crash bug
[Program exits cleanly]
```

## Future Improvements

This workaround can be removed when:
1. BeeWare fixes the NSApplication.terminate() GIL management in Rubicon
2. Toga implements comprehensive exit hooks that bypass the Objective-C bridge
3. Python 3.14+ changes GIL behavior to be more forgiving during finalization

## References

- [Toga Discussion #2717](https://github.com/beeware/toga/discussions/2717) - Exit signal handling
- [Toga Discussion #2753](https://github.com/beeware/toga/discussions/2753) - Exit process handling
- [Rubicon Releases](https://github.com/beeware/rubicon-objc/releases) - Version history
- [Rubicon Issue #128](https://github.com/beeware/rubicon-objc/issues/128) - Event loop termination

## Implementation Location

**File**: `src/apple_music_history_converter/apple_music_play_history_converter.py`
**Method**: `AppleMusicConverterApp.on_exit()`
**Lines**: 447-462

---

**Last Updated**: January 2025
**Status**: Workaround active, monitoring BeeWare for official fix
