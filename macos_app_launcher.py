#!/usr/bin/env python3
"""
macOS-specific launcher for Apple Music Play History Converter

This wrapper handles macOS-specific initialization issues that can prevent
PyInstaller-built tkinter applications from launching properly.
"""

import sys
import os
import platform
import tkinter as tk
from pathlib import Path

def setup_macos_environment():
    """Setup macOS-specific environment variables and paths for GUI applications."""
    
    # Ensure we're running on macOS
    if platform.system() != 'Darwin':
        return
    
    # Set up environment for bundled app
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We're running in a PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        
        # Set TCL_LIBRARY and TK_LIBRARY for tkinter
        tcl_lib = bundle_dir / 'tcl8'
        tk_lib = bundle_dir / 'tk8'
        
        if tcl_lib.exists():
            os.environ['TCL_LIBRARY'] = str(tcl_lib)
        if tk_lib.exists():
            os.environ['TK_LIBRARY'] = str(tk_lib)
        
        # Ensure PATH includes the bundle directory for dylibs
        current_path = os.environ.get('PATH', '')
        if str(bundle_dir) not in current_path:
            os.environ['PATH'] = f"{bundle_dir}:{current_path}"
        
        # Set DYLD_LIBRARY_PATH for dynamic libraries
        dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        if str(bundle_dir) not in dyld_path:
            if dyld_path:
                os.environ['DYLD_LIBRARY_PATH'] = f"{bundle_dir}:{dyld_path}"
            else:
                os.environ['DYLD_LIBRARY_PATH'] = str(bundle_dir)
    
    # Force use of native macOS theme
    os.environ['TK_AQUA'] = '1'
    
    # Ensure proper display configuration
    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':0'

def create_root_window():
    """Create and configure the root tkinter window with macOS-specific settings."""
    
    # Create root window
    root = tk.Tk()
    root.title("Apple Music Play History Converter")
    
    # macOS-specific window configuration
    if platform.system() == 'Darwin':
        try:
            # Try to set macOS-specific attributes
            root.tk.call('::tk::unsupported::MacWindowStyle', 
                        'style', root._w, 'document', 'closeBox')
        except tk.TclError:
            # If that fails, continue without it
            pass
        
        # Ensure the window appears in the dock properly
        root.lift()
        root.attributes('-topmost', True)
        root.after_idle(lambda: root.attributes('-topmost', False))
    
    return root

def main():
    """Main entry point with macOS-specific setup."""
    
    print("Starting Apple Music Play History Converter...")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    # Check if we're in a bundle
    if getattr(sys, 'frozen', False):
        print(f"Running from PyInstaller bundle: {sys._MEIPASS}")
    else:
        print("Running from source")
    
    try:
        # Setup macOS environment
        setup_macos_environment()
        print("macOS environment setup complete")
        
        # Test tkinter availability
        print("Testing tkinter...")
        test_root = tk.Tk()
        test_root.withdraw()  # Hide the test window
        test_root.destroy()
        print("tkinter test successful")
        
        # Import and start the main application
        print("Importing main application...")
        from apple_music_play_history_converter import CSVProcessorApp
        
        print("Creating main window...")
        root = create_root_window()
        
        print("Initializing application...")
        app = CSVProcessorApp(root)
        
        print("Starting main loop...")
        root.mainloop()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Failed to import required modules")
        sys.exit(1)
        
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()