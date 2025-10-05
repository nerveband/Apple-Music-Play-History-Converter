"""Main entry point for Apple Music History Converter."""

import sys
from pathlib import Path

# Add the package directory to the path so we can import the application
package_dir = Path(__file__).parent
sys.path.insert(0, str(package_dir))

# Import the Briefcase app wrapper which includes network diagnostics
from app import AppleMusicHistoryConverterApp


if __name__ == '__main__':
    # Use the app wrapper which runs diagnostics and then creates the Toga app
    app_wrapper = AppleMusicHistoryConverterApp()
    app_wrapper.main_loop()
