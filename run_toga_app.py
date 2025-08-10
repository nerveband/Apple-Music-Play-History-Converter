#!/usr/bin/env python3
"""
Apple Music Play History Converter - Toga Version Runner
Runs the Toga-based GUI version of the application.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_dir = project_root / "src" / "apple_music_history_converter"
sys.path.insert(0, str(src_dir))

def main():
    """Run the Toga version of Apple Music Play History Converter."""
    try:
        # Import and run the Toga app
        from apple_music_play_history_converter import main as create_app
        print("🎵 Starting Apple Music Play History Converter (Toga Version)...")
        print("━" * 60)
        
        app = create_app()
        app.main_loop()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n💡 Make sure you have installed the required dependencies:")
        print("   pip install toga pandas requests darkdetect")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()