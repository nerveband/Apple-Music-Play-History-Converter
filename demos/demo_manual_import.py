#!/usr/bin/env python3
"""
Demo script showing manual import functionality for MusicBrainz database.
"""

import tkinter as tk
from database_dialogs import ManualImportDialog
from music_search_service import MusicSearchService

def demo_manual_import():
    """Demo the manual import dialog."""
    # Create the main window
    root = tk.Tk()
    root.title("Manual Import Demo")
    root.geometry("400x200")
    
    # Create music search service
    search_service = MusicSearchService()
    
    def show_import_dialog():
        """Show the manual import dialog."""
        dialog = ManualImportDialog(root, search_service)
        success = dialog.show_and_wait()
        
        if success:
            result_label.config(text="✅ Manual import successful!", fg="green")
        else:
            result_label.config(text="❌ Manual import cancelled or failed", fg="red")
    
    # Create UI
    info_label = tk.Label(root, text="Click the button below to test manual import", 
                         font=("Arial", 12))
    info_label.pack(pady=20)
    
    import_btn = tk.Button(root, text="Open Manual Import Dialog", 
                          command=show_import_dialog,
                          font=("Arial", 10),
                          bg="#4CAF50", fg="white", 
                          padx=20, pady=10)
    import_btn.pack(pady=10)
    
    result_label = tk.Label(root, text="", font=("Arial", 10))
    result_label.pack(pady=10)
    
    instructions = tk.Label(root, 
                           text="The dialog will guide you through:\n"
                                "1. Downloading the .tar.zst file from MusicBrainz\n"
                                "2. Selecting the file for import\n"
                                "3. Processing and building the database",
                           font=("Arial", 9), justify=tk.LEFT)
    instructions.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    demo_manual_import()
