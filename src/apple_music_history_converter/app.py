"""Apple Music History Converter - Briefcase Entry Point

This module provides the main entry point for the Briefcase-packaged application.
"""

import tkinter as tk
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

# Import the main application class
from .apple_music_play_history_converter import CSVProcessorApp


class AppleMusicHistoryConverterApp:
    """Main application class for Briefcase."""

    def __init__(self):
        """Initialize the application."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Apple Music History Converter")
        
        try:
            self.root = tk.Tk()
            self.root.title("Apple Music Play History Converter")
            self.logger.info("Tkinter root window created successfully")
            
            # Set the app icon if available
            icon_path = Path(__file__).parent / "resources" / "appicon.png"
            if icon_path.exists():
                try:
                    self.root.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
                    self.logger.info(f"App icon loaded from {icon_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to load app icon: {e}")
            else:
                self.logger.warning(f"App icon not found at {icon_path}")
            
            # Create the main application
            self.logger.info("Creating CSVProcessorApp instance")
            self.csv_processor = CSVProcessorApp(self.root)
            self.logger.info("Application initialization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            raise

    def main_loop(self):
        """Start the main application loop."""
        self.logger.info("Starting main application loop")
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            raise
        finally:
            self.logger.info("Application loop ended")


def main():
    """Entry point for the application."""
    logger = logging.getLogger(__name__)
    logger.info("=== Apple Music History Converter Starting ===")
    
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