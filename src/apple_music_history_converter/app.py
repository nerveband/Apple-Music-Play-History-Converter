"""Apple Music History Converter - Briefcase Entry Point

This module provides the main entry point for the Briefcase-packaged application.
Now using Toga for cross-platform GUI support.
"""

import sys
import os
import logging
from pathlib import Path

# Set up logging for better debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import the Toga-based application
try:
    from .apple_music_play_history_converter import main as create_app
except ImportError:
    from apple_music_play_history_converter import main as create_app


class AppleMusicHistoryConverterApp:
    """Main application class for Briefcase using Toga."""

    def __init__(self):
        """Initialize the application."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Apple Music History Converter (Toga version)")
        
        try:
            # Create the Toga application
            self.logger.info("Creating Toga application instance")
            self.app = create_app()
            self.logger.info("Application initialization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            raise

    def main_loop(self):
        """Start the main application loop."""
        self.logger.info("Starting Toga main application loop")
        try:
            self.app.main_loop()
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            raise
        finally:
            self.logger.info("Application loop ended")


def main():
    """Entry point for the application."""
    logger = logging.getLogger(__name__)
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