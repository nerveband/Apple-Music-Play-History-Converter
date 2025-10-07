#!/usr/bin/env python3
"""
Cross-platform application directories using platformdirs.

This module provides consistent, platform-appropriate paths for:
- User data (database, settings)
- User logs (debug logs, API logs)
- User cache (temporary files)

Platform-specific paths:
- macOS: ~/Library/Application Support/AppleMusicConverter, ~/Library/Logs/AppleMusicConverter
- Windows: %LOCALAPPDATA%\\AppleMusicConverter, %LOCALAPPDATA%\\AppleMusicConverter\\Logs
- Linux: ~/.local/share/AppleMusicConverter, ~/.cache/AppleMusicConverter/log
"""

from pathlib import Path
import platformdirs

# Application metadata
APP_NAME = "AppleMusicConverter"
APP_AUTHOR = "nerveband"

def get_user_data_dir() -> Path:
    """
    Get the platform-appropriate user data directory.

    This is where persistent data like databases and settings should be stored.

    Returns:
        Path: Platform-specific user data directory

    Examples:
        - macOS: ~/Library/Application Support/AppleMusicConverter
        - Windows: C:\\Users\\<user>\\AppData\\Local\\AppleMusicConverter
        - Linux: ~/.local/share/AppleMusicConverter
    """
    data_dir = Path(platformdirs.user_data_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_user_log_dir() -> Path:
    """
    Get the platform-appropriate user log directory.

    This is where log files should be stored.

    Returns:
        Path: Platform-specific user log directory

    Examples:
        - macOS: ~/Library/Logs/AppleMusicConverter
        - Windows: C:\\Users\\<user>\\AppData\\Local\\AppleMusicConverter\\Logs
        - Linux: ~/.cache/AppleMusicConverter/log
    """
    log_dir = Path(platformdirs.user_log_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_user_cache_dir() -> Path:
    """
    Get the platform-appropriate user cache directory.

    This is where temporary/cache files should be stored.

    Returns:
        Path: Platform-specific user cache directory

    Examples:
        - macOS: ~/Library/Caches/AppleMusicConverter
        - Windows: C:\\Users\\<user>\\AppData\\Local\\AppleMusicConverter\\Cache
        - Linux: ~/.cache/AppleMusicConverter
    """
    cache_dir = Path(platformdirs.user_cache_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_settings_path() -> Path:
    """
    Get the settings file path.

    Returns:
        Path: Path to settings.json file in the user data directory
    """
    return get_user_data_dir() / "settings.json"


def get_database_dir() -> Path:
    """
    Get the database directory path.

    MusicBrainz database files are stored in a 'musicbrainz' subdirectory
    within the user data directory.

    Returns:
        Path: Directory containing MusicBrainz database files
    """
    db_dir = get_user_data_dir() / "musicbrainz"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def get_log_path(log_name: str) -> Path:
    """
    Get path for a specific log file.

    Args:
        log_name: Name of the log file (e.g., 'network_diagnostics.log')

    Returns:
        Path: Full path to the log file in the platform-appropriate log directory
    """
    return get_user_log_dir() / log_name


def get_logging_settings() -> dict:
    """
    Get logging settings from settings.json.
    Returns default logging settings if not found.

    Returns:
        dict: Logging configuration with keys:
            - enabled: bool (master switch)
            - file_logging: bool (write to files)
            - console_logging: bool (print to terminal)
            - level: str (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            - use_emoji: bool (emoji prefixes in terminal)
            - max_file_size_mb: int (log rotation size)
            - backup_count: int (rotated logs to keep)
    """
    import json

    default_settings = {
        "enabled": True,
        "file_logging": True,
        "console_logging": True,
        "level": "INFO",
        "use_emoji": True,
        "max_file_size_mb": 10,
        "backup_count": 5
    }

    try:
        settings_path = get_settings_path()
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return settings.get("logging", default_settings)
    except Exception:
        pass

    return default_settings


def save_logging_settings(logging_config: dict) -> bool:
    """
    Save logging settings to settings.json.

    Args:
        logging_config: Dict containing logging configuration

    Returns:
        bool: True if save successful, False otherwise
    """
    import json

    try:
        settings_path = get_settings_path()

        # Load existing settings or create new
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}

        # Update logging section
        settings["logging"] = logging_config

        # Save back to file
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        return True
    except Exception:
        return False


def initialize_logging_settings_if_needed():
    """
    Initialize logging settings in settings.json if they don't exist.
    This is called automatically on module import.
    """
    import json

    try:
        settings_path = get_settings_path()
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            # Only add if missing
            if "logging" not in settings:
                default_logging = {
                    "enabled": True,
                    "file_logging": True,
                    "console_logging": True,
                    "level": "INFO",
                    "use_emoji": True,
                    "max_file_size_mb": 10,
                    "backup_count": 5
                }
                settings["logging"] = default_logging

                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=2)
    except Exception:
        pass  # Fail silently if we can't initialize


# Pre-create all directories on module import
try:
    get_user_data_dir()
    get_user_log_dir()
    get_user_cache_dir()
    get_database_dir()
    initialize_logging_settings_if_needed()
except Exception as e:
    print(f"Warning: Failed to create app directories: {e}")


if __name__ == "__main__":
    """Print directory locations for debugging"""
    print("="*80)
    print("Apple Music Converter - Directory Locations")
    print("="*80)
    print(f"User Data Directory:  {get_user_data_dir()}")
    print(f"User Log Directory:   {get_user_log_dir()}")
    print(f"User Cache Directory: {get_user_cache_dir()}")
    print(f"Settings File:        {get_settings_path()}")
    print(f"Database Directory:   {get_database_dir()}")
    print("="*80)
