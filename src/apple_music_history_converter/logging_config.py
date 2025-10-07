#!/usr/bin/env python3
"""
Centralized logging configuration that outputs like print() but also logs to files.

Usage:
    from logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("This prints to terminal AND logs to file!")

    # For user-facing output that should ALWAYS print regardless of logging settings:
    logger.print_always("This always prints to terminal")

Feature Flag Support:
    Logging can be disabled via settings.json. When disabled:
    - No file I/O
    - No string formatting overhead
    - logger.debug/info/warning/error/critical become no-ops
    - logger.print_always() still works (for user-facing output)
"""

import sys
import logging
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any

try:
    from .app_directories import get_log_path, get_settings_path, get_user_log_dir
except ImportError:
    from app_directories import get_log_path, get_settings_path, get_user_log_dir


class PrintLikeFormatter(logging.Formatter):
    """
    Formatter that makes log output look like print() statements with optional emoji.

    Terminal output: Just the message (clean, like print)
    File output: Full details with timestamp, level, module, line number
    """

    # Emoji prefixes for different log levels (terminal only)
    TERMINAL_FORMATS = {
        logging.DEBUG: "🔍 %(message)s",
        logging.INFO: "%(message)s",  # No prefix for info (cleanest)
        logging.WARNING: "⚠️  %(message)s",
        logging.ERROR: "❌ %(message)s",
        logging.CRITICAL: "🚨 %(message)s",
    }

    # Detailed format for file output
    FILE_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s"

    def __init__(self, use_emoji=True, for_file=False):
        """
        Args:
            use_emoji: If True, adds emoji prefixes to terminal output
            for_file: If True, uses detailed format for file logging
        """
        self.use_emoji = use_emoji
        self.for_file = for_file
        super().__init__()

    def format(self, record):
        if self.for_file:
            # File output: detailed with timestamp
            formatter = logging.Formatter(
                self.FILE_FORMAT,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        elif self.use_emoji:
            # Terminal output: emoji + message
            log_fmt = self.TERMINAL_FORMATS.get(record.levelno, "%(message)s")
            formatter = logging.Formatter(log_fmt)
        else:
            # Terminal output: just message (exactly like print)
            formatter = logging.Formatter("%(message)s")

        return formatter.format(record)


# ============================================================================
# Settings Management
# ============================================================================

# Default logging settings
DEFAULT_LOGGING_SETTINGS = {
    "enabled": True,              # Master switch
    "file_logging": True,          # Write to log files
    "console_logging": True,       # Print to terminal
    "level": "INFO",               # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "use_emoji": True,             # Emoji prefixes in terminal
    "max_file_size_mb": 10,        # Log rotation size
    "backup_count": 5              # Number of rotated logs to keep
}


def load_logging_settings() -> Dict[str, Any]:
    """
    Load logging settings from settings.json.
    Returns default settings if file doesn't exist or is invalid.

    Returns:
        Dict containing logging configuration
    """
    try:
        settings_path = get_settings_path()
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                # Return logging section if it exists, otherwise defaults
                return settings.get("logging", DEFAULT_LOGGING_SETTINGS.copy())
    except Exception:
        # Silently fall back to defaults if loading fails
        pass

    return DEFAULT_LOGGING_SETTINGS.copy()


def is_logging_enabled() -> bool:
    """
    Check if logging is enabled via settings.

    Returns:
        bool: True if logging is enabled, False otherwise
    """
    settings = load_logging_settings()
    return settings.get("enabled", True)


def save_logging_settings(logging_settings: Dict[str, Any]) -> bool:
    """
    Save logging settings to settings.json.

    Args:
        logging_settings: Dict containing logging configuration

    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        settings_path = get_settings_path()

        # Load existing settings or create new
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}

        # Update logging section
        settings["logging"] = logging_settings

        # Save back to file
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        return True
    except Exception:
        return False


# ============================================================================
# SmartLogger Class (Feature Flag Support)
# ============================================================================

class SmartLogger:
    """
    Logger that respects feature flags and provides backwards compatibility.
    When logging is disabled, becomes a no-op (zero overhead).

    This wrapper provides:
    - Zero overhead when logging disabled (early return, no string formatting)
    - print_always() method for user-facing output
    - Lazy string formatting (only formats when enabled)
    - Full compatibility with stdlib logging.Logger API
    """

    def __init__(self, name: str, settings: Optional[Dict[str, Any]] = None):
        """
        Initialize SmartLogger with optional settings override.

        Args:
            name: Logger name (usually __name__)
            settings: Optional settings dict to override loaded settings
        """
        self.name = name
        self.settings = settings if settings is not None else load_logging_settings()
        self.enabled = self.settings.get("enabled", True)
        self.console_logging = self.settings.get("console_logging", True)
        self.file_logging = self.settings.get("file_logging", True)

        # Only create actual logger if logging is enabled
        if self.enabled:
            # Convert string level to int
            level_str = self.settings.get("level", "INFO")
            level = getattr(logging, level_str.upper(), logging.INFO)

            self._logger = setup_logger(
                name=name,
                level=level,
                use_emoji=self.settings.get("use_emoji", True),
                print_to_terminal=self.console_logging,
                max_bytes=self.settings.get("max_file_size_mb", 10) * 1024 * 1024,
                backup_count=self.settings.get("backup_count", 5)
            )
        else:
            self._logger = None

    def is_enabled(self, level: int = logging.DEBUG) -> bool:
        """
        Check if logging is enabled for a specific level.

        Args:
            level: Logging level to check

        Returns:
            bool: True if logging is enabled for this level
        """
        if not self.enabled or not self._logger:
            return False
        return self._logger.isEnabledFor(level)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with traceback (only if enabled)"""
        if self.enabled and self._logger:
            self._logger.exception(msg, *args, **kwargs)

    def print_always(self, msg: str, flush: bool = True):
        """
        Print to console ALWAYS, regardless of logging settings.
        Use this for user-facing output that should always be visible.

        Args:
            msg: Message to print
            flush: Whether to flush output immediately (default: True)
        """
        print(msg, flush=flush)

    # Aliases for compatibility
    warn = warning


# ============================================================================
# Logger Cache (avoid recreation)
# ============================================================================

_logger_cache: Dict[str, SmartLogger] = {}


def get_logger(name: str, settings: Optional[Dict[str, Any]] = None) -> SmartLogger:
    """
    Get or create a SmartLogger instance with caching.

    Args:
        name: Logger name (usually __name__)
        settings: Optional settings override (for testing)

    Returns:
        SmartLogger instance

    Example:
        from logging_config import get_logger

        logger = get_logger(__name__)
        logger.info("This respects logging settings")
        logger.print_always("This ALWAYS prints")
    """
    # Use settings-specific cache key if custom settings provided
    cache_key = name if settings is None else f"{name}:{id(settings)}"

    if cache_key not in _logger_cache:
        _logger_cache[cache_key] = SmartLogger(name, settings)

    return _logger_cache[cache_key]


def clear_logger_cache():
    """
    Clear the logger cache.
    Useful when settings change and loggers need to be recreated.
    """
    global _logger_cache
    _logger_cache.clear()


# ============================================================================
# Legacy setup_logger (for backwards compatibility)
# ============================================================================

def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: str = None,
    use_emoji: bool = True,
    print_to_terminal: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up a logger that prints to terminal (like print) AND logs to file.

    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file name (e.g., 'myapp.log'). If None, uses name.log
        use_emoji: If True, adds emoji prefixes to terminal output
        print_to_terminal: If True, prints to terminal; if False, only logs to file
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup log files to keep

    Returns:
        Configured logger instance

    Examples:
        # Basic usage (prints to terminal like print, logs to file):
        logger = setup_logger(__name__)
        logger.info("Hello!")  # Terminal: "Hello!"

        # With emoji (default):
        logger.warning("Be careful!")  # Terminal: "⚠️  Be careful!"

        # Without emoji (pure print style):
        logger = setup_logger(__name__, use_emoji=False)
        logger.info("Clean output")  # Terminal: "Clean output"

        # File-only logging (no terminal output):
        logger = setup_logger(__name__, print_to_terminal=False)
        logger.info("This only goes to file")  # Terminal: (nothing)
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False  # Don't propagate to root logger

    # 1. TERMINAL HANDLER (prints like print, with flush) - only if enabled
    if print_to_terminal:
        # Make it flush immediately (like print with flush=True)
        class FlushingStreamHandler(logging.StreamHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()

        terminal_handler = FlushingStreamHandler(sys.stdout)
        terminal_handler.setLevel(level)
        terminal_handler.setFormatter(PrintLikeFormatter(use_emoji=use_emoji, for_file=False))

        logger.addHandler(terminal_handler)

    # 2. FILE HANDLER (detailed logging with rotation)
    if log_file is None:
        log_file = f"{name.split('.')[-1]}.log"

    try:
        log_path = get_log_path(log_file)

        # Use rotating file handler to prevent huge log files
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(PrintLikeFormatter(use_emoji=False, for_file=True))

        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, at least print to terminal
        logger.error(f"Failed to set up file logging: {e}")

    return logger


# Pre-configure the root logger for the entire app
def configure_app_logging(level=logging.INFO, use_emoji=True):
    """
    Configure logging for the entire application.
    Call this once at app startup.

    Args:
        level: Default logging level
        use_emoji: Whether to use emoji in terminal output
    """
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our custom handlers
    terminal_handler = logging.StreamHandler(sys.stdout)
    terminal_handler.setLevel(level)
    terminal_handler.setFormatter(PrintLikeFormatter(use_emoji=use_emoji, for_file=False))
    root_logger.addHandler(terminal_handler)


if __name__ == "__main__":
    """Demo of SmartLogger with feature flag support"""
    print("="*80)
    print("DEMO: SmartLogger with Feature Flag Support")
    print("="*80)

    # Example 1: Logging ENABLED (default)
    print("\n1. Logging ENABLED (default):")
    logger1 = get_logger("demo.enabled")
    logger1.debug("This won't show (INFO level)")
    logger1.info("Info message")
    logger1.warning("Warning message")
    logger1.error("Error message")
    logger1.print_always("✅ This ALWAYS prints (user-facing)")

    # Example 2: Logging DISABLED (zero overhead)
    print("\n2. Logging DISABLED (zero overhead):")
    disabled_settings = {"enabled": False}
    logger2 = get_logger("demo.disabled", settings=disabled_settings)
    logger2.info("This won't show (logging disabled)")
    logger2.error("This won't show either")
    logger2.print_always("✅ But print_always() still works!")

    # Example 3: Debug level
    print("\n3. Debug level enabled:")
    debug_settings = {"enabled": True, "level": "DEBUG", "use_emoji": True}
    logger3 = get_logger("demo.debug", settings=debug_settings)
    logger3.debug("🔍 Now you can see debug messages!")
    logger3.info("And info messages")

    # Example 4: Console-only (no file logging)
    print("\n4. Console-only (no file logging):")
    console_settings = {"enabled": True, "file_logging": False, "console_logging": True}
    logger4 = get_logger("demo.console", settings=console_settings)
    logger4.info("This prints but doesn't write to file")

    # Example 5: Check if logging is enabled
    print("\n5. Feature flag check:")
    print(f"   is_logging_enabled() = {is_logging_enabled()}")
    print(f"   logger1.is_enabled(logging.INFO) = {logger1.is_enabled(logging.INFO)}")
    print(f"   logger2.is_enabled(logging.INFO) = {logger2.is_enabled(logging.INFO)}")

    # Show where logs are saved
    print(f"\n✅ Logs are saved to:")
    print(f"   {get_user_log_dir()}")
    print(f"\n✅ Settings file:")
    print(f"   {get_settings_path()}")
