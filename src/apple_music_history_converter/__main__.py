"""Main entry point for Apple Music History Converter."""

import sys
from pathlib import Path

# Add the package directory to the path so we can import the application
package_dir = Path(__file__).parent
sys.path.insert(0, str(package_dir))

from apple_music_play_history_converter import main


if __name__ == '__main__':
    app = main()
    app.main_loop()