"""
Export Format Handlers - Support for multiple output formats.
"""

import pandas as pd
from typing import List, Dict
from .logging_config import get_logger

logger = get_logger(__name__)

def _get_track_value(track: Dict, *keys: str) -> str:
    for key in keys:
        if key in track and track.get(key) not in (None, ""):
            return str(track.get(key))
    return ""


def export_lastfm_csv(tracks: List[Dict], output_path: str) -> bool:
    """
    Export tracks to Last.fm CSV format.

    Format: Artist, Track, Album, Timestamp, Album Artist, Duration

    Args:
        tracks: List of track dictionaries
        output_path: Path to output CSV file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert to DataFrame
        rows = []
        for track in tracks:
            artist = _get_track_value(track, "artist", "Artist")
            track_name = _get_track_value(track, "track", "Track")
            album = _get_track_value(track, "album", "Album")
            timestamp = _get_track_value(track, "timestamp", "Timestamp")
            duration = track.get("duration", track.get("Duration", 0))
            rows.append(
                {
                    "Artist": artist,
                    "Track": track_name,
                    "Album": album,
                    "Timestamp": timestamp,
                    "Album Artist": artist,  # Same as Artist per Last.fm spec
                    "Duration": duration,
                }
            )

        df = pd.DataFrame(rows)

        # Save to CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"[EXPORT] Last.fm CSV: {len(tracks)} tracks -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"[EXPORT] Last.fm CSV export failed: {e}")
        return False


def export_listenbrainz_json(tracks: List[Dict], output_path: str) -> bool:
    """
    Export tracks to ListenBrainz JSON format.

    Format: [{"track_metadata": {...}, "listened_at": <unix_timestamp>}]

    Args:
        tracks: List of track dictionaries
        output_path: Path to output JSON file

    Returns:
        True if successful, False otherwise
    """
    try:
        import json

        # Convert timestamps to Unix epoch
        listenbrainz_data = []
        for track in tracks:
            # Parse timestamp and convert to Unix epoch
            timestamp_str = track.get('timestamp', '')

            try:
                # Handle ISO 8601 format (e.g., "2023-12-12 13:18:00")
                if isinstance(timestamp_str, str):
                    if 'T' in timestamp_str:
                        # ISO format: "2023-12-12T13:18:00Z" or "2023-12-12T13:18:00"
                        dt = pd.to_datetime(timestamp_str, utc=True)
                    else:
                        # Space-separated: "2023-12-12 13:18:00"
                        dt = pd.to_datetime(timestamp_str, utc=True)
                else:
                    dt = pd.to_datetime(timestamp_str, utc=True)

                unix_timestamp = int(dt.timestamp())
            except Exception:
                # Fallback to current time if parsing fails
                logger.warning(f"[EXPORT] Timestamp parse failed: '{timestamp_str}', using current time")
                unix_timestamp = int(pd.Timestamp.now().timestamp())

            # Build ListenBrainz format
            listenbrainz_data.append({
                "track_metadata": {
                    "artist_name": track.get('artist', ''),
                    "track_name": track.get('track', ''),
                    "release_name": track.get('album', '')
                },
                "listened_at": unix_timestamp
            })

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(listenbrainz_data, f, indent=2, ensure_ascii=False)

        logger.info(f"[EXPORT] ListenBrainz JSON: {len(tracks)} tracks -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"[EXPORT] ListenBrainz JSON export failed: {e}")
        return False


def export_universal_csv(tracks: List[Dict], original_df: pd.DataFrame, output_path: str) -> bool:
    """
    Export tracks to Universal CSV format (all original fields).

    Preserves all columns from the original CSV file.

    Args:
        tracks: List of track dictionaries
        original_df: Original DataFrame with all columns
        output_path: Path to output CSV file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Save original DataFrame (preserves all fields)
        original_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"[EXPORT] Universal CSV: {len(tracks)} tracks -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"[EXPORT] Universal CSV export failed: {e}")
        return False


def export_spotify_csv(tracks: List[Dict], output_path: str) -> bool:
    """
    Export tracks to Spotify CSV format.

    Format: artist, track, album, timestamp, ms_played

    Args:
        tracks: List of track dictionaries
        output_path: Path to output CSV file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'artist': track.get('artist', ''),
                'track': track.get('track', ''),
                'album': track.get('album', ''),
                'timestamp': track.get('timestamp', ''),
                'ms_played': track.get('duration', 0) * 1000  # Convert to milliseconds
            }
            for track in tracks
        ])

        # Save to CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"[EXPORT] Spotify CSV: {len(tracks)} tracks -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"[EXPORT] Spotify CSV export failed: {e}")
        return False


def export_itunes_xml(tracks: List[Dict], output_path: str) -> bool:
    """
    Export tracks to iTunes Library XML (plist) format.

    Args:
        tracks: List of track dictionaries
        output_path: Path to output XML file

    Returns:
        True if successful, False otherwise
    """
    try:
        import plistlib
        import datetime

        plist_tracks = {}
        for idx, track in enumerate(tracks, start=1):
            artist = _get_track_value(track, "artist", "Artist")
            name = _get_track_value(track, "track", "Track")
            album = _get_track_value(track, "album", "Album")
            timestamp = _get_track_value(track, "timestamp", "Timestamp")
            duration = track.get("duration", track.get("Duration", 0))

            try:
                played = pd.to_datetime(timestamp, utc=True)
                played_dt = played.to_pydatetime()
            except Exception:
                played_dt = datetime.datetime.utcnow()

            plist_tracks[str(idx)] = {
                "Track ID": idx,
                "Name": name,
                "Artist": artist,
                "Album": album,
                "Play Date UTC": played_dt,
                "Total Time": int(float(duration) * 1000),
            }

        plist_data = {
            "Major Version": 1,
            "Minor Version": 1,
            "Date": datetime.datetime.utcnow(),
            "Tracks": plist_tracks,
        }

        with open(output_path, "wb") as f:
            plistlib.dump(plist_data, f)

        logger.info(f"[EXPORT] iTunes XML: {len(tracks)} tracks -> {output_path}")
        return True
    except Exception as e:
        logger.error(f"[EXPORT] iTunes XML export failed: {e}")
        return False


# Format names and extensions
FORMATS = {
    'lastfm': {
        'name': 'Last.fm CSV',
        'extension': '.csv',
        'handler': export_lastfm_csv,
        'description': 'Last.fm and Last.fm-compatible scrobblers'
    },
    'listenbrainz': {
        'name': 'ListenBrainz JSON',
        'extension': '.json',
        'handler': export_listenbrainz_json,
        'description': 'Direct import to ListenBrainz.org'
    },
    'universal': {
        'name': 'Universal CSV',
        'extension': '.csv',
        'handler': export_universal_csv,
        'description': 'All available fields from original CSV'
    },
    'spotify': {
        'name': 'Spotify CSV',
        'extension': '.csv',
        'handler': export_spotify_csv,
        'description': 'Third-party Spotify importers'
    },
    'itunes_xml': {
        'name': 'iTunes XML',
        'extension': '.xml',
        'handler': export_itunes_xml,
        'description': 'iTunes Library XML (plist)'
    }
}


def get_format_info(format_key: str) -> Dict:
    """Get format information by key."""
    return FORMATS.get(format_key, {
        'name': 'Unknown',
        'extension': '.csv',
        'handler': export_lastfm_csv,
        'description': 'Last.fm CSV format'
    })


def export_tracks(format_key: str, tracks: List[Dict], output_path: str, original_df: pd.DataFrame = None) -> bool:
    """
    Export tracks to specified format.

    Args:
        format_key: One of 'lastfm', 'listenbrainz', 'universal', 'spotify', 'itunes_xml'
        tracks: List of track dictionaries
        output_path: Path to output file (extension will be adjusted)
        original_df: Original DataFrame (required for 'universal' format)

    Returns:
        True if successful, False otherwise
    """
    format_info = get_format_info(format_key)
    handler = format_info['handler']

    # Adjust output path with correct extension
    base_path = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
    adjusted_path = base_path + format_info['extension']

    # Call appropriate export handler
    if format_key == 'universal':
        if original_df is None:
            logger.error("[EXPORT] Universal format requires original DataFrame")
            return False
        return handler(tracks, original_df, adjusted_path)
    else:
        return handler(tracks, adjusted_path)
