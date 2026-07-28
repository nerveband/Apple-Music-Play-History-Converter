#!/usr/bin/env python3
"""Persistent per-user track mapping cache.

The mutable mapping cache intentionally uses SQLite rather than DuckDB. DuckDB
remains the analytical engine for the read-mostly MusicBrainz catalogue, but its
ART primary-key index has had fatal upsert failures under repeated cache writes.
SQLite provides transactional UPSERT semantics for this small key/value workload.
"""

import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from .app_directories import get_default_user_data_dir, get_user_data_dir
    from .logging_config import get_logger
except ImportError:
    from app_directories import get_default_user_data_dir, get_user_data_dir
    from logging_config import get_logger

logger = get_logger(__name__)


class TrackMappingCache:
    """Thread-safe SQLite cache for track-to-artist mappings."""

    def __init__(self, db_path: Optional[str] = None):
        self._conn: Optional[sqlite3.Connection] = None
        self._enabled = True
        self._lock = threading.RLock()
        self._db_path = Path(db_path) if db_path else get_user_data_dir() / "track_mappings.sqlite3"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._open_database()
            if db_path is None:
                self._migrate_legacy_duckdb()
            logger.debug("TrackMappingCache initialized at %s", self._db_path)
        except sqlite3.DatabaseError as exc:
            logger.warning("Mapping cache is unreadable; rebuilding it: %s", exc)
            self.close()
            try:
                quarantine = self._db_path.with_name(
                    f"{self._db_path.name}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                if self._db_path.exists():
                    self._db_path.replace(quarantine)
                for suffix in ("-wal", "-shm"):
                    side_file = Path(f"{self._db_path}{suffix}")
                    if side_file.exists():
                        side_file.unlink()
                self._open_database()
                logger.warning("Rebuilt mapping cache; unreadable file retained at %s", quarantine)
            except Exception as recovery_exc:
                logger.error("Failed to rebuild track mapping cache: %s", recovery_exc)
                self.close()
                self._enabled = False
        except Exception as exc:
            logger.error("Failed to initialize track mapping cache: %s", exc)
            self.close()
            self._enabled = False

    def _open_database(self) -> None:
        self._conn = sqlite3.connect(
            str(self._db_path),
            timeout=30,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.execute("PRAGMA quick_check").fetchone()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if not self._conn:
            return
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS user_track_mappings (
                    track_hash TEXT PRIMARY KEY,
                    apple_song_name TEXT NOT NULL,
                    apple_album_name TEXT,
                    apple_artist_name TEXT,
                    mb_recording_mbid TEXT,
                    mb_artist_credit_name TEXT,
                    mb_release_name TEXT,
                    confidence TEXT,
                    verified_by TEXT DEFAULT 'auto',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    use_count INTEGER DEFAULT 1
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mapping_last_used
                ON user_track_mappings(last_used_at)
            """)

    def _migrate_legacy_duckdb(self) -> None:
        """Best-effort, idempotent import of the legacy DuckDB mapping cache."""
        if not self._conn:
            return
        candidates = [
            self._db_path.with_name("track_mappings.duckdb"),
            get_default_user_data_dir() / "track_mappings.duckdb",
        ]
        legacy_path = next(
            (path for path in dict.fromkeys(candidates) if path.exists()),
            None,
        )
        if legacy_path is None:
            return
        marker = self._db_path.with_suffix(".sqlite3.legacy-imported")
        if marker.exists():
            return

        try:
            import duckdb
            legacy = duckdb.connect(str(legacy_path), read_only=True)
            try:
                legacy_rows = legacy.execute("""
                    SELECT track_hash, apple_song_name, apple_album_name,
                           apple_artist_name, mb_recording_mbid,
                           mb_artist_credit_name, mb_release_name, confidence,
                           verified_by, created_at, last_used_at, use_count
                    FROM user_track_mappings
                """).fetchall()
            finally:
                legacy.close()

            rows = []
            for legacy_row in legacy_rows:
                row = list(legacy_row)
                for index in (9, 10):
                    if isinstance(row[index], datetime):
                        row[index] = row[index].isoformat(timespec="seconds")
                rows.append(tuple(row))
            with self._lock, self._conn:
                self._conn.executemany(self._upsert_sql(), rows)
            marker.write_text(
                f"Migrated {len(rows)} rows to {self._db_path.name}\n",
                encoding="utf-8",
            )
            logger.info("Migrated %s legacy track mappings to SQLite", len(rows))
        except Exception as exc:
            # A broken legacy cache must never prevent the app from starting.
            logger.warning("Legacy track mapping migration skipped: %s", exc)

    @staticmethod
    def _upsert_sql() -> str:
        return """
            INSERT INTO user_track_mappings (
                track_hash, apple_song_name, apple_album_name,
                apple_artist_name, mb_recording_mbid,
                mb_artist_credit_name, mb_release_name, confidence,
                verified_by, created_at, last_used_at, use_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_hash) DO UPDATE SET
                apple_song_name = excluded.apple_song_name,
                apple_album_name = excluded.apple_album_name,
                apple_artist_name = excluded.apple_artist_name,
                mb_recording_mbid = excluded.mb_recording_mbid,
                mb_artist_credit_name = excluded.mb_artist_credit_name,
                mb_release_name = excluded.mb_release_name,
                confidence = excluded.confidence,
                verified_by = CASE
                    WHEN user_track_mappings.verified_by = 'user'
                         AND excluded.verified_by != 'user'
                    THEN user_track_mappings.verified_by
                    ELSE excluded.verified_by
                END,
                last_used_at = excluded.last_used_at,
                use_count = user_track_mappings.use_count + 1
        """

    @staticmethod
    def _compute_hash(song: str, album: Optional[str], artist: Optional[str]) -> str:
        parts = [
            (song or "").lower().strip(),
            (album or "").lower().strip(),
            (artist or "").lower().strip(),
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    def lookup(self, song: str, album: Optional[str] = None,
               artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        track_hash = self._compute_hash(song, album, artist)
        try:
            with self._lock, self._conn:
                row = self._conn.execute(
                    "SELECT * FROM user_track_mappings WHERE track_hash = ?",
                    (track_hash,),
                ).fetchone()
                if row:
                    self._conn.execute("""
                        UPDATE user_track_mappings
                        SET last_used_at = CURRENT_TIMESTAMP,
                            use_count = use_count + 1
                        WHERE track_hash = ?
                    """, (track_hash,))
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.warning("Track mapping lookup failed: %s", exc)
            return None

    def _store(self, apple_song: str, apple_album: Optional[str],
               apple_artist: Optional[str], mb_artist_credit: str,
               mb_release: Optional[str], mb_recording_mbid: Optional[str],
               confidence: str, verified_by: str) -> bool:
        if not self.is_enabled:
            return False
        now = datetime.now().isoformat(timespec="seconds")
        values = (
            self._compute_hash(apple_song, apple_album, apple_artist),
            apple_song, apple_album, apple_artist, mb_recording_mbid,
            mb_artist_credit, mb_release, confidence, verified_by,
            now, now, 1,
        )
        try:
            with self._lock, self._conn:
                if verified_by != "user":
                    existing = self._conn.execute(
                        "SELECT verified_by FROM user_track_mappings WHERE track_hash = ?",
                        (values[0],),
                    ).fetchone()
                    if existing and existing[0] == "user":
                        return True
                self._conn.execute(self._upsert_sql(), values)
            return True
        except sqlite3.Error as exc:
            logger.warning("Failed to store track mapping: %s", exc)
            return False

    def store(self, apple_song: str, apple_album: Optional[str],
              apple_artist: Optional[str], mb_artist_credit: str,
              mb_release: Optional[str] = None,
              mb_recording_mbid: Optional[str] = None,
              confidence: str = "high") -> bool:
        if confidence not in ("high", "medium", "manual"):
            return False
        return self._store(
            apple_song, apple_album, apple_artist, mb_artist_credit,
            mb_release, mb_recording_mbid, confidence, "auto",
        )

    def store_user_verified(self, apple_song: str, apple_album: Optional[str],
                            apple_artist: Optional[str], mb_artist_credit: str,
                            mb_release: Optional[str] = None) -> bool:
        return self._store(
            apple_song, apple_album, apple_artist, mb_artist_credit,
            mb_release, None, "manual", "user",
        )

    def get_stats(self) -> Dict[str, Any]:
        if not self.is_enabled:
            return {"enabled": False}
        try:
            with self._lock:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM user_track_mappings"
                ).fetchone()[0]
                by_confidence = self._conn.execute("""
                    SELECT confidence, COUNT(*) FROM user_track_mappings
                    GROUP BY confidence
                """).fetchall()
                by_verified = self._conn.execute("""
                    SELECT verified_by, COUNT(*) FROM user_track_mappings
                    GROUP BY verified_by
                """).fetchall()
            return {
                "enabled": True,
                "total_mappings": total,
                "by_confidence": dict(by_confidence),
                "by_verified": dict(by_verified),
                "db_path": str(self._db_path),
                "engine": "sqlite",
            }
        except sqlite3.Error as exc:
            return {"enabled": True, "error": str(exc)}

    def prune_old_entries(self, days: int = 365) -> int:
        if not self.is_enabled:
            return 0
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        try:
            with self._lock, self._conn:
                cursor = self._conn.execute("""
                    DELETE FROM user_track_mappings
                    WHERE last_used_at < ? AND verified_by != 'user'
                """, (cutoff,))
            return max(cursor.rowcount, 0)
        except sqlite3.Error as exc:
            logger.warning("Failed to prune old entries: %s", exc)
            return 0

    def clear_all(self) -> bool:
        if not self.is_enabled:
            return False
        try:
            with self._lock, self._conn:
                self._conn.execute("DELETE FROM user_track_mappings")
            return True
        except sqlite3.Error as exc:
            logger.warning("Failed to clear mappings: %s", exc)
            return False

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    def __del__(self):
        self.close()

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._conn is not None


_default_cache: Optional[TrackMappingCache] = None


def get_default_cache() -> TrackMappingCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = TrackMappingCache()
    return _default_cache
