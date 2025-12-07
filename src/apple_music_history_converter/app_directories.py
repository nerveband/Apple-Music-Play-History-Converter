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
    Get the base database directory path.

    The MusicBrainz manager expects the base directory (user data dir) and
    will add the 'musicbrainz' subdirectory itself.

    Returns:
        Path: Base directory for database storage (user data dir)
    """
    # Return the user data dir - the manager adds /musicbrainz itself
    return get_user_data_dir()


def get_log_path(log_name: str) -> Path:
    """
    Get path for a specific log file.

    Args:
        log_name: Name of the log file (e.g., 'network_diagnostics.log')

    Returns:
        Path: Full path to the log file in the platform-appropriate log directory
    """
    return get_user_log_dir() / log_name


# ============================================================================
# Testing Infrastructure Settings
# ============================================================================

# Default testing settings - disabled by default for zero overhead
DEFAULT_TESTING_SETTINGS = {
    "enabled": False,           # Master switch - when False, zero overhead
    "log_actions": True,        # Log widget interactions (clicks, value changes)
    "log_state": True,          # Log state snapshots after actions
    "verbose": False            # Extra detailed logging for debugging
}


def get_testing_settings() -> dict:
    """
    Get testing infrastructure settings from settings.json.
    Returns default testing settings if not found.

    Testing mode is disabled by default to ensure zero overhead for regular users.
    Enable via:
    - Settings file: {"testing": {"enabled": true}}
    - Command line: python run_toga_app.py --test-mode
    - Environment variable: TEST_MODE=1

    Returns:
        dict: Testing configuration with keys:
            - enabled: bool (master switch, default False)
            - log_actions: bool (log widget interactions)
            - log_state: bool (log state snapshots)
            - verbose: bool (extra detailed logging)
    """
    import json
    import os

    # Check environment variable first (highest priority)
    if os.environ.get('TEST_MODE') == '1':
        settings = DEFAULT_TESTING_SETTINGS.copy()
        settings['enabled'] = True
        if os.environ.get('TEST_VERBOSE') == '1':
            settings['verbose'] = True
        return settings

    try:
        settings_path = get_settings_path()
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return settings.get("testing", DEFAULT_TESTING_SETTINGS.copy())
    except Exception:
        pass

    return DEFAULT_TESTING_SETTINGS.copy()


def save_testing_settings(testing_config: dict) -> bool:
    """
    Save testing settings to settings.json.

    Args:
        testing_config: Dict containing testing configuration

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

        # Update testing section
        settings["testing"] = testing_config

        # Save back to file
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        return True
    except Exception:
        return False


def is_testing_enabled() -> bool:
    """
    Quick check if testing mode is enabled.

    Returns:
        bool: True if testing mode is enabled
    """
    import os

    # Environment variable takes priority
    if os.environ.get('TEST_MODE') == '1':
        return True

    return get_testing_settings().get('enabled', False)


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
