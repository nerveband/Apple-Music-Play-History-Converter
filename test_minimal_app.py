#!/usr/bin/env python3
"""
Minimal test app to isolate the crash issue
"""

import sys
import os
import platform
import tkinter as tk
from tkinter import ttk

def main():
    print("=== MINIMAL APP TEST ===")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    # Check if we're in a bundle
    if getattr(sys, 'frozen', False):
        print(f"Running from PyInstaller bundle: {sys._MEIPASS}")
    else:
        print("Running from source")
    
    try:
        print("Creating tkinter window...")
        root = tk.Tk()
        root.title("Minimal Test App")
        root.geometry("400x300")
        
        # Add some basic widgets
        label = tk.Label(root, text="✅ App launched successfully!", font=("Arial", 16))
        label.pack(pady=50)
        
        button = tk.Button(root, text="Close", command=root.quit)
        button.pack(pady=20)
        
        print("✅ Window created successfully")
        print("Starting mainloop...")
        
        # Start the GUI
        root.mainloop()
        
        print("✅ App closed normally")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())