#!/usr/bin/env python3
"""
Test script to verify manual import dialog fixes.
"""

import tkinter as tk
import sys
from database_dialogs import ManualImportDialog
from music_search_service import MusicSearchService

def test_manual_import_dialog():
    """Test manual import dialog creation and display."""
    print("Testing Manual Import Dialog Fixes...")
    print("=" * 50)
    
    # Create test window
    root = tk.Tk()
    root.title("Manual Import Test")
    root.geometry("300x200")
    
    # Create music search service
    try:
        search_service = MusicSearchService()
        print("✅ MusicSearchService created successfully")
    except Exception as e:
        print(f"❌ Failed to create MusicSearchService: {e}")
        return
    
    def test_dialog():
        """Test creating and showing the dialog."""
        try:
            print("🔄 Creating ManualImportDialog...")
            dialog = ManualImportDialog(root, search_service)
            print("✅ ManualImportDialog created successfully")
            
            print("🔄 Testing show_and_wait method...")
            # Note: This will show the dialog - close it to continue
            success = dialog.show_and_wait()
            print(f"✅ Dialog completed. Success: {success}")
            
        except Exception as e:
            print(f"❌ Error testing dialog: {e}")
            import traceback
            traceback.print_exc()
    
    # Create test button
    test_button = tk.Button(root, text="Test Manual Import Dialog", 
                           command=test_dialog,
                           bg="#4CAF50", fg="white", 
                           padx=20, pady=10)
    test_button.pack(pady=50)
    
    info_label = tk.Label(root, text="Click the button to test the manual import dialog\n(Close the dialog when it opens)")
    info_label.pack(pady=10)
    
    print("✅ Test window created")
    print("📋 Click the button in the window to test the manual import dialog")
    print("📋 Close the dialog when it opens to verify it works without crashing")
    
    root.mainloop()

if __name__ == "__main__":
    test_manual_import_dialog()
