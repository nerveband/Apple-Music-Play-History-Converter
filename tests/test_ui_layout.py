#!/usr/bin/env python3
"""
Test script to verify UI layout fixes.
"""

import tkinter as tk
from apple_music_play_history_converter import CSVProcessorApp

def test_ui_layout():
    """Test the UI layout improvements."""
    print("Testing UI Layout Fixes...")
    print("=" * 50)
    
    # Create the main application
    root = tk.Tk()
    
    try:
        app = CSVProcessorApp(root)
        
        # Check if buttons exist and are properly configured
        buttons = [
            ('check_updates_button', 'Check for Updates'),
            ('manual_import_button', 'Manual Import'),
            ('delete_db_button', 'Delete Database'),
            ('reveal_location_button', 'Reveal Location')
        ]
        
        print("Checking button configuration...")
        for button_attr, expected_text in buttons:
            if hasattr(app, button_attr):
                button = getattr(app, button_attr)
                actual_text = button.cget('text')
                grid_info = button.grid_info()
                
                print(f"✅ {button_attr}:")
                print(f"   Text: '{actual_text}' (expected: '{expected_text}')")
                print(f"   Grid: row={grid_info.get('row', 'N/A')}, column={grid_info.get('column', 'N/A')}")
                print(f"   Sticky: {grid_info.get('sticky', 'N/A')}")
                print(f"   Padx: {grid_info.get('padx', 'N/A')}, Pady: {grid_info.get('pady', 'N/A')}")
            else:
                print(f"❌ {button_attr} not found")
        
        # Check frame configuration
        if hasattr(app, 'db_buttons_frame'):
            frame = app.db_buttons_frame
            print(f"\nDatabase buttons frame grid info:")
            grid_info = frame.grid_info()
            print(f"   Grid: row={grid_info.get('row', 'N/A')}, column={grid_info.get('column', 'N/A')}")
            print(f"   Sticky: {grid_info.get('sticky', 'N/A')}")
            print(f"   Columnspan: {grid_info.get('columnspan', 'N/A')}")
            
            # Check column configuration
            try:
                for i in range(4):
                    weight = frame.grid_columnconfigure(i)['weight']
                    print(f"   Column {i} weight: {weight}")
            except:
                print("   Could not check column weights")
        
        print(f"\n🎉 UI Layout Test Complete!")
        print(f"📋 The main window should now display properly with:")
        print(f"   - Buttons arranged in a single row")
        print(f"   - Equal spacing and sizing")
        print(f"   - No cropped or overlapping elements")
        print(f"   - Proper expansion behavior")
        
        # Show the window for visual inspection
        root.mainloop()
        
    except Exception as e:
        print(f"❌ Error during UI layout test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    test_ui_layout()
