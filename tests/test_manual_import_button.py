#!/usr/bin/env python3
"""
Test script to verify manual import button functionality.
"""

import tkinter as tk
from apple_music_play_history_converter import CSVProcessorApp

def test_manual_import_button():
    """Test that the manual import button exists and is accessible."""
    print("Testing Manual Import Button...")
    print("=" * 50)
    
    # Create the main application
    root = tk.Tk()
    root.withdraw()  # Hide the main window for testing
    
    try:
        app = CSVProcessorApp(root)
        
        # Check if manual import button exists
        if hasattr(app, 'manual_import_button'):
            print("✅ Manual import button exists in main interface")
            
            # Check if button is properly configured
            button_text = app.manual_import_button.cget('text')
            if button_text == "Manual Import":
                print(f"✅ Button text is correct: '{button_text}'")
            else:
                print(f"❌ Button text is incorrect: '{button_text}'")
            
            # Check if command is properly set
            if app.manual_import_button.cget('command'):
                print("✅ Button command is configured")
            else:
                print("❌ Button command is not configured")
                
            # Check if method exists
            if hasattr(app, 'manual_import_database'):
                print("✅ manual_import_database method exists")
            else:
                print("❌ manual_import_database method missing")
                
        else:
            print("❌ Manual import button not found in main interface")
            
        # Check database buttons frame layout
        buttons_in_frame = []
        for child in app.db_buttons_frame.winfo_children():
            if isinstance(child, tk.Button) or hasattr(child, 'cget'):
                try:
                    button_text = child.cget('text')
                    buttons_in_frame.append(button_text)
                except:
                    pass
        
        print(f"\nButtons in database management frame: {buttons_in_frame}")
        
        if "Manual Import" in buttons_in_frame:
            print("✅ Manual Import button is properly placed in database management section")
        else:
            print("❌ Manual Import button not found in database management section")
            
        print("\nManual Import Button Test Complete!")
        print("=" * 50)
        print("🎉 The manual import button should now be visible in the main interface")
        print("📍 Look for it in the 'Music Database Settings' section")
        print("🔘 It's located next to 'Check for Updates', 'Delete Database', and 'Reveal Location' buttons")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    finally:
        root.destroy()

if __name__ == "__main__":
    test_manual_import_button()
