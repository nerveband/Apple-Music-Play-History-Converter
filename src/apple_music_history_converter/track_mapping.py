#!/usr/bin/env python3
"""
Per-User Track Mapping Cache (Phase 3).

Caches verified track matches for instant lookup on repeat imports.
Stores the mapping between Apple Music track info and MusicBrainz results.

This provides:
- Instant lookup (<1ms) for previously matched tracks
- Persistent storage across sessions
- Confidence tracking for match quality
- User verification support for manual corrections
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

try:
    from .app_directories import get_user_data_dir
    from .logging_config import get_logger
except ImportError:
    from app_directories import get_user_data_dir
    from logging_config import get_logger

logger = get_logger(__name__)


class TrackMappingCache:
    """
    Persistent cache for track-to-artist mappings.

    Uses DuckDB for fast hash-based lookups of previously matched tracks.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the track mapping cache.

        Args:
            db_path: Optional path to database file. If not provided,
                     uses the default user data directory.
        """
        self._conn = None
        self._enabled = DUCKDB_AVAILABLE

        if not DUCKDB_AVAILABLE:
            logger.warning("DuckDB not available - track mapping cache disabled")
            return

        if db_path is None:
            db_path = str(get_user_data_dir() / "track_mappings.duckdb")

        self._db_path = Path(db_path)

        try:
            self._conn = duckdb.connect(str(self._db_path))
            self._ensure_schema()
            logger.debug(f"TrackMappingCache initialized at {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize track mapping cache: {e}")
            self._enabled = False

    def _ensure_schema(self) -> None:
        """Create the mapping table if it doesn't exist."""
        if not self._conn:
            return

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS user_track_mappings (
                -- Key: hash of (song_name, album_name, artist_name)
                track_hash VARCHAR PRIMARY KEY,

                -- Original Apple data (for debugging/display)
                apple_song_name VARCHAR NOT NULL,
                apple_album_name VARCHAR,
                apple_artist_name VARCHAR,

                -- MusicBrainz result
                mb_recording_mbid VARCHAR,
                mb_artist_credit_name VARCHAR,
                mb_release_name VARCHAR,

                -- Metadata
                confidence VARCHAR,  -- 'high', 'medium', 'low', 'manual'
                verified_by VARCHAR DEFAULT 'auto',  -- 'auto', 'user'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER DEFAULT 1
            )
        """)

        # Create index for fast lookups
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mapping_hash
            ON user_track_mappings(track_hash)
        """)

        # Create index for pruning old entries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mapping_last_used
            ON user_track_mappings(last_used_at)
        """)

    def _compute_hash(self, song: str, album: Optional[str], artist: Optional[str]) -> str:
        """
        Compute a hash key for a track.

        Uses normalized lowercase strings to ensure consistent lookup.

        Args:
            song: Song/track name
            album: Album name (optional)
            artist: Artist name (optional)

        Returns:
            SHA256 hash of the normalized track info
        """
        # Normalize: lowercase, strip whitespace
        parts = [
            (song or "").lower().strip(),
            (album or "").lower().strip(),
            (artist or "").lower().strip()
        ]
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:32]

    def lookup(self, song: str, album: Optional[str] = None,
               artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fast lookup for a previously matched track.

        Args:
            song: Song/track name
            album: Album name (optional)
            artist: Artist name (optional)

        Returns:
            Dict with match info if found, None otherwise.
            Contains: mb_artist_credit_name, mb_release_name, confidence, etc.
        """
        if not self._enabled or not self._conn:
            return None

        track_hash = self._compute_hash(song, album, artist)

        try:
            result = self._conn.execute("""
                SELECT
                    track_hash,
                    apple_song_name,
                    apple_album_name,
                    apple_artist_name,
                    mb_recording_mbid,
                    mb_artist_credit_name,
                    mb_release_name,
                    confidence,
                    verified_by,
                    created_at,
                    last_used_at,
                    use_count
                FROM user_track_mappings
                WHERE track_hash = ?
            """, [track_hash]).fetchone()

            if result:
                # Update last_used_at and use_count
                self._conn.execute("""
                    UPDATE user_track_mappings
                    SET last_used_at = CURRENT_TIMESTAMP,
                        use_count = use_count + 1
                    WHERE track_hash = ?
                """, [track_hash])

                return {
                    'track_hash': result[0],
                    'apple_song_name': result[1],
                    'apple_album_name': result[2],
                    'apple_artist_name': result[3],
                    'mb_recording_mbid': result[4],
                    'mb_artist_credit_name': result[5],
                    'mb_release_name': result[6],
                    'confidence': result[7],
                    'verified_by': result[8],
                    'created_at': result[9],
                    'last_used_at': result[10],
                    'use_count': result[11]
                }
            return None

        except Exception as e:
            logger.debug(f"Track mapping lookup failed: {e}")
            return None

    def store(self, apple_song: str, apple_album: Optional[str],
              apple_artist: Optional[str], mb_artist_credit: str,
              mb_release: Optional[str] = None,
              mb_recording_mbid: Optional[str] = None,
              confidence: str = 'high') -> bool:
        """
        Store a new track mapping.

        Only stores high/medium confidence matches to avoid caching errors.

        Args:
            apple_song: Original song name from Apple Music
            apple_album: Original album name from Apple Music
            apple_artist: Original artist name from Apple Music
            mb_artist_credit: MusicBrainz artist credit name (the result)
            mb_release: MusicBrainz release name (optional)
            mb_recording_mbid: MusicBrainz recording MBID (optional)
            confidence: Match confidence ('high', 'medium', 'low', 'manual')

        Returns:
            True if stored successfully, False otherwise
        """
        if not self._enabled or not self._conn:
            return False

        # Only cache high/medium confidence matches
        if confidence not in ('high', 'medium', 'manual'):
            return False

        track_hash = self._compute_hash(apple_song, apple_album, apple_artist)

        try:
            # Use INSERT OR REPLACE to handle updates
            self._conn.execute("""
                INSERT OR REPLACE INTO user_track_mappings (
                    track_hash,
                    apple_song_name,
                    apple_album_name,
                    apple_artist_name,
                    mb_recording_mbid,
                    mb_artist_credit_name,
                    mb_release_name,
                    confidence,
                    verified_by,
                    created_at,
                    last_used_at,
                    use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'auto', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """, [
                track_hash,
                apple_song,
                apple_album,
                apple_artist,
                mb_recording_mbid,
                mb_artist_credit,
                mb_release,
                confidence
            ])

            logger.debug(f"Cached mapping: '{apple_song}' -> '{mb_artist_credit}' ({confidence})")
            return True

        except Exception as e:
            logger.debug(f"Failed to store track mapping: {e}")
            return False

    def store_user_verified(self, apple_song: str, apple_album: Optional[str],
                           apple_artist: Optional[str], mb_artist_credit: str,
                           mb_release: Optional[str] = None) -> bool:
        """
        Store a user-verified track mapping.

        Used when user manually confirms or corrects a match.

        Args:
            apple_song: Original song name from Apple Music
            apple_album: Original album name from Apple Music
            apple_artist: Original artist name from Apple Music
            mb_artist_credit: User-verified artist credit name
            mb_release: User-verified release name (optional)

        Returns:
            True if stored successfully, False otherwise
        """
        if not self._enabled or not self._conn:
            return False

        track_hash = self._compute_hash(apple_song, apple_album, apple_artist)

        try:
            self._conn.execute("""
                INSERT OR REPLACE INTO user_track_mappings (
                    track_hash,
                    apple_song_name,
                    apple_album_name,
                    apple_artist_name,
                    mb_recording_mbid,
                    mb_artist_credit_name,
                    mb_release_name,
                    confidence,
                    verified_by,
                    created_at,
                    last_used_at,
                    use_count
                ) VALUES (?, ?, ?, ?, NULL, ?, ?, 'manual', 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """, [
                track_hash,
                apple_song,
                apple_album,
                apple_artist,
                mb_artist_credit,
                mb_release
            ])

            logger.debug(f"User verified mapping: '{apple_song}' -> '{mb_artist_credit}'")
            return True

        except Exception as e:
            logger.debug(f"Failed to store user-verified mapping: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the mapping cache.

        Returns:
            Dict with cache statistics
        """
        if not self._enabled or not self._conn:
            return {'enabled': False}

        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM user_track_mappings"
            ).fetchone()[0]

            by_confidence = self._conn.execute("""
                SELECT confidence, COUNT(*)
                FROM user_track_mappings
                GROUP BY confidence
            """).fetchall()

            by_verified = self._conn.execute("""
                SELECT verified_by, COUNT(*)
                FROM user_track_mappings
                GROUP BY verified_by
            """).fetchall()

            return {
                'enabled': True,
                'total_mappings': total,
                'by_confidence': dict(by_confidence),
                'by_verified': dict(by_verified),
                'db_path': str(self._db_path)
            }

        except Exception as e:
            logger.debug(f"Failed to get cache stats: {e}")
            return {'enabled': True, 'error': str(e)}

    def prune_old_entries(self, days: int = 365) -> int:
        """
        Remove entries not used in the specified number of days.

        Args:
            days: Number of days of inactivity before pruning

        Returns:
            Number of entries removed
        """
        if not self._enabled or not self._conn:
            return 0

        try:
            # Get count before
            before = self._conn.execute(
                "SELECT COUNT(*) FROM user_track_mappings"
            ).fetchone()[0]

            # Delete old entries (but keep user-verified ones longer)
            self._conn.execute("""
                DELETE FROM user_track_mappings
                WHERE last_used_at < CURRENT_TIMESTAMP - INTERVAL ? DAY
                  AND verified_by != 'user'
            """, [days])

            # Get count after
            after = self._conn.execute(
                "SELECT COUNT(*) FROM user_track_mappings"
            ).fetchone()[0]

            removed = before - after
            if removed > 0:
                logger.info(f"Pruned {removed} old track mappings")
            return removed

        except Exception as e:
            logger.debug(f"Failed to prune old entries: {e}")
            return 0

    def clear_all(self) -> bool:
        """
        Clear all cached mappings.

        Returns:
            True if cleared successfully, False otherwise
        """
        if not self._enabled or not self._conn:
            return False

        try:
            self._conn.execute("DELETE FROM user_track_mappings")
            logger.info("Cleared all track mappings")
            return True
        except Exception as e:
            logger.debug(f"Failed to clear mappings: {e}")
            return False

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self):
        """Cleanup on deletion."""
        self.close()

    @property
    def is_enabled(self) -> bool:
        """Check if the cache is enabled and functional."""
        return self._enabled and self._conn is not None


# Module-level singleton instance
_default_cache: Optional[TrackMappingCache] = None


def get_default_cache() -> TrackMappingCache:
    """
    Get the default track mapping cache instance.

    Returns a singleton instance using the default database path.
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = TrackMappingCache()
    return _default_cache
