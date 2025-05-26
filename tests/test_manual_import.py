#!/usr/bin/env python3
"""Test script for manual import functionality."""

import os
import sys
from pathlib import Path

# Add the project directory to the Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from music_search_service import MusicSearchService
from database_dialogs import ManualImportDialog
import tkinter as tk


def test_manual_import():
    """Test the manual import dialog functionality."""
    print("Testing Manual Import Functionality...")
    print("=" * 50)
    
    # Create a test window
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Initialize music search service
    music_search_service = MusicSearchService()
    
    # Create manual import dialog
    print("Creating ManualImportDialog...")
    dialog = ManualImportDialog(root, music_search_service)
    
    # Check if dialog was created successfully
    if hasattr(dialog, 'dialog'):
        print("✓ ManualImportDialog created successfully")
    else:
        print("✗ Failed to create ManualImportDialog")
        return
    
    # Test the import_database_file method
    print("\nTesting import_database_file method...")
    test_file = "/path/to/musicbrainz-artist-recordings.tar.zst"
    
    # This will fail because the file doesn't exist, but it tests the method
    try:
        result = music_search_service.import_database_file(test_file)
        if result:
            print("✓ Import method returned True (unexpected)")
        else:
            print("✓ Import method returned False (expected - file doesn't exist)")
    except Exception as e:
        print(f"✗ Import method raised exception: {e}")
    
    print("\nManual Import Dialog Test Complete!")
    root.destroy()


if __name__ == "__main__":
    test_manual_import()
