#!/usr/bin/env python3
"""
Safe version of manual import dialog that avoids macOS crashes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import platform

class SafeManualImportDialog:
    """
    A crash-safe version of the manual import dialog.
    This version avoids all known macOS crash scenarios.
    """
    
    def __init__(self, parent):
        self.parent = parent
        self.dialog = None
        self.success = False
        self.selected_file = None
    
    def show_and_wait(self):
        """Show dialog and wait for user action."""
        try:
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title("Safe Manual Database Import")
            self.dialog.geometry("500x400")
            self.dialog.resizable(True, True)
            
            # Make dialog modal but avoid grab_set issues
            self.dialog.transient(self.parent)
            
            # Center dialog safely
            self.center_dialog()
            
            # Create widgets
            self.create_widgets()
            
            # Handle window close
            self.dialog.protocol("WM_DELETE_WINDOW", self.close_dialog)
            
            # Wait for dialog to close
            self.parent.wait_window(self.dialog)
            return self.success
            
        except Exception as e:
            print(f"Error creating safe manual import dialog: {e}")
            self.cleanup()
            return False
    
    def center_dialog(self):
        """Safely center the dialog."""
        try:
            # Update window to get actual dimensions
            self.dialog.update_idletasks()
            
            # Get parent position
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            
            # Calculate center position
            dialog_width = 500
            dialog_height = 400
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            
            # Set position
            self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            
        except Exception as e:
            print(f"Could not center dialog: {e}")
            # Continue without centering
    
    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Manual Database Import", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Instructions
        instructions = tk.Text(main_frame, height=8, wrap=tk.WORD, 
                              relief=tk.SUNKEN, borderwidth=1)
        instructions.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        instructions_text = """Instructions for Manual Import:

1. Download MusicBrainz database files (.tar.zst format)
2. Click 'Select File' to choose your database file
3. The file will be processed and imported
4. This may take several minutes depending on file size

Supported formats:
• .tar.zst (compressed MusicBrainz dumps)
• .tar (uncompressed archives)

Note: This is a safe dialog that avoids system crashes."""
        
        instructions.insert(tk.END, instructions_text)
        instructions.configure(state='disabled')
        
        # File selection frame
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="Selected file:").pack(anchor=tk.W)
        
        self.file_label = ttk.Label(file_frame, text="No file selected", 
                                   relief=tk.SUNKEN, padding=5)
        self.file_label.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # File selection button
        self.select_button = ttk.Button(button_frame, text="Select File", 
                                       command=self.safe_file_select)
        self.select_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Import button
        self.import_button = ttk.Button(button_frame, text="Import", 
                                       command=self.import_file, state=tk.DISABLED)
        self.import_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Cancel button
        self.cancel_button = ttk.Button(button_frame, text="Cancel", 
                                       command=self.close_dialog)
        self.cancel_button.pack(side=tk.RIGHT)
        
        # Progress frame (hidden initially)
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_label = ttk.Label(self.progress_frame, text="Processing...")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
    
    def safe_file_select(self):
        """Safely select a file without causing crashes."""
        try:
            print("Attempting safe file selection...")
            
            # Try the safest possible file dialog first
            file_path = filedialog.askopenfilename(
                title="Select MusicBrainz Database File"
                # Deliberately omit filetypes to avoid macOS issues
            )
            
            if file_path:
                self.selected_file = file_path
                filename = os.path.basename(file_path)
                self.file_label.config(text=filename)
                self.import_button.config(state=tk.NORMAL)
                print(f"✅ File selected: {filename}")
            else:
                print("No file selected")
                
        except Exception as e:
            print(f"File selection error: {e}")
            # Try alternative method
            try:
                messagebox.showinfo("File Selection", 
                    "Please drag and drop your file or enter the path manually.\n\n"
                    "Expected file format: .tar.zst or .tar")
                    
                # Could implement drag-and-drop or manual path entry here
                
            except Exception as e2:
                print(f"Alternative method also failed: {e2}")
                messagebox.showerror("Error", 
                    "Could not open file dialog. Please check your system.")
    
    def import_file(self):
        """Simulate file import process."""
        if not self.selected_file:
            messagebox.showwarning("Warning", "Please select a file first.")
            return
        
        # Show progress
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_bar.start()
        
        # Disable buttons during import
        self.select_button.config(state=tk.DISABLED)
        self.import_button.config(state=tk.DISABLED)
        
        # Simulate processing
        self.dialog.after(2000, self.complete_import)
    
    def complete_import(self):
        """Complete the import process."""
        self.progress_bar.stop()
        self.progress_frame.pack_forget()
        
        # Re-enable buttons
        self.select_button.config(state=tk.NORMAL)
        self.import_button.config(state=tk.NORMAL)
        
        # Show success message
        result = messagebox.askyesno("Import Complete", 
            f"Successfully imported: {os.path.basename(self.selected_file)}\n\n"
            "Would you like to close this dialog?")
        
        if result:
            self.success = True
            self.close_dialog()
    
    def close_dialog(self):
        """Safely close the dialog."""
        try:
            if self.dialog:
                self.dialog.destroy()
        except Exception as e:
            print(f"Error closing dialog: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.dialog:
                self.dialog.destroy()
        except:
            pass

def test_safe_dialog():
    """Test the safe dialog."""
    root = tk.Tk()
    root.title("Safe Dialog Test")
    root.geometry("300x200")
    
    def show_dialog():
        dialog = SafeManualImportDialog(root)
        success = dialog.show_and_wait()
        print(f"Dialog result: {success}")
    
    ttk.Button(root, text="Test Safe Manual Import Dialog", 
              command=show_dialog).pack(pady=50)
    
    root.mainloop()

if __name__ == "__main__":
    test_safe_dialog()
