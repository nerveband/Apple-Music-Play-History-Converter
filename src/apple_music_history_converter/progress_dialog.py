import tkinter as tk
from tkinter import ttk
import threading
import sv_ttk
import darkdetect


class ProgressDialog:
    """Progress dialog for long-running operations like database downloads."""
    
    def __init__(self, parent, title="Progress", message="Processing..."):
        self.parent = parent
        self.cancelled = False
        self.completed = False
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.resizable(False, False)
        
        # Apply theme to dialog
        try:
            is_dark = darkdetect.isDark()
            if is_dark:
                sv_ttk.set_theme("dark")
            else:
                sv_ttk.set_theme("light")
        except Exception:
            sv_ttk.set_theme("light")
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
        self.dialog.geometry(f"400x150+{x}+{y}")
        
        self._create_widgets(message)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
    
    def _create_widgets(self, message):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Message label
        self.message_label = ttk.Label(main_frame, text=message, font=("Arial", 10))
        self.message_label.pack(pady=(0, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            variable=self.progress_var, 
            maximum=100, 
            length=350
        )
        self.progress_bar.pack(pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Initializing...", font=("Arial", 9))
        self.status_label.pack(pady=(0, 10))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        self.cancel_button = ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.cancel
        )
        self.cancel_button.pack(side=tk.RIGHT)
    
    def update_progress(self, percentage, status_message):
        """Update progress bar and status message."""
        if self.dialog.winfo_exists():
            self.progress_var.set(percentage)
            self.status_label.config(text=status_message)
            
            if percentage >= 100:
                self.completed = True
                self.cancel_button.config(text="Close")
            
            self.dialog.update_idletasks()
    
    def cancel(self):
        """Cancel the operation."""
        if not self.completed:
            self.cancelled = True
        self.dialog.destroy()
    
    def is_cancelled(self):
        """Check if operation was cancelled."""
        return self.cancelled
    
    def is_completed(self):
        """Check if operation completed."""
        return self.completed
    
    def show(self):
        """Show the dialog."""
        self.dialog.focus_set()
        return self.dialog


class DatabaseDownloadDialog(ProgressDialog):
    """Specialized progress dialog for database downloads."""
    
    def __init__(self, parent, search_service):
        self.search_service = search_service
        self.download_thread = None
        
        super().__init__(
            parent, 
            title="Download MusicBrainz Database", 
            message="Downloading MusicBrainz database (~200MB)..."
        )
        
        # Start download in background thread
        self.start_download()
    
    def start_download(self):
        """Start the download process in a background thread."""
        self.download_thread = threading.Thread(target=self._download_worker)
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def _download_worker(self):
        """Worker method for downloading database."""
        try:
            success = self.search_service.download_database(self.update_progress)
            
            if success and not self.cancelled:
                self.dialog.after(0, lambda: self.update_progress(100, "Download completed successfully!"))
            elif self.cancelled:
                self.dialog.after(0, lambda: self.update_progress(0, "Download cancelled"))
            else:
                self.dialog.after(0, lambda: self.update_progress(0, "Download failed"))
                
        except Exception as e:
            self.dialog.after(0, lambda: self.update_progress(0, f"Error: {str(e)}"))
    
    def cancel(self):
        """Cancel the download operation."""
        if not self.completed:
            self.search_service.cancel_download()
        super().cancel()


class FirstTimeSetupDialog:
    """Dialog shown to first-time users for database setup."""
    
    def __init__(self, parent):
        self.parent = parent
        self.choice = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Music Database Setup")
        self.dialog.geometry("450x200")
        self.dialog.resizable(False, False)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 225
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 100
        self.dialog.geometry(f"450x200+{x}+{y}")
        
        self._create_widgets()
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self.use_itunes)
    
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Warning icon and title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame, 
            text="⚠️  Music Database Required", 
            font=("Arial", 14, "bold")
        )
        title_label.pack()
        
        # Description
        desc_label = ttk.Label(
            main_frame,
            text="To search music metadata, please download the MusicBrainz database\n(~200MB) or use the iTunes API as an alternative.",
            font=("Arial", 10),
            justify=tk.CENTER
        )
        desc_label.pack(pady=(0, 20))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Download button
        download_button = ttk.Button(
            button_frame,
            text="Download Now",
            command=self.download_database
        )
        download_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # iTunes API button
        itunes_button = ttk.Button(
            button_frame,
            text="Use iTunes API",
            command=self.use_itunes
        )
        itunes_button.pack(side=tk.LEFT)
    
    def download_database(self):
        """User chose to download database."""
        self.choice = "download"
        self.dialog.destroy()
    
    def use_itunes(self):
        """User chose to use iTunes API."""
        self.choice = "itunes"
        self.dialog.destroy()
    
    def show_and_wait(self):
        """Show dialog and wait for user choice."""
        self.dialog.wait_window()
        return self.choice
