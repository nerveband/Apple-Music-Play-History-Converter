# Tauri Remaining Work + Feature Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the Tauri migration by removing dev-only test injections, hardening the sidecar for production paths, adding pragmatic test mode for real CSVs, and mirroring core Toga features across UI, settings, and exports.

**Architecture:** React/TypeScript frontend (Vite + Tailwind) talks to Rust commands and event streams; Rust manages a Python sidecar over stdin/stdout JSON. A gated “Test Dashboard” provides deterministic UI testing with injected CSV paths when file dialogs can’t be automated.

**Tech Stack:** Tauri v2, Rust, React 19, TypeScript, Vite, Tailwind v4, Python 3.12, pytest.

---

### Task 1: Bring `tauri-app/` + migration docs into this worktree

**Files:**
- Add: `tauri-app/**`
- Add: `docs/REMAINING_WORK_AND_TESTING.md`
- Add: `docs/TAURI_MIGRATION_PLAN.md`

**Step 1: Copy missing files into the worktree (skip node_modules)**

Run:
```bash
rsync -a --exclude node_modules --exclude dist \
  "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/tauri-app/" \
  "tauri-app/"
rsync -a \
  "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/docs/REMAINING_WORK_AND_TESTING.md" \
  "docs/REMAINING_WORK_AND_TESTING.md"
rsync -a \
  "/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/docs/TAURI_MIGRATION_PLAN.md" \
  "docs/TAURI_MIGRATION_PLAN.md"
```

**Step 2: Verify files are present**

Run:
```bash
ls tauri-app/src tauri-app/src-tauri docs | cat
```
Expected: `tauri-app/src`, `tauri-app/src-tauri`, and the two docs are present.

**Step 3: Commit**

```bash
git add tauri-app docs/REMAINING_WORK_AND_TESTING.md docs/TAURI_MIGRATION_PLAN.md
git commit -m "chore: add tauri app and migration docs"
```

---

### Task 2: Remove App.tsx auto-test injection and add test-mode gating

**Files:**
- Modify: `tauri-app/src/App.tsx`
- Create: `tauri-app/src/lib/testMode.ts`

**Step 1: Write failing test (TS unit) for test-mode flag**

Create `tauri-app/src/lib/testMode.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { isTestMode } from "./testMode";

describe("testMode", () => {
  it("defaults to false", () => {
    expect(isTestMode()).toBe(false);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd tauri-app
npm install
npx vitest run src/lib/testMode.test.ts
```
Expected: FAIL (module not found).

**Step 3: Write minimal implementation**

Create `tauri-app/src/lib/testMode.ts`:
```ts
export function isTestMode(): boolean {
  return import.meta.env.VITE_TEST_MODE === "true";
}

export function testDataDir(): string | null {
  return import.meta.env.VITE_TEST_DATA_DIR || null;
}
```

Update `tauri-app/src/App.tsx`:
- Remove the `useEffect` block that auto-loads `_test_csvs` on startup.
- Add `import { isTestMode } from "./lib/testMode";` (no runtime effect yet).

**Step 4: Run test to verify it passes**

```bash
cd tauri-app
npx vitest run src/lib/testMode.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src/App.tsx tauri-app/src/lib/testMode.ts tauri-app/src/lib/testMode.test.ts tauri-app/package.json tauri-app/package-lock.json
git commit -m "test: add test-mode flag and remove App.tsx auto-test"
```

---

### Task 3: Add Test Dashboard with CSV injection (no file picker)

**Files:**
- Create: `tauri-app/src/components/TestDashboard.tsx`
- Modify: `tauri-app/src/App.tsx`
- Modify: `tauri-app/src/components/FileSelection.tsx`
- Modify: `tauri-app/src/lib/commands.ts`

**Step 1: Write failing test for test CSV discovery**

Create `tauri-app/src/lib/testModeCsvs.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { resolveTestCsvs } from "./testModeCsvs";

describe("resolveTestCsvs", () => {
  it("returns empty list when no dir set", async () => {
    const csvs = await resolveTestCsvs(null);
    expect(csvs).toEqual([]);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd tauri-app
npx vitest run src/lib/testModeCsvs.test.ts
```
Expected: FAIL (module not found).

**Step 3: Write minimal implementation**

Create `tauri-app/src/lib/testModeCsvs.ts`:
```ts
import { readDir } from "@tauri-apps/plugin-fs";

export async function resolveTestCsvs(dir: string | null): Promise<string[]> {
  if (!dir) return [];
  const entries = await readDir(dir);
  return entries
    .filter((e) => e.isFile && e.name?.toLowerCase().endsWith(".csv"))
    .map((e) => `${dir}/${e.name}`);
}
```

Create `tauri-app/src/components/TestDashboard.tsx` with:
- CSV picker list from `resolveTestCsvs(testDataDir())`
- Buttons: `Load CSV`, `Start`, `Pause/Resume`, `Stop`, `Export` (writes to app data dir)
- Scenario runner: `Run Full E2E` (load -> start -> wait -> pause -> wait -> resume -> stop -> export)
- Inline report list of steps with pass/fail

Update `tauri-app/src/App.tsx`:
- Add `const testMode = isTestMode();`
- Render `<TestDashboard ... />` when `testMode` is true
- Provide `setFileInfo` and `handleStatusChange` to dashboard to reuse app state

Update `tauri-app/src/components/FileSelection.tsx`:
- Add optional `testPath?: string` and `onTestSelect?: (info: FileInfo) => void`
- If `testPath` is set, show a “Use Test CSV” button that calls `analyzeCsv(testPath)`

**Step 4: Run test to verify it passes**

```bash
cd tauri-app
npx vitest run src/lib/testModeCsvs.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src/components/TestDashboard.tsx tauri-app/src/App.tsx tauri-app/src/components/FileSelection.tsx tauri-app/src/lib/testModeCsvs.ts tauri-app/src/lib/testModeCsvs.test.ts tauri-app/src/lib/commands.ts
git commit -m "feat: add test dashboard with CSV injection"
```

---

### Task 4: Emit and handle sidecar events for pause/stop/status/errors

**Files:**
- Modify: `tauri-app/src-tauri/src/sidecar.rs`
- Modify: `tauri-app/src/hooks/useSearch.ts`
- Modify: `tauri-app/src/lib/commands.ts`
- Modify: `tauri-app/src/App.tsx`

**Step 1: Write failing Rust test for message mapping**

Add to `tauri-app/src-tauri/src/sidecar.rs`:
```rust
#[cfg(test)]
mod tests {
    use super::SidecarMessage;

    #[test]
    fn parses_pause_message() {
        let json = r#"{\"type\":\"searchPaused\",\"paused\":true}"#;
        let msg: SidecarMessage = serde_json::from_str(json).unwrap();
        match msg {
            SidecarMessage::SearchPaused { paused } => assert!(paused),
            _ => panic!("wrong variant"),
        }
    }
}
```
Expected: FAIL (variant missing).

**Step 2: Update sidecar message enum + event forwarding**

In `tauri-app/src-tauri/src/sidecar.rs`:
- Add variants for `SearchPaused`, `SearchStopped`, `Error`, `Status`, `FileAnalysis`, `CsvPreview`, `CsvLoaded`.
- Emit events from stdout handler:
  - `search_paused`, `search_stopped`, `sidecar_error`, `sidecar_status`, `file_analysis`, `csv_preview`, `csv_loaded`

**Step 3: Update frontend listeners**

In `tauri-app/src/hooks/useSearch.ts`:
- Listen to `search_paused` and set `isPaused`.
- Listen to `search_stopped` and set `isSearching=false`, `isPaused=false`.

In `tauri-app/src/App.tsx`:
- Listen for `sidecar_error` and toast error + reset search state.

**Step 4: Run Rust tests**

```bash
cd tauri-app/src-tauri
cargo test sidecar::tests::parses_pause_message
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src-tauri/src/sidecar.rs tauri-app/src/hooks/useSearch.ts tauri-app/src/App.tsx tauri-app/src/lib/commands.ts
git commit -m "feat: forward sidecar pause/stop/error/status events"
```

---

### Task 5: Production hardening for sidecar path resolution

**Files:**
- Modify: `tauri-app/src-tauri/src/sidecar.rs`
- Modify: `tauri-app/python-sidecar/sidecar.py`
- Modify: `tauri-app/src-tauri/tauri.conf.json`

**Step 1: Write failing Rust test for sidecar path resolution**

Add to `tauri-app/src-tauri/src/sidecar.rs`:
```rust
#[cfg(test)]
mod path_tests {
    use super::resolve_sidecar_path;
    use std::path::PathBuf;

    #[test]
    fn falls_back_to_dev_path() {
        let dev = resolve_sidecar_path(None).unwrap();
        assert!(dev.ends_with("python-sidecar/sidecar.py"));
    }
}
```
Expected: FAIL (helper missing).

**Step 2: Implement dev/prod path resolution**

In `tauri-app/src-tauri/src/sidecar.rs`:
- Add `resolve_sidecar_path(resource_dir: Option<PathBuf>) -> Result<PathBuf, String>`.
- If `resource_dir` is present, use `resource_dir/python-sidecar/sidecar.py`.
- Otherwise use `../python-sidecar/sidecar.py` relative to `src-tauri`.
- Pass an env var `APP_RESOURCE_DIR` into the python process when resource_dir exists.

In `tauri-app/src-tauri/tauri.conf.json`:
- Add `"resources": ["../python-sidecar", "../../src/apple_music_history_converter"]` under `bundle`.

In `tauri-app/python-sidecar/sidecar.py`:
- If `APP_RESOURCE_DIR` env var set, prepend `APP_RESOURCE_DIR/../../src/apple_music_history_converter` or `APP_RESOURCE_DIR/src/apple_music_history_converter` to sys.path.
- Fallback to current relative `Path(__file__).parent.parent.parent / "src" / "apple_music_history_converter"`.

**Step 3: Run Rust test**

```bash
cd tauri-app/src-tauri
cargo test path_tests::falls_back_to_dev_path
```
Expected: PASS.

**Step 4: Commit**

```bash
git add tauri-app/src-tauri/src/sidecar.rs tauri-app/src-tauri/tauri.conf.json tauri-app/python-sidecar/sidecar.py
git commit -m "feat: resolve sidecar path for dev and bundle"
```

---

### Task 6: Improve CSV validation and network error handling in sidecar

**Files:**
- Modify: `tauri-app/python-sidecar/sidecar.py`
- Test: `tests_toga/test_sidecar_validation.py` (new)

**Step 1: Write failing test for invalid CSV handling**

Create `tests_toga/test_sidecar_validation.py`:
```python
from pathlib import Path
from tauri_app_python_sidecar_stub import validate_csv_headers

def test_invalid_csv_headers(tmp_path: Path):
    csv = tmp_path / "bad.csv"
    csv.write_text("NotAHeader\n1,2\n", encoding="utf-8")
    ok, err = validate_csv_headers(csv)
    assert ok is False
    assert "Unknown CSV format" in err
```

**Step 2: Run test to verify it fails**

```bash
pytest tests_toga/test_sidecar_validation.py::test_invalid_csv_headers -v
```
Expected: FAIL (stub missing).

**Step 3: Implement minimal validation helper**

In `tauri-app/python-sidecar/sidecar.py`:
- Add a helper `validate_csv_headers(path: Path) -> tuple[bool, str]` that checks for known columns:
  - `Play Duration Milliseconds`, `Date Played`, `Play Count`
- Use this helper in `analyze_csv` and `load_csv`.
- If invalid, call `send_error` with context `csv_validation` and return early.

Add a tiny importable wrapper module for tests:
- Create `tauri-app/python-sidecar/tauri_app_python_sidecar_stub.py` that imports the helper.

**Step 4: Run test to verify it passes**

```bash
pytest tests_toga/test_sidecar_validation.py::test_invalid_csv_headers -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/python-sidecar/sidecar.py tauri-app/python-sidecar/tauri_app_python_sidecar_stub.py tests_toga/test_sidecar_validation.py
git commit -m "test: validate CSV headers and surface sidecar errors"
```

---

### Task 7: Add iTunes XML export support and wire to Tauri UI

**Files:**
- Modify: `src/apple_music_history_converter/export_formats.py`
- Modify: `tauri-app/src/lib/types.ts`
- Modify: `tauri-app/src/components/sections/ServicesSection.tsx`
- Test: `tests_toga/test_export_formats.py`

**Step 1: Write failing test for iTunes XML format**

Add to `tests_toga/test_export_formats.py`:
```python
def test_export_itunes_xml(tmp_path):
    from apple_music_history_converter import export_formats
    tracks = [{"artist": "A", "track": "T", "album": "AL", "timestamp": "2024-01-01 10:00:00"}]
    out = tmp_path / "out.xml"
    assert export_formats.export_tracks("itunes_xml", tracks, str(out)) is True
    xml = out.read_text(encoding="utf-8")
    assert "plist" in xml
```

**Step 2: Run test to verify it fails**

```bash
pytest tests_toga/test_export_formats.py::test_export_itunes_xml -v
```
Expected: FAIL (format missing).

**Step 3: Implement iTunes XML export**

In `src/apple_music_history_converter/export_formats.py`:
- Add `export_itunes_xml` using `plistlib` and basic iTunes Library XML structure.
- Add new format key `itunes_xml` with `.xml` extension.

Update `tauri-app/src/lib/types.ts`:
- Add `itunes_xml` to `ExportFormat` and `EXPORT_FORMATS`.

Update `tauri-app/src/components/sections/ServicesSection.tsx`:
- Add the new export format to the list.

**Step 4: Run test to verify it passes**

```bash
pytest tests_toga/test_export_formats.py::test_export_itunes_xml -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add src/apple_music_history_converter/export_formats.py tauri-app/src/lib/types.ts tauri-app/src/components/sections/ServicesSection.tsx tests_toga/test_export_formats.py
git commit -m "feat: add iTunes XML export format"
```

---

### Task 8: Implement core UI parity for Results + Logs

**Files:**
- Modify: `tauri-app/src/components/ResultsPanel.tsx`
- Create: `tauri-app/src/components/LogPanel.tsx`
- Modify: `tauri-app/src/hooks/useLogs.ts`
- Modify: `tauri-app/src/App.tsx`

**Step 1: Write failing test for log accumulation**

Create `tauri-app/src/hooks/useLogs.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { createLogState } from "./useLogs";

describe("useLogs", () => {
  it("adds entries", () => {
    const state = createLogState();
    state.add("info", "hello");
    expect(state.logs.length).toBe(1);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd tauri-app
npx vitest run src/hooks/useLogs.test.ts
```
Expected: FAIL (module missing).

**Step 3: Implement minimal log store**

Create `tauri-app/src/hooks/useLogs.ts`:
- Export `createLogState()` for test use.
- Provide `logs`, `add`, `clear`.

Add `LogPanel.tsx`:
- Scrollable log list, simple filter (info/warn/error), clear button.

Update `ResultsPanel.tsx`:
- Show last export path and “Save”/“Copy” buttons (wire to new commands later).
- Add a simple status row mirroring Toga’s “Save required to enable search”.

Update `App.tsx`:
- Render `LogPanel` under `ResultsPanel` (or a right-column area if you refactor layout).

**Step 4: Run test to verify it passes**

```bash
cd tauri-app
npx vitest run src/hooks/useLogs.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src/components/ResultsPanel.tsx tauri-app/src/components/LogPanel.tsx tauri-app/src/hooks/useLogs.ts tauri-app/src/hooks/useLogs.test.ts tauri-app/src/App.tsx
git commit -m "feat: add log panel and results parity"
```

---

### Task 9: Wire Settings parity (Services + Database + Advanced)

**Files:**
- Modify: `tauri-app/src/components/sections/ServicesSection.tsx`
- Modify: `tauri-app/src/components/sections/DatabaseSection.tsx`
- Modify: `tauri-app/src/components/sections/AdvancedSection.tsx`
- Modify: `tauri-app/src/lib/commands.ts`
- Modify: `tauri-app/python-sidecar/sidecar.py`

**Step 1: Write failing test for settings updates**

Create `tests_toga/test_tauri_sidecar_settings.py`:
```python
def test_sidecar_sets_itunes_country():
    from tauri_app_python_sidecar_stub import apply_settings
    state = {}
    apply_settings(state, {"itunes_country": "IT"})
    assert state["itunes_country"] == "IT"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests_toga/test_tauri_sidecar_settings.py::test_sidecar_sets_itunes_country -v
```
Expected: FAIL (stub missing).

**Step 3: Implement settings actions**

In `tauri-app/python-sidecar/sidecar.py`:
- Add a `settings` dict to `SidecarHandler`.
- Add `apply_settings(settings: dict)` and message action `setSettings` to update:
  - `itunes_country`
  - `itunes_rate_limit`
  - `apple_music_enabled`
  - `apple_music_team_id`, `apple_music_key_id`, `apple_music_key_path`
- After update, call `MusicSearchServiceV2` setters (if available) or set on service.

In `tauri-app/src/lib/commands.ts`:
- Add `setSettings(payload)` invoke.

In `ServicesSection.tsx`:
- Add Apple Music toggle and credential inputs (Team ID, Key ID, Key Path)
- Add iTunes country dropdown and rate limit input
- Add iTunes API status check button (invoke new `check_itunes_status` command)

In `DatabaseSection.tsx`:
- Wire buttons to new commands: `download_database`, `delete_database`, `check_database_updates`

In `AdvancedSection.tsx`:
- Wire “Open Logs Folder” and “Clear Search Cache” actions to new commands.

**Step 4: Run test to verify it passes**

```bash
pytest tests_toga/test_tauri_sidecar_settings.py::test_sidecar_sets_itunes_country -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src/components/sections/ServicesSection.tsx tauri-app/src/components/sections/DatabaseSection.tsx tauri-app/src/components/sections/AdvancedSection.tsx tauri-app/src/lib/commands.ts tauri-app/python-sidecar/sidecar.py tauri-app/python-sidecar/tauri_app_python_sidecar_stub.py tests_toga/test_tauri_sidecar_settings.py
git commit -m "feat: wire settings parity for services/database/advanced"
```

---

### Task 10: Add UI dialogs and parity conveniences

**Files:**
- Create: `tauri-app/src/components/Dialogs.tsx`
- Modify: `tauri-app/src/App.tsx`

**Step 1: Write failing test for dialog state**

Create `tauri-app/src/components/Dialogs.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { Dialogs } from "./Dialogs";

it("renders when open", () => {
  render(<Dialogs showHowTo={true} onCloseHowTo={() => {}} />);
  expect(screen.getByText(/How to Use/i)).toBeTruthy();
});
```

**Step 2: Run test to verify it fails**

```bash
cd tauri-app
npm install @testing-library/react @testing-library/jest-dom
npx vitest run src/components/Dialogs.test.tsx
```
Expected: FAIL (component missing).

**Step 3: Implement dialogs**

Create `Dialogs.tsx`:
- How to Use dialog
- About dialog
- Generic confirm dialog (used for delete DB)

Wire in `App.tsx` and add a “How to Use” button in header.

**Step 4: Run test to verify it passes**

```bash
cd tauri-app
npx vitest run src/components/Dialogs.test.tsx
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tauri-app/src/components/Dialogs.tsx tauri-app/src/components/Dialogs.test.tsx tauri-app/src/App.tsx tauri-app/package.json tauri-app/package-lock.json
git commit -m "feat: add dialogs for how-to and about"
```

---

### Task 11: Pragmatic E2E verification in Test Dashboard

**Files:**
- Modify: `tauri-app/src/components/TestDashboard.tsx`

**Step 1: Add scenario assertions**
- Verify pause keeps progress static for 2s.
- Verify resume advances progress again.
- Verify stop halts updates.
- Verify export file exists at destination.

**Step 2: Manual verification**

Run the Tauri app in test mode:
```bash
cd tauri-app
VITE_TEST_MODE=true VITE_TEST_DATA_DIR="/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Documents/GitHub/Apple-Music-Play-History-Converter/_test_csvs" npm run dev
```
Expected: Test Dashboard visible, real CSVs listed, full E2E scenario runs.

**Step 3: Commit**

```bash
git add tauri-app/src/components/TestDashboard.tsx
git commit -m "test: add E2E scenario assertions in test dashboard"
```

---

**Plan complete and saved to `docs/plans/2026-02-03-tauri-remaining-work-and-parity.md`. Two execution options:**

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
