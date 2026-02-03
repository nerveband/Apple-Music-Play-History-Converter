# Remaining Work & Testing Strategy

## Status Overview
**Migration Status**: ✅ Toga to Tauri Migration Code Complete.
**Basic Verification**: ✅ Automated "Happy Path" test (Load -> Search) is injected and verified.

## What is Left?

### 1. Code Cleanup
- **Remove Injection**: The temporary automated test logic in `App.tsx` (auto-load/auto-start) needs to be removed or moved to a dedicated test mode.
- **Refactoring**: Ensure no Toga-related implementation code remains in the active path (legacy files can be archived).

### 2. Production Hardening
- **Python Sidecar Path**: 
  - *Current*: `../../` (Development)
  - *Required*: For a release build, the path logic in `sidecar.rs` and `sidecar.py` must dynamically detect the bundled resource directory provided by Tauri's sidecar bundling.
- **Error Handling**: Enhance robustness against invalid CSVs or network failures.

### 3. Edge-Case Verification
We need to verify the following scenarios which are not covered by the current simple test:
- **Pause/Resume**: Does the search actually stop and restart without duplicating or skipping tracks?
- **Stop**: does it cleanly terminate the python thread?
- **Export**: 
  - Verify JSON export structure.
  - Verify XML export structure.
  - Verify iTunes XML compatibility.

## Testing Strategy: "Self-Driving" Test Dashboard

To verify full GUI functionality programmatically without manual clicking:

### Proposed "Test Mode"
We can implement a hidden or debug-only "Test Dashboard" in the application.

**Features:**
1.  **Scenario Runner**: A drop-down to select a test scenario (e.g., "Full E2E", "Export Test", "Pause/Resume Test").
2.  **Auto-Pilot**: The app simulates user actions (programmatically invoking `startSearch`, `togglePause`, etc.) with delays.
3.  **Verification**: 
    - The app checks internal state (e.g., "Is `isPaused` true?").
    - The app writes a "Report Card" to a log file or displays it on screen.

### Benefits
- **Reproducible**: Run the exact same test sequence every time.
- **Visual**: You can watch the app "work itself".
- **Comprehensive**: Tests the actual UI state and React hooks, not just the backend commands.

### Next Steps
1.  Approve creation of `TestDashboard.tsx`.
2.  Define the list of scenarios to implement.
