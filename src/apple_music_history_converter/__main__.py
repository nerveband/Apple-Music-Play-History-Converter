"""Main entry point for Apple Music History Converter."""

import tkinter as tk
import sys
import os
from pathlib import Path

# Add the package directory to the path so we can import the application
package_dir = Path(__file__).parent
sys.path.insert(0, str(package_dir))

from apple_music_play_history_converter import CSVProcessorApp


def main():
    """Main application entry point."""
    root = tk.Tk()
    root.title("Apple Music Play History Converter")
    app = CSVProcessorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()