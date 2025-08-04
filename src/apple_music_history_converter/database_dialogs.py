#!/usr/bin/env python3
"""
Database management dialogs for MusicBrainz integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os
import sv_ttk
import darkdetect


class FirstTimeSetupDialog:
    """Dialog shown when MusicBrainz database is not available."""
    
    def __init__(self, parent):
        self.parent = parent
        self.choice = None
        self.dialog = None
    
    def show_and_wait(self):
        """Show dialog and wait for user choice."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("MusicBrainz Setup")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
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
        self.dialog.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 50,
            self.parent.winfo_rooty() + 50
        ))
        
        self.create_widgets()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        return self.choice
    
    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🎵 Music Search Setup", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Description
        desc_text = """To find missing artist information, choose how you'd like to search for music data:

🗄️ MusicBrainz Database (Recommended)
• Fast offline searches (1-5ms per track)
• Comprehensive music database
• One-time 2GB download
• Best for large music libraries
• Requires: 8GB RAM recommended (6GB minimum)

🌐 iTunes API
• No download required
• Online searches only
• Rate limited (slower for large files)
• Good for quick conversions
• Works on any system

📁 Manual Import
• Use if automatic download fails
• Import your own MusicBrainz database file"""
        
        desc_label = ttk.Label(main_frame, text=desc_text, justify=tk.LEFT, font=("Arial", 11))
        desc_label.pack(pady=(0, 25))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Download button
        download_btn = ttk.Button(button_frame, text="📥 Download MusicBrainz (~2GB)", 
                                 command=self.choose_download)
        download_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # iTunes button
        itunes_btn = ttk.Button(button_frame, text="🌐 Use iTunes API", 
                               command=self.choose_itunes)
        itunes_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Manual import button
        manual_btn = ttk.Button(button_frame, text="📁 Manual Import", 
                               command=self.choose_manual)
        manual_btn.pack(side=tk.LEFT)
    
    def choose_download(self):
        """User chose to download database."""
        self.choice = "download"
        self.dialog.destroy()
    
    def choose_itunes(self):
        """User chose iTunes API."""
        self.choice = "itunes"
        self.dialog.destroy()
    
    def choose_manual(self):
        """User chose manual import."""
        self.choice = "manual"
        self.dialog.destroy()
    
    def cancel(self):
        """User cancelled."""
        self.choice = "cancel"
        self.dialog.destroy()


class DatabaseDownloadDialog:
    """Dialog for downloading MusicBrainz database with progress."""
    
    def __init__(self, parent, music_search_service, on_complete_callback=None):
        self.parent = parent
        self.music_search_service = music_search_service
        self.on_complete_callback = on_complete_callback
        self.dialog = None
        self.cancelled = False
        self.download_thread = None
        self.start_time = None
        self.download_url = None
        self.last_downloaded = 0
        self.last_time = None
        self.last_speed_update = None
        self.speed_samples = []
        self.speed_update_interval = 1.5  # Update speed every 1.5 seconds
        
    def show(self):
        """Show the download dialog."""
        try:
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title("Downloading MusicBrainz Database")
            self.dialog.geometry("600x400")
            self.dialog.resizable(False, False)
            self.dialog.transient(self.parent)
            
            # Apply theme to dialog
            try:
                is_dark = darkdetect.isDark()
                if is_dark:
                    sv_ttk.set_theme("dark")
                else:
                    sv_ttk.set_theme("light")
            except Exception:
                sv_ttk.set_theme("light")
            
            # Center the dialog safely
            try:
                self.dialog.geometry("+%d+%d" % (
                    self.parent.winfo_rootx() + 50,
                    self.parent.winfo_rooty() + 50
                ))
            except:
                # If centering fails, use default position
                pass
            
            # Handle window close
            self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
            
            self.create_widgets()
            
            # Set grab after widgets are created
            try:
                self.dialog.grab_set()
            except:
                # If grab_set fails on some systems, continue without it
                pass
            
            self.start_download()
            
        except Exception as e:
            print(f"Error creating database download dialog: {e}")
            if self.dialog:
                try:
                    self.dialog.destroy()
                except:
                    pass
    
    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Downloading MusicBrainz Database", 
                               font=("Arial", 12, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Warning about file size and system requirements
        warning_label = ttk.Label(main_frame, 
                                 text="⚠️ This will download approximately 2GB of data",
                                 foreground="orange")
        warning_label.pack(pady=(0, 5))
        
        # System requirements warning
        req_label = ttk.Label(main_frame, 
                             text="💾 System Requirements: 8GB RAM recommended (6GB minimum)",
                             foreground="red", font=("Arial", 10, "bold"))
        req_label.pack(pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Preparing download...")
        self.status_label.pack(pady=(0, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.pack(pady=(0, 10))
        
        # Progress text
        self.progress_label = ttk.Label(main_frame, text="0%")
        self.progress_label.pack(pady=(0, 10))
        
        # Download details frame
        details_frame = ttk.LabelFrame(main_frame, text="Download Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 15))
        
        # URL display
        url_frame = ttk.Frame(details_frame)
        url_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(url_frame, text="Source URL:", font=("Arial", 9, "bold")).pack(anchor="w")
        
        # Theme-aware URL text widget colors
        try:
            is_dark = darkdetect.isDark()
            if is_dark:
                url_bg = "#3c3c3c"
                url_fg = "#ffffff"
            else:
                url_bg = "#f0f0f0"
                url_fg = "#000000"
        except Exception:
            url_bg = "#f0f0f0"
            url_fg = "#000000"
        
        self.url_text = tk.Text(url_frame, height=2, width=50, wrap=tk.WORD, 
                               font=("Courier", 8), state=tk.DISABLED, 
                               background=url_bg, foreground=url_fg, cursor="arrow")
        self.url_text.pack(fill=tk.X, pady=(2, 0))
        
        # URL copy button
        url_button_frame = ttk.Frame(details_frame)
        url_button_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.copy_url_button = ttk.Button(url_button_frame, text="Copy URL", 
                                         command=self.copy_url, state="disabled")
        self.copy_url_button.pack(side=tk.LEFT)
        
        self.open_url_button = ttk.Button(url_button_frame, text="Open in Browser", 
                                         command=self.open_url, state="disabled")
        self.open_url_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Statistics
        stats_frame = ttk.Frame(details_frame)
        stats_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.elapsed_label = ttk.Label(stats_frame, text="Elapsed: 0s", 
                                      font=("Arial", 9))
        self.elapsed_label.pack(side=tk.LEFT)
        
        self.speed_label = ttk.Label(stats_frame, text="Speed: 0 MB/s", 
                                    font=("Arial", 9))
        self.speed_label.pack(side=tk.RIGHT)
        
        # Cancel button
        self.cancel_button = ttk.Button(main_frame, text="Cancel", command=self.cancel)
        self.cancel_button.pack()
    
    def start_download(self):
        """Start the download in a separate thread."""
        self.start_time = time.time()
        self.last_time = self.start_time
        self.download_thread = threading.Thread(target=self.download_worker, daemon=True)
        self.download_thread.start()
    
    def copy_url(self):
        """Copy the download URL to clipboard."""
        if self.download_url:
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(self.download_url)
            self.copy_url_button.config(text="Copied!", state="disabled")
            self.dialog.after(2000, lambda: self.copy_url_button.config(text="Copy URL", state="normal"))
    
    def open_url(self):
        """Open the download URL in browser."""
        if self.download_url:
            import webbrowser
            webbrowser.open(self.download_url)
    
    def download_worker(self):
        """Worker thread for downloading."""
        try:
            # Create progress callback
            def progress_callback(message, progress, extra_data=None):
                if not self.cancelled:
                    self.parent.after(0, self.update_status, message, progress, extra_data)
            
            # Perform actual download
            success = self.music_search_service.download_database(progress_callback)
            
            if success and not self.cancelled:
                self.parent.after(0, self.download_complete)
            elif not self.cancelled:
                self.parent.after(0, self.download_error, "Download failed")
                
        except Exception as e:
            if not self.cancelled:
                self.parent.after(0, self.download_error, str(e))
    
    def update_status(self, message, progress, extra_data=None):
        """Update status message and progress with improved display."""
        def update():
            if not self.cancelled and self.dialog.winfo_exists():
                self.status_label.config(text=message)
                
                # Handle URL from extra_data
                if extra_data and "url" in extra_data:
                    self.download_url = extra_data["url"]
                    self.url_text.config(state=tk.NORMAL)
                    self.url_text.delete(1.0, tk.END)
                    self.url_text.insert(1.0, self.download_url)
                    self.url_text.config(state=tk.DISABLED)
                    self.copy_url_button.config(state="normal")
                    self.open_url_button.config(state="normal")
                
                # Ensure progress is a number
                try:
                    progress_num = float(progress) if progress is not None else 0
                except (ValueError, TypeError):
                    progress_num = 0
                
                self.progress_var.set(progress_num)
                
                # Calculate elapsed time and speed
                current_time = time.time()
                if self.start_time:
                    elapsed = current_time - self.start_time
                    elapsed_text = f"Elapsed: {int(elapsed//60):02d}:{int(elapsed%60):02d}"
                    self.elapsed_label.config(text=elapsed_text)
                    
                    # Calculate download speed (rate limited)
                    if "MB downloaded" in message:
                        try:
                            import re
                            mb_match = re.search(r'(\d+(?:\.\d+)?)\s*MB', message)
                            if mb_match:
                                current_mb = float(mb_match.group(1))
                                
                                # Initialize timing if this is the first measurement
                                if self.last_speed_update is None:
                                    self.last_speed_update = current_time
                                    self.last_downloaded = current_mb
                                    self.speed_label.config(text="Speed: Calculating...")
                                    return
                                
                                # Only update speed display every few seconds
                                time_since_last_update = current_time - self.last_speed_update
                                if time_since_last_update >= self.speed_update_interval:
                                    mb_diff = current_mb - self.last_downloaded
                                    current_speed = mb_diff / time_since_last_update
                                    
                                    # Keep a rolling average of the last 3 speed samples
                                    self.speed_samples.append(current_speed)
                                    if len(self.speed_samples) > 3:
                                        self.speed_samples.pop(0)
                                    
                                    # Calculate average speed
                                    avg_speed = sum(self.speed_samples) / len(self.speed_samples)
                                    
                                    # Update display with smooth speed
                                    if avg_speed > 0:
                                        self.speed_label.config(text=f"Speed: {avg_speed:.1f} MB/s")
                                    
                                    # Update for next calculation
                                    self.last_speed_update = current_time
                                    self.last_downloaded = current_mb
                        except Exception as e:
                            # Don't let speed calculation errors break the download
                            pass
                    elif "Extracting" in message or "Decompressing" in message:
                        # Clear speed display when moving to extraction phase
                        self.speed_label.config(text="Speed: N/A")
                
                # Enhanced progress label with percentage and estimated completion
                if progress_num > 0:
                    # Show progress percentage without duplication
                    progress_text = f"{progress_num:.1f}%"
                    
                    # Add MB information if available in message
                    if "MB" in message:
                        # Extract MB info from message for cleaner display
                        try:
                            import re
                            mb_match = re.search(r'(\d+(?:\.\d+)?)\s*MB', message)
                            if mb_match:
                                mb_downloaded = float(mb_match.group(1))
                                # Estimate total size based on progress (assume ~2GB total)
                                total_mb = mb_downloaded / (progress_num / 100) if progress_num > 0 else 2048
                                progress_text = f"{progress_num:.1f}% • {mb_downloaded:.0f} MB / {total_mb:.0f} MB"
                        except:
                            progress_text = f"{progress_num:.1f}%"
                    
                    self.progress_label.config(text=progress_text)
                else:
                    self.progress_label.config(text="Starting...")
        
        self.parent.after(0, update)
    
    def update_progress(self, progress):
        """Update progress bar."""
        if not self.cancelled and self.dialog.winfo_exists():
            self.progress_var.set(progress)
            self.progress_label.config(text=f"{progress:.1f}%")
    
    def download_complete(self):
        """Handle successful download completion."""
        if not self.cancelled and self.dialog.winfo_exists():
            messagebox.showinfo("Download Complete", 
                               "MusicBrainz database downloaded successfully!")
            self.dialog.destroy()
            
            # Call the completion callback to refresh the main application
            if self.on_complete_callback:
                try:
                    self.on_complete_callback()
                except Exception as e:
                    print(f"Error calling download completion callback: {e}")
    
    def download_error(self, error_message):
        """Handle download error."""
        if not self.cancelled and self.dialog.winfo_exists():
            messagebox.showerror("Download Error", 
                                f"Failed to download database:\n{error_message}")
            self.dialog.destroy()
    
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True
        if self.music_search_service:
            self.music_search_service.cancel_download()
        
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.destroy()
    
    def is_cancelled(self):
        """Check if download was cancelled."""
        return self.cancelled


class ManualImportDialog:
    """Dialog for manual database import with instructions."""
    
    def __init__(self, parent, music_search_service):
        self.parent = parent
        self.music_search_service = music_search_service
        self.dialog = None
        self.success = False
    
    def show_and_wait(self):
        """Show dialog and wait for user action."""
        try:
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title("Manual Database Import")
            self.dialog.geometry("600x450")
            self.dialog.resizable(False, False)
            self.dialog.transient(self.parent)
            
            # Apply theme to dialog
            try:
                is_dark = darkdetect.isDark()
                if is_dark:
                    sv_ttk.set_theme("dark")
                else:
                    sv_ttk.set_theme("light")
            except Exception:
                sv_ttk.set_theme("light")
            
            # Center the dialog safely
            try:
                self.dialog.geometry("+%d+%d" % (
                    self.parent.winfo_rootx() + 50,
                    self.parent.winfo_rooty() + 50
                ))
            except:
                # If centering fails, use default position
                pass
            
            self.create_widgets()
            
            # Set grab after widgets are created
            try:
                self.dialog.grab_set()
            except:
                # If grab_set fails on some systems, continue without it
                pass
            
            # Wait for dialog to close
            self.parent.wait_window(self.dialog)
            return self.success
            
        except Exception as e:
            print(f"Error creating manual import dialog: {e}")
            if self.dialog:
                try:
                    self.dialog.destroy()
                except:
                    pass
            return False
    
    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Manual Database Import", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Instructions
        instructions = """To manually download and import the MusicBrainz database:

1. Visit: https://musicbrainz.org/doc/MusicBrainz_Database/Download
   
2. Look for the latest "mb_artist_credit_name" dump file
   (It will be named like: mb_artist_credit_name-20241124-235959.tar.zst)
   
3. Download this file (approximately 2GB)

4. Once downloaded, click "Import File" below to select the downloaded file

Note: The file must be a .tar.zst file containing the MusicBrainz artist data.
The import process will extract and build the database, which may take
several minutes depending on your computer's speed."""
        
        inst_label = ttk.Label(main_frame, text=instructions, justify=tk.LEFT)
        inst_label.pack(pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.status_label = ttk.Label(status_frame, text="No file selected")
        self.status_label.pack()
        
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        import_btn = ttk.Button(button_frame, text="Import File", 
                               command=self.import_file)
        import_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        close_btn = ttk.Button(button_frame, text="Close", 
                              command=self.close)
        close_btn.pack(side=tk.LEFT)
    
    def import_file(self):
        """Handle file import."""
        try:
            # Use basic file dialog without filetypes to avoid macOS crash
            file_path = filedialog.askopenfilename(
                parent=self.dialog,
                title="Select MusicBrainz Database File (.tar.zst or .tar)"
            )
        except Exception as e:
            print(f"File dialog error: {e}")
            messagebox.showerror("Error", "Could not open file dialog. Please check your system configuration.")
            return
        
        if not file_path:
            return
        
        # Validate file type after selection
        if not (file_path.lower().endswith('.tar.zst') or file_path.lower().endswith('.tar')):
            result = messagebox.askyesno(
                "File Type Warning", 
                f"Selected file '{os.path.basename(file_path)}' does not appear to be a MusicBrainz database file (.tar.zst or .tar).\n\n"
                "Do you want to proceed anyway?"
            )
            if not result:
                return
        
        self.status_label.config(text=f"Selected: {file_path.split('/')[-1]}")
        self.progress_bar.start()
        
        # Start import in thread
        threading.Thread(target=self.import_worker, args=(file_path,), daemon=True).start()
    
    def import_worker(self, file_path):
        """Worker thread for importing."""
        try:
            from pathlib import Path
            
            # Create a progress callback
            def progress_callback(progress, message):
                self.dialog.after(0, self.update_status, message, progress)
            
            # Use the music search service to import the file
            success = self.music_search_service.import_database_file(file_path, progress_callback)
            
            if success:
                self.dialog.after(0, self.import_complete)
            else:
                self.dialog.after(0, self.import_error, "Import failed. Please check the file and try again.")
                
        except Exception as e:
            self.dialog.after(0, self.import_error, str(e))
    
    def update_status(self, message, progress):
        """Update status message."""
        self.status_label.config(text=message)
        if progress > 0:
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate', value=progress)
    
    def import_complete(self):
        """Handle successful import."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', value=100)
        self.status_label.config(text="Import completed successfully!")
        self.success = True
        messagebox.showinfo("Success", "MusicBrainz database imported successfully!")
        self.dialog.destroy()
    
    def import_error(self, error_message):
        """Handle import error."""
        self.progress_bar.stop()
        self.status_label.config(text="Import failed")
        messagebox.showerror("Import Error", error_message)
    
    def close(self):
        """Close dialog."""
        self.dialog.destroy()
