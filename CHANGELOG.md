# Changelog

## 3.0.3

- Move the mutable user-track mapping cache from DuckDB to SQLite to prevent
  fatal duplicate-primary-key failures on large histories with repeated tracks.
- Import readable legacy DuckDB mappings once and rebuild a corrupt SQLite
  mapping cache without preventing application startup.
- Add a first-class external storage location for MusicBrainz data, caches, and
  logs, including an environment override for automation.
- Reload saved progress after an automatic Python sidecar restart.
- Synchronize all application version sources and add an automated drift check.
- Refresh Node, React, Vite, Tauri, Rust, Python, and packaged dependencies.

## 3.0.2

### Fixed

- macOS: Python sidecar failed to launch on signed/notarized release builds (Apple Silicon and Intel) with `code signature ... not valid for use in process: ... different Team IDs` (#14). Added a hardened-runtime entitlements plist that disables library validation and allows the dyld environment so the embedded Python framework loads under our Developer ID signature.

## 3.0.1

### Fixed

- Bundled the Python sidecar for macOS and Windows release builds so users no longer depend on system Python or pip packages
- Added durable session logs with OS, app version, launch time, and sidecar lifecycle metadata for startup and search failures
- Made backend startup failures visible in the UI with direct log access for support
- Bundled the Windows WebView2 offline installer for first-run installs
- Defaulted local/test macOS release builds to ad-hoc signing while preserving Developer ID signing via environment variables for real releases
- Aligned the Tauri JS/Rust toolchain to current 2.x releases, fixing the Windows MSI `__TAURI_BUNDLE_TYPE` patch warning

## 3.0.0

Complete rewrite as a native desktop app using Tauri, replacing the legacy Python/Toga UI.

### New

- Native desktop app built with Tauri + React + TypeScript + Rust
- Modern UI with dark/light mode, resizable columns, and drag-and-drop CSV loading
- Apple Music API search provider via Cloudflare Workers proxy
- Album data matching across all search providers (iTunes, MusicBrainz API, MusicBrainz Local DB, Apple Music API)
- Real-time search progress with elapsed time, ETA, and found/missing counters
- Editable preview table — fix artist/track/album before searching
- Resume support — pick up where you left off after stopping
- Retry workflows for missing and rate-limited tracks
- Export to Last.fm CSV, Spotify CSV, Universal CSV, iTunes XML, and ListenBrainz JSON
- Per-provider rate limit controls with pause/resume
- MusicBrainz local database management (download, import, optimize)
- API health status badges on each search provider
- Click-outside-to-close dialogs
- Missing/rate-limited track detail dialogs
- Log panel with real-time search activity

### Fixed

- ETA display now shows h:mm:ss format instead of raw seconds
- Missing Tracks dialog now shows actual track data (not just a count)
- Search Again no longer re-normalizes the CSV if the same file is loaded
- Table headers are opaque (no bleed-through on scroll)
- Eliminated double-throttling for iTunes and MusicBrainz API providers
- MusicBrainz API rate limit setting now actually applies (was hardcoded)
- Apple Music API badge shows its own status instead of sharing iTunes status
- Duplicate startup notifications eliminated (React StrictMode guard)
- API status messages suppressed from log panel (badges already show them)

### Removed

- Legacy Python/Toga desktop app
- Old build system (build.py, DMG packaging)
- Wiki documentation (replaced by in-app help)

## 2.0.4

- Thread safety fixes for Intel Mac compatibility

## 2.0.3

- Fuzzy matching algorithm improvements
- Apostrophe mismatch fix for artist matching

## 2.0.2

- MusicBrainz local database support
- Batch search optimization

## 2.0.1

- Bug fixes and stability improvements

## 2.0.0

- Initial public release with Toga UI
