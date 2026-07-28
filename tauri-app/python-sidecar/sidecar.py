#!/usr/bin/env python3
"""
Apple Music History Converter - Python Sidecar for Tauri
JSON-based IPC wrapper for the existing Python backend.

This sidecar communicates with the Tauri frontend via stdin/stdout JSON messages.
"""

import json
import sys
import os
import re
import asyncio
import traceback
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
import threading
import queue
import time
import chardet  # Ensure PyInstaller bundles requests' charset detector.

# ---------------------------------------------------------------------------
# Path resolution: add the project's src/ directory so that package imports
# like ``from apple_music_history_converter.X import Y`` work correctly.
# We also add the package directory itself so that bare imports
# (``from music_search_service_v2 import ...``) keep working.
# ---------------------------------------------------------------------------
_src_dir: Optional[Path] = None
_pkg_dir: Optional[Path] = None

if not getattr(sys, "frozen", False):
    _project_root_candidates = [
        # Strategy 1: Development - sidecar.py lives in tauri-app/python-sidecar/
        Path(__file__).resolve().parent.parent.parent,
        # Strategy 1b: Production resources - src/ is next to python-sidecar/
        Path(__file__).resolve().parent.parent,
        # Strategy 2: CWD is src-tauri/ during dev
        Path.cwd().parent.parent,
        # Strategy 3: Production bundled (sidecar next to src/)
        Path(__file__).resolve().parent,
    ]

    for _root in _project_root_candidates:
        candidate = _root / "src"
        pkg = candidate / "apple_music_history_converter"
        if pkg.exists():
            _src_dir = candidate
            _pkg_dir = pkg
            break

    if _src_dir is None or _pkg_dir is None:
        print(json.dumps({
            "type": "error",
            "error": "Source directory not found in any expected location",
            "cwd": str(Path.cwd()),
            "script_path": str(Path(__file__)),
            "tried_roots": [str(p) for p in _project_root_candidates]
        }), file=sys.stderr, flush=True)
        sys.exit(1)

    # Add src/ so ``from apple_music_history_converter.X import Y`` works
    sys.path.insert(0, str(_src_dir))

# ---------------------------------------------------------------------------
# Imports from the existing backend
# Use fully-qualified package imports so that relative imports inside
# the modules (e.g. ``from .logging_config import ...``) resolve correctly.
# ---------------------------------------------------------------------------
try:
    from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2
    from apple_music_history_converter import export_formats
    from apple_music_history_converter.app_directories import get_settings_path, get_storage_root
    from apple_music_history_converter.logging_config import get_logger
except ImportError as e:
    print(json.dumps({
        "type": "error",
        "error": f"Failed to import modules: {e}",
        "traceback": traceback.format_exc()
    }), file=sys.stderr, flush=True)
    sys.exit(1)

logger = get_logger(__name__)

# Default shared Cloudflare Worker proxy URL for Apple Music API
DEFAULT_APPLE_MUSIC_PROXY_URL = "https://am-proxy.wavedepth.workers.dev"
APP_VERSION = "3.0.3"

# Pre-compiled emoji pattern for Windows compatibility
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)

# ---------------------------------------------------------------------------
# Column mapping per CSV file type
# ---------------------------------------------------------------------------
# Maps raw CSV columns -> standard keys used by export_formats and search
COLUMN_MAP = {
    "Play Activity": {
        "artist": ["Artist", "Container Artist Name"],
        "track": ["Song Name", "Track Description", "Title"],
        "album": ["Album Name", "Container Album Name"],
        "timestamp": ["Event End Timestamp", "Event Start Timestamp", "Event Timestamp"],
        "duration": ["Media Duration In Milliseconds", "Play Duration Milliseconds"],
        "isrc": ["ISRC", "Isrc", "International Standard Recording Code", "Recording ISRC Code"],
        "container_id": ["Container ID"],
        "container_type": ["Container Type"],
        "iso_country": ["ISO Country"],
    },
    "Recently Played Tracks": {
        "artist": [],  # Artist is embedded in Track Description as "Artist - Track"
        "track": ["Track Description"],
        "album": ["Container Description"],
        "timestamp": ["Last Event End Timestamp", "First Event Timestamp", "Last Modified"],
        "duration": ["Media duration in millis", "Max Play Duration in millis"],
        "isrc": ["ISRC", "Isrc", "Recording ISRC Code"],
    },
    "Play History Daily Tracks": {
        "artist": [],  # Artist is embedded in Track Description as "Artist - Track"
        "track": ["Track Description"],
        "album": ["Container Description"],
        "timestamp": ["Date Played"],
        "duration": ["Play Duration Milliseconds", "Media Duration In Milliseconds"],
        "isrc": ["ISRC", "Isrc", "Recording ISRC Code"],
    },
}

UNKNOWN_COLUMN_KEYWORDS = {
    "artist": [
        "artist",
        "performer",
        "singer",
        "band",
        "composer",
        "creator",
    ],
    "track": [
        "track",
        "song",
        "title",
        "recording",
        "name",
    ],
    "album": [
        "album",
        "record",
        "release",
        "container",
        "collection",
    ],
    "timestamp": [
        "timestamp",
        "played at",
        "date played",
        "event end",
        "event start",
        "last event",
        "time",
        "played",
    ],
    "duration": [
        "ms_played",
        "duration",
        "play duration",
        "milliseconds",
        "millis",
        "length",
    ],
    "isrc": [
        "isrc",
        "recording isrc code",
        "recording code",
        "international standard recording code",
    ],
}

UNKNOWN_FIELD_ORDER = ["artist", "track", "album", "timestamp", "duration", "isrc"]

# Map ISO country codes to Apple Music storefront codes
ISO_TO_STOREFRONT = {
    "US": "us", "GB": "gb", "AU": "au", "CA": "ca", "DE": "de",
    "FR": "fr", "JP": "jp", "KR": "kr", "BR": "br", "MX": "mx",
    "IT": "it", "ES": "es", "NL": "nl", "SE": "se", "NO": "no",
    "DK": "dk", "FI": "fi", "NZ": "nz", "IN": "in", "SG": "sg",
    "ZA": "za", "AT": "at", "BE": "be", "CH": "ch", "IE": "ie",
    "PT": "pt", "PL": "pl", "CZ": "cz", "HU": "hu", "RO": "ro",
    "GR": "gr", "TR": "tr", "RU": "ru", "IL": "il", "AE": "ae",
    "SA": "sa", "EG": "eg", "NG": "ng", "KE": "ke", "TH": "th",
    "MY": "my", "PH": "ph", "ID": "id", "VN": "vn", "TW": "tw",
    "HK": "hk", "CL": "cl", "CO": "co", "AR": "ar", "PE": "pe",
}


STOREFRONT_NAME_TO_CODE = {
    "united states": "us", "united kingdom": "gb", "australia": "au",
    "canada": "ca", "germany": "de", "france": "fr", "japan": "jp",
    "south korea": "kr", "brazil": "br", "mexico": "mx", "italy": "it",
    "spain": "es", "netherlands": "nl", "sweden": "se", "norway": "no",
    "denmark": "dk", "finland": "fi", "new zealand": "nz", "india": "in",
    "singapore": "sg", "south africa": "za", "austria": "at", "belgium": "be",
    "switzerland": "ch", "ireland": "ie", "portugal": "pt", "poland": "pl",
    "czech republic": "cz", "czechia": "cz", "hungary": "hu", "romania": "ro",
    "greece": "gr", "turkey": "tr", "russia": "ru", "israel": "il",
    "united arab emirates": "ae", "saudi arabia": "sa", "egypt": "eg",
    "nigeria": "ng", "kenya": "ke", "thailand": "th", "malaysia": "my",
    "philippines": "ph", "indonesia": "id", "vietnam": "vn", "taiwan": "tw",
    "hong kong": "hk", "chile": "cl", "colombia": "co", "argentina": "ar",
    "peru": "pe",
}


class AsyncRateLimiter:
    """Token-bucket rate limiter for async contexts."""

    def __init__(self, requests_per_minute: int = 20):
        self.requests_per_minute = max(1, requests_per_minute)
        self._interval = 60.0 / self.requests_per_minute
        self._last_request = 0.0

    async def acquire(self):
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self._interval:
            await asyncio.sleep(self._interval - elapsed)
        self._last_request = time.time()

    def update_rate(self, requests_per_minute: int):
        self.requests_per_minute = max(1, requests_per_minute)
        self._interval = 60.0 / self.requests_per_minute


def _extract_artist_track(description: str):
    """Split 'Artist - Track' format used in Recently Played and Daily Tracks."""
    if not description or description == "N/A":
        return "", description or ""
    parts = description.split(" - ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", description.strip()


def _first_present(row: Dict, keys: List[str]) -> str:
    """Return the first non-empty value for any of the given keys."""
    for k in keys:
        val = row.get(k)
        if val is not None and str(val).strip() and str(val).strip() != "nan":
            return str(val).strip()
    return ""


def _first_present_with_key(row: Dict, keys: List[str]) -> Tuple[str, str]:
    """Return the first non-empty value and the source key."""
    for k in keys:
        val = row.get(k)
        if val is not None and str(val).strip() and str(val).strip() != "nan":
            return str(val).strip(), k
    return "", ""


def _header_tokens(header: str) -> Set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", header.lower()) if token}


def _score_unknown_header(header: str, field: str) -> int:
    header_l = header.lower()
    tokens = _header_tokens(header_l)
    score = 0

    for keyword in UNKNOWN_COLUMN_KEYWORDS[field]:
        keyword_l = keyword.lower()
        keyword_tokens = [tok for tok in re.split(r"[^a-z0-9]+", keyword_l) if tok]
        if keyword_l in header_l:
            score += 12 + len(keyword_tokens)
        elif keyword_tokens and all(tok in tokens for tok in keyword_tokens):
            score += 6 + len(keyword_tokens)

    if field == "duration":
        if {"ms", "millisecond", "milliseconds", "millis"} & tokens:
            score += 10
        if {"duration", "play", "played"} & tokens:
            score += 4

    if field == "timestamp" and {"ms", "millisecond", "milliseconds", "millis"} & tokens:
        score -= 6
    if field == "track" and "album" in tokens:
        score -= 4
    if field == "album" and ("track" in tokens or "song" in tokens):
        score -= 4

    return score


def _infer_unknown_column_map(raw_rows: List[Dict]) -> Dict[str, List[str]]:
    """Infer canonical column mapping for unknown CSV formats using header heuristics."""
    inferred = {field: [] for field in UNKNOWN_FIELD_ORDER}
    if not raw_rows:
        return inferred

    headers: List[str] = []
    seen_headers: Set[str] = set()
    for row in raw_rows[:25]:
        for key in row.keys():
            key_str = str(key).strip()
            if key_str and key_str not in seen_headers:
                headers.append(key_str)
                seen_headers.add(key_str)

    if not headers:
        return inferred

    header_order = {name: idx for idx, name in enumerate(headers)}
    remaining = set(headers)

    for field in UNKNOWN_FIELD_ORDER:
        scored = []
        for header in remaining:
            score = _score_unknown_header(header, field)
            if score > 0:
                scored.append((score, header_order[header], header))
        if not scored:
            continue

        scored.sort(key=lambda item: (-item[0], item[1]))
        chosen = scored[0][2]
        inferred[field] = [chosen]
        remaining.remove(chosen)

    return inferred


def _parse_duration_seconds(duration_raw: str, source_column: str, file_type: str) -> float:
    """Parse duration values and normalize to seconds."""
    try:
        raw_value = float(duration_raw) if duration_raw else 0.0
    except (ValueError, TypeError):
        return 0.0

    if file_type != "Unknown":
        return round(raw_value / 1000.0, 2)

    source_l = (source_column or "").lower()
    if any(token in source_l for token in ["ms", "millisecond", "milliseconds", "millis"]):
        return round(raw_value / 1000.0, 2)
    if raw_value > 1000:
        return round(raw_value / 1000.0, 2)
    return round(raw_value, 2)


def _normalize_isrc(value: str) -> str:
    """Normalize ISRC codes to uppercase 12-char alphanumeric format."""
    if value is None:
        return ""

    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value).strip()).upper()
    if not cleaned or cleaned == "NAN":
        return ""

    # ISRC format: CCXXXYYNNNNN (2 letters + 3 alnum + 7 digits)
    if len(cleaned) == 12 and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", cleaned):
        return cleaned

    return ""


def _find_isrc_in_row(row: Dict) -> str:
    """Fallback ISRC discovery by scanning column names."""
    for key, value in row.items():
        key_l = str(key).lower()
        if "isrc" in key_l or "recording code" in key_l:
            normalized = _normalize_isrc(str(value))
            if normalized:
                return normalized
    return ""


def normalize_tracks(raw_rows: List[Dict], file_type: str) -> List[Dict]:
    """Normalize raw CSV rows into standard track dicts for search/export.

    Standard dict keys: artist, track, album, timestamp, duration, isrc
    Plus any _raw_* keys for debugging.
    """
    if file_type == "Unknown":
        col_map = _infer_unknown_column_map(raw_rows)
    else:
        col_map = COLUMN_MAP.get(file_type, COLUMN_MAP["Play Activity"])
    tracks = []
    for row in raw_rows:
        artist = _first_present(row, col_map.get("artist", []))
        track_name = _first_present(row, col_map.get("track", []))
        album = _first_present(row, col_map.get("album", []))
        timestamp = _first_present(row, col_map.get("timestamp", []))
        duration_raw, duration_key = _first_present_with_key(row, col_map.get("duration", []))
        isrc = _normalize_isrc(_first_present(row, col_map.get("isrc", [])))
        if not isrc:
            isrc = _find_isrc_in_row(row)

        # Container metadata (Play Activity only)
        container_id = _first_present(row, col_map.get("container_id", []))
        container_type = _first_present(row, col_map.get("container_type", []))
        iso_country = _first_present(row, col_map.get("iso_country", []))

        # For Recently Played / Daily Tracks, artist is embedded in Track Description
        if not artist and track_name:
            artist, track_name = _extract_artist_track(track_name)

        # Also try splitting album description (e.g. "Joe Hisaishi - Spirited Away...")
        if not artist and album:
            a, _ = _extract_artist_track(album)
            if a:
                artist = a

        duration = _parse_duration_seconds(duration_raw, duration_key, file_type)

        track_dict = {
            "artist": artist,
            "track": track_name,
            "album": album,
            "timestamp": timestamp,
            "duration": round(duration, 2),
            "isrc": isrc,
            # Internal state
            "_found": False,
            "_source": "",
            "_artist_matched": "",
            "_album_matched": "",
            "_error": "",
            "_rate_limited": False,
        }

        # Also check Store Front Name for human-readable country
        store_front_name = _first_present(row, ["Store Front Name"])
        if not iso_country and store_front_name:
            sf_code = STOREFRONT_NAME_TO_CODE.get(store_front_name.lower().strip(), "")
            if sf_code:
                iso_country = sf_code.upper()

        # Only include container metadata when present (Play Activity CSVs)
        if container_id:
            track_dict["_container_id"] = container_id.strip()
        if container_type:
            track_dict["_container_type"] = container_type.strip().upper()
        if iso_country:
            track_dict["_iso_country"] = iso_country.strip().upper()

        tracks.append(track_dict)
    return tracks


def detect_file_type(header_line: str) -> str:
    """Detect CSV file type from header columns."""
    if "Play Duration Milliseconds" in header_line and "Song Name" in header_line:
        return "Play Activity"
    if "Date Played" in header_line and "Track Description" in header_line:
        return "Play History Daily Tracks"
    if "Last Event End Timestamp" in header_line or ("Track Description" in header_line and "Total plays" in header_line):
        return "Recently Played Tracks"
    # Fallback heuristics
    if "Play Duration Milliseconds" in header_line:
        return "Play Activity"
    if "Track Description" in header_line:
        return "Recently Played Tracks"
    return "Unknown"


class SidecarHandler:
    """Handles IPC messages from Tauri frontend."""

    PROGRESS_SAVE_INTERVAL = 250

    def __init__(self):
        self.music_service: Optional[MusicSearchServiceV2] = None
        self.current_df = None
        self.current_tracks: List[Dict] = []
        self.current_file_type: str = ""
        self.current_file_path: str = ""
        self.search_thread: Optional[threading.Thread] = None
        self.stop_search_flag = False
        self.pause_search_flag = False
        self.rate_limited_tracks: List[Dict] = []
        self.preview_edits_by_file: Dict[str, Dict[int, Dict[str, str]]] = {}
        self.settings: Dict[str, Any] = {}
        self.settings_file = self._get_settings_path()
        self.progress_file = self.settings_file.parent / "search_progress.json"
        self._skip_rate_limit_wait = threading.Event()
        self._rate_limit_wait_active = False
        self._load_settings()
        # Pre-emptive rate limiter for Apple Music API calls
        rpm = int(self.settings.get("apple_music_requests_per_minute", 20))
        self._rate_limiter = AsyncRateLimiter(requests_per_minute=rpm)

    # ------------------------------------------------------------------
    # IPC helpers
    # ------------------------------------------------------------------
    def send_message(self, msg: Dict[str, Any]):
        """Send JSON message to stdout for Tauri to receive."""
        import sys as _sys
        try:
            line = json.dumps(msg, default=str)
            print(line, flush=True)
        except Exception as e:
            _sys.stderr.write(f"[SIDECAR] send_message failed: {e}\n")
            _sys.stderr.flush()

    def send_error(self, error: str, context: str = ""):
        """Send error message."""
        self.send_message({
            "type": "error",
            "error": str(error),
            "context": context
        })

    def send_status(self, status: str):
        """Send status update."""
        self.send_message({"type": "status", "status": status})

    def send_log(self, message: str, level: str = "info"):
        """Send a log message to the frontend."""
        self.send_message({
            "type": "log",
            "level": level,
            "message": _EMOJI_RE.sub('', message) if message else ""
        })

    def send_progress(self, current: int, total: int, found: int, missing: int,
                      provider: str, status: str, current_track: str = "",
                      elapsed_seconds: float = 0, estimated_remaining_seconds: float = 0,
                      rate_limited: int = 0):
        """Send search progress update."""
        safe_track = _EMOJI_RE.sub('', current_track) if current_track else ""
        self.send_message({
            "type": "progress",
            "current": current,
            "total": total,
            "found": found,
            "missing": missing,
            "provider": provider,
            "status": status,
            "currentTrack": safe_track,
            "elapsedSeconds": elapsed_seconds,
            "estimatedRemainingSeconds": estimated_remaining_seconds,
            "rateLimited": rate_limited,
        })

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def _get_settings_path(self) -> Path:
        """Get platform-specific settings file path."""
        return get_settings_path()

    def _load_settings(self):
        """Load settings from disk."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load settings: {e}", file=sys.stderr)
                self.settings = {}

    def _save_settings(self):
        """Save settings to disk."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save settings: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Search resume persistence
    # ------------------------------------------------------------------
    def _save_progress(
        self,
        provider: str,
        current_index: int,
        total: int,
        found: int,
        missing: int,
        rate_limited: int,
        elapsed_seconds: float,
    ):
        """Persist resumable search state to disk."""
        found_rows, rate_limited_rows = self._build_progress_snapshot(current_index)
        payload = {
            "version": 2,
            "provider": provider,
            "file_path": self.current_file_path,
            "file_type": self.current_file_type,
            "current_index": max(0, current_index),
            "total": total,
            "found": found,
            "missing": missing,
            "rate_limited": rate_limited,
            "elapsed_seconds": max(0.0, elapsed_seconds),
            "saved_at": time.time(),
            "found_rows": found_rows,
            "rate_limited_rows": rate_limited_rows,
        }
        tmp_path = self.progress_file.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, separators=(",", ":"))
            tmp_path.replace(self.progress_file)
        except Exception as e:
            self.send_log(f"Failed to save progress snapshot: {e}", "warning")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def _load_progress(self) -> Optional[Dict[str, Any]]:
        """Load resumable search state from disk."""
        try:
            if not self.progress_file.exists():
                return None
            with open(self.progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            file_path = data.get("file_path", "")
            if not file_path:
                return None

            # v1 snapshots stored full tracks, v2 stores compact found/rate-limited rows.
            version = int(data.get("version", 1))
            if version == 1:
                tracks = data.get("tracks")
                if not isinstance(tracks, list):
                    return None
            else:
                if not isinstance(data.get("found_rows", []), list):
                    data["found_rows"] = []
                if not isinstance(data.get("rate_limited_rows", []), list):
                    data["rate_limited_rows"] = []
            return data
        except Exception as e:
            self.send_log(f"Failed to load saved progress: {e}", "warning")
            return None

    def _clear_progress(self):
        """Remove persisted resumable state."""
        try:
            if self.progress_file.exists():
                self.progress_file.unlink()
        except Exception as e:
            self.send_log(f"Failed to clear saved progress: {e}", "warning")

    def _build_progress_snapshot(self, current_index: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return compact per-row state for processed rows only."""
        processed_limit = min(max(0, int(current_index)), len(self.current_tracks))
        found_rows: List[Dict[str, Any]] = []
        rate_limited_rows: List[Dict[str, Any]] = []

        for idx in range(processed_limit):
            track = self.current_tracks[idx]
            base = {
                "index": idx,
                "artist": track.get("artist", ""),
                "track": track.get("track", ""),
                "album": track.get("album", ""),
                "isrc": track.get("isrc", ""),
            }

            if track.get("_found"):
                found_rows.append({
                    **base,
                    "source": track.get("_source", ""),
                    "artist_matched": track.get("_artist_matched", ""),
                    "album_matched": track.get("_album_matched", ""),
                })
            elif track.get("_rate_limited"):
                rate_limited_rows.append({
                    **base,
                    "error": track.get("_error", ""),
                })

        return found_rows, rate_limited_rows

    def _restore_progress_snapshot(self, state: Dict[str, Any]):
        """Apply persisted per-row state to current_tracks before resume."""
        version = int(state.get("version", 1))
        if version == 1:
            saved_tracks = state.get("tracks", [])
            if isinstance(saved_tracks, list) and len(saved_tracks) == len(self.current_tracks):
                self.current_tracks = saved_tracks
                self.rate_limited_tracks = [t for t in self.current_tracks if t.get("_rate_limited")]
            return

        current_index = min(
            max(0, int(state.get("current_index", 0))),
            len(self.current_tracks),
        )
        for idx in range(current_index):
            track = self.current_tracks[idx]
            track["_found"] = False
            track["_rate_limited"] = False
            track["_source"] = ""
            track["_artist_matched"] = ""
            track["_album_matched"] = ""
            track["_error"] = ""

        for row in state.get("found_rows", []):
            try:
                idx = int(row.get("index", -1))
            except Exception:
                continue
            if idx < 0 or idx >= len(self.current_tracks):
                continue
            track = self.current_tracks[idx]
            track["artist"] = str(row.get("artist", track.get("artist", "")))
            track["track"] = str(row.get("track", track.get("track", "")))
            track["album"] = str(row.get("album", track.get("album", "")))
            track["isrc"] = str(row.get("isrc", track.get("isrc", "")))
            track["_found"] = True
            track["_rate_limited"] = False
            track["_source"] = str(row.get("source", ""))
            track["_artist_matched"] = str(row.get("artist_matched", ""))
            track["_album_matched"] = str(row.get("album_matched", ""))
            track["_error"] = ""

        rate_limited_tracks: List[Dict[str, Any]] = []
        for row in state.get("rate_limited_rows", []):
            try:
                idx = int(row.get("index", -1))
            except Exception:
                continue
            if idx < 0 or idx >= len(self.current_tracks):
                continue
            track = self.current_tracks[idx]
            track["artist"] = str(row.get("artist", track.get("artist", "")))
            track["track"] = str(row.get("track", track.get("track", "")))
            track["album"] = str(row.get("album", track.get("album", "")))
            track["isrc"] = str(row.get("isrc", track.get("isrc", "")))
            track["_found"] = False
            track["_rate_limited"] = True
            track["_source"] = ""
            track["_artist_matched"] = ""
            track["_album_matched"] = ""
            track["_error"] = str(row.get("error", "Rate limited"))
            rate_limited_tracks.append(track)

        self.rate_limited_tracks = rate_limited_tracks

    def _send_resume_state(self):
        """Emit resume state summary for frontend startup dialog."""
        state = self._load_progress()
        if not state:
            self.send_message({"type": "resumeState", "available": False})
            return

        file_path = state.get("file_path", "")
        self.send_message({
            "type": "resumeState",
            "available": bool(file_path and Path(file_path).exists()),
            "filePath": file_path,
            "fileType": state.get("file_type", ""),
            "provider": state.get("provider", "musicbrainz_api"),
            "current": int(state.get("current_index", 0)),
            "total": int(state.get("total", 0)),
            "found": int(state.get("found", 0)),
            "missing": int(state.get("missing", 0)),
            "rateLimited": int(state.get("rate_limited", 0)),
            "elapsedSeconds": float(state.get("elapsed_seconds", 0.0)),
        })

    async def _batch_lookup_apple_music_isrc(self, tracks: List[Dict], start_time: float = 0, total_tracks: int = 0) -> Dict[str, Dict[str, str]]:
        """Prefetch Apple Music matches for ISRC codes in batches (max 25/request)."""
        if not tracks or not self.music_service:
            return {}

        isrc_codes = sorted({
            _normalize_isrc(t.get("isrc", ""))
            for t in tracks
            if _normalize_isrc(t.get("isrc", ""))
        })
        if not isrc_codes:
            return {}

        if not hasattr(self.music_service, "_is_apple_music_configured") or not self.music_service._is_apple_music_configured():
            return {}

        get_service = getattr(self.music_service, "_get_apple_music_service", None)
        if not callable(get_service):
            return {}

        apple_service = get_service()
        if not apple_service:
            return {}

        matches: Dict[str, Dict[str, str]] = {}
        total_batches = (len(isrc_codes) + 24) // 25

        for batch_idx in range(total_batches):
            if self.stop_search_flag:
                break
            chunk = isrc_codes[batch_idx * 25:(batch_idx + 1) * 25]
            try:
                await self._rate_limiter.acquire()
                response = await apple_service.lookup_by_isrc(chunk)
            except Exception as e:
                self.send_log(f"ISRC batch {batch_idx + 1}/{total_batches} failed: {e}", "warning")
                continue

            for song in response.get("data", []):
                attrs = song.get("attributes", {})
                code = _normalize_isrc(attrs.get("isrc", ""))
                if not code:
                    continue
                matches[code] = {
                    "artist": attrs.get("artistName", ""),
                    "album": attrs.get("albumName", ""),
                    "track": attrs.get("name", ""),
                }

            phase2_msg = f"Phase 2/3: ISRC batch {batch_idx + 1}/{total_batches} ({len(matches)} matched)"
            self.send_status(phase2_msg)
            self.send_progress(
                current=0, total=total_tracks or total_batches,
                found=0, missing=0, provider="apple_music",
                status=phase2_msg,
                elapsed_seconds=time.time() - start_time if start_time else 0,
                estimated_remaining_seconds=(total_batches - batch_idx - 1) * self._rate_limiter._interval,
                rate_limited=0,
            )

        if matches:
            self.send_log(
                f"ISRC batch lookup matched {len(matches)} of {len(isrc_codes)} unique codes",
                "info",
            )
        return matches

    async def _batch_lookup_albums_by_container_id(
        self,
        tracks: List[Dict],
        start_time: float = 0,
        total_tracks: int = 0,
    ) -> Dict[str, Dict[str, Any]]:
        """Prefetch album data for tracks that have Apple Music Container IDs.

        Groups tracks by container_id, fetches each unique album once,
        and returns a mapping of container_id -> album track list.
        Each album entry has 'artist' (album artist) and 'tracks' (list of
        {name, artistName, albumName, durationInMillis, isrc, trackNumber}).
        """
        if not tracks or not self.music_service:
            return {}

        # Fallback storefront: user's configured setting (defaults to "us")
        fallback_storefront = self.settings.get("itunes_country", "us").lower()

        # Collect unique album container IDs with storefronts from CSV data
        album_ids: Dict[str, str] = {}  # container_id -> storefront
        for t in tracks:
            cid = t.get("_container_id", "")
            ctype = t.get("_container_type", "")
            if not cid or ctype != "ALBUM":
                continue
            # Only numeric IDs are Apple Music catalog IDs
            if not cid.isdigit():
                continue
            if cid not in album_ids:
                iso = t.get("_iso_country", "")
                storefront = ISO_TO_STOREFRONT.get(iso, "") if iso else ""
                album_ids[cid] = storefront or fallback_storefront

        if not album_ids:
            return {}

        if not hasattr(self.music_service, "_is_apple_music_configured") or not self.music_service._is_apple_music_configured():
            return {}

        get_service = getattr(self.music_service, "_get_apple_music_service", None)
        if not callable(get_service):
            return {}

        apple_service = get_service()
        if not apple_service:
            return {}

        self.send_log(
            f"Looking up {len(album_ids)} unique albums by Container ID...",
            "info",
        )

        album_cache: Dict[str, Dict[str, Any]] = {}
        fetched = 0
        failed = 0
        total_albums = len(album_ids)

        for album_idx, (container_id, storefront) in enumerate(album_ids.items()):
            if self.stop_search_flag:
                break
            try:
                await self._rate_limiter.acquire()
                response = await apple_service.lookup_album_with_tracks(
                    container_id, storefront=storefront,
                )
                album_data = (response.get("data") or [None])[0]
                if not album_data:
                    failed += 1
                    continue

                album_attrs = album_data.get("attributes", {})
                album_artist = album_attrs.get("artistName", "")
                album_name = album_attrs.get("name", "")

                # Extract tracks from relationships
                track_list = []
                relationships = album_data.get("relationships", {})
                tracks_rel = relationships.get("tracks", {})
                for song in tracks_rel.get("data", []):
                    sa = song.get("attributes", {})
                    track_list.append({
                        "name": sa.get("name", ""),
                        "artistName": sa.get("artistName", ""),
                        "albumName": sa.get("albumName", album_name),
                        "durationInMillis": sa.get("durationInMillis", 0),
                        "isrc": sa.get("isrc", ""),
                        "trackNumber": sa.get("trackNumber", 0),
                    })

                album_cache[container_id] = {
                    "artist": album_artist,
                    "album": album_name,
                    "tracks": track_list,
                }
                fetched += 1
            except Exception as e:
                failed += 1
                err_str = str(e)
                if "404" in err_str:
                    self.send_log(f"Album {container_id} no longer available on Apple Music (removed or region-restricted)", "info")
                else:
                    self.send_log(f"Album lookup failed for {container_id}: {e}", "warning")

            phase1_msg = f"Phase 1/3: Album {album_idx + 1}/{total_albums} ({fetched} fetched, {failed} unavailable)"
            self.send_status(phase1_msg)
            self.send_progress(
                current=0, total=total_tracks or total_albums,
                found=0, missing=0, provider="apple_music",
                status=phase1_msg,
                elapsed_seconds=time.time() - start_time if start_time else 0,
                estimated_remaining_seconds=(total_albums - album_idx - 1) * self._rate_limiter._interval,
                rate_limited=0,
            )

        self.send_log(
            f"Album lookup complete: {fetched} fetched, {failed} unavailable, "
            f"{sum(len(a['tracks']) for a in album_cache.values())} album tracks cached",
            "info",
        )
        if failed > 0:
            self.send_log(
                f"{failed} albums were unavailable (removed or region-restricted). "
                f"Those tracks will be matched by ISRC or name search instead.",
                "info",
            )
        return album_cache

    @staticmethod
    def _match_track_in_album(
        song_name: str,
        duration_ms: float,
        album_tracks: List[Dict],
        tolerance_ms: float = 3000,
    ) -> Optional[Dict]:
        """Match a CSV track to an album track by name and duration.

        Returns the best matching track dict or None.
        """
        if not album_tracks or not song_name:
            return None

        song_lower = song_name.lower().strip()
        candidates = []

        for t in album_tracks:
            track_name_lower = t.get("name", "").lower().strip()
            if not track_name_lower:
                continue

            # Exact name match
            if track_name_lower == song_lower:
                candidates.append((0, t))
                continue

            # One is a substring of the other (handles truncation, extra suffixes)
            if song_lower in track_name_lower or track_name_lower in song_lower:
                candidates.append((1, t))
                continue

            # Fuzzy: strip common suffixes and try again
            # e.g. "Song (Remastered)" vs "Song"
            stripped_song = re.sub(r"\s*\(.*?\)\s*$", "", song_lower).strip()
            stripped_track = re.sub(r"\s*\(.*?\)\s*$", "", track_name_lower).strip()
            if stripped_song and stripped_track and (stripped_song == stripped_track):
                candidates.append((2, t))

        if not candidates:
            return None

        # Sort by match quality (lower is better)
        candidates.sort(key=lambda x: x[0])

        # If only one candidate, return it
        if len(candidates) == 1:
            return candidates[0][1]

        # Multiple candidates: use duration to disambiguate
        if duration_ms and duration_ms > 0:
            best = None
            best_diff = float("inf")
            for _, t in candidates:
                t_dur = t.get("durationInMillis", 0)
                if t_dur > 0:
                    diff = abs(t_dur - duration_ms)
                    if diff < best_diff:
                        best_diff = diff
                        best = t
            if best and best_diff <= tolerance_ms:
                return best

        # Fall back to best name match
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Service lifecycle
    # ------------------------------------------------------------------
    def initialize_service(self):
        """Initialize the music search service."""
        try:
            if self.music_service is None:
                self.music_service = MusicSearchServiceV2()
            if self.settings:
                self.music_service.settings.update(self.settings)
                if "search_provider" in self.settings:
                    self.music_service.set_search_provider(self.settings["search_provider"])
            # Wire rate-limit callbacks for frontend visibility + skip control.
            self.music_service.rate_limit_callback = self._on_rate_limit_notice
            self.music_service.rate_limit_wait_callback = self._on_rate_limit_wait
            self.music_service.rate_limit_hit_callback = self._on_rate_limit_hit
            self.send_message({"type": "initialized", "success": True})
        except Exception as e:
            self.send_error(str(e), "initialize_service")

    def apply_settings(self, settings: Dict[str, Any]):
        """Apply settings from frontend to service."""
        if "storage_root" in settings:
            storage_root = settings["storage_root"]
            if storage_root is None:
                settings["storage_root"] = ""
            elif not isinstance(storage_root, str):
                raise ValueError("Storage location must be a path")
            else:
                storage_root = storage_root.strip()
                if storage_root:
                    storage_path = Path(storage_root).expanduser()
                    if not storage_path.is_absolute():
                        raise ValueError("Storage location must be an absolute path")
                    storage_path.mkdir(parents=True, exist_ok=True)
                    probe = storage_path / ".apple-music-converter-write-test"
                    probe.write_text("ok", encoding="utf-8")
                    probe.unlink()
                    settings["storage_root"] = str(storage_path)
        self.settings.update(settings)
        self._save_settings()
        if self.music_service:
            self.music_service.settings.update(settings)
            if "search_provider" in settings:
                self.music_service.set_search_provider(settings["search_provider"])
        if "apple_music_requests_per_minute" in settings:
            self._rate_limiter.update_rate(int(settings["apple_music_requests_per_minute"]))

    def _on_rate_limit_notice(self, wait_seconds: float):
        """Callback from MusicSearchService when iTunes wait starts."""
        self.send_status(f"iTunes rate limit reached, waiting {int(round(wait_seconds))}s")

    def _on_rate_limit_hit(self):
        """Callback from MusicSearchService when iTunes 403/429 rate limit is detected."""
        self.send_status("iTunes API rate limit detected")

    def _on_rate_limit_wait(self, wait_seconds: float):
        """Interruptible wait callback with explicit skip signal support."""
        total = max(0.0, float(wait_seconds))
        self._rate_limit_wait_active = True
        self._skip_rate_limit_wait.clear()
        self.send_message({
            "type": "rateLimitWait",
            "active": True,
            "seconds": total,
            "skipped": False,
        })

        skipped = False
        deadline = time.monotonic() + total
        while True:
            if self.stop_search_flag:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if self._skip_rate_limit_wait.wait(timeout=min(0.25, remaining)):
                skipped = True
                break

        self._skip_rate_limit_wait.clear()
        self._rate_limit_wait_active = False
        self.send_message({
            "type": "rateLimitWait",
            "active": False,
            "seconds": 0.0,
            "skipped": skipped,
        })
        if skipped:
            self.send_status("Skipped current iTunes rate-limit wait")

    def skip_rate_limit_wait(self):
        """Skip active iTunes rate-limit wait (one-shot)."""
        if not self._rate_limit_wait_active:
            self.send_status("No active rate-limit wait")
            return

        self.send_status("Skipping current rate-limit wait...")
        self._skip_rate_limit_wait.set()

    # ------------------------------------------------------------------
    # Database status
    # ------------------------------------------------------------------
    def get_database_status(self) -> Dict[str, Any]:
        """Get status of available databases/APIs."""
        status = {
            "type": "databaseStatus",
            "downloaded": False,
            "trackCount": 0,
            "size": "0 B",
            "lastUpdated": "Never",
            "optimized": False,
        }

        if self.music_service:
            try:
                mb = self.music_service.musicbrainz_manager
                if mb:
                    db_available = False
                    if hasattr(mb, 'is_database_available'):
                        db_available = mb.is_database_available()
                    elif hasattr(mb, 'is_ready'):
                        db_available = mb.is_ready()

                    status["downloaded"] = db_available

                    if db_available:
                        if hasattr(mb, 'get_track_count'):
                            try:
                                status["trackCount"] = mb.get_track_count() or 0
                            except Exception:
                                pass

                        if hasattr(mb, 'data_dir'):
                            data_dir = Path(mb.data_dir) if mb.data_dir else None
                            if data_dir and data_dir.exists():
                                total_size = sum(f.stat().st_size for f in data_dir.rglob('*') if f.is_file())
                                if total_size > 1_000_000_000:
                                    status["size"] = f"{total_size / 1_000_000_000:.1f} GB"
                                elif total_size > 1_000_000:
                                    status["size"] = f"{total_size / 1_000_000:.1f} MB"
                                else:
                                    status["size"] = f"{total_size / 1000:.0f} KB"

                        if hasattr(mb, 'is_optimized'):
                            try:
                                status["optimized"] = mb.is_optimized()
                            except Exception:
                                pass

                        if hasattr(mb, 'get_optimization_status'):
                            try:
                                opt = mb.get_optimization_status()
                                status["optimized"] = opt.get("ready", False)
                            except Exception:
                                pass

            except Exception as e:
                self.send_log(f"Error checking database: {e}", "warning")

        self.send_message(status)
        return status

    # ------------------------------------------------------------------
    # CSV file operations
    # ------------------------------------------------------------------
    def _detect_encoding(self, file_path: str) -> str:
        """Detect CSV file encoding."""
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(4096)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue

        try:
            import chardet
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read(10000))
                return result.get('encoding') or 'utf-8'
        except ImportError:
            pass

        return 'utf-8'

    def analyze_csv(self, file_path: str) -> Dict[str, Any]:
        """Analyze a CSV file and return info."""
        try:
            path = Path(file_path)
            if not path.exists():
                self.send_error(f"File not found: {file_path}", "analyze_csv")
                return {}

            self.send_status("Detecting file encoding...")
            encoding = self._detect_encoding(file_path)
            self.send_log(f"Encoding detected: {encoding}")

            with open(path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()

            file_type = detect_file_type(first_line)
            self.send_log(f"File type: {file_type}")

            self.send_status("Counting rows...")
            with open(path, 'r', encoding=encoding) as f:
                row_count = sum(1 for _ in f) - 1

            # Check for exported CSV format (Artist/Track/Album/Timestamp columns)
            is_converted = False
            found_count = 0
            missing_count = 0
            exported_columns = {"Artist", "Track", "Album", "Timestamp"}
            header_cols = {c.strip() for c in first_line.split(",")}
            if exported_columns.issubset(header_cols):
                is_converted = True
                self.send_log("Detected previously exported CSV format")
                try:
                    import pandas as pd
                    df = pd.read_csv(file_path, encoding=encoding)
                    df = df.fillna("")
                    for _, row in df.iterrows():
                        artist = str(row.get("Artist", "")).strip()
                        track = str(row.get("Track", "")).strip()
                        if artist and track:
                            found_count += 1
                        else:
                            missing_count += 1
                    self.send_log(f"Exported CSV: {found_count} found, {missing_count} missing")
                except Exception:
                    pass

            self.send_status(f"Analyzed: {max(row_count, 0):,} rows")

            result = {
                "type": "fileAnalysis",
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "rowCount": max(row_count, 0),
                "fileType": file_type,
                "isConvertedCsv": is_converted,
                "foundCount": found_count,
                "missingCount": missing_count,
            }

            self.send_message(result)
            return result

        except Exception as e:
            self.send_error(str(e), "analyze_csv")
            return {}

    def get_preview(self, file_path: str) -> bool:
        """Get first 100 rows of CSV for preview, with normalized columns."""
        try:
            import pandas as pd

            self.send_status("Loading preview rows...")
            encoding = self._detect_encoding(file_path)

            # Read header to detect file type
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()
            file_type = detect_file_type(first_line)

            df = pd.read_csv(file_path, nrows=100, encoding=encoding)
            df = df.fillna('')
            raw_rows = df.to_dict('records')

            self.send_status(f"Normalizing {len(raw_rows)} preview rows...")

            # Normalize to standard columns for preview
            normalized = normalize_tracks(raw_rows, file_type)

            # Build preview rows: [Artist, Track, Album, Timestamp, Duration]
            preview_rows = []
            for t in normalized:
                preview_rows.append([
                    t.get("artist", ""),
                    t.get("track", ""),
                    t.get("album", ""),
                    t.get("timestamp", ""),
                    str(t.get("duration", "")),
                ])

            self.send_message({
                "type": "csvPreview",
                "path": file_path,
                "headers": ["Artist", "Track", "Album", "Timestamp", "Duration"],
                "rows": preview_rows,
            })
            self.send_log(f"Preview ready: {len(preview_rows)} rows")
            return True

        except Exception as e:
            self.send_error(str(e), "get_preview")
            return False

    def set_preview_edits(self, file_path: str, rows: List[Dict[str, Any]]) -> bool:
        """Store preview edits keyed by file path and row index."""
        if not file_path:
            self.send_error("No file path provided", "set_preview_edits")
            return False

        edits_by_row: Dict[int, Dict[str, str]] = {}
        for entry in rows or []:
            try:
                idx = int(entry.get("index", -1))
            except (TypeError, ValueError):
                continue
            if idx < 0:
                continue

            edits_by_row[idx] = {
                "artist": str(entry.get("artist", "")),
                "track": str(entry.get("track", "")),
                "album": str(entry.get("album", "")),
            }

        if edits_by_row:
            self.preview_edits_by_file[file_path] = edits_by_row
        else:
            self.preview_edits_by_file.pop(file_path, None)

        self.send_status(
            f"Saved {len(edits_by_row)} preview edit"
            + ("" if len(edits_by_row) == 1 else "s")
        )
        return True

    def _apply_preview_edits(self, file_path: str):
        edits = self.preview_edits_by_file.get(file_path)
        if not edits:
            return

        applied = 0
        for idx, row_edits in edits.items():
            if idx < 0 or idx >= len(self.current_tracks):
                continue
            track = self.current_tracks[idx]
            for key in ("artist", "track", "album"):
                if key in row_edits and row_edits[key] is not None:
                    track[key] = str(row_edits[key]).strip()
            applied += 1

        if applied:
            self.send_log(f"Applied {applied} preview edits before search", "info")

    def load_csv(self, file_path: str) -> bool:
        """Load and process a CSV file, normalizing columns."""
        try:
            import pandas as pd

            self.send_status("Detecting encoding for full load...")
            encoding = self._detect_encoding(file_path)
            self.send_log(f"Using encoding: {encoding}")

            # Detect file type from header
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()
            self.current_file_type = detect_file_type(first_line)

            # Load full CSV
            self.send_status(f"Reading CSV ({encoding})...")
            self.current_df = pd.read_csv(file_path, encoding=encoding)
            self.current_file_path = file_path
            self.send_status(f"Read {len(self.current_df):,} rows, normalizing...")

            # Normalize to standard track dicts
            raw_rows = self.current_df.fillna('').to_dict('records')
            self.current_tracks = normalize_tracks(raw_rows, self.current_file_type)
            self.send_status(f"Normalized {len(self.current_tracks)} tracks")

            # Detect most common storefront from CSV
            self._detect_csv_storefront()

            self.send_status("Applying preview edits...")
            self._apply_preview_edits(file_path)
            self.rate_limited_tracks = []

            self.send_message({
                "type": "csvLoaded",
                "success": True,
                "rowCount": len(self.current_tracks),
                "fileType": self.current_file_type,
            })
            self.send_log(f"CSV loaded: {len(self.current_tracks)} tracks ready for search")

            return True

        except Exception as e:
            self.send_error(str(e), "load_csv")
            return False

    def _detect_csv_storefront(self):
        """Detect the most common storefront from CSV country data and log it."""
        if not self.current_tracks:
            return

        country_counts: Dict[str, int] = {}
        for t in self.current_tracks:
            iso = t.get("_iso_country", "")
            if iso:
                country_counts[iso] = country_counts.get(iso, 0) + 1

        if not country_counts:
            return

        total_with_country = sum(country_counts.values())
        most_common = max(country_counts, key=lambda k: country_counts[k])
        pct = (country_counts[most_common] / total_with_country) * 100
        storefront = ISO_TO_STOREFRONT.get(most_common, most_common.lower())

        self.send_log(
            f"Detected storefront from CSV: {most_common} ({pct:.0f}% of tracks) -> {storefront}"
        )

        # Auto-set the storefront if it differs from current setting
        current_sf = self.settings.get("itunes_country", "us").lower()
        if storefront != current_sf:
            self.send_log(
                f"Auto-updating storefront from '{current_sf}' to '{storefront}' based on CSV data"
            )
            self.settings["itunes_country"] = storefront
            self._save_settings()
            if self.music_service:
                self.music_service.settings["itunes_country"] = storefront

    def load_exported_csv(self, file_path: str) -> bool:
        """Load a previously exported CSV (Artist/Track/Album/Timestamp format).

        Marks tracks with non-empty Artist+Track as found, others as missing.
        """
        try:
            import pandas as pd

            self.send_status("Loading exported CSV...")
            encoding = self._detect_encoding(file_path)
            df = pd.read_csv(file_path, encoding=encoding)
            df = df.fillna("")
            self.current_df = df
            self.current_file_path = file_path
            self.current_file_type = "Exported"

            tracks = []
            found_count = 0
            missing_count = 0
            for _, row in df.iterrows():
                artist = str(row.get("Artist", "")).strip()
                track_name = str(row.get("Track", "")).strip()
                album = str(row.get("Album", "")).strip()
                timestamp = str(row.get("Timestamp", "")).strip()
                is_found = bool(artist and track_name)

                track_dict = {
                    "artist": artist,
                    "track": track_name,
                    "album": album,
                    "timestamp": timestamp,
                    "duration": 0,
                    "isrc": "",
                    "_found": is_found,
                    "_source": "exported" if is_found else "",
                    "_artist_matched": artist if is_found else "",
                    "_album_matched": album if is_found else "",
                    "_error": "" if is_found else "Missing from previous export",
                    "_rate_limited": False,
                }
                tracks.append(track_dict)
                if is_found:
                    found_count += 1
                else:
                    missing_count += 1

            self.current_tracks = tracks
            self.rate_limited_tracks = []

            self.send_message({
                "type": "csvLoaded",
                "success": True,
                "rowCount": len(tracks),
                "fileType": "Exported",
            })

            # Emit track results for already-found tracks
            for i, t in enumerate(tracks):
                if t["_found"]:
                    self.send_message({
                        "type": "trackResult",
                        "index": i,
                        "artist": t["artist"],
                        "track": t["track"],
                        "album": t["album"],
                        "found": True,
                        "rateLimited": False,
                        "source": "exported",
                    })

            self.send_log(
                f"Loaded exported CSV: {found_count} already found, "
                f"{missing_count} missing (will be re-searched)"
            )
            return True

        except Exception as e:
            self.send_error(str(e), "load_exported_csv")
            return False

    def start_search_missing_only(self, provider: str):
        """Start search only for tracks marked as not found."""
        if not self.current_tracks:
            self.send_error("No tracks loaded", "start_search_missing_only")
            return

        retry_pairs = [
            (idx, track)
            for idx, track in enumerate(self.current_tracks)
            if not track.get("_found")
        ]

        if not retry_pairs:
            self.send_log("All tracks already found - nothing to search")
            self.send_message({
                "type": "searchComplete",
                "total": len(self.current_tracks),
                "found": len(self.current_tracks),
                "missing": 0,
                "rateLimited": 0,
                "provider": provider,
            })
            return

        retry_tracks = [track for _, track in retry_pairs]
        retry_indices = [idx for idx, _ in retry_pairs]

        # Reset state for missing tracks
        for t in retry_tracks:
            t["_found"] = False
            t["_error"] = ""
            t["_source"] = ""
            t["_artist_matched"] = ""
            t["_album_matched"] = ""

        self.send_log(f"Searching for {len(retry_tracks)} missing tracks with {provider}")
        self.start_search(provider, run_tracks=retry_tracks, run_indices=retry_indices)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def _sleep_async(self, seconds: float):
        await asyncio.sleep(max(0.0, seconds))

    async def _interruptible_sleep(self, seconds: float, allow_skip: bool = False) -> Tuple[bool, bool]:
        """Sleep in short intervals so stop/skip signals can interrupt waits."""
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            if self.stop_search_flag:
                return False, False
            if allow_skip and self._skip_rate_limit_wait.is_set():
                self._skip_rate_limit_wait.clear()
                return False, True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True, False
            await asyncio.sleep(min(0.25, remaining))

    @staticmethod
    def _is_transient_search_error(error_message: str) -> bool:
        if not error_message:
            return False

        lowered = error_message.lower()
        if "403" in lowered or "rate limit" in lowered:
            return False

        transient_tokens = [
            "timeout",
            "timed out",
            "network",
            "connection",
            "temporar",
            "unavailable",
            "reset",
            "refused",
            "dns",
            "502",
            "503",
            "504",
        ]
        return any(token in lowered for token in transient_tokens)

    async def _search_with_backoff(
        self,
        song_name: str,
        artist_name: Optional[str],
        album_name: Optional[str],
        isrc: Optional[str],
        timeout_seconds: float = 15.0,
        storefront: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search with bounded retries for transient network failures."""
        if not self.music_service:
            return {"success": False, "error": "Music service unavailable"}

        # Pre-emptive throttle for Apple Music API only (iTunes and MusicBrainz have their own rate limiters)
        provider = self.music_service.get_search_provider() if hasattr(self.music_service, 'get_search_provider') else ""
        if provider == "apple_music":
            await self._rate_limiter.acquire()

        # Local DB needs a longer timeout (cold start, large queries)
        if provider == "musicbrainz":
            timeout_seconds = max(timeout_seconds, 60.0)

        # Temporarily override storefront if provided per-track
        original_storefront = None
        if storefront and self.music_service:
            original_storefront = self.music_service.settings.get("itunes_country")
            self.music_service.settings["itunes_country"] = storefront

        backoff_seconds = [2.0, 5.0, 10.0]
        max_attempts = len(backoff_seconds) + 1

        for attempt in range(max_attempts):
            try:
                result = await asyncio.wait_for(
                    self.music_service.search_song(
                        song_name=song_name,
                        artist_name=artist_name,
                        album_name=album_name,
                        isrc=isrc,
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                result = {"success": False, "error": f"Search timed out ({int(timeout_seconds)}s)"}
            except Exception as exc:  # noqa: BLE001 - search provider exceptions are surfaced as errors
                result = {"success": False, "error": str(exc)}

            if result and result.get("success"):
                if original_storefront is not None and self.music_service:
                    self.music_service.settings["itunes_country"] = original_storefront
                return result

            error_message = result.get("error", "") if isinstance(result, dict) else str(result)

            # Check for 429 rate limit from proxy
            if "429" in error_message:
                # Try to extract resetMs from error
                reset_match = re.search(r"resetMs[\"']?\s*[:=]\s*(\d+)", error_message)
                wait_ms = int(reset_match.group(1)) if reset_match else 60000
                wait_secs = wait_ms / 1000.0
                self.send_log(
                    f"[WARN] Rate limited by server (429). Waiting {wait_secs:.0f}s before retrying. "
                    f"Consider lowering requests/min in settings.",
                    "warning",
                )
                self._rate_limit_wait_active = True
                self._skip_rate_limit_wait.clear()
                self.send_message({
                    "type": "rateLimitWait",
                    "active": True,
                    "seconds": wait_secs,
                    "skipped": False,
                })
                completed_wait, skipped_wait = await self._interruptible_sleep(wait_secs, allow_skip=True)
                self._rate_limit_wait_active = False
                self.send_message({
                    "type": "rateLimitWait",
                    "active": False,
                    "seconds": 0.0,
                    "skipped": skipped_wait,
                })
                if skipped_wait:
                    self.send_status("Skipped current 429 retry wait")
                if self.stop_search_flag:
                    if original_storefront is not None and self.music_service:
                        self.music_service.settings["itunes_country"] = original_storefront
                    return {"success": False, "error": "Search stopped"}
                # Retry once after server-indicated wait
                if attempt < max_attempts - 1 and (completed_wait or skipped_wait):
                    continue

            should_retry = (
                attempt < len(backoff_seconds)
                and self._is_transient_search_error(error_message)
            )
            if not should_retry:
                if original_storefront is not None and self.music_service:
                    self.music_service.settings["itunes_country"] = original_storefront
                return result if isinstance(result, dict) else {"success": False, "error": error_message}

            wait_seconds = backoff_seconds[attempt]
            self.send_log(
                f"Transient error, retrying in {int(wait_seconds)}s: {error_message}",
                "warning",
            )
            completed_wait, _ = await self._interruptible_sleep(wait_seconds, allow_skip=False)
            if not completed_wait:
                if original_storefront is not None and self.music_service:
                    self.music_service.settings["itunes_country"] = original_storefront
                return {"success": False, "error": "Search stopped"}

        # Restore original storefront
        if original_storefront is not None and self.music_service:
            self.music_service.settings["itunes_country"] = original_storefront

        return {"success": False, "error": "Search failed after retries"}

    def start_search(
        self,
        provider: str,
        resume_state: Optional[Dict[str, Any]] = None,
        run_tracks: Optional[List[Dict[str, Any]]] = None,
        run_indices: Optional[List[int]] = None,
    ):
        """Start searching tracks with specified provider."""
        tracks_for_run = run_tracks if run_tracks is not None else self.current_tracks
        if not tracks_for_run:
            self.send_error("No tracks loaded", "start_search")
            return

        if run_indices is not None and len(run_indices) != len(tracks_for_run):
            self.send_error("run_indices must match run_tracks length", "start_search")
            return

        if run_indices is None:
            run_indices = list(range(len(tracks_for_run)))

        if self.search_thread and self.search_thread.is_alive():
            # Signal the old search to stop (non-blocking)
            self.stop_search_flag = True
            if self.music_service and hasattr(self.music_service, '_exit_event'):
                self.music_service._exit_event.set()
            self.search_thread.join(timeout=2.0)
            if self.search_thread.is_alive():
                self.send_error("Previous search still running, please wait", "start_search")
                return

        if not self.music_service:
            self.initialize_service()
            if not self.music_service:
                self.send_error("Failed to initialize music service", "start_search")
                return

        # Set the provider
        self.music_service.set_search_provider(provider)
        self.stop_search_flag = False
        self.pause_search_flag = False
        self._skip_rate_limit_wait.clear()
        self._rate_limit_wait_active = False
        # Clear exit event for the new search
        if hasattr(self.music_service, '_exit_event'):
            self.music_service._exit_event.clear()
        self.rate_limited_tracks = [t for t in self.current_tracks if t.get("_rate_limited")]

        start_index = 0
        found = 0
        missing = 0
        rate_limited = len([t for t in tracks_for_run if t.get("_rate_limited")])
        resumed_elapsed = 0.0

        if resume_state and run_tracks is None:
            start_index = int(resume_state.get("current_index", 0))
            found = int(resume_state.get("found", 0))
            missing = int(resume_state.get("missing", 0))
            rate_limited = int(resume_state.get("rate_limited", rate_limited))
            resumed_elapsed = float(resume_state.get("elapsed_seconds", 0.0))
        elif run_tracks is None:
            self._clear_progress()

        def search_worker():
            # Create a new event loop for this thread (search_song is async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(
                    self._run_search(
                        provider=provider,
                        start_index=start_index,
                        found=found,
                        missing=missing,
                        rate_limited=rate_limited,
                        resumed_elapsed=resumed_elapsed,
                        run_tracks=tracks_for_run,
                        run_indices=run_indices,
                    )
                )
            except Exception as e:
                import traceback
                traceback.print_exc(file=sys.stderr)
                self.send_error(str(e), "search_worker")
                # Ensure the UI resets if the search thread crashes
                self.send_message({
                    "type": "searchStopped",
                    "success": False,
                    "current": 0,
                    "total": len(tracks_for_run),
                    "found": 0,
                    "missing": 0,
                })
            finally:
                loop.close()

        self.search_thread = threading.Thread(target=search_worker, daemon=True)
        self.search_thread.start()
        if run_tracks is not None:
            self.send_log(f"Retrying {len(tracks_for_run)} rate-limited tracks with provider: {provider}")
        elif resume_state and start_index > 0:
            self.send_log(f"Resumed search with provider: {provider} at track {start_index}/{len(self.current_tracks)}")
        else:
            self.send_log(f"Search started with provider: {provider}")

    async def _run_search(
        self,
        provider: str,
        start_index: int = 0,
        found: int = 0,
        missing: int = 0,
        rate_limited: int = 0,
        resumed_elapsed: float = 0.0,
        run_tracks: Optional[List[Dict[str, Any]]] = None,
        run_indices: Optional[List[int]] = None,
    ):
        """Async search loop - runs search_song for each track."""
        tracks_for_run = run_tracks if run_tracks is not None else self.current_tracks
        total = len(tracks_for_run)
        index_map = run_indices if run_indices is not None else list(range(total))
        persist_progress = run_tracks is None

        if len(index_map) != total:
            raise ValueError("run_indices length must match run_tracks length")

        start_time = time.time() - max(0.0, resumed_elapsed)

        if start_index >= total:
            self.send_message({
                "type": "searchComplete",
                "total": total,
                "found": found,
                "missing": missing,
                "rateLimited": rate_limited,
                "provider": provider,
            })
            if persist_progress:
                self._clear_progress()
            return

        # Log rate limit info for API-based providers
        remaining_tracks = total - start_index
        if provider in ("apple_music", "itunes", "musicbrainz_api"):
            rpm = self._rate_limiter.requests_per_minute
            interval = self._rate_limiter._interval
            est_minutes = (remaining_tracks * interval) / 60.0
            self.send_log(
                f"[INFO] API rate: {rpm} requests/min (1 every {interval:.1f}s)",
            )
            if est_minutes > 1:
                self.send_log(
                    f"[INFO] Estimated time for {remaining_tracks} tracks: ~{est_minutes:.0f} minutes",
                )
                if est_minutes > 30:
                    self.send_log(
                        "[INFO] You can leave this running in the background or overnight for large libraries",
                    )

        isrc_batch_matches: Dict[str, Dict[str, str]] = {}
        album_cache: Dict[str, Dict[str, Any]] = {}
        skip_single_isrc_lookup = False
        if provider == "apple_music":
            # Phase 1: Container ID album lookups (most accurate)
            has_container_ids = any(
                t.get("_container_id", "") and t.get("_container_type", "") == "ALBUM"
                for t in tracks_for_run[start_index:]
            )
            if has_container_ids:
                album_ids_count = len({
                    t.get("_container_id", "")
                    for t in tracks_for_run[start_index:]
                    if t.get("_container_id", "") and t.get("_container_type", "") == "ALBUM"
                    and t.get("_container_id", "").isdigit()
                })
                self.send_status("Phase 1/3: Looking up album metadata...")
                self.send_log(f"Found {album_ids_count} unique albums to look up")
                self.send_progress(
                    current=0, total=total, found=0, missing=0,
                    provider=provider,
                    status=f"Phase 1/3: Looking up {album_ids_count} albums...",
                    elapsed_seconds=time.time() - start_time,
                    estimated_remaining_seconds=album_ids_count * self._rate_limiter._interval,
                    rate_limited=0,
                )
                album_cache = await self._batch_lookup_albums_by_container_id(tracks_for_run[start_index:], start_time=start_time, total_tracks=total)

            # Phase 2: ISRC batch lookups (for tracks without container match)
            has_isrc_candidates = any(
                _normalize_isrc(t.get("isrc", ""))
                for t in tracks_for_run[start_index:]
            )
            if has_isrc_candidates:
                isrc_count = len({
                    _normalize_isrc(t.get("isrc", ""))
                    for t in tracks_for_run[start_index:]
                    if _normalize_isrc(t.get("isrc", ""))
                })
                self.send_status("Phase 2/3: Batch matching ISRCs...")
                self.send_log(f"Matching {isrc_count} unique ISRC codes")
                # Send a progress event so the main UI shows activity
                self.send_progress(
                    current=0, total=total, found=0, missing=0,
                    provider=provider,
                    status=f"Phase 2/3: Matching {isrc_count} ISRCs...",
                    elapsed_seconds=time.time() - start_time,
                    estimated_remaining_seconds=(isrc_count // 25) * self._rate_limiter._interval,
                    rate_limited=0,
                )
                isrc_batch_matches = await self._batch_lookup_apple_music_isrc(tracks_for_run[start_index:], start_time=start_time, total_tracks=total)
                skip_single_isrc_lookup = True

        # Phase 3: Per-track search
        if provider == "apple_music":
            self.send_status("Phase 3/3: Searching individual tracks...")

        # Throttle progress events: send at most every 100 tracks or 0.5s
        _PROGRESS_THROTTLE_TRACKS = 100
        _PROGRESS_THROTTLE_SECS = 0.5
        _last_progress_time = 0.0

        for i in range(start_index, total):
            track = tracks_for_run[i]
            output_index = index_map[i]
            if self.stop_search_flag:
                elapsed = time.time() - start_time
                if persist_progress:
                    self._save_progress(
                        provider=provider,
                        current_index=i,
                        total=total,
                        found=found,
                        missing=missing,
                        rate_limited=rate_limited,
                        elapsed_seconds=elapsed,
                    )
                self.send_message({
                    "type": "searchStopped",
                    "success": True,
                    "current": i,
                    "total": total,
                    "found": found,
                    "missing": missing,
                })
                return

            # Pause loop
            while self.pause_search_flag and not self.stop_search_flag:
                await asyncio.sleep(0.1)

            if self.stop_search_flag:
                elapsed = time.time() - start_time
                if persist_progress:
                    self._save_progress(
                        provider=provider,
                        current_index=i,
                        total=total,
                        found=found,
                        missing=missing,
                        rate_limited=rate_limited,
                        elapsed_seconds=elapsed,
                    )
                return

            artist = track.get("artist", "")
            title = track.get("track", "")
            album = track.get("album", "")
            isrc = track.get("isrc", "")
            normalized_isrc = _normalize_isrc(isrc)
            track_display = f"{artist} - {title}" if artist else title

            # Time estimates
            elapsed = time.time() - start_time
            if i > 0:
                avg_per = elapsed / i
                remaining = avg_per * (total - i)
            else:
                remaining = 0

            # Throttle progress events to avoid flooding the UI
            now = time.time()
            should_send_progress = (
                i == start_index  # first track
                or (i + 1) == total  # last track
                or (i - start_index) % _PROGRESS_THROTTLE_TRACKS == 0
                or (now - _last_progress_time) >= _PROGRESS_THROTTLE_SECS
            )
            if should_send_progress:
                _last_progress_time = now
                self.send_progress(
                    current=i + 1,
                    total=total,
                    found=found,
                    missing=missing,
                    provider=provider,
                    status="Searching...",
                    current_track=track_display,
                    elapsed_seconds=elapsed,
                    estimated_remaining_seconds=remaining,
                    rate_limited=rate_limited,
                )

            # Skip tracks with no useful data
            if not title and not artist:
                missing += 1
                track["_found"] = False
                track["_error"] = "No track or artist data"
                self.send_message({
                    "type": "trackResult",
                    "index": output_index,
                    "artist": track.get("artist", ""),
                    "track": track.get("track", ""),
                    "album": track.get("album", ""),
                    "found": False,
                    "rateLimited": False,
                    "source": "",
                })
                if persist_progress and (((i + 1) % self.PROGRESS_SAVE_INTERVAL) == 0 or i == total - 1):
                    self._save_progress(
                        provider=provider,
                        current_index=i + 1,
                        total=total,
                        found=found,
                        missing=missing,
                        rate_limited=rate_limited,
                        elapsed_seconds=elapsed,
                    )
                # Yield every 200 skipped tracks to prevent event flooding
                if missing % 200 == 0:
                    await asyncio.sleep(0)
                continue

            # Container ID album match (Apple Music provider, Play Activity CSVs)
            if provider == "apple_music" and album_cache:
                container_id = track.get("_container_id", "")
                container_type = track.get("_container_type", "")
                if container_id and container_type == "ALBUM" and container_id in album_cache:
                    album_data = album_cache[container_id]
                    duration_ms = track.get("duration", 0) * 1000  # stored as seconds
                    matched = self._match_track_in_album(
                        song_name=title,
                        duration_ms=duration_ms,
                        album_tracks=album_data.get("tracks", []),
                    )
                    if matched:
                        found += 1
                        track["_found"] = True
                        track["_source"] = "apple_music_album"
                        track["_artist_matched"] = matched.get("artistName", "")
                        track["_album_matched"] = matched.get("albumName", album)
                        if matched.get("artistName"):
                            track["artist"] = matched["artistName"]
                        if matched.get("albumName"):
                            track["album"] = matched["albumName"]
                        if matched.get("isrc"):
                            track["isrc"] = matched["isrc"]

                        self.send_message({
                            "type": "trackResult",
                            "index": output_index,
                            "artist": track.get("artist", ""),
                            "track": track.get("track", ""),
                            "album": track.get("album", ""),
                            "found": True,
                            "rateLimited": False,
                            "source": "apple_music_album",
                        })

                        if persist_progress and ((i + 1) % self.PROGRESS_SAVE_INTERVAL) == 0:
                            self._save_progress(
                                provider=provider,
                                current_index=i + 1,
                                total=total,
                                found=found,
                                missing=missing,
                                rate_limited=rate_limited,
                                elapsed_seconds=elapsed,
                            )
                        # Yield every 50 cached matches to prevent event flooding
                        if found % 50 == 0:
                            await asyncio.sleep(0)
                        continue

            # Batch-primed ISRC match (Apple Music provider)
            if normalized_isrc and provider == "apple_music":
                isrc_match = isrc_batch_matches.get(normalized_isrc)
                if isrc_match:
                    found += 1
                    track["_found"] = True
                    track["_source"] = "apple_music"
                    track["_artist_matched"] = isrc_match.get("artist", artist)
                    track["_album_matched"] = isrc_match.get("album", album)
                    if isrc_match.get("artist"):
                        track["artist"] = isrc_match["artist"]
                    if isrc_match.get("album"):
                        track["album"] = isrc_match["album"]
                    if isrc_match.get("track"):
                        track["track"] = isrc_match["track"]

                    self.send_message({
                        "type": "trackResult",
                        "index": output_index,
                        "artist": track.get("artist", ""),
                        "track": track.get("track", ""),
                        "album": track.get("album", ""),
                        "found": track.get("_found", False),
                        "rateLimited": track.get("_rate_limited", False),
                        "source": track.get("_source", ""),
                    })

                    if persist_progress and ((i + 1) % self.PROGRESS_SAVE_INTERVAL) == 0:
                        self._save_progress(
                            provider=provider,
                            current_index=i + 1,
                            total=total,
                            found=found,
                            missing=missing,
                            rate_limited=rate_limited,
                            elapsed_seconds=elapsed,
                        )
                    continue

            # Determine per-track storefront from CSV country data
            track_storefront = None
            iso_country = track.get("_iso_country", "")
            if iso_country:
                track_storefront = ISO_TO_STOREFRONT.get(iso_country)

            # Perform search with bounded retries for transient network errors.
            result = await self._search_with_backoff(
                song_name=title,
                artist_name=artist if artist else None,
                album_name=album if album else None,
                isrc=None if skip_single_isrc_lookup else (normalized_isrc if normalized_isrc else None),
                timeout_seconds=15.0,
                storefront=track_storefront,
            )

            if result and result.get("success"):
                found += 1
                track["_found"] = True
                track["_source"] = result.get("source", provider)
                track["_artist_matched"] = result.get("artist", artist)
                track["_album_matched"] = result.get("album", album)
                # Update the track's artist with the matched one for export
                if result.get("artist"):
                    track["artist"] = result["artist"]
                if result.get("album"):
                    track["album"] = result["album"]
            else:
                error_msg = result.get("error", "") if result else ""
                # Check for rate limiting
                if "403" in error_msg or "rate" in error_msg.lower():
                    rate_limited += 1
                    track["_rate_limited"] = True
                    self.rate_limited_tracks.append(track)
                else:
                    missing += 1
                track["_found"] = False
                track["_error"] = error_msg

            # Emit per-track result for the results table
            self.send_message({
                "type": "trackResult",
                "index": output_index,
                "artist": track.get("artist", ""),
                "track": track.get("track", ""),
                "album": track.get("album", ""),
                "found": track.get("_found", False),
                "rateLimited": track.get("_rate_limited", False),
                "source": track.get("_source", ""),
            })

            # Log each result for visibility
            if track.get("_found"):
                self.send_log(f"[OK] {track_display} (via {track.get('_source', provider)})")
            elif track.get("_rate_limited"):
                self.send_log(f"[RATE] {track_display} - rate limited", "warning")
            else:
                error_info = track.get("_error", "not found")
                self.send_log(f"[MISS] {track_display} - {error_info}", "warning")

            if persist_progress and (((i + 1) % self.PROGRESS_SAVE_INTERVAL) == 0 or i == total - 1):
                self._save_progress(
                    provider=provider,
                    current_index=i + 1,
                    total=total,
                    found=found,
                    missing=missing,
                    rate_limited=rate_limited,
                    elapsed_seconds=elapsed,
                )

        # Search complete
        self.send_message({
            "type": "searchComplete",
            "total": total,
            "found": found,
            "missing": missing,
            "rateLimited": rate_limited,
            "provider": provider,
        })
        self.send_log(
            f"Search complete: {found} found, {missing} missing"
            + (f", {rate_limited} rate-limited" if rate_limited else "")
        )
        if persist_progress:
            self._clear_progress()

    def pause_search_toggle(self) -> bool:
        """Toggle pause state of search."""
        self.pause_search_flag = not self.pause_search_flag
        self.send_message({
            "type": "searchPaused",
            "paused": self.pause_search_flag,
        })
        return self.pause_search_flag

    def stop_search_now(self):
        """Stop the current search - non-blocking."""
        self.stop_search_flag = True
        self.pause_search_flag = False
        self._skip_rate_limit_wait.set()
        self._rate_limit_wait_active = False

        # Wake up any rate-limit sleeps immediately
        if self.music_service and hasattr(self.music_service, '_exit_event'):
            self.music_service._exit_event.set()

        # Do NOT join the search thread here - it blocks the main message loop
        # and can cause the UI to appear frozen. The search thread will detect
        # stop_search_flag and exit on its own.
        self.send_message({"type": "searchStopped", "success": True})
        self.send_log("Search stopped")

    def resume_search(self, provider_override: Optional[str] = None):
        """Resume previously interrupted search if progress snapshot exists."""
        state = self._load_progress()
        if not state:
            self.send_error("No saved search progress found", "resume_search")
            return

        file_path = state.get("file_path", "")
        if not file_path or not Path(file_path).exists():
            self.send_error("Saved CSV file no longer exists", "resume_search")
            self._clear_progress()
            return

        provider = provider_override or state.get("provider", "musicbrainz_api")

        # Reload CSV for original dataframe/export context, then restore per-track state.
        if not self.load_csv(file_path):
            self.send_error("Failed to reload CSV for resume", "resume_search")
            return

        self._restore_progress_snapshot(state)

        self.start_search(provider, resume_state=state)

    def clear_resume_state(self):
        """Clear any persisted resume snapshot."""
        self._clear_progress()
        self.send_message({"type": "resumeState", "available": False})
        self.send_status("Saved search progress cleared")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_results(self, format_key: str, output_path: str) -> bool:
        """Export results to specified format."""
        try:
            if not self.current_tracks:
                self.send_error("No tracks to export", "export_results")
                return False

            self.send_status(f"Exporting to {format_key} format...")

            success = export_formats.export_tracks(
                format_key=format_key,
                tracks=self.current_tracks,
                output_path=output_path,
                original_df=self.current_df,
            )

            self.send_message({
                "type": "exportComplete",
                "success": success,
                "format": format_key,
                "path": output_path,
            })

            if success:
                self.send_log(f"Exported {len(self.current_tracks)} tracks to {output_path}")
            return success

        except Exception as e:
            self.send_error(str(e), "export_results")
            return False

    def export_missing(self, output_path: str) -> bool:
        """Export tracks that were not found."""
        try:
            missing = [t for t in self.current_tracks if not t.get("_found")]
            if not missing:
                self.send_error("No missing tracks to export", "export_missing")
                return False

            import pandas as pd
            df = pd.DataFrame([{
                "Artist": t.get("artist", ""),
                "Track": t.get("track", ""),
                "Album": t.get("album", ""),
                "Timestamp": t.get("timestamp", ""),
                "Error": t.get("_error", ""),
            } for t in missing])
            df.to_csv(output_path, index=False, encoding='utf-8-sig')

            self.send_message({
                "type": "exportComplete",
                "success": True,
                "format": "missing",
                "path": output_path,
                "count": len(missing),
            })
            self.send_log(f"Exported {len(missing)} missing tracks to {output_path}")
            return True

        except Exception as e:
            self.send_error(str(e), "export_missing")
            return False

    def export_rate_limited(self, output_path: str) -> bool:
        """Export tracks that were rate-limited."""
        try:
            rl = [t for t in self.current_tracks if t.get("_rate_limited")]
            if not rl:
                self.send_error("No rate-limited tracks to export", "export_rate_limited")
                return False

            import pandas as pd
            df = pd.DataFrame([{
                "Artist": t.get("artist", ""),
                "Track": t.get("track", ""),
                "Album": t.get("album", ""),
                "Timestamp": t.get("timestamp", ""),
            } for t in rl])
            df.to_csv(output_path, index=False, encoding='utf-8-sig')

            self.send_message({
                "type": "exportComplete",
                "success": True,
                "format": "rate_limited",
                "path": output_path,
                "count": len(rl),
            })
            return True

        except Exception as e:
            self.send_error(str(e), "export_rate_limited")
            return False

    def retry_rate_limited(self, provider: str):
        """Retry searching rate-limited tracks."""
        retry_pairs = [
            (idx, track)
            for idx, track in enumerate(self.current_tracks)
            if track.get("_rate_limited")
        ]
        if not retry_pairs:
            self.send_error("No rate-limited tracks to retry", "retry_rate_limited")
            return

        retry_tracks = [track for _, track in retry_pairs]
        retry_indices = [idx for idx, _ in retry_pairs]

        # Reset rate limited flags
        for t in retry_tracks:
            t["_rate_limited"] = False
            t["_found"] = False
            t["_error"] = ""

        self.rate_limited_tracks = []
        self.start_search(provider, run_tracks=retry_tracks, run_indices=retry_indices)

    def retry_missing(self, provider: str):
        """Retry searching tracks that are missing (excluding rate-limited rows)."""
        retry_pairs = [
            (idx, track)
            for idx, track in enumerate(self.current_tracks)
            if not track.get("_found") and not track.get("_rate_limited")
        ]
        if not retry_pairs:
            self.send_error("No missing tracks to retry", "retry_missing")
            return

        retry_tracks = [track for _, track in retry_pairs]
        retry_indices = [idx for idx, _ in retry_pairs]

        for track in retry_tracks:
            track["_found"] = False
            track["_error"] = ""
            track["_source"] = ""
            track["_artist_matched"] = ""
            track["_album_matched"] = ""

        self.start_search(provider, run_tracks=retry_tracks, run_indices=retry_indices)

    # ------------------------------------------------------------------
    # Apple Music API configuration
    # ------------------------------------------------------------------
    def configure_apple_music(
        self,
        team_id: str,
        key_id: str,
        key_path: str,
        proxy_url: str = "",
        proxy_key: str = "",
    ):
        """Configure Apple Music API credentials."""
        try:
            self.settings["apple_music_team_id"] = (team_id or "").strip()
            self.settings["apple_music_key_id"] = (key_id or "").strip()
            self.settings["apple_music_key_path"] = (key_path or "").strip()
            self.settings["apple_music_proxy_url"] = (proxy_url or "").strip()
            self.settings["apple_music_proxy_key"] = (proxy_key or "").strip()
            self.settings["apple_music_enabled"] = True
            self._save_settings()

            if self.music_service:
                self.music_service.settings.update(self.settings)
                if hasattr(self.music_service, "apple_music_service"):
                    self.music_service.apple_music_service = None

            self.send_message({
                "type": "appleMusicConfigured",
                "success": True,
            })
            self.send_log("Apple Music API credentials saved")
        except Exception as e:
            self.send_error(str(e), "configure_apple_music")

    def _resolve_proxy_url(self) -> str:
        """Return the configured proxy URL, falling back to the shared default."""
        url = (self.settings.get("apple_music_proxy_url") or "").strip()
        if url:
            return url
        # If no local credentials are configured, use the shared proxy
        has_local = (
            self.settings.get("apple_music_team_id")
            and self.settings.get("apple_music_key_id")
            and self.settings.get("apple_music_key_path")
        )
        if not has_local:
            return DEFAULT_APPLE_MUSIC_PROXY_URL
        return ""

    def test_apple_music_credentials(self):
        """Test Apple Music API credentials."""
        try:
            from apple_music_history_converter.apple_music_service import AppleMusicService
            svc = AppleMusicService(
                team_id=self.settings.get("apple_music_team_id"),
                key_id=self.settings.get("apple_music_key_id"),
                private_key_path=self.settings.get("apple_music_key_path"),
                storefront=self.settings.get("itunes_country", "us"),
                proxy_base_url=self._resolve_proxy_url(),
                proxy_api_key=self.settings.get("apple_music_proxy_key"),
            )

            loop = asyncio.new_event_loop()
            try:
                success, message = loop.run_until_complete(svc.test_credentials())
            finally:
                loop.close()

            self.send_message({
                "type": "appleMusicTestResult",
                "success": success,
                "message": message,
            })
        except Exception as e:
            self.send_message({
                "type": "appleMusicTestResult",
                "success": False,
                "message": str(e),
            })

    def get_apple_music_status(self):
        """Check Apple Music API status."""
        try:
            from apple_music_history_converter.apple_music_service import AppleMusicService
            has_builtin = AppleMusicService.has_builtin_credentials()
        except Exception:
            has_builtin = False

        has_custom = bool(
            (
                self.settings.get("apple_music_team_id")
                and self.settings.get("apple_music_key_id")
                and self.settings.get("apple_music_key_path")
            )
            or self.settings.get("apple_music_proxy_url")
        )
        # The shared proxy is always available as a fallback
        has_shared_proxy = bool(self._resolve_proxy_url())
        enabled = self.settings.get("apple_music_enabled", False)

        self.send_message({
            "type": "appleMusicStatus",
            "hasBuiltin": has_builtin,
            "hasCustom": has_custom,
            "hasSharedProxy": has_shared_proxy,
            "enabled": enabled,
        })

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------
    def download_database(self):
        """Download MusicBrainz database."""
        if not self.music_service:
            self.initialize_service()
        if not self.music_service:
            self.send_error("Music service not available", "download_database")
            return

        def progress_cb(*args, **kwargs):
            message = args[0] if len(args) > 0 else kwargs.get("message", "")
            percent = args[1] if len(args) > 1 else kwargs.get("percent", 0)
            self.send_message({
                "type": "downloadProgress",
                "message": _EMOJI_RE.sub('', str(message)) if message else "",
                "percent": percent if isinstance(percent, (int, float)) else 0,
            })

        try:
            ok = self.music_service.download_database(progress_callback=progress_cb)
            self.send_status("Database download complete" if ok else "Database download failed")
            self.get_database_status()
        except Exception as e:
            self.send_error(str(e), "download_database")

    def delete_database(self):
        """Delete MusicBrainz database."""
        if not self.music_service:
            self.initialize_service()
        if not self.music_service:
            self.send_error("Music service not available", "delete_database")
            return

        try:
            ok = self.music_service.delete_database()
            self.send_status("Database deleted" if ok else "Database delete failed")
            self.get_database_status()
        except Exception as e:
            self.send_error(str(e), "delete_database")

    def import_database(self, db_path: str):
        """Import a MusicBrainz database file."""
        if not db_path:
            self.send_error("No database path provided", "import_database")
            return

        try:
            import shutil
            # Determine target directory
            if self.music_service and hasattr(self.music_service.musicbrainz_manager, 'data_dir'):
                target_dir = Path(self.music_service.musicbrainz_manager.data_dir)
            else:
                if sys.platform == "darwin":
                    target_dir = Path.home() / ".apple_music_converter"
                elif sys.platform == "win32":
                    target_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AppleMusicConverter"
                else:
                    target_dir = Path.home() / ".apple_music_converter"

            target_dir.mkdir(parents=True, exist_ok=True)
            src = Path(db_path)
            target = target_dir / src.name
            shutil.copy2(str(src), str(target))
            self.send_status(f"Database imported: {target.name}")
            self.send_log(f"Database imported from {src.name}")
            self.get_database_status()
        except Exception as e:
            self.send_error(str(e), "import_database")

    def check_database_updates(self):
        """Check for database updates."""
        if not self.music_service:
            self.initialize_service()
        if not self.music_service:
            self.send_status("Music service not available")
            return

        try:
            result = self.music_service.check_for_updates()
            if isinstance(result, tuple):
                has_update, msg = result
                self.send_status(msg if msg else ("Update available" if has_update else "Database is up to date"))
            else:
                self.send_status("Update check complete")
        except Exception as e:
            self.send_error(str(e), "check_database_updates")

    def show_database_location(self):
        """Open database directory in OS file manager."""
        if not self.music_service:
            self.initialize_service()

        if self.music_service and hasattr(self.music_service, "get_database_path"):
            db_dir = Path(self.music_service.get_database_path())
        else:
            if sys.platform == "darwin":
                db_dir = Path.home() / "Library" / "Application Support" / "AppleMusicConverter"
            elif sys.platform == "win32":
                db_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AppleMusicConverter"
            else:
                db_dir = Path.home() / ".apple_music_converter"

        db_dir.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(db_dir)], check=False)
            elif sys.platform == "win32":
                os.startfile(str(db_dir))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(db_dir)], check=False)
            self.send_status(f"Opened database location: {db_dir}")
        except Exception as e:
            self.send_error(str(e), "show_database_location")

    def optimize_database(self):
        """Trigger MusicBrainz optimization in background."""
        if not self.music_service:
            self.initialize_service()
        if not self.music_service:
            self.send_error("Music service not available", "optimize_database")
            return

        try:
            started = self.music_service.start_progressive_loading()
            if started:
                self.send_status("Database optimization started")
            else:
                self.send_status("Database optimization could not be started")
            self.get_database_status()
        except Exception as e:
            self.send_error(str(e), "optimize_database")

    def clear_cache(self):
        """Clear the search cache."""
        if self.music_service:
            self.music_service.clear_search_cache()
        self.send_status("Search cache cleared")
        self.send_log("Search cache cleared")

    def get_settings(self):
        """Return current settings to frontend."""
        settings = dict(self.settings)
        effective_storage_root = get_storage_root()
        if effective_storage_root is not None:
            settings["storage_root"] = str(effective_storage_root)
        self.send_message({
            "type": "settingsLoaded",
            "settings": settings,
        })

    # ------------------------------------------------------------------
    # iTunes status check
    # ------------------------------------------------------------------
    def check_itunes_status(self):
        """Check iTunes API availability."""
        self._probe_api_status(
            label="iTunes API",
            url="https://itunes.apple.com/search?term=test&limit=1",
            rate_limited_codes={403},
            context="check_itunes_status",
        )

    def check_musicbrainz_api_status(self):
        """Check MusicBrainz API availability."""
        self._probe_api_status(
            label="MusicBrainz API",
            url="https://musicbrainz.org/ws/2/recording?query=test&limit=1&fmt=json",
            headers={"User-Agent": f"AppleMusicConverter/{APP_VERSION} (nerveband@gmail.com)"},
            rate_limited_codes={503},
            context="check_musicbrainz_api_status",
        )

    def check_apple_music_api_status(self):
        """Check Apple Music API availability via the proxy."""
        proxy_url = self._resolve_proxy_url()
        if not proxy_url:
            self.send_status("Apple Music API: Not configured")
            return
        self._probe_api_status(
            label="Apple Music API",
            url=f"{proxy_url.rstrip('/')}/health",
            rate_limited_codes={429},
            context="check_apple_music_api_status",
        )

    def _probe_api_status(
        self,
        label: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        rate_limited_codes: Optional[Set[int]] = None,
        context: str = "",
    ) -> None:
        """
        Probe API health with lightweight retry/backoff.

        Status checks should tolerate transient transport resets and return a
        user-readable status message instead of a hard sidecar error event.
        """
        try:
            import requests
        except Exception as e:
            self.send_error(str(e), context or "probe_api_status")
            return

        merged_headers = {"Connection": "close"}
        if headers:
            merged_headers.update(headers)

        retries = [0.25, 0.75]  # total attempts = 3
        last_exc: Optional[Exception] = None
        rate_limited = rate_limited_codes or set()

        for attempt in range(len(retries) + 1):
            try:
                resp = requests.get(url, headers=merged_headers, timeout=timeout)
                if resp.status_code == 200:
                    self.send_status(f"{label}: OK")
                elif resp.status_code in rate_limited:
                    self.send_status(f"{label}: Rate limited ({resp.status_code})")
                else:
                    self.send_status(f"{label}: Error {resp.status_code}")
                return
            except requests.exceptions.RequestException as e:
                last_exc = e
                if attempt < len(retries):
                    delay = retries[attempt]
                    self.send_log(
                        f"{label} status check failed (attempt {attempt + 1}/{len(retries) + 1}): {e}. "
                        f"Retrying in {delay:.2f}s",
                        "warning",
                    )
                    time.sleep(delay)
                    continue
                break

        # Treat transport instability as status signal, not hard-sidecar error.
        if last_exc is None:
            self.send_status(f"{label}: Error")
            return

        message = str(last_exc)
        lowered = message.lower()
        if "connection reset by peer" in lowered or "connection aborted" in lowered:
            self.send_status(f"{label}: Network error (connection reset). Try again.")
        elif isinstance(last_exc, requests.exceptions.Timeout):
            self.send_status(f"{label}: Network timeout. Try again.")
        elif isinstance(last_exc, requests.exceptions.SSLError):
            self.send_status(f"{label}: TLS/SSL error.")
        else:
            # Status probes should never surface as hard app errors.
            self.send_status(f"{label}: Network error. Try again.")
        self.send_log(f"{label} probe failed after retries: {message}", "warning")

    # ------------------------------------------------------------------
    # Message dispatcher
    # ------------------------------------------------------------------
    def handle_message(self, msg: Dict[str, Any]):
        """Handle incoming IPC message."""
        action = msg.get("action", "")

        try:
            if action == "initialize":
                self.initialize_service()

            elif action == "getDatabaseStatus":
                self.get_database_status()

            elif action == "analyzeCSV":
                self.analyze_csv(msg.get("path", ""))

            elif action == "loadCSV":
                self.load_csv(msg.get("path", ""))

            elif action == "getPreview":
                self.get_preview(msg.get("path", ""))

            elif action == "setPreviewEdits":
                self.set_preview_edits(
                    msg.get("path", ""),
                    msg.get("rows", []),
                )

            elif action == "loadExportedCSV":
                self.load_exported_csv(msg.get("path", ""))

            elif action == "startSearchMissingOnly":
                self.start_search_missing_only(msg.get("provider", "musicbrainz_api"))

            elif action == "startSearch":
                self.start_search(msg.get("provider", "musicbrainz_api"))

            elif action == "resumeSearch":
                self.resume_search(msg.get("provider"))

            elif action == "getResumeState":
                self._send_resume_state()

            elif action == "clearResumeState":
                self.clear_resume_state()

            elif action == "pauseSearch":
                self.pause_search_toggle()

            elif action == "stopSearch":
                self.stop_search_now()

            elif action == "export":
                self.export_results(
                    msg.get("format", "lastfm"),
                    msg.get("path", ""),
                )

            elif action == "exportMissing":
                self.export_missing(msg.get("path", ""))

            elif action == "exportRateLimited":
                self.export_rate_limited(msg.get("path", ""))

            elif action == "retryRateLimited":
                self.retry_rate_limited(msg.get("provider", "itunes"))

            elif action == "retryMissing":
                self.retry_missing(msg.get("provider", "itunes"))

            elif action == "skipRateLimitWait":
                self.skip_rate_limit_wait()

            elif action == "setProvider":
                if self.music_service:
                    self.music_service.set_search_provider(msg.get("provider", "musicbrainz"))
                self.send_message({
                    "type": "providerSet",
                    "provider": msg.get("provider", "musicbrainz"),
                })

            elif action == "setSettings":
                self.apply_settings(msg.get("settings", {}))
                self.send_status("Settings updated")

            elif action == "getSettings":
                self.get_settings()

            elif action == "checkItunesStatus":
                self.check_itunes_status()

            elif action == "checkMusicBrainzApiStatus":
                self.check_musicbrainz_api_status()

            elif action == "checkAppleMusicApiStatus":
                self.check_apple_music_api_status()

            elif action == "configureAppleMusic":
                self.configure_apple_music(
                    msg.get("teamId", ""),
                    msg.get("keyId", ""),
                    msg.get("keyPath", ""),
                    msg.get("proxyUrl", ""),
                    msg.get("proxyKey", ""),
                )

            elif action == "testAppleMusicCredentials":
                self.test_apple_music_credentials()

            elif action == "getAppleMusicStatus":
                self.get_apple_music_status()

            elif action == "downloadDatabase":
                self.download_database()

            elif action == "deleteDatabase":
                self.delete_database()

            elif action == "importDatabase":
                self.import_database(msg.get("path", ""))

            elif action == "checkDatabaseUpdates":
                self.check_database_updates()

            elif action == "showDatabaseLocation":
                self.show_database_location()

            elif action == "optimizeDatabase":
                self.optimize_database()

            elif action == "clearCache":
                self.clear_cache()

            elif action == "ping":
                self.send_message({"type": "pong"})

            else:
                self.send_error(f"Unknown action: {action}", "handle_message")

        except Exception as e:
            self.send_error(str(e), f"handle_message:{action}")


def main():
    """Main entry point for sidecar."""
    handler = SidecarHandler()

    handler.send_message({
        "type": "ready",
        "version": APP_VERSION,
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            handler.handle_message(msg)
        except json.JSONDecodeError as e:
            handler.send_error(f"Invalid JSON: {e}", "main")
        except Exception as e:
            handler.send_error(f"Error: {e}", "main")


if __name__ == "__main__":
    main()
