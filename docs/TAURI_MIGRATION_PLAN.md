# Toga to Tauri Migration Plan

> **Complete migration of Apple Music History Converter from Toga to Tauri**
>
> This document defines the full scope, architecture, and implementation strategy for migrating the existing Toga-based application to Tauri with a React/TypeScript frontend and Rust backend.

---

## Executive Summary

| Component | Current (Toga) | Target (Tauri) |
|-----------|----------------|----------------|
| UI Framework | Toga (Python) | React + TypeScript |
| Backend | Python (direct) | Rust + Python sidecar |
| Icons | Text-based | Phosphor Icons |
| Styling | Toga Pack styles | TailwindCSS v4 |
| Distribution | PyInstaller | Tauri bundler |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Tauri Application                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌────────────────────────────┐  │
│  │   React Frontend    │◄───│      Rust Backend          │  │
│  │   (TypeScript)      │    │   (IPC Commands)           │  │
│  │                     │    │                            │  │
│  │  - Phosphor Icons   │    │  - File dialog             │  │
│  │  - TailwindCSS v4   │    │  - Sidecar management      │  │
│  │  - Accordion panels │    │  - Settings persistence    │  │
│  │  - Progress UI      │    │  - Event emission          │  │
│  └─────────────────────┘    └────────────┬───────────────┘  │
│                                          │                  │
│                                          ▼                  │
│                              ┌───────────────────────────┐  │
│                              │    Python Sidecar         │  │
│                              │   (stdin/stdout JSON)     │  │
│                              │                           │  │
│                              │  - MusicSearchServiceV2   │  │
│                              │  - CSV processing         │  │
│                              │  - API integrations       │  │
│                              │  - Database operations    │  │
│                              └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Feature Inventory (Toga to Tauri Mapping)

### 1. Header Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| App title | Label with typography.large_title | P1 |
| Subtitle | Label with typography.body | P1 |
| "How to Use" button | Button opens modal/dialog | P2 |

### 2. File Selection Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Select file button | Native Tauri file dialog | P1 |
| File info display | Name, size, row count, type badge | P1 |
| Delete/clear button | Reset file state | P1 |

### 3. Preview Section (SplitContainer left)

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Preview table | First 100 rows in HTML table | P1 |
| Columns: Artist, Track, Album, Timestamp, Album Artist, Duration | Table headings | P1 |
| Info label | "Select a CSV to see the first rows" | P1 |

### 4. Results Section (SplitContainer right)

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Last saved output path | Display path of saved file | P1 |
| Save button | Save converted CSV | P1 |
| Copy button | Copy to clipboard | P2 |
| Save status indicator | "Save required to enable search" | P1 |
| Search button | "Search with [Provider]" | P1 |
| Stop button | Stop current search | P1 |
| Export Missing Artists button | Export unmatched tracks | P2 |
| Rate limit row (iTunes) | Skip wait, Retry, Export buttons | P2 |
| Log display | MultilineTextInput for status messages | P1 |

### 5. Progress Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Progress bar | Horizontal bar with percentage | P1 |
| Progress label | Status text | P1 |
| Detailed stats label | Found/missing/processing info | P1 |
| Elapsed time | Timer display | P2 |
| ETA | Estimated remaining time | P2 |

### 6. Settings Sidebar - Accordion Sections

#### 6.1 Services Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Provider selection | Radio buttons: MusicBrainz/API/iTunes | P1 |
| Apple Music API toggle | Switch enable/disable | P2 |
| Apple Music API credentials | Team ID, Key ID, Key path inputs | P3 |
| iTunes API status check | Button + status label | P2 |
| iTunes rate limit input | Number input + Save button | P2 |
| iTunes storefront select | Dropdown (US, GB, etc.) | P2 |
| Pause/Resume rate limiting | Toggle button | P2 |

#### 6.2 Database & MusicBrainz Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Database status | Downloaded/Not Downloaded | P1 |
| Database size | File size display | P2 |
| Track count | Number of indexed tracks | P2 |
| Download button | Download ~2GB database | P1 |
| Check Updates button | Check for DB updates | P2 |
| Manual Import button | Import existing DB | P3 |
| Delete Database button | Remove local DB | P2 |
| Show Location button | Open DB folder in Finder | P2 |
| Optimize Now button | Run DB optimization | P3 |
| MusicBrainz API URL | Display URL | P2 |
| MusicBrainz API status | Check button + status | P2 |

#### 6.3 Advanced Section

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| View Logs button | Open log directory | P2 |
| Clear Search Cache | Clear cached searches | P2 |

### 7. Dialogs

| Toga Feature | Implementation | Priority |
|--------------|----------------|----------|
| Instructions dialog | Modal with usage steps | P2 |
| About dialog | App info, version, credits | P2 |
| Confirm dialogs | Resume search, delete DB, etc. | P1 |
| Info dialogs | Notifications | P1 |

---

## IPC Commands (Rust Backend)

### File Operations

```rust
#[tauri::command]
async fn select_file() -> Result<FileInfo, String>

#[tauri::command]
async fn analyze_csv(path: String) -> Result<FileInfo, String>

#[tauri::command]
async fn get_csv_preview(path: String, max_rows: usize) -> Result<Vec<Vec<String>>, String>

#[tauri::command]
async fn save_csv(path: String, format: String) -> Result<String, String>

#[tauri::command]
async fn copy_to_clipboard(content: String) -> Result<(), String>
```

### Search Operations

```rust
#[tauri::command]
async fn start_search(file_path: String, provider: String) -> Result<(), String>

#[tauri::command]
async fn stop_search() -> Result<(), String>

#[tauri::command]
async fn toggle_pause() -> Result<bool, String>

#[tauri::command]
async fn skip_rate_limit() -> Result<(), String>

#[tauri::command]
async fn retry_rate_limited() -> Result<(), String>
```

### Export Operations

```rust
#[tauri::command]
async fn export_results(format: String, output_path: String) -> Result<String, String>

#[tauri::command]
async fn export_missing_artists(output_path: String) -> Result<String, String>

#[tauri::command]
async fn export_rate_limited(output_path: String) -> Result<String, String>
```

### Database Operations

```rust
#[tauri::command]
async fn get_database_status() -> Result<DatabaseStatus, String>

#[tauri::command]
async fn download_database() -> Result<(), String>

#[tauri::command]
async fn delete_database() -> Result<(), String>

#[tauri::command]
async fn check_database_updates() -> Result<UpdateInfo, String>

#[tauri::command]
async fn import_database(path: String) -> Result<(), String>

#[tauri::command]
async fn optimize_database() -> Result<(), String>

#[tauri::command]
async fn show_database_location() -> Result<(), String>
```

### Settings Operations

```rust
#[tauri::command]
async fn get_settings() -> Result<Settings, String>

#[tauri::command]
async fn update_settings(settings: Settings) -> Result<(), String>

#[tauri::command]
async fn set_provider(provider: String) -> Result<(), String>

#[tauri::command]
async fn check_api_status(api: String) -> Result<ApiStatus, String>
```

### System Operations

```rust
#[tauri::command]
async fn open_logs_folder() -> Result<(), String>

#[tauri::command]
async fn clear_cache() -> Result<(), String>

#[tauri::command]
async fn get_app_info() -> Result<AppInfo, String>
```

---

## Event Emissions (Rust to Frontend)

```rust
// Search progress updates
window.emit("search:progress", SearchProgress { 
    current, total, found, missing, provider, status, current_track,
    elapsed_seconds, estimated_remaining_seconds
})

// Database download progress
window.emit("database:download_progress", DownloadProgress {
    downloaded_bytes, total_bytes, percent, speed
})

// Log messages
window.emit("log", LogEntry {
    level, message, timestamp
})

// Settings changed
window.emit("settings:changed", Settings { ... })

// Search completed
window.emit("search:complete", SearchResult {
    total, found, missing, rate_limited
})
```

---

## Python Sidecar Protocol

### Message Format

```json
// Request (Rust -> Python)
{
  "id": "uuid",
  "type": "command_name",
  "payload": { ... }
}

// Response (Python -> Rust)
{
  "id": "uuid",
  "type": "response" | "error" | "event",
  "payload": { ... }
}

// Event (Python -> Rust, unsolicited)
{
  "id": null,
  "type": "event",
  "event": "progress" | "log",
  "payload": { ... }
}
```

### Commands

| Command | Payload | Response |
|---------|---------|----------|
| `initialize` | `{}` | `{version, db_status}` |
| `analyze_csv` | `{path}` | `{rows, columns, file_type, preview}` |
| `start_search` | `{path, provider, resume}` | Progress events |
| `stop_search` | `{}` | `{stopped: true}` |
| `toggle_pause` | `{}` | `{paused: bool}` |
| `export` | `{format, output_path}` | `{path, rows_written}` |
| `get_settings` | `{}` | `{settings object}` |
| `update_settings` | `{settings}` | `{ok: true}` |
| `download_database` | `{}` | Progress events |
| `delete_database` | `{}` | `{ok: true}` |
| `check_api` | `{api: "musicbrainz" \| "itunes"}` | `{status, message}` |

---

## Implementation Phases

### Phase 1: Core Infrastructure (Days 1-2)

- [ ] Set up Phosphor Icons in React
- [ ] Create base component library (Button, Input, Accordion, Table)
- [ ] Implement Tauri IPC command stubs
- [ ] Create Python sidecar with basic JSON IPC
- [ ] Wire file dialog to work in native Tauri window

### Phase 2: File Handling (Days 2-3)

- [ ] Implement `analyze_csv` (Rust calls Python sidecar)
- [ ] Implement `get_csv_preview` 
- [ ] Build Preview table component
- [ ] Build file info display with type detection badge

### Phase 3: Search Integration (Days 3-5)

- [ ] Implement `start_search` with sidecar
- [ ] Implement progress event streaming
- [ ] Build progress bar with stats
- [ ] Implement pause/stop/resume controls
- [ ] Implement rate limit skip functionality

### Phase 4: Settings UI (Days 5-6)

- [ ] Build Accordion component
- [ ] Implement Services section (providers, Apple Music, iTunes)
- [ ] Implement Database section (status, download, management)
- [ ] Implement Advanced section (logs, cache)
- [ ] Wire settings persistence

### Phase 5: Export & Polish (Days 6-7)

- [ ] Implement all 4 export formats
- [ ] Implement export missing artists
- [ ] Implement export rate-limited tracks
- [ ] Add timer/ETA display
- [ ] Add "How to Use" dialog
- [ ] Add About dialog
- [ ] Final testing and bug fixes

---

## File Structure

```
tauri-app/
├── src/                          # React frontend
│   ├── App.tsx                   # Main application component
│   ├── index.css                 # TailwindCSS styles
│   ├── components/
│   │   ├── ui/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Accordion.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Progress.tsx
│   │   │   ├── Dialog.tsx
│   │   │   └── Select.tsx
│   │   ├── FileSelection.tsx
│   │   ├── PreviewTable.tsx
│   │   ├── ResultsPanel.tsx
│   │   ├── ProgressSection.tsx
│   │   ├── SettingsSidebar.tsx
│   │   ├── ServicesSection.tsx
│   │   ├── DatabaseSection.tsx
│   │   └── AdvancedSection.tsx
│   ├── hooks/
│   │   ├── useTauri.ts           # Tauri availability check
│   │   ├── useSearch.ts          # Search state management
│   │   ├── useSettings.ts        # Settings state
│   │   └── useDatabase.ts        # Database state
│   └── lib/
│       ├── commands.ts           # Tauri IPC wrappers
│       └── types.ts              # TypeScript interfaces
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs                # IPC commands
│   │   ├── sidecar.rs            # Python sidecar management
│   │   └── settings.rs           # Settings persistence
│   └── Cargo.toml
└── python-sidecar/
    ├── sidecar.py                # Main entry point
    ├── ipc.py                    # JSON IPC handler
    ├── csv_processor.py          # CSV analysis
    ├── search_service.py         # MusicSearchServiceV2 wrapper
    └── requirements.txt
```

---

## Testing Checklist

### Native Window Tests

- [ ] Tauri window opens on `npm run tauri dev`
- [ ] File dialog opens when clicking "Select CSV File"
- [ ] CSV loads and shows in preview table
- [ ] Provider selection works
- [ ] Search starts and shows progress
- [ ] Stop/Pause controls work
- [ ] Export produces valid files

### Settings Tests

- [ ] Accordion expand/collapse works
- [ ] Provider radio buttons work
- [ ] Settings persist between sessions
- [ ] Database download shows progress
- [ ] Database delete confirms and works

### Error Handling

- [ ] Invalid CSV shows error message
- [ ] Network errors handled gracefully
- [ ] Sidecar crash recovery
- [ ] Rate limit handling with countdown

---

## Dependencies

### Frontend (package.json)

```json
{
  "@tauri-apps/api": "^2.10.0",
  "@tauri-apps/plugin-dialog": "^2.6.0",
  "@tauri-apps/plugin-fs": "^2.4.5",
  "@tauri-apps/plugin-shell": "^2.3.4",
  "@phosphor-icons/react": "^2.1.7",
  "react": "^19.0.0",
  "tailwindcss": "^4.0.0"
}
```

### Backend (Cargo.toml)

```toml
[dependencies]
tauri = "2"
tauri-plugin-dialog = "2"
tauri-plugin-fs = "2"
tauri-plugin-shell = "2"
tauri-plugin-opener = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
```

### Python Sidecar (requirements.txt)

```
pandas
httpx
duckdb
```

---

## Success Criteria

1. **Functional parity**: All Toga features work in Tauri
2. **Performance**: CSV files up to 200k rows load without freezing
3. **Cross-platform**: Works on macOS, Windows, Linux
4. **Native feel**: Uses native file dialogs and window chrome
5. **No emojis**: All icons from Phosphor Icons library
