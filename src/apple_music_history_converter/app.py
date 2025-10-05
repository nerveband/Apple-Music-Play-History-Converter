"""Apple Music History Converter - Briefcase Entry Point

This module provides the main entry point for the Briefcase-packaged application.
Now using Toga for cross-platform GUI support.
"""

import sys
import os
from pathlib import Path

try:
    from .logging_config import get_logger
except ImportError:
    from logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Enable NSLog on macOS for packaged apps
if sys.platform == 'darwin':
    try:
        import nslog
        logger.info("✅ NSLog enabled for stdout/stderr capture")
    except ImportError:
        logger.warning("⚠️ NSLog not available - using standard output")

# Import the Toga-based application
try:
    from .apple_music_play_history_converter import main as create_app
except ImportError:
    from apple_music_play_history_converter import main as create_app


class AppleMusicHistoryConverterApp:
    """Main application class for Briefcase using Toga."""

    def __init__(self):
        """Initialize the application."""
        logger.info("Initializing Apple Music History Converter (Toga version)")

        # Run network diagnostics on startup
        logger.print_always("="*80)
        logger.print_always("Starting network diagnostics...")
        logger.print_always("="*80)
        try:
            from apple_music_history_converter.network_diagnostics import run_diagnostics
            logger.info("Running network diagnostics...")
            logger.debug("About to call run_diagnostics()")
            diagnostics_passed = run_diagnostics(verbose=True)
            logger.debug(f"Diagnostics completed: {diagnostics_passed}")
            if diagnostics_passed:
                logger.print_always("✅ Network diagnostics PASSED")
            else:
                logger.error("⚠️ Network diagnostics FAILED")
        except Exception as e:
            logger.error(f"❌ Network diagnostics ERROR: {e}")
            import traceback
            traceback.print_exc()

        try:
            # Create the Toga application
            logger.info("Creating Toga application instance")
            self.app = create_app()
            logger.info("Application initialization completed successfully")

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise

    def main_loop(self):
        """Start the main application loop."""
        logger.info("Starting Toga main application loop")
        try:
            self.app.main_loop()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        finally:
            logger.info("Application loop ended")


def main():
    """Entry point for the application."""
    logger.info("=== Apple Music History Converter Starting (Toga Version) ===")

    try:
        # Initialize and check platform info
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Script location: {__file__}")

        app = AppleMusicHistoryConverterApp()
        app.main_loop()

    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
    finally:
        logger.info("=== Apple Music History Converter Ending ===")


if __name__ == '__main__':
    main()