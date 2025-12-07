#!/usr/bin/env python3
"""
Session Aligner (Phase 2) - Album-Session Alignment.

Detects when consecutive tracks in a play history are from the same album
and aligns them as a unit to a single MusicBrainz release, improving accuracy.

This is particularly useful for:
- Recently Played exports where users listen to full albums
- Avoiding mismatches when the same song appears on multiple albums
- Providing consistent artist credits across an album session
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

try:
    from .logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AlbumSession:
    """Represents a contiguous block of tracks from the same album."""
    album_name: str
    artist_hint: str
    tracks: List[Dict[str, Any]] = field(default_factory=list)
    start_index: int = 0

    # Results from MusicBrainz alignment
    mb_release_name: Optional[str] = None
    mb_artist_credit: Optional[str] = None
    aligned: bool = False

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    def __repr__(self) -> str:
        return f"AlbumSession('{self.album_name}', {self.track_count} tracks, aligned={self.aligned})"


class SessionAligner:
    """
    Align contiguous plays from the same album to a single MusicBrainz release.

    When a user listens to multiple tracks from the same album consecutively,
    this class detects these "sessions" and ensures all tracks get matched
    to the same MusicBrainz release, providing consistent artist credits.

    Usage:
        aligner = SessionAligner(musicbrainz_manager, min_session_size=3)
        sessions = aligner.detect_sessions(tracks)
        aligned_tracks = aligner.align_all_sessions(sessions, tracks)
    """

    # Minimum number of consecutive tracks to consider as a session
    DEFAULT_MIN_SESSION_SIZE = 3

    def __init__(self, manager, min_session_size: int = DEFAULT_MIN_SESSION_SIZE):
        """
        Initialize SessionAligner.

        Args:
            manager: MusicBrainzManagerV2Optimized instance for database queries
            min_session_size: Minimum consecutive tracks to form a session (default: 3)
        """
        self.manager = manager
        self.min_session_size = min_session_size

        # Stats
        self.stats = {
            'sessions_detected': 0,
            'sessions_aligned': 0,
            'tracks_in_sessions': 0,
            'tracks_aligned': 0
        }

    def detect_sessions(self, tracks: List[Dict[str, Any]]) -> List[AlbumSession]:
        """
        Detect album sessions in a list of tracks.

        A session is a group of 3+ consecutive tracks with the same
        album name (Container Description).

        Args:
            tracks: List of track dictionaries with 'album' and optionally 'artist' keys

        Returns:
            List of AlbumSession objects representing detected sessions
        """
        sessions: List[AlbumSession] = []

        if not tracks:
            return sessions

        current_session: Optional[AlbumSession] = None

        for i, track in enumerate(tracks):
            album = self._normalize_album_name(track.get('album', ''))
            artist = track.get('artist', '') or track.get('original_artist', '')

            # Skip tracks without album info
            if not album:
                # Close current session if exists
                if current_session and current_session.track_count >= self.min_session_size:
                    sessions.append(current_session)
                current_session = None
                continue

            # Check if this track continues the current session
            if current_session and current_session.album_name == album:
                current_session.tracks.append(track)
            else:
                # Save previous session if it meets minimum size
                if current_session and current_session.track_count >= self.min_session_size:
                    sessions.append(current_session)

                # Start new session
                current_session = AlbumSession(
                    album_name=album,
                    artist_hint=artist,
                    tracks=[track],
                    start_index=i
                )

        # Don't forget the last session
        if current_session and current_session.track_count >= self.min_session_size:
            sessions.append(current_session)

        # Update stats
        self.stats['sessions_detected'] = len(sessions)
        self.stats['tracks_in_sessions'] = sum(s.track_count for s in sessions)

        logger.info(f"Detected {len(sessions)} album sessions with {self.stats['tracks_in_sessions']} total tracks")

        return sessions

    def align_session(self, session: AlbumSession) -> AlbumSession:
        """
        Align a session to a single MusicBrainz release.

        Queries MusicBrainz for all tracks from the album and finds the
        best matching release for the session.

        Args:
            session: AlbumSession to align

        Returns:
            Updated AlbumSession with alignment results
        """
        if session.track_count < self.min_session_size:
            return session

        # Get all tracks from this release in MusicBrainz
        release_tracks = self._get_release_tracks(
            session.album_name,
            session.artist_hint
        )

        if not release_tracks:
            logger.debug(f"No release found for session: {session.album_name}")
            return session

        # Determine the dominant artist credit from release tracks
        artist_credits = {}
        for rt in release_tracks:
            credit = rt.get('artist_credit', '')
            if credit:
                artist_credits[credit] = artist_credits.get(credit, 0) + 1

        if not artist_credits:
            return session

        # Use the most common artist credit
        dominant_artist = max(artist_credits.keys(), key=lambda k: artist_credits[k])
        dominant_release = release_tracks[0].get('release_name', session.album_name)

        # Update session with alignment info
        session.mb_artist_credit = dominant_artist
        session.mb_release_name = dominant_release
        session.aligned = True

        logger.debug(f"Aligned session '{session.album_name}' -> artist='{dominant_artist}'")

        return session

    def align_all_sessions(self, sessions: List[AlbumSession],
                           tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply session alignments to the track list.

        For each aligned session, updates the matching tracks with the
        session's artist credit and release info.

        Args:
            sessions: List of AlbumSession objects (after alignment)
            tracks: Original list of track dictionaries

        Returns:
            Updated list of track dictionaries with session alignments applied
        """
        # Build a map of track index -> session alignment
        session_map: Dict[int, AlbumSession] = {}

        for session in sessions:
            if not session.aligned:
                self.align_session(session)

            if session.aligned:
                for offset, _ in enumerate(session.tracks):
                    track_index = session.start_index + offset
                    session_map[track_index] = session

        # Apply alignments to tracks
        aligned_count = 0
        for i, track in enumerate(tracks):
            if i in session_map:
                session = session_map[i]

                # Only update if we don't already have an artist
                if not track.get('artist') or track.get('artist', '').startswith('['):
                    track['artist'] = session.mb_artist_credit
                    track['album'] = session.mb_release_name or track.get('album', '')
                    track['match_source'] = 'session_aligned'
                    track['match_confidence'] = 'high_session'
                    aligned_count += 1

        self.stats['sessions_aligned'] = sum(1 for s in sessions if s.aligned)
        self.stats['tracks_aligned'] = aligned_count

        logger.info(f"Session alignment: {aligned_count} tracks updated from {self.stats['sessions_aligned']} sessions")

        return tracks

    def _get_release_tracks(self, album_name: str,
                            artist_hint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all tracks from a MusicBrainz release.

        Args:
            album_name: Album/release name to search
            artist_hint: Optional artist name to narrow results

        Returns:
            List of track info dictionaries from the release
        """
        if not hasattr(self.manager, '_conn') or self.manager._conn is None:
            return []

        try:
            # Clean the album name for comparison
            clean_album = self.manager.clean_text_conservative(album_name) if hasattr(self.manager, 'clean_text_conservative') else album_name.lower().strip()

            # Query for all tracks on releases matching this album name
            # Use both HOT and COLD tables for comprehensive coverage
            sql = """
                SELECT DISTINCT
                    artist_credit_name,
                    release_name,
                    recording_name,
                    score
                FROM musicbrainz_hot
                WHERE lower(release_name) LIKE ?
                ORDER BY score ASC
                LIMIT 100
            """

            results = self.manager._conn.execute(
                sql,
                [f"%{clean_album}%"]
            ).fetchall()

            if not results:
                # Try COLD table
                sql = sql.replace('musicbrainz_hot', 'musicbrainz_cold')
                results = self.manager._conn.execute(
                    sql,
                    [f"%{clean_album}%"]
                ).fetchall()

            release_tracks = []
            for row in results:
                release_tracks.append({
                    'artist_credit': row[0],
                    'release_name': row[1],
                    'recording_name': row[2],
                    'score': row[3]
                })

            # If we have an artist hint, filter to matching artists
            if artist_hint and release_tracks:
                clean_artist = artist_hint.lower().strip()
                filtered = [
                    rt for rt in release_tracks
                    if clean_artist in rt['artist_credit'].lower()
                ]
                if filtered:
                    return filtered

            return release_tracks

        except Exception as e:
            logger.debug(f"Error getting release tracks: {e}")
            return []

    def _normalize_album_name(self, album: str) -> str:
        """Normalize album name for consistent comparison."""
        if not album:
            return ''
        return album.lower().strip()

    def get_stats(self) -> Dict[str, int]:
        """Get session alignment statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            'sessions_detected': 0,
            'sessions_aligned': 0,
            'tracks_in_sessions': 0,
            'tracks_aligned': 0
        }
