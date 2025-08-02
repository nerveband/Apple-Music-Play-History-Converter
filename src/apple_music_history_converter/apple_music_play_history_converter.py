import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import requests
import time
import threading
from collections import deque
import json
import os
import sys
import csv
import io
import platform
from pathlib import Path
import sv_ttk
from threading import Lock
from music_search_service import MusicSearchService
from database_dialogs import FirstTimeSetupDialog, DatabaseDownloadDialog, ManualImportDialog
import re

class ToolTip:
    """Simple tooltip widget for tkinter."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, background="#ffffe0", 
                        relief="solid", borderwidth=1, font=("Arial", 9))
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class CSVProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Music Play History Converter")
        self.root.minsize(width=1200, height=850)  # Increased minimum to ensure visibility
        
        # Set initial window size that guarantees Results and Preview are visible
        self.root.geometry("1300x900")
        
        # Configure root grid for proper resizing
        self.root.grid_columnconfigure(0, weight=3)  # Main content area (wider)
        self.root.grid_columnconfigure(1, weight=1)  # Settings panel
        self.root.grid_rowconfigure(0, weight=0)     # Header (fixed)
        self.root.grid_rowconfigure(1, weight=0)     # File selection (fixed)
        self.root.grid_rowconfigure(2, weight=3)     # Results row (expandable, higher weight)
        self.root.grid_rowconfigure(3, weight=0)     # Progress row (fixed, smaller)
        
        # Initialize MusicBrainz search service BEFORE creating widgets
        self.music_search_service = MusicSearchService()
        
        self.create_widgets()
        self.pause_itunes_search = False
        self.stop_itunes_search = False  # New flag for stopping search
        self.processing_thread = None
        self.file_size = 0
        self.row_count = 0
        
        # Rate limiting setup
        self.api_calls = deque(maxlen=20)  # Track last 20 API calls
        self.api_lock = Lock()  # Thread-safe lock for API calls
        self.rate_limit_timer = None
        self.api_wait_start = None
        self.wait_duration = 0  # Reset wait duration
        self.skip_wait_requested = False  # Flag to skip current wait
        self.failed_requests = []  # Track failed iTunes requests for retry reporting
        self.processing_start_time = None  # Track total processing time
        
        # Processing counters
        self.musicbrainz_count = 0
        self.itunes_count = 0
        self.rate_limit_hits = 0
        self.last_rate_limit_time = None
        
        # New processing counters for two-phase approach
        self.musicbrainz_found = 0
        self.itunes_found = 0
        self.estimated_missing_artists = 0
        
    def create_widgets(self):
        # Colors
        bg_color = '#ececed'
        primary_color = '#FF3B30'
        secondary_color = '#007AFF'
        text_color = '#000000'
        button_bg_color = '#51607a'
        button_text_color = '#000000'  # Changed to black

        # Styles
        style = ttk.Style()
        style.configure('TLabel', background=bg_color, foreground=text_color)
        style.configure('TButton', background=button_bg_color, foreground=button_text_color)
        
        # Configure red button style
        style.configure('Red.TButton', 
                       background='#c53021', 
                       foreground=button_text_color)  # Changed to black
        style.map('Red.TButton',
                 foreground=[('disabled', '#666666'),
                           ('pressed', button_text_color),
                           ('active', button_text_color)],
                 background=[('active', '#d64937'),
                           ('disabled', '#a52819')])

        style.configure('TRadiobutton', background=bg_color, foreground=text_color)
        style.configure('TCheckbutton', background=bg_color, foreground=text_color)
        style.configure('TFrame', background=bg_color)

        self.root.configure(bg=bg_color)
        
        # Compact header section
        header_frame = ttk.Frame(self.root)
        header_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=20, pady=(15, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        
        self.title_label = ttk.Label(header_frame, text="Apple Music Play History Converter", font=("Arial", 16, "bold"))
        self.title_label.grid(row=0, column=0, sticky='w')

        # Instructions button on the same row as title
        self.instructions_button = ttk.Button(header_frame, text="How to Use", command=self.show_instructions, style='TButton')
        self.instructions_button.grid(row=0, column=1, padx=(10, 0))
        
        self.subtitle_label = ttk.Label(header_frame, text="Convert Apple Music CSV files to Last.fm format", font=("Arial", 10))
        self.subtitle_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(2, 0))

        # Main content area - File selection and processing
        self.main_frame = ttk.LabelFrame(self.root, text="1. Select Your Apple Music CSV File", padding=(15, 10))
        self.main_frame.grid(row=1, column=0, padx=(20, 10), pady=(5, 5), sticky='ew')
        self.main_frame.grid_columnconfigure(0, weight=1)

        # File selection row
        file_select_frame = ttk.Frame(self.main_frame)
        file_select_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        file_select_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ttk.Entry(file_select_frame, font=("Arial", 11))
        self.file_entry.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self.file_entry.insert(0, "No file selected")
        self.file_entry.config(state='readonly')

        self.browse_button = ttk.Button(file_select_frame, text="Choose CSV File", command=self.browse_file, style='TButton')
        self.browse_button.grid(row=0, column=1)

        # File type section
        type_frame = ttk.LabelFrame(self.main_frame, text="2. File Type (auto-detected)", padding=(10, 8))
        type_frame.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        
        self.file_type_var = tk.StringVar()
        self.file_type_var.trace_add("write", lambda *args: self.update_time_estimate())
        
        self.play_history_radio = ttk.Radiobutton(type_frame, text="Play History Daily Tracks", variable=self.file_type_var, value="play-history")
        self.play_history_radio.grid(row=0, column=0, sticky='w', pady=1)

        self.recently_played_radio = ttk.Radiobutton(type_frame, text="Recently Played Tracks", variable=self.file_type_var, value="recently-played")
        self.recently_played_radio.grid(row=1, column=0, sticky='w', pady=1)

        self.play_activity_radio = ttk.Radiobutton(type_frame, text="Play Activity", variable=self.file_type_var, value="play-activity")
        self.play_activity_radio.grid(row=2, column=0, sticky='w', pady=1)

        self.converted_radio = ttk.Radiobutton(type_frame, text="Other/Generic CSV", variable=self.file_type_var, value="generic")
        self.converted_radio.grid(row=3, column=0, sticky='w', pady=1)

        # Convert button
        convert_frame = ttk.Frame(self.main_frame)
        convert_frame.grid(row=2, column=0, pady=(5, 0))
        
        self.convert_button = ttk.Button(convert_frame, text="🎵 Convert to Last.fm Format", command=self.convert_csv, style='TButton')
        self.convert_button.grid(row=0, column=0)
        
        # Add tooltip for convert button
        ToolTip(self.convert_button, 
               "Converts your Apple Music CSV to Last.fm format.\n"
               "• First processes everything through MusicBrainz (if available)\n"
               "• Then uses iTunes API for missing artists (if enabled)\n"
               "• You can pause, resume, or save results at any time")
        
        # Settings panel on the right
        self.settings_frame = ttk.LabelFrame(self.root, text="Settings", padding=(10, 8))
        self.settings_frame.grid(row=1, column=1, padx=(10, 20), pady=(5, 5), sticky='nsew')
        self.settings_frame.grid_columnconfigure(0, weight=1)

        # Search provider selection
        provider_section = ttk.LabelFrame(self.settings_frame, text="Music Search Provider", padding=(8, 6))
        provider_section.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        
        self.search_provider_var = tk.StringVar(value=self.music_search_service.get_search_provider())
        
        musicbrainz_radio = ttk.Radiobutton(provider_section, text="MusicBrainz (offline, fast)", 
                                           variable=self.search_provider_var, value="musicbrainz",
                                           command=self.on_search_provider_change)
        musicbrainz_radio.grid(row=0, column=0, sticky='w', pady=(0, 2))
        
        itunes_radio = ttk.Radiobutton(provider_section, text="iTunes API (online, rate-limited)", 
                                      variable=self.search_provider_var, value="itunes",
                                      command=self.on_search_provider_change)
        itunes_radio.grid(row=1, column=0, sticky='w')
        
        # Add tooltips for search providers
        ToolTip(musicbrainz_radio, 
               "Offline music database with 40M+ recordings.\n"
               "• Ultra-fast searches (1-5ms per track)\n"
               "• Requires 8GB RAM and 3GB storage\n"
               "• Processes entire file first, then iTunes handles missing artists\n"
               "• Best for large files and repeated use")
        
        ToolTip(itunes_radio, 
               "Apple's online music search API ONLY.\n"
               "• No download required, works on any system\n"
               "• Slower searches (100-500ms per track)\n"
               "• Rate limited to ~20 requests per minute\n"
               "• Hides MusicBrainz options when selected")

        # MusicBrainz Database Status
        self.mb_section = ttk.LabelFrame(self.settings_frame, text="MusicBrainz Database", padding=(8, 6))
        self.mb_section.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        self.mb_section.grid_columnconfigure(0, weight=1)
        
        status_frame = ttk.Frame(self.mb_section)
        status_frame.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        status_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky='w')
        self.db_status_label = ttk.Label(status_frame, text="Not Downloaded", font=("Arial", 10, "bold"))
        self.db_status_label.grid(row=0, column=1, sticky='w', padx=(10, 0))
        
        self.download_button = ttk.Button(self.mb_section, text="Download Database (~2GB)", command=self.download_database)
        self.download_button.grid(row=1, column=0, sticky='ew', pady=(0, 3))
        
        # Add tooltip for download button
        ToolTip(self.download_button, 
               "Downloads the latest MusicBrainz database.\n"
               "• File size: ~2GB compressed\n"
               "• Requires: 8GB RAM to operate\n"
               "• One-time download for offline use")
        
        # Database management buttons
        self.check_updates_button = ttk.Button(self.mb_section, text="Check Updates", command=self.check_for_updates)
        self.check_updates_button.grid(row=2, column=0, sticky='ew', pady=(0, 3))
        
        self.manual_import_button = ttk.Button(self.mb_section, text="Manual Import", command=self.manual_import_database)
        self.manual_import_button.grid(row=3, column=0, sticky='ew', pady=(0, 3))
        
        # Additional management buttons in collapsed form
        manage_frame = ttk.Frame(self.mb_section)
        manage_frame.grid(row=4, column=0, sticky='ew')
        manage_frame.grid_columnconfigure(0, weight=1)
        manage_frame.grid_columnconfigure(1, weight=1)
        
        self.delete_db_button = ttk.Button(manage_frame, text="Delete", command=self.delete_database)
        self.delete_db_button.grid(row=0, column=0, sticky='ew', padx=(0, 2))
        
        self.reveal_location_button = ttk.Button(manage_frame, text="Show Files", command=self.reveal_database_location)
        self.reveal_location_button.grid(row=0, column=1, sticky='ew', padx=(2, 0))
        
        # Database info
        info_frame = ttk.Frame(self.mb_section)
        info_frame.grid(row=5, column=0, sticky='ew', pady=(6, 0))
        
        self.db_size_label = ttk.Label(info_frame, text="Size: 0MB", font=("Arial", 9))
        self.db_size_label.grid(row=0, column=0, sticky='w')
        
        self.db_updated_label = ttk.Label(info_frame, text="Never updated", font=("Arial", 9))
        self.db_updated_label.grid(row=1, column=0, sticky='w')
        
        # Advanced options
        self.advanced_section = ttk.LabelFrame(self.settings_frame, text="Advanced Options", padding=(8, 6))
        self.advanced_section.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        
        # Auto-fallback setting
        self.fallback_var = tk.BooleanVar(value=self.music_search_service.get_auto_fallback())
        self.fallback_checkbox = ttk.Checkbutton(self.advanced_section, 
                                                text="Auto-fallback to iTunes if no results", 
                                                variable=self.fallback_var,
                                                command=self.on_fallback_changed)
        self.fallback_checkbox.grid(row=0, column=0, sticky='w')
        
        # Add tooltip for auto-fallback
        ToolTip(self.fallback_checkbox, 
               "When enabled, if MusicBrainz doesn't find an artist,\n"
               "the app will automatically search iTunes API as backup.\n"
               "This improves results but may slow down processing.")
        
        # Update database status display
        self.update_database_status()
        
        # Initialize UI state based on current search provider
        initial_provider = self.search_provider_var.get()
        self.root.after_idle(lambda: self._update_provider_ui(initial_provider))
        
        # Initialize full_file_path
        self.full_file_path = None

        # iTunes API Frame
        self.itunes_frame = ttk.LabelFrame(self.settings_frame, text="iTunes API Options", padding=(8, 6))
        self.itunes_frame.grid(row=3, column=0, sticky='ew', pady=(0, 8))

        # iTunes API search checkbox with clearer purpose
        self.itunes_api_var = tk.BooleanVar()
        self.itunes_api_checkbox = ttk.Checkbutton(self.itunes_frame, 
                                                  text="🌐 Search iTunes for missing artists (Phase 2)", 
                                                  variable=self.itunes_api_var)
        self.itunes_api_checkbox.grid(row=0, column=0, sticky='w', pady=(0, 6))
        
        # Add comprehensive tooltip for the checkbox
        ToolTip(self.itunes_api_checkbox, 
               "When to enable this:\n"
               "✅ Your CSV has tracks missing artist information\n"
               "✅ You want to find missing artists using iTunes API\n"
               "\n"
               "How it works:\n"
               "• Phase 1: Process ALL tracks with MusicBrainz (fast)\n"
               "• Phase 2: Search iTunes ONLY for tracks still missing artists\n"
               "\n"
               "❌ Leave unchecked if:\n"
               "• Your CSV already has all artist names\n"
               "• You only want MusicBrainz results\n"
               "• You want to avoid iTunes API rate limits")

        # Rate limit control
        rate_frame = ttk.Frame(self.itunes_frame)
        rate_frame.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        rate_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(rate_frame, text="Rate limit:").grid(row=0, column=0, sticky='w')
        
        self.rate_limit_var = tk.StringVar(value="20")
        self.rate_limit_entry = ttk.Entry(rate_frame, textvariable=self.rate_limit_var, width=8)
        self.rate_limit_entry.grid(row=0, column=1, sticky='w', padx=(5, 5))
        
        ttk.Label(rate_frame, text="req/min").grid(row=0, column=2, sticky='w')
        
        # Rate limit warning
        self.rate_limit_warning = ttk.Label(self.itunes_frame, 
                                          text="⚠️ Max 20 req/min recommended", 
                                          foreground='#666666',
                                          font=("Arial", 9))
        self.rate_limit_warning.grid(row=2, column=0, sticky='w')

        # Bind rate limit entry to update estimation
        self.rate_limit_entry.bind('<KeyRelease>', self.update_time_estimate)
        self.itunes_api_checkbox.config(command=self.update_time_estimate)

        # API Status frame
        status_section = ttk.Frame(self.itunes_frame)
        status_section.grid(row=3, column=0, sticky='ew', pady=(3, 0))
        
        self.api_status_label = ttk.Label(status_section, text="Status: Ready", font=("Arial", 9))
        self.api_status_label.grid(row=0, column=0, sticky='w')
        
        self.api_timer_label = ttk.Label(status_section, text="", font=("Arial", 9))
        self.api_timer_label.grid(row=1, column=0, sticky='w')

        # API Control buttons
        control_frame = ttk.Frame(self.itunes_frame)
        control_frame.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)

        self.pause_resume_button = ttk.Button(control_frame, text="Pause", command=self.toggle_pause_resume, state='disabled')
        self.pause_resume_button.grid(row=0, column=0, sticky='ew', padx=(0, 2))

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_itunes_search, style='Red.TButton', state='disabled')
        self.stop_button.grid(row=0, column=1, sticky='ew', padx=(2, 0))
        
        # Add tooltips for control buttons
        ToolTip(self.pause_resume_button, 
               "Pause or resume iTunes API artist searches.\n"
               "MusicBrainz searches cannot be paused (they're too fast).\n"
               "You can always save your current results.")
        
        ToolTip(self.stop_button, 
               "Stop all iTunes API searches completely.\n"
               "You'll be asked if you want to continue without\n"
               "searching for remaining missing artists.")


        # Results and preview in a horizontal layout
        content_frame = ttk.Frame(self.root)
        content_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=(5, 0), sticky='nsew')
        content_frame.grid_columnconfigure(0, weight=1)  # Results area
        content_frame.grid_columnconfigure(1, weight=1)  # Preview area
        content_frame.grid_rowconfigure(0, weight=1, minsize=400)  # Ensure minimum height for visibility
        
        # Results area (left side)
        results_frame = ttk.LabelFrame(content_frame, text="Results", padding=(10, 8))
        results_frame.grid(row=0, column=0, padx=(0, 5), pady=0, sticky='nsew')
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1)
        
        # Action buttons
        action_frame = ttk.Frame(results_frame)
        action_frame.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        action_frame.grid_columnconfigure(2, weight=1)  # Push improve button to right
        
        self.copy_button = ttk.Button(action_frame, text="📋 Copy to Clipboard", command=self.copy_to_clipboard, style='TButton')
        self.copy_button.grid(row=0, column=0, padx=(0, 8))

        self.save_button = ttk.Button(action_frame, text="💾 Save as CSV File", command=self.save_as_csv, style='TButton')
        self.save_button.grid(row=0, column=1, padx=(0, 8))
        
        # Post-processing button (only visible after conversion)
        self.reprocess_button = ttk.Button(action_frame, text="🔍 Search for Missing Artists", 
                                         command=self.reprocess_missing_artists, style='TButton')
        self.reprocess_button.grid(row=0, column=3, sticky='e')
        self.reprocess_button.grid_remove()  # Hide initially
        
        # Add tooltips for action buttons
        ToolTip(self.copy_button, 
               "Copy the converted CSV data to clipboard.\n"
               "You can then paste it into any application.")
        
        ToolTip(self.save_button, 
               "Save the converted data as a CSV file.\n"
               "Compatible with Last.fm and Universal Scrobbler.")
        
        ToolTip(self.reprocess_button, 
               "Search for artists that were missing after conversion.\n"
               "Uses iTunes API to find additional artist information.\n"
               "You can pause, resume, or stop this process anytime.")
        
        # Output text area (ensure minimum visible height)
        self.output_text = scrolledtext.ScrolledText(results_frame, height=15, wrap=tk.NONE, font=('Courier', 9))
        self.output_text.grid(row=1, column=0, sticky='nsew')
        
        # Add placeholder text to show it exists
        placeholder_text = """📄 Converted CSV Results

Your converted Apple Music data will appear here after processing.

The output will be in Last.fm compatible format:
Artist, Track, Album, Timestamp, Album Artist, Duration

Click "Convert to Last.fm Format" to get started!"""
        
        self.output_text.insert(tk.END, placeholder_text)
        self.output_text.config(state='disabled')
        
        # Preview area (right side)
        self.preview_frame = ttk.LabelFrame(content_frame, text="Preview", padding=(10, 8))
        self.preview_frame.grid(row=0, column=1, padx=(5, 0), pady=0, sticky='nsew')
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)

        self.preview_table = ttk.Treeview(self.preview_frame, columns=("Artist", "Track", "Album", "Timestamp"), show='headings', height=15)
        self.preview_table.heading("Artist", text="Artist")
        self.preview_table.heading("Track", text="Track")
        self.preview_table.heading("Album", text="Album")
        self.preview_table.heading("Timestamp", text="Timestamp")
        
        # Configure column widths for compact display
        self.preview_table.column("Artist", width=100)
        self.preview_table.column("Track", width=120)
        self.preview_table.column("Album", width=100)
        self.preview_table.column("Timestamp", width=80)
        
        self.preview_table.grid(row=0, column=0, sticky='nsew')
        
        # Add scrollbar for preview
        preview_scroll = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.preview_table.yview)
        preview_scroll.grid(row=0, column=1, sticky='ns')
        self.preview_table.configure(yscrollcommand=preview_scroll.set)
        
        # Add placeholder data to preview
        placeholder_values = ["Artist Name", "Track Name", "Album Name", "2024-01-01 12:00"]
        self.preview_table.insert("", "end", values=placeholder_values)
        self.preview_table.insert("", "end", values=["Taylor Swift", "Anti-Hero", "Midnights", "2024-03-15 14:30"])
        self.preview_table.insert("", "end", values=["The Beatles", "Here Comes the Sun", "Abbey Road", "2024-03-15 14:27"])
        self.preview_table.insert("", "end", values=["📄 Sample preview data", "Your converted tracks", "will appear here", "after processing"])


        # Progress bar and status (always visible at bottom)
        self.progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=(10, 8))
        self.progress_frame.grid(row=3, column=0, columnspan=2, padx=20, pady=(5, 15), sticky='ew')
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky='ew', pady=(0, 5))

        self.progress_label = ttk.Label(self.progress_frame, text="🎵 Ready to convert your Apple Music files", font=("Arial", 10))
        self.progress_label.grid(row=1, column=0, sticky='w')

        self.message_label = ttk.Label(self.progress_frame, text="", foreground="blue", font=("Arial", 10))
        self.message_label.grid(row=2, column=0, sticky='w', pady=(5, 0))
        
        # Enhanced status bar with comprehensive information
        status_frame = ttk.Frame(self.progress_frame)
        status_frame.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        status_frame.grid_columnconfigure(0, weight=1)
        
        # File information row
        file_info_frame = ttk.Frame(status_frame)
        file_info_frame.grid(row=0, column=0, sticky='ew', pady=(0, 3))
        file_info_frame.grid_columnconfigure(0, weight=1)
        
        self.file_info_label = ttk.Label(file_info_frame, text="📄 No file loaded", 
                                        font=("Arial", 11), foreground="gray")
        self.file_info_label.grid(row=0, column=0, sticky='w')
        
        # Processing status row
        processing_frame = ttk.Frame(status_frame)
        processing_frame.grid(row=1, column=0, sticky='ew', pady=(0, 3))
        processing_frame.grid_columnconfigure(0, weight=1)
        processing_frame.grid_columnconfigure(1, weight=0)
        processing_frame.grid_columnconfigure(2, weight=0)
        processing_frame.grid_columnconfigure(3, weight=0)
        
        self.songs_processed_label = ttk.Label(processing_frame, text="🎵 Songs: 0/0", 
                                              font=("Arial", 11, "bold"), foreground="blue")
        self.songs_processed_label.grid(row=0, column=0, sticky='w')
        
        self.musicbrainz_stats_label = ttk.Label(processing_frame, text="🗄️ MB: 0", 
                                                font=("Arial", 11), foreground="green")
        self.musicbrainz_stats_label.grid(row=0, column=1, sticky='w', padx=(20, 0))
        
        self.itunes_stats_label = ttk.Label(processing_frame, text="🌐 iTunes: 0", 
                                           font=("Arial", 11), foreground="blue")
        self.itunes_stats_label.grid(row=0, column=2, sticky='w', padx=(15, 0))
        
        self.rate_limit_stats_label = ttk.Label(processing_frame, text="⚠️ Limits: 0", 
                                               font=("Arial", 11), foreground="green")
        self.rate_limit_stats_label.grid(row=0, column=3, sticky='w', padx=(15, 0))
        
        self.wait_time_label = ttk.Label(processing_frame, text="", 
                                        font=("Arial", 11), foreground="orange")
        self.wait_time_label.grid(row=0, column=4, sticky='w', padx=(15, 0))
        
        # Skip wait button (initially hidden)
        self.skip_wait_button = ttk.Button(processing_frame, text="Clear Queue", 
                                         command=self.skip_current_wait, 
                                         style='Red.TButton', width=12)
        self.skip_wait_button.grid(row=0, column=5, sticky='w', padx=(10, 0))
        self.skip_wait_button.grid_remove()  # Hide initially
        
        # Add tooltips for enhanced status elements
        ToolTip(self.file_info_label, 
               "Information about the loaded CSV file:\n"
               "• File size and row count\n"
               "• Estimated missing artists to find")
        
        ToolTip(self.songs_processed_label, 
               "Processing progress: Songs completed / Total songs\n"
               "Shows how many tracks have been processed.")
        
        ToolTip(self.musicbrainz_stats_label, 
               "Artists found using MusicBrainz offline database.\n"
               "Ultra-fast searches (1-5ms each).")
        
        ToolTip(self.itunes_stats_label, 
               "Artists found using iTunes API.\n"
               "Slower searches (100-500ms) with rate limiting.")
        
        ToolTip(self.rate_limit_stats_label, 
               "iTunes API rate limit hits.\n"
               "Green: No limits • Orange: 1-4 • Red: 5+")
        
        ToolTip(self.wait_time_label, 
               "iTunes API rate limit wait time.\n"
               "Shows countdown when API is temporarily limited.")
        
        ToolTip(self.skip_wait_button, 
               "Clear entire rate limit queue.\n"
               "Resets rate limiting and continues immediately.\n"
               "Clears all 20 pending API call timestamps.\n"
               "Failed requests will be tracked and reported.")
        
        # Process control buttons in status bar
        control_row_frame = ttk.Frame(status_frame)
        control_row_frame.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        control_row_frame.grid_columnconfigure(0, weight=1)
        
        control_buttons_frame = ttk.Frame(control_row_frame)
        control_buttons_frame.grid(row=0, column=1, sticky='e')
        
        self.process_pause_button = ttk.Button(control_buttons_frame, text="Pause", 
                                              command=self.toggle_process_pause, state='disabled',
                                              width=8)
        self.process_pause_button.grid(row=0, column=0, padx=(0, 5))
        
        self.process_stop_button = ttk.Button(control_buttons_frame, text="Stop", 
                                             command=self.stop_process, state='disabled',
                                             width=8)
        self.process_stop_button.grid(row=0, column=1)
        
        # Add tooltips for process control
        ToolTip(self.process_pause_button, 
               "Pause/resume the entire CSV processing.\n"
               "You can pause at any time and save current results.")
        
        ToolTip(self.process_stop_button, 
               "Stop CSV processing completely.\n"
               "You'll be able to save current results before stopping.")
        
        # Add process control state variables
        self.process_paused = False
        self.process_stopped = False
        
        # Start MusicBrainz optimization automatically if database is available (after all widgets are created)
        self.root.after(100, self.start_background_optimization)
        
    def start_background_optimization(self):
        """Start MusicBrainz optimization in background if database is available."""
        if (self.music_search_service.get_search_provider() == "musicbrainz" and 
            self.music_search_service.musicbrainz_manager.is_database_available()):
            
            # Show optimization status in progress area
            self.progress_label.config(text="🎵 Optimizing MusicBrainz for faster searches...")
            
            def progress_callback(message, percent, start_time):
                elapsed = time.time() - start_time
                timer_text = f" (Elapsed: {elapsed:.0f}s)"
                self.root.after(0, lambda: self.progress_label.config(text=f"🔧 Optimizing: {message}{timer_text}"))
            
            def completion_callback():
                self.root.after(0, lambda: self.progress_label.config(text="🎵 Ready to convert your Apple Music files (MusicBrainz optimized)"))
            
            # Start progressive loading in background
            import threading
            def optimize():
                try:
                    self.music_search_service.start_progressive_loading(progress_callback)
                    completion_callback()
                except Exception as e:
                    print(f"Optimization error: {e}")
                    self.root.after(0, lambda: self.progress_label.config(text="🎵 Ready to convert your Apple Music files"))
            
            threading.Thread(target=optimize, daemon=True).start()

    def show_instructions(self):
        instructions = tk.Toplevel(self.root)
        instructions.title("How to Use Apple Music Converter")
        instructions.geometry("700x500")
        instructions.resizable(True, True)

        # Make the dialog resizable
        instructions.grid_columnconfigure(0, weight=1)
        instructions.grid_rowconfigure(0, weight=1)

        text = scrolledtext.ScrolledText(instructions, wrap=tk.WORD, font=("Arial", 11), padx=20, pady=20)
        text.grid(row=0, column=0, sticky='nsew')

        instructions_text = """🎵 Apple Music Play History Converter

Convert your Apple Music listening history into a format compatible with Last.fm and other scrobbling services.

📋 STEP 1: Get Your Apple Music Data

1. Visit privacy.apple.com and sign in with your Apple ID
2. Click "Request a copy of your data"
3. Select "Apple Media Services" from the list
4. Wait for Apple to prepare your data (usually 1-3 days)
5. Download and extract the ZIP file when ready

📁 STEP 2: Find Your CSV Files

Look for these files in your downloaded data:
• Apple Music - Play History Daily Tracks.csv
• Apple Music - Recently Played Tracks.csv  
• Apple Music Play Activity.csv

🔧 STEP 3: Convert Your Data

1. Click "Choose CSV File" and select one of the files above
2. The file type will be detected automatically
3. Choose your music search provider in the Settings panel:
   • MusicBrainz: Fast, offline database (~2GB download)
   • iTunes API: Online search, rate-limited
4. Click "Convert to Last.fm Format"

💾 STEP 4: Save Your Results

1. Review the converted data in the preview table
2. Click "Save as CSV File" to download your converted data
3. Use "Fix Missing Artists" if some tracks are missing artist info

🌐 STEP 5: Import to Last.fm

• Use Universal Scrobbler (universalscrobbler.com)
• Go to "Scrobble Manually in Bulk" section
• Paste or upload your converted CSV file

ℹ️ About Search Providers

MusicBrainz Database:
• Downloads once (~2GB), works offline
• Fast searches (1-5ms per track)
• Comprehensive music database
• Recommended for large files

iTunes API:
• No download required
• Online searches only
• Rate limited (20 requests/minute recommended)
• Good for smaller files or as backup

🔒 Privacy & Security

Everything happens on your computer. Your music data never leaves this application (except when using iTunes API for artist searches).

Made with ❤️ by Ashraf Ali
Questions? Email: hello@ashrafali.net"""
        
        text.insert(tk.END, instructions_text)
        text.configure(state='disabled')

    def browse_file(self):
        try:
            # Smart initial directory - check for test CSV folder for demos
            initial_dir = None
            test_csv_path = Path(__file__).parent / "tests" / "_test_csvs"
            if test_csv_path.exists():
                initial_dir = str(test_csv_path)
            
            # Use basic file dialog without filetypes to avoid macOS crash
            file_path = filedialog.askopenfilename(
                title="Select Apple Music CSV File",
                initialdir=initial_dir,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        except Exception as e:
            print(f"File dialog error: {e}")
            messagebox.showerror("Error", "Could not open file dialog. Please check your system configuration.")
            return
        
        if file_path:
            # Validate file type after selection
            if not file_path.lower().endswith('.csv'):
                result = messagebox.askyesno(
                    "File Type Warning", 
                    f"Selected file '{os.path.basename(file_path)}' does not appear to be a CSV file.\n\n"
                    "Do you want to proceed anyway?"
                )
                if not result:
                    return
            
            self.file_entry.config(state='normal')
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, os.path.basename(file_path))  # Show just filename
            self.file_entry.config(state='readonly')
            self.full_file_path = file_path  # Store full path separately
            self.auto_select_file_type(file_path)
            self.check_file_size(file_path)
            self.update_time_estimate()

    def check_file_size(self, file_path):
        """Comprehensive file analysis with missing artist estimation."""
        try:
            file_path = Path(file_path)
            self.file_size = file_path.stat().st_size / (1024 * 1024)  # Size in MB
            
            # Count rows and analyze content with proper encoding handling
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            row_count = 0
            missing_artists = 0
            
            for encoding in encodings_to_try:
                try:
                    import csv
                    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                        csv_reader = csv.reader(f)
                        headers = next(csv_reader, [])  # Read header row
                        
                        # Count rows and estimate missing artists
                        for row_num, row in enumerate(csv_reader):
                            row_count += 1
                            
                            # Only sample first 1000 rows for missing artist estimation (performance)
                            if row_num < 1000:
                                if self.has_missing_artist(row, headers):
                                    missing_artists += 1
                    
                    # Extrapolate missing artists count for large files
                    if row_count > 1000:
                        missing_artists = int((missing_artists / min(1000, row_count)) * row_count)
                    
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    print(f"Error analyzing file with {encoding}: {e}")
                    continue
            
            self.row_count = max(0, row_count)
            self.estimated_missing_artists = missing_artists
            
            # Update comprehensive file information
            file_info = f"📄 {self.row_count:,} tracks • {self.file_size:.1f} MB • ~{missing_artists:,} missing artists"
            self.file_info_label.config(text=file_info, foreground="blue")
            
            # Update songs counter
            self.songs_processed_label.config(text=f"🎵 Songs: 0/{self.row_count:,}")
            
            # Smart suggestion for iTunes API checkbox
            missing_percentage = (missing_artists / max(1, self.row_count)) * 100
            
            if missing_percentage > 20:  # More than 20% missing artists
                self.itunes_api_var.set(True)  # Auto-enable
                suggestion = f"✅ iTunes search auto-enabled ({missing_percentage:.0f}% missing artists)"
                color = "green"
            elif missing_percentage > 5:  # 5-20% missing artists
                suggestion = f"💡 Consider enabling iTunes search ({missing_percentage:.0f}% missing artists)"
                color = "orange"
            else:  # Less than 5% missing artists
                self.itunes_api_var.set(False)  # Auto-disable
                suggestion = f"ℹ️ iTunes search not needed ({missing_percentage:.0f}% missing artists)"
                color = "blue"
            
            self.message_label.config(text=suggestion, foreground=color)
            
        except Exception as e:
            print(f"Error checking file size: {e}")
            self.file_size = 0
            self.row_count = 0
            self.estimated_missing_artists = 0
            self.file_info_label.config(text="📄 Could not analyze file", foreground="red")
            self.message_label.config(text="Could not read file information", foreground="red")

    def has_missing_artist(self, row, headers):
        """Estimate if a row has missing artist information."""
        try:
            # Common artist column names
            artist_columns = ['Artist Name', 'Artist', 'Track Description']
            
            for col_name in artist_columns:
                if col_name in headers:
                    col_index = headers.index(col_name)
                    if col_index < len(row):
                        artist_value = row[col_index].strip()
                        if artist_value and artist_value.lower() not in ['', 'unknown', 'various']:
                            return False  # Has artist
            
            # If we get here, likely missing artist
            return True
            
        except Exception:
            return True  # Assume missing if we can't determine

    def auto_select_file_type(self, file_path):
        """Auto-select file type based on filename and CSV column analysis."""
        file_name = Path(file_path).name  # Get just the filename without path
        detected_type = None
        detection_method = ""
        
        # First try filename pattern matching
        filename_patterns = {
            'play-activity': ['Play Activity', 'Apple Music Play Activity'],
            'recently-played': ['Recently Played Tracks', 'Apple Music - Recently Played Tracks'],
            'play-history': ['Play History Daily Tracks', 'Apple Music - Play History Daily Tracks']
        }
        
        for file_type, patterns in filename_patterns.items():
            if any(pattern in file_name for pattern in patterns):
                detected_type = file_type
                detection_method = "filename"
                break
        
        # If filename detection fails, analyze CSV column headers
        if not detected_type:
            detected_type = self.detect_file_type_from_columns(file_path)
            if detected_type:
                detection_method = "content"
        
        # Apply the detected type and show feedback
        if detected_type:
            self.file_type_var.set(detected_type)
            
            # Show success message with detection method
            type_names = {
                'play-activity': 'Apple Music Play Activity',
                'recently-played': 'Recently Played Tracks', 
                'play-history': 'Play History Daily Tracks'
            }
            
            detection_source = "🎯 Auto-detected" if detection_method == "filename" else "🔍 Content-detected"
            self.message_label.config(
                text=f"{detection_source}: {type_names.get(detected_type, detected_type)}",
                foreground="green"
            )
        else:
            # No detection possible - ask user to select manually
            self.message_label.config(
                text="⚠️ Could not auto-detect file type - please select manually",
                foreground="orange"
            )
    
    def detect_file_type_from_columns(self, file_path):
        """Detect file type by analyzing CSV column headers."""
        try:
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                        # Read first few lines to get headers
                        reader = csv.reader(f)
                        headers = []
                        for i, row in enumerate(reader):
                            if i == 0:  # Header row
                                headers = [col.strip() for col in row]
                                break
                        
                        if not headers:
                            continue
                            
                        # Convert headers to lowercase for case-insensitive matching
                        headers_lower = [h.lower() for h in headers]
                        
                        # Define column signatures for each file type
                        signatures = {
                            'play-activity': {
                                'required': ['song name', 'event timestamp', 'play duration milliseconds'],
                                'characteristic': ['album name', 'artist name', 'end reason type']
                            },
                            'recently-played': {
                                'required': ['track description', 'first event timestamp', 'play duration in millis'],
                                'characteristic': ['container description', 'total plays', 'total skips']
                            },
                            'play-history': {
                                'required': ['track description', 'date played', 'play duration milliseconds'],
                                'characteristic': ['hours', 'play count', 'skip count']
                            }
                        }
                        
                        # Score each file type based on column matches
                        best_match = None
                        best_score = 0
                        
                        for file_type, sig in signatures.items():
                            score = 0
                            
                            # Check required columns (higher weight)
                            required_matches = sum(1 for req in sig['required'] 
                                                 if any(req in header for header in headers_lower))
                            score += required_matches * 3
                            
                            # Check characteristic columns (lower weight)
                            char_matches = sum(1 for char in sig['characteristic'] 
                                             if any(char in header for header in headers_lower))
                            score += char_matches * 1
                            
                            if score > best_score:
                                best_score = score
                                best_match = file_type
                        
                        # Return best match if confidence is high enough
                        if best_score >= 6:  # Require at least 2 required + some characteristic matches
                            return best_match
                        
                        break  # Successfully read file, but no clear match
                        
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    print(f"Error analyzing columns with {encoding}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error detecting file type from columns: {e}")
            
        return None

    def check_system_ram(self):
        """Check if system has sufficient RAM for MusicBrainz. Returns warning message or None."""
        try:
            import psutil
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
            
            if total_ram_gb < 6:
                return f"System RAM: {total_ram_gb:.1f}GB (6GB minimum required for MusicBrainz)"
            elif total_ram_gb < 8:
                return f"System RAM: {total_ram_gb:.1f}GB (8GB recommended for optimal performance)"
            else:
                return None  # Sufficient RAM
        except ImportError:
            # psutil not available, skip RAM check
            return None
        except Exception:
            # Failed to check RAM, skip warning
            return None

    def ensure_search_provider_ready(self):
        """Ensure search provider is configured with minimal dialog interruptions."""
        current_provider = self.music_search_service.get_search_provider()
        
        # If MusicBrainz is selected but not available
        if current_provider == "musicbrainz" and not self.music_search_service.musicbrainz_manager.is_database_available():
            
            # Check system RAM before suggesting MusicBrainz
            ram_warning = self.check_system_ram()
            
            # Smart default: suggest iTunes API for quick start
            dialog_text = "MusicBrainz database not found.\n\n"
            if ram_warning:
                dialog_text += f"⚠️ {ram_warning}\n\n"
            
            dialog_text += ("Quick Option: Switch to iTunes API (ready immediately)\n" +
                          "Advanced Option: Download MusicBrainz database (~2GB)\n\n" +
                          "Would you like to use iTunes API for now?\n" +
                          "(You can always switch to MusicBrainz later in Settings)")
            
            response = messagebox.askyesno("🎵 Quick Setup Required", dialog_text)
            
            if response:
                # User chose iTunes - switch automatically
                self.itunes_api_var.set(True)
                self.musicbrainz_var.set(False)
                self.update_search_provider()
                self.message_label.config(
                    text="✅ Switched to iTunes API - ready to convert!",
                    foreground="green"
                )
                return True
            else:
                # User wants MusicBrainz - show simplified setup
                self.show_musicbrainz_setup()
                return False
                
        # If iTunes is selected, it's always ready
        elif current_provider == "itunes":
            return True
            
        # MusicBrainz is available
        elif current_provider == "musicbrainz":
            return True
        
        # Fallback - something went wrong, default to iTunes
        else:
            self.itunes_api_var.set(True)
            self.musicbrainz_var.set(False)
            self.update_search_provider()
            return True
    
    def show_musicbrainz_setup(self):
        """Show simplified MusicBrainz setup dialog."""
        setup_dialog = FirstTimeSetupDialog(self.root)
        choice = setup_dialog.show_and_wait()
        
        if choice == "download":
            def on_setup_download_complete():
                """Callback for setup download completion."""
                if self.music_search_service.musicbrainz_manager.is_database_available():
                    self.musicbrainz_var.set(True)
                    self.itunes_api_var.set(False)
                    self.update_search_provider()
                    self.message_label.config(
                        text="✅ MusicBrainz ready - let's convert your music!",
                        foreground="green"
                    )
                else:
                    # Download failed, fallback to iTunes
                    self.itunes_api_var.set(True)
                    self.musicbrainz_var.set(False)
                    self.update_search_provider()
                    messagebox.showinfo(
                        "Fallback Mode",
                        "Switched to iTunes API mode. You can try MusicBrainz setup again later from Settings."
                    )
            
            download_dialog = DatabaseDownloadDialog(self.root, self.music_search_service, on_setup_download_complete)
            download_dialog.show()
        elif choice == "manual":
            manual_dialog = ManualImportDialog(self.root, self.music_search_service)
            success = manual_dialog.show_and_wait()
            if success:
                self.musicbrainz_var.set(True)
                self.itunes_api_var.set(False)
                self.update_search_provider()
                self.message_label.config(
                    text="✅ MusicBrainz imported successfully!",
                    foreground="green"
                )
            else:
                # Manual import failed, fallback to iTunes
                self.itunes_api_var.set(True)
                self.musicbrainz_var.set(False)
                self.update_search_provider()
        elif choice == "itunes":
            # User chose iTunes during setup
            self.itunes_api_var.set(True)
            self.musicbrainz_var.set(False)
            self.update_search_provider()
            self.message_label.config(
                text="✅ iTunes API ready - let's convert your music!",
                foreground="green"
            )
        else:
            # User cancelled setup
            return False
        
        return True

    def reset_processing_stats(self):
        """Reset processing statistics for a new conversion."""
        self.musicbrainz_count = 0
        self.itunes_count = 0
        self.rate_limit_hits = 0
        self.last_rate_limit_time = None
        self.update_stats_display()

    def update_stats_display(self):
        """Update the statistics display in the UI."""
        try:
            self.musicbrainz_stats_label.config(text=f"🗄️ MusicBrainz: {self.musicbrainz_count}")
            self.itunes_stats_label.config(text=f"🌐 iTunes API: {self.itunes_count}")
            
            # Color-code rate limits based on frequency
            rate_limit_text = f"⚠️ Rate limits: {self.rate_limit_hits}"
            if self.rate_limit_hits == 0:
                color = "green"
            elif self.rate_limit_hits < 5:
                color = "orange"
            else:
                color = "red"
            
            self.rate_limit_stats_label.config(text=rate_limit_text, foreground=color)
            
            # Add timing info if we hit rate limits recently
            if self.last_rate_limit_time and self.rate_limit_hits > 0:
                elapsed = time.time() - self.last_rate_limit_time
                if elapsed < 60:  # Show recent rate limit info
                    timing_text = f" (last: {elapsed:.0f}s ago)"
                    current_text = self.rate_limit_stats_label.cget("text")
                    self.rate_limit_stats_label.config(text=current_text + timing_text)
        except Exception as e:
            print(f"Error updating stats display: {e}")

    def convert_csv(self):
        file_path = getattr(self, 'full_file_path', None)
        file_type = self.file_type_var.get()
        if not file_path or not file_type:
            self.message_label.config(text="❌ Please select a CSV file first", foreground="red")
            return
        
        # Clear placeholders
        self.output_text.config(state='normal')
        self.output_text.delete(1.0, tk.END)
        for item in self.preview_table.get_children():
            self.preview_table.delete(item)

        # Only warn for very large files (10k+ rows) and make it informational
        if self.row_count > 10000:
            estimated_time = max(1, int(self.row_count/1000))
            self.message_label.config(
                text=f"📊 Large file detected: {self.row_count:,} rows (estimated time: ~{estimated_time} min)",
                foreground="blue"
            )

        self.output_text.delete(1.0, tk.END)
        for row in self.preview_table.get_children():
            self.preview_table.delete(row)

        self.progress_var.set(0)
        self.progress_label.config(text="Processing...")
        self.message_label.config(text="")
        
        # Reset processing statistics
        self.reset_processing_stats()

        # Check if user needs to setup their search provider
        if not self.ensure_search_provider_ready():
            return
        
        # Auto-start MusicBrainz optimization if available (no dialog interruption)
        if (self.music_search_service.get_search_provider() == "musicbrainz" and 
            self.music_search_service.musicbrainz_manager.is_database_available()):
            
            self._optimization_start_time = time.time()
            
            def progress_callback(message, percent, start_time):
                elapsed = time.time() - start_time
                timer_text = f" (Elapsed: {elapsed:.0f}s)"
                self.progress_label.config(text=f"🔧 Search optimization: {message}{timer_text}")
                self.root.update_idletasks()
            
            # Start progressive loading in background
            self.music_search_service.start_progressive_loading(progress_callback)
            self.progress_label.config(text="🎵 Starting MusicBrainz optimization (searches work immediately)...")
            self.root.update_idletasks()

        # Reset process control state
        self.process_stopped = False
        self.process_paused = False
        self.process_pause_button.config(state='normal', text="Pause")
        self.process_stop_button.config(state='normal')

        self.processing_thread = threading.Thread(target=self.process_csv, args=(file_path, file_type))
        self.processing_thread.start()

    def toggle_pause_resume(self):
        if self.pause_itunes_search:
            self.pause_itunes_search = False
            self.pause_resume_button.config(text="Pause iTunes Search")
            self.api_status_label.config(text="API Status: Resumed")
        else:
            self.pause_itunes_search = True
            self.pause_resume_button.config(text="Resume iTunes Search")
            self.api_status_label.config(text="API Status: Paused")

    def stop_itunes_search(self):
        self.stop_itunes_search = True
        self.pause_itunes_search = False
        self.pause_resume_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.api_status_label.config(text="API Status: Stopped")
        self.api_timer_label.config(text="Wait time: 0s")
        self.api_wait_start = None  # Reset timer start
        self.wait_duration = 0  # Reset wait duration
        
        # Ask user if they want to continue with conversion
        if messagebox.askyesno("iTunes Search Stopped", 
                             "iTunes artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
            return True
        else:
            # If user doesn't want to continue, stop the entire process
            if self.processing_thread and self.processing_thread.is_alive():
                self.message_label.config(text="Conversion cancelled by user.", foreground="red")
                self.progress_label.config(text="Processing stopped.")
            return False

    def process_csv(self, file_path, file_type):
        """Process CSV file with two-phase approach: MusicBrainz first, then iTunes."""
        start_time = time.time()
        self.processing_start_time = start_time  # Track for elapsed time display
        
        try:
            # Reset stats for new processing
            self.musicbrainz_found = 0
            self.itunes_found = 0
            self.rate_limit_hits = 0
            self.failed_requests.clear()  # Clear previous failed requests
            
            # Phase 1: Load and process entire CSV with MusicBrainz
            self.progress_label.config(text="📂 Loading CSV file...")
            self.root.update_idletasks()
            
            # Load entire CSV at once for better processing control
            all_data = self.load_entire_csv(file_path, file_type)
            if not all_data:
                return
            
            total_tracks = len(all_data)
            self.progress_var.set(0)
            
            # Phase 1: MusicBrainz processing for all tracks
            self.progress_label.config(text="🗄️ Phase 1: Processing with MusicBrainz database...")
            self.root.update_idletasks()
            
            musicbrainz_results, missing_tracks = self.process_with_musicbrainz(all_data, total_tracks)
            
            # Check if user wants to search for missing artists
            final_results = musicbrainz_results
            
            if missing_tracks and self.itunes_api_var.get():
                # Phase 2: iTunes processing for missing tracks only
                elapsed_str = self._get_elapsed_time_str()
                self.progress_label.config(text=f"🌐 Phase 2: Searching {len(missing_tracks)} missing artists with iTunes...{elapsed_str}")
                self.root.update_idletasks()
                
                itunes_results = self.process_missing_with_itunes(missing_tracks, len(musicbrainz_results), total_tracks)
                final_results.extend(itunes_results)
            
            # Finalize and display results
            self.finalize_processing(final_results, start_time)
            
        except Exception as e:
            self.progress_label.config(text=f"❌ Processing error: {str(e)}")
            self.message_label.config(text=f"Error processing file: {str(e)}", foreground="red")
            # Disable process controls
            self.process_pause_button.config(state='disabled')
            self.process_stop_button.config(state='disabled')

    def update_rate_limit_timer(self):
        if self.api_wait_start is not None and not self.process_stopped:
            elapsed = time.time() - self.api_wait_start
            remaining = max(0, self.wait_duration - elapsed)
            # Update status bar wait time instead of iTunes API section
            self.wait_time_label.config(text=f"⏳ Wait: {remaining:.1f}s")
            if remaining > 0 and not self.process_stopped and not self.skip_wait_requested:
                self.root.after(100, self.update_rate_limit_timer)
            else:
                self.api_wait_start = None
                self.wait_time_label.config(text="")
                self.skip_wait_button.grid_remove()  # Hide skip button when wait ends

    def skip_current_wait(self):
        """Skip the current rate limit wait by clearing the entire API call queue."""
        self.skip_wait_requested = True
        self.api_wait_start = None
        self.wait_time_label.config(text="")
        self.skip_wait_button.grid_remove()
        
        # Clear the entire rate limit queue to reset rate limiting
        with self.api_lock:
            self.api_calls.clear()
            print(f"🚀 Rate limit queue cleared - skipping wait and resetting rate limiter")
        
        # Update API status to show queue was cleared
        self.api_status_label.config(text="API Status: Queue Cleared")

    def _interruptible_wait(self, duration):
        """Wait for the specified duration, but allow interruption via skip_wait_requested."""
        start_time = time.time()
        while time.time() - start_time < duration:
            if self.skip_wait_requested or self.process_stopped:
                break
            time.sleep(0.1)  # Sleep in small increments to allow interruption
            self.root.update_idletasks()  # Keep UI responsive

    def _get_elapsed_time_str(self):
        """Get formatted elapsed time string since processing started."""
        if self.processing_start_time is None:
            return ""
        elapsed = time.time() - self.processing_start_time
        if elapsed < 60:
            return f" ({elapsed:.0f}s)"
        elif elapsed < 3600:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            return f" ({minutes}m {seconds}s)"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f" ({hours}h {minutes}m)"

    def process_csv_data(self, df_chunk):
        """Process CSV data and return processed data with counts."""
        # This is a placeholder method - actual processing logic handled elsewhere
        pass

    def toggle_pause_resume(self):
        if self.pause_itunes_search:
            self.pause_itunes_search = False
            self.pause_resume_button.config(text="Pause iTunes Search")
            self.api_status_label.config(text="API Status: Resumed")
        else:
            self.pause_itunes_search = True
            self.pause_resume_button.config(text="Resume iTunes Search")
            self.api_status_label.config(text="API Status: Paused")

    def stop_itunes_search(self):
        self.stop_itunes_search = True
        self.pause_itunes_search = False
        self.pause_resume_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.api_status_label.config(text="API Status: Stopped")
        self.api_timer_label.config(text="Wait time: 0s")
        self.api_wait_start = None  # Reset timer start
        self.wait_duration = 0  # Reset wait duration
        
        # Ask user if they want to continue with conversion
        if messagebox.askyesno("iTunes Search Stopped", 
                             "iTunes artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
            return True
        else:
            # If user doesn't want to continue, stop the entire process
            if self.processing_thread and self.processing_thread.is_alive():
                self.message_label.config(text="Conversion cancelled by user.", foreground="red")
                self.progress_label.config(text="Processing stopped.")
            return False

    def process_chunk(self, chunk, file_type):
        processed_data = []
        current_timestamp = pd.Timestamp.now()
        success_count = 0
        missing_artists = 0
        attributed_artists = 0
        failed_requests = 0
        itunes_search_time = 0

        if file_type in ['converted', 'generic']:
            # Handle both converted and generic CSV files
            for index, row in chunk.iterrows():
                try:
                    artist = row.get('Artist', '').strip() if pd.notna(row.get('Artist')) else ''
                    track = row.get('Track', '').strip() if pd.notna(row.get('Track')) else ''
                    album = row.get('Album', '').strip() if pd.notna(row.get('Album')) else ''
                    timestamp = row.get('Timestamp', current_timestamp)
                    album_artist = row.get('Album Artist', '').strip() if pd.notna(row.get('Album Artist')) else ''
                    
                    # Handle duration as either string or number
                    duration = row.get('Duration', 180)
                    if isinstance(duration, str):
                        try:
                            duration = int(float(duration))
                        except ValueError:
                            duration = 180
                    elif pd.isna(duration):
                        duration = 180
                    else:
                        duration = int(duration)

                    # Check if artist lookup should be performed
                    # - Artist is missing AND
                    # - Either iTunes API is enabled OR MusicBrainz is selected as provider
                    should_search_artist = (not artist and not self.stop_itunes_search and 
                                           (self.itunes_api_var.get() or 
                                            self.music_search_service.get_search_provider() == "musicbrainz"))
                    
                    if should_search_artist:
                        while self.pause_itunes_search and not self.stop_itunes_search:
                            time.sleep(0.1)  # Wait while paused
                        
                        if self.stop_itunes_search:
                            # If search was stopped, check if we should continue
                            if not messagebox.askyesno("Artist Search Stopped", 
                                                     "Artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
                                raise InterruptedError("Conversion cancelled by user")
                            break  # Exit the loop and continue with remaining processing
                        
                        try:
                            itunes_start_time = time.time()
                            artist = self.search_artist(track, album)
                            itunes_end_time = time.time()
                            itunes_search_time += itunes_end_time - itunes_start_time
                            if artist:  # Only count as success if artist was found
                                attributed_artists += 1
                                provider = self.music_search_service.get_search_provider()
                                stats_text = f"🗄️{self.musicbrainz_count} 🌐{self.itunes_count}"
                                if self.rate_limit_hits > 0:
                                    stats_text += f" ⚠️{self.rate_limit_hits}"
                                self.progress_label.config(text=f"{provider.title()} search {attributed_artists + failed_requests}: Artist found for '{track}' [{stats_text}]")
                            else:
                                failed_requests += 1
                                stats_text = f"🗄️{self.musicbrainz_count} 🌐{self.itunes_count}"
                                if self.rate_limit_hits > 0:
                                    stats_text += f" ⚠️{self.rate_limit_hits}"
                                self.progress_label.config(text=f"Search {attributed_artists + failed_requests}: No artist found for '{track}' [{stats_text}]")
                            self.root.update_idletasks()
                        except Exception as e:
                            failed_requests += 1
                            self.progress_label.config(text=f"Search {attributed_artists + failed_requests}: Failed for '{track}' - {str(e)}")
                            self.root.update_idletasks()

                    if not artist:
                        missing_artists += 1

                    processed_data.append([artist, track, album, timestamp, artist or album_artist, duration])
                    success_count += 1
                except InterruptedError:
                    # Propagate the interruption
                    raise
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'play-history':
            for index, row in chunk.iterrows():
                try:
                    track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                    if len(track_info) == 2:
                        artist, track = track_info
                    else:
                        artist, track = '', row['Track Description']
                    artist = artist.strip()
                    track = track.strip()
                    duration = int(row['Play Duration Milliseconds']) // 1000 if pd.notna(row['Play Duration Milliseconds']) else 180
                    processed_data.append([artist, track, '', current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                    if not artist:
                        missing_artists += 1
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'recently-played':
            for index, row in chunk.iterrows():
                try:
                    track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                    if len(track_info) == 2:
                        artist, track = track_info
                    else:
                        artist, track = '', row['Track Description']
                    artist = artist.strip()
                    track = track.strip()
                    album = row['Container Description'].strip() if pd.notna(row['Container Description']) else ''
                    duration = int(row['Media duration in millis']) // 1000 if pd.notna(row['Media duration in millis']) else 180
                    processed_data.append([artist, track, album, current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                    if not artist:
                        missing_artists += 1
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'play-activity':
            for index, row in chunk.iterrows():
                try:
                    artist = row.get('Artist Name', '').strip() if pd.notna(row.get('Artist Name')) else ''
                    track = row.get('Song Name', '').strip() if pd.notna(row.get('Song Name')) else ''
                    album = row.get('Album Name', '').strip() if pd.notna(row.get('Album Name')) else ''
                    duration = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180

                    # Check if artist lookup should be performed
                    # - Artist is missing AND
                    # - Either iTunes API is enabled OR MusicBrainz is selected as provider
                    should_search_artist = (not artist and not self.stop_itunes_search and 
                                           (self.itunes_api_var.get() or 
                                            self.music_search_service.get_search_provider() == "musicbrainz"))
                    
                    if should_search_artist:
                        while self.pause_itunes_search and not self.stop_itunes_search:
                            time.sleep(0.1)  # Wait while paused
                        
                        if self.stop_itunes_search:
                            # If search was stopped, check if we should continue
                            if not messagebox.askyesno("Artist Search Stopped", 
                                                     "Artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
                                raise InterruptedError("Conversion cancelled by user")
                            break  # Exit the loop and continue with remaining processing
                        
                        try:
                            itunes_start_time = time.time()
                            artist = self.search_artist(track, album)
                            itunes_end_time = time.time()
                            itunes_search_time += itunes_end_time - itunes_start_time
                            if artist:  # Only count as success if artist was found
                                attributed_artists += 1
                                provider = self.music_search_service.get_search_provider()
                                stats_text = f"🗄️{self.musicbrainz_count} 🌐{self.itunes_count}"
                                if self.rate_limit_hits > 0:
                                    stats_text += f" ⚠️{self.rate_limit_hits}"
                                self.progress_label.config(text=f"{provider.title()} search {attributed_artists + failed_requests}: Artist found for '{track}' [{stats_text}]")
                            else:
                                failed_requests += 1
                                stats_text = f"🗄️{self.musicbrainz_count} 🌐{self.itunes_count}"
                                if self.rate_limit_hits > 0:
                                    stats_text += f" ⚠️{self.rate_limit_hits}"
                                self.progress_label.config(text=f"Search {attributed_artists + failed_requests}: No artist found for '{track}' [{stats_text}]")
                            self.root.update_idletasks()
                        except Exception as e:
                            failed_requests += 1
                            self.progress_label.config(text=f"Search {attributed_artists + failed_requests}: Failed for '{track}' - {str(e)}")
                            self.root.update_idletasks()

                    if not artist:
                        missing_artists += 1

                    processed_data.append([artist, track, album, current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                except InterruptedError:
                    # Propagate the interruption
                    raise
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        return processed_data, success_count, missing_artists, attributed_artists, failed_requests, itunes_search_time

    def update_rate_limit_timer(self):
        if self.api_wait_start is not None and not self.process_stopped:
            elapsed = time.time() - self.api_wait_start
            remaining = max(0, self.wait_duration - elapsed)
            # Update status bar wait time instead of iTunes API section
            self.wait_time_label.config(text=f"⏳ Wait: {remaining:.1f}s")
            if remaining > 0 and not self.process_stopped and not self.skip_wait_requested:
                self.root.after(100, self.update_rate_limit_timer)
            else:
                self.api_wait_start = None
                self.wait_time_label.config(text="")
                self.skip_wait_button.grid_remove()  # Hide skip button when wait ends

    def toggle_process_pause(self):
        """Toggle pause/resume for entire process."""
        if self.process_paused:
            self.process_paused = False
            self.process_pause_button.config(text="Pause")
            self.progress_label.config(text="🎵 Processing resumed...")
        else:
            self.process_paused = True
            self.process_pause_button.config(text="Resume")
            self.progress_label.config(text="⏸️ Processing paused (click Resume to continue)")

    def stop_process(self):
        """Stop the entire processing."""
        if messagebox.askyesno("Stop Processing", 
                             "Stop processing the CSV file?\n\nYou can save your current results before stopping."):
            self.process_stopped = True
            self.process_pause_button.config(state='disabled')
            self.process_stop_button.config(state='disabled')
            self.progress_label.config(text="🛑 Processing stopped by user")

    def search_artist(self, track_name, album=None, use_musicbrainz_first=True):
        """Search for artist with MusicBrainz-first workflow."""
        import time
        search_start = time.time()
        
        # Clean track name
        clean_track = re.sub(r'\s*\(.*?\)\s*', '', track_name).strip()
        if not clean_track:
            return None
        
        # Get current search provider
        current_provider = self.music_search_service.get_search_provider()
        
        # New workflow: Always try MusicBrainz first if available, regardless of current provider
        if use_musicbrainz_first and self.music_search_service.musicbrainz_manager.is_database_available():
            musicbrainz_start = time.time()
            search_result = self.music_search_service.search_song(clean_track, None, album)
            musicbrainz_time = time.time() - musicbrainz_start
            
            if search_result.get("success"):
                # Found result in MusicBrainz
                total_time = time.time() - search_start
                
                # Update counter and display
                self.musicbrainz_count += 1
                self.root.after(0, self.update_stats_display)
                
                print(f"MusicBrainz search for '{clean_track}': {musicbrainz_time*1000:.2f}ms (total: {total_time*1000:.2f}ms) - SUCCESS")
                return search_result["artist"]
            else:
                print(f"MusicBrainz search for '{clean_track}': {musicbrainz_time*1000:.2f}ms - NO RESULT")
        
        # If MusicBrainz failed or iTunes is explicitly selected, use iTunes API
        if current_provider == "itunes" or (use_musicbrainz_first and self.fallback_var.get()):
            itunes_start = time.time()
            try:
                result = self._search_itunes_api(clean_track, album)
                itunes_time = time.time() - itunes_start
                total_time = time.time() - search_start
                
                # Update counter and display
                self.itunes_count += 1
                self.root.after(0, self.update_stats_display)
                
                fallback_text = " (fallback)" if use_musicbrainz_first else ""
                print(f"iTunes search for '{clean_track}'{fallback_text}: {itunes_time*1000:.2f}ms (total: {total_time*1000:.2f}ms) - {'SUCCESS' if result else 'NO RESULT'}")
                return result
            except Exception as e:
                # Check if this is a rate limit error
                if "429" in str(e) or "rate limit" in str(e).lower():
                    self.rate_limit_hits += 1
                    self.last_rate_limit_time = time.time()
                    print(f"🚫 RATE LIMIT HIT for '{clean_track}' - Hit #{self.rate_limit_hits} at {time.strftime('%H:%M:%S')}")
                    self.root.after(0, self.update_stats_display)
                raise e
        
        # No results found
        return None

    def _show_itunes_fallback_dialog(self, track_name):
        """Show dialog asking user if they want to use iTunes API fallback."""
        # This is simplified - the old complex dialog logic has been removed
        # since we now use the auto-fallback checkbox setting
        return 'yes_once' if self.fallback_var.get() else 'no'

    def _legacy_code_to_remove(self):
        # This is old broken code that needs to be removed
        return None  # Early return to skip all the broken code below
        if False:  # Disabled
            # User chose to download database
            download_dialog = DatabaseDownloadDialog(self.root, self.music_search_service)
            download_dialog.show()
            self.root.wait_window(download_dialog.dialog)
            
            # Retry search after download
            retry_result = self.music_search_service.search_song(clean_track, None, album)
            if retry_result.get("success"):
                total_time = time.time() - search_start
                print(f"MusicBrainz search for '{clean_track}' (after download): {total_time*1000:.2f}ms - SUCCESS")
                return retry_result["artist"]
        
        elif False:  # choice == "manual_import":
            # User chose manual import
            import_dialog = ManualImportDialog(self.root, self.music_search_service)
            import_dialog.show()
            self.root.wait_window(import_dialog.dialog)
            
            # Retry search after import
            retry_result = self.music_search_service.search_song(clean_track, None, album)
            if retry_result.get("success"):
                    total_time = time.time() - search_start
                    print(f"MusicBrainz search for '{clean_track}' (after import): {total_time*1000:.2f}ms - SUCCESS")
                    return retry_result["artist"]
            
            elif choice == "itunes":
                # User chose iTunes API
                self.music_search_service.set_search_provider("itunes")
                self.update_search_provider_ui()
                
                # Retry search after provider change
                itunes_start = time.time()
                try:
                    result = self._search_itunes_api(clean_track, album)
                    itunes_time = time.time() - itunes_start
                    total_time = time.time() - search_start
                    
                    # Update counter and display
                    self.itunes_count += 1
                    self.root.after(0, self.update_stats_display)
                    
                    print(f"iTunes search for '{clean_track}' (fallback): {itunes_time*1000:.2f}ms (total: {total_time*1000:.2f}ms) - {'SUCCESS' if result else 'NO RESULT'}")
                    return result
                except Exception as e:
                    # Check if this is a rate limit error
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        self.rate_limit_hits += 1
                        self.last_rate_limit_time = time.time()
                        print(f"🚫 RATE LIMIT HIT for '{clean_track}' (fallback) - Hit #{self.rate_limit_hits} at {time.strftime('%H:%M:%S')}")
                        self.root.after(0, self.update_stats_display)
                    raise e
            
            # If all else fails, try iTunes as fallback
            fallback_start = time.time()
            fallback_result = self._search_itunes_api(clean_track, album)
            fallback_time = time.time() - fallback_start
            total_time = time.time() - search_start
            print(f"iTunes fallback search for '{clean_track}': {fallback_time*1000:.2f}ms (total: {total_time*1000:.2f}ms)")
            return fallback_result
        
        elif search_result.get("use_itunes") or search_result.get("use_itunes_fallback"):
            # Use iTunes API (either as primary choice or fallback)
            fallback_start = time.time()
            result = self._search_itunes_api(clean_track, album)
            fallback_time = time.time() - fallback_start
            total_time = time.time() - search_start
            print(f"iTunes search for '{clean_track}' (configured): {fallback_time*1000:.2f}ms (total: {total_time*1000:.2f}ms)")
            return result
        
        else:
            # No results found in MusicBrainz - offer iTunes API fallback
            if not hasattr(self, '_itunes_fallback_asked') or not self._itunes_fallback_asked:
                response = self._show_itunes_fallback_dialog(clean_track)
                if response == 'yes_always':
                    # Enable iTunes fallback for all future searches
                    self.music_search_service.set_auto_fallback(True)
                    self._itunes_fallback_asked = True
                    fallback_result = self._search_itunes_api(clean_track, album)
                    total_time = time.time() - search_start
                    print(f"iTunes fallback search for '{clean_track}': {total_time*1000:.2f}ms")
                    return fallback_result
                elif response == 'yes_once':
                    # Use iTunes just for this search
                    fallback_result = self._search_itunes_api(clean_track, album)
                    total_time = time.time() - search_start
                    print(f"iTunes fallback search for '{clean_track}': {total_time*1000:.2f}ms")
                    return fallback_result
                elif response == 'no_always':
                    # Don't ask again for this session
                    self._itunes_fallback_asked = True
                # response == 'no' - just continue to return None
            
            # No results found
            total_time = time.time() - search_start
            print(f"No results found for '{clean_track}': {total_time*1000:.2f}ms")
            return None

    def _show_itunes_fallback_dialog(self, track_name):
        """Show dialog asking if user wants to use iTunes API fallback."""
        import tkinter.messagebox as msgbox
        
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Artist Not Found")
        dialog.geometry("500x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        self.dialog_result = None
        
        # Main message
        message_frame = tk.Frame(dialog)
        message_frame.pack(pady=20, padx=20, fill="x")
        
        title_label = tk.Label(message_frame, text="🔍 Artist Not Found in MusicBrainz", 
                              font=("Arial", 12, "bold"))
        title_label.pack()
        
        track_label = tk.Label(message_frame, text=f"Track: \"{track_name}\"", 
                              font=("Arial", 10))
        track_label.pack(pady=(10, 5))
        
        message_label = tk.Label(message_frame, 
                                text="Would you like to search iTunes API as fallback?\n" +
                                     "(iTunes API is rate-limited but may find additional matches)",
                                justify="center")
        message_label.pack(pady=5)
        
        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def on_yes_always():
            self.dialog_result = 'yes_always'
            dialog.destroy()
        
        def on_yes_once():
            self.dialog_result = 'yes_once'
            dialog.destroy()
        
        def on_no():
            self.dialog_result = 'no'
            dialog.destroy()
            
        def on_no_always():
            self.dialog_result = 'no_always'
            dialog.destroy()
        
        ttk.Button(button_frame, text="Yes, Always Use iTunes", 
                   command=on_yes_always, width=18).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Yes, Just This Once", 
                   command=on_yes_once, width=18).pack(side="left", padx=5)
        ttk.Button(button_frame, text="No", 
                   command=on_no, width=10).pack(side="left", padx=5)
        ttk.Button(button_frame, text="No, Don't Ask Again", 
                   command=on_no_always, width=18).pack(side="left", padx=5)
        
        # Wait for user response
        dialog.wait_window()
        return self.dialog_result or 'no'

    def _search_itunes_api(self, track, album):
        """Search using iTunes API with rate limiting."""
        # Rate limiting: ensure no more than X calls per minute
        with self.api_lock:
            current_time = time.time()
            rate_limit = int(self.rate_limit_var.get())
            
            # Remove API calls older than 1 minute
            while self.api_calls and current_time - self.api_calls[0] > 60:
                self.api_calls.popleft()
            
            # If we've made rate_limit calls in the last minute, wait
            if len(self.api_calls) >= rate_limit:
                self.wait_duration = 60 - (current_time - self.api_calls[0])
                if self.wait_duration > 0:
                    self.api_status_label.config(text="API Status: Rate Limited")
                    self.api_wait_start = current_time
                    self.skip_wait_requested = False  # Reset skip flag
                    self.skip_wait_button.grid()  # Show skip button
                    self.update_rate_limit_timer()
                    self._interruptible_wait(self.wait_duration)
            
            try:
                # Try first with just the track name
                artist = self._try_search(track)
                if not artist and album:
                    # If no result or artist not found, try with album
                    artist = self._try_search(f"{track} {album}")
                
                if artist:
                    self.api_status_label.config(text="API Status: Success")
                    return artist
                else:
                    raise Exception("No results found")
                    
            except Exception as e:
                self.api_status_label.config(text=f"API Status: Error - {str(e)}")
                raise

    def _try_search(self, search_term):
        """Helper method to perform the actual iTunes API search."""
        try:
            # URL encode the search term
            encoded_term = requests.utils.quote(search_term)
            url = f"https://itunes.apple.com/search?term={encoded_term}&entity=song&limit=5"  # Get top 5 results
            
            # Make the API call with timeout
            response = requests.get(url, timeout=10)
            self.api_calls.append(time.time())  # Record the API call time
            
            if response.status_code == 429:
                # Rate limit hit
                self.rate_limit_hits += 1
                self.last_rate_limit_time = time.time()
                print(f"🚫 RATE LIMIT HIT (HTTP 429) for '{search_term}' - Hit #{self.rate_limit_hits} at {time.strftime('%H:%M:%S')}")
                self.root.after(0, self.update_stats_display)
                raise Exception(f"Rate limit exceeded (HTTP 429). Try reducing the request rate.")
            elif response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}")
            
            data = response.json()
            
            if not isinstance(data, dict) or 'resultCount' not in data or 'results' not in data:
                raise Exception("Invalid response format")
            
            if data['resultCount'] > 0:
                # Try to find the most relevant result
                # Prefer results where the track name matches exactly
                exact_matches = [r for r in data['results'] 
                               if r.get('trackName', '').lower().startswith(search_term.lower())]
                
                if exact_matches:
                    return exact_matches[0]['artistName']
                elif data['results']:
                    return data['results'][0]['artistName']
            
            return None
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(str(e))

    def display_preview(self, df):
        # Clear existing items
        for item in self.preview_table.get_children():
            self.preview_table.delete(item)
            
        # Add new items (simplified columns for space efficiency)
        for index, row in df.iterrows():
            # Only show essential columns in preview
            values = [row.get('Artist', ''), row.get('Track', ''), row.get('Album', ''), str(row.get('Timestamp', ''))[:16]]
            self.preview_table.insert("", "end", values=values)

    def copy_to_clipboard(self):
        if self.row_count > 5000:
            warning = f"Copying {self.row_count} rows to clipboard may use a lot of memory. Do you want to continue?"
            if not messagebox.askyesno("Warning", warning):
                return

        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_text.get(1.0, tk.END))
        messagebox.showinfo("Copied", "CSV output copied to clipboard.")

    def save_as_csv(self):
        if not hasattr(self, 'processed_df'):
            messagebox.showerror("Error", "No data to save. Please process a CSV file first.")
            return

        file_type = self.file_type_var.get()
        if file_type == 'play-history':
            file_name = 'Play_History_Data.csv'
        elif file_type == 'recently-played':
            file_name = 'Recently_Played_Data.csv'
        else:
            file_name = 'Converted_Data.csv'

        try:
            # Use basic save dialog without filetypes to avoid macOS crash
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv", 
                initialfile=file_name,
                title="Save CSV File"
            )
        except Exception as e:
            print(f"Save dialog error: {e}")
            messagebox.showerror("Error", "Could not open save dialog. Please check your system configuration.")
            return
        
        if file_path:
            try:
                # Use UTF-8 with BOM for better Excel compatibility across platforms
                self.processed_df.to_csv(
                    file_path, 
                    index=False, 
                    encoding='utf-8-sig',
                    lineterminator='\n'  # Consistent line endings across platforms
                )
                # Store the output file path and show post-processing button
                self.last_output_file = file_path
                self.reprocess_button.grid()  # Make button visible
                
                messagebox.showinfo("💾 Saved Successfully", f"CSV file saved to:\n{os.path.basename(file_path)}\n\n" +
                                  "💡 Tip: Use '🔍 Search for Missing Artists' in the Results area to find any missing artist information.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save CSV file:\n{str(e)}")

    def _try_search(self, search_term):
        """Helper method to perform the actual iTunes API search."""
        try:
            # URL encode the search term
            encoded_term = requests.utils.quote(search_term)
            url = f"https://itunes.apple.com/search?term={encoded_term}&entity=song&limit=5"  # Get top 5 results
            
            # Make the API call with timeout
            response = requests.get(url, timeout=10)
            self.api_calls.append(time.time())  # Record the API call time
            
            if response.status_code == 429:
                # Rate limit hit
                self.rate_limit_hits += 1
                self.last_rate_limit_time = time.time()
                print(f"🚫 RATE LIMIT HIT (HTTP 429) for '{search_term}' - Hit #{self.rate_limit_hits} at {time.strftime('%H:%M:%S')}")
                self.root.after(0, self.update_stats_display)
                raise Exception(f"Rate limit exceeded (HTTP 429). Try reducing the request rate.")
            elif response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}")
            
            data = response.json()
            
            if not isinstance(data, dict) or 'resultCount' not in data or 'results' not in data:
                raise Exception("Invalid response format")
            
            if data['resultCount'] > 0:
                # Try to find the most relevant result
                # Prefer results where the track name matches exactly
                exact_matches = [r for r in data['results'] 
                               if r.get('trackName', '').lower().startswith(search_term.lower())]
                
                if exact_matches:
                    return exact_matches[0]['artistName']
                elif data['results']:
                    return data['results'][0]['artistName']
            
            return None
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(str(e))

    def update_time_estimate(self, event=None):
        """Update the estimated time for API search based on rate limit and file size."""
        if not hasattr(self, 'row_count') or not self.row_count or not self.file_entry.get():
            return
            
        if not self.itunes_api_var.get():
            self.api_status_label.config(text="API Status: Ready")
            return
            
        try:
            rate_limit = int(self.rate_limit_var.get())
            if rate_limit <= 0:
                raise ValueError
                
            # Calculate estimated time
            missing_artists = self.count_missing_artists()
            if missing_artists == 0:
                self.api_status_label.config(text="No missing artists to search for")
                return
                
            total_minutes = missing_artists / rate_limit
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            seconds = int((total_minutes * 60) % 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
                
            # Show warning if rate limit > 20
            if rate_limit > 20:
                self.rate_limit_warning.config(foreground='red')
            else:
                self.rate_limit_warning.config(foreground='black')
                
            estimate_text = f"Estimated time for {missing_artists:,} missing artists: {time_str}"
            if rate_limit > 20:
                estimate_text += " (High rate limit may cause errors)"
                
            self.api_status_label.config(text=estimate_text)
            
        except ValueError:
            self.api_status_label.config(text="Please enter a valid rate limit")

    def count_missing_artists(self):
        """Count how many rows are missing artist information."""
        try:
            if not hasattr(self, 'full_file_path') or not self.full_file_path:
                return 0
                
            # Read CSV with proper settings to handle mixed types
            df = pd.read_csv(self.full_file_path, 
                           low_memory=False,
                           dtype=str,  # Read all columns as strings
                           na_values=['', 'nan', 'NaN', 'null', None],
                           keep_default_na=True)
            
            file_type = self.file_type_var.get()
            missing_count = 0
            
            # First check what columns we actually have
            columns = set(df.columns)
            
            if file_type == 'play-activity':
                # For play activity, check if we have a song but missing artist info
                if 'Song Name' in columns:
                    # Count rows where we have a song name but no artist info
                    has_song = df['Song Name'].notna() & (df['Song Name'].str.strip() != '')
                    # Check for artist info in Container Artist Name
                    has_artist = pd.Series(False, index=df.index)
                    if 'Container Artist Name' in columns:
                        has_artist |= df['Container Artist Name'].notna() & (df['Container Artist Name'].str.strip() != '')
                    missing_count = (has_song & ~has_artist).sum()
                    
            elif file_type in ['generic', 'converted']:
                if 'Artist' in columns:
                    missing_count = df['Artist'].isna().sum() + (df['Artist'].fillna('').str.strip() == '').sum()
            elif file_type in ['play-history', 'recently-played']:
                if 'Track Description' in columns:
                    missing_count = sum(1 for x in df['Track Description'].fillna('') if not str(x).strip() or ' - ' not in str(x))
            
            return missing_count
            
        except Exception as e:
            print(f"Error counting missing artists: {str(e)}")  # Debug info
            return 0

    def on_search_provider_change(self):
        """Handle search provider change with improved performance."""
        provider = self.search_provider_var.get()
        
        # Use after_idle to prevent UI blocking during rapid switches
        self.root.after_idle(lambda: self._update_provider_ui(provider))
    
    def _update_provider_ui(self, provider):
        """Update UI based on search provider with optimized performance."""
        # Set provider in service
        self.music_search_service.set_search_provider(provider)
        
        # Show/hide UI sections based on provider
        if provider == "itunes":
            # Hide MusicBrainz sections completely
            self.mb_section.grid_remove()
            
            # Modify auto-fallback checkbox for iTunes-only mode
            self.fallback_checkbox.config(text="iTunes API only mode", state="disabled")
            self.fallback_var.set(False)  # No fallback needed in iTunes-only mode
            
        else:  # MusicBrainz mode
            # Show MusicBrainz sections
            self.mb_section.grid()
            
            # Restore auto-fallback checkbox for MusicBrainz mode
            self.fallback_checkbox.config(text="Auto-fallback to iTunes if no results", state="normal")
            self.fallback_var.set(self.music_search_service.get_auto_fallback())
            
            # Update database status (only when needed)
            self.update_database_status()

    def on_fallback_changed(self):
        self.music_search_service.set_auto_fallback(self.fallback_var.get())

    def update_database_status(self):
        """Update the database status display."""
        db_info = self.music_search_service.musicbrainz_manager.get_database_info()
        
        if db_info['exists']:
            self.db_status_label.config(text="Downloaded")
            self.download_button.config(state='disabled')
            self.check_updates_button.config(state='normal')
            self.delete_db_button.config(state='normal')
            self.reveal_location_button.config(state='normal')
            self.db_size_label.config(text=f"Database Size: {db_info['size_mb']}MB")
            
            # Format the last updated date
            if 'last_updated' in db_info:
                try:
                    from datetime import datetime
                    updated_date = datetime.fromisoformat(db_info['last_updated'].replace('Z', '+00:00'))
                    formatted_date = updated_date.strftime("%Y-%m-%d %H:%M")
                    self.db_updated_label.config(text=f"Last Updated: {formatted_date}")
                except:
                    self.db_updated_label.config(text=f"Last Updated: {db_info.get('last_updated', 'Unknown')}")
            else:
                self.db_updated_label.config(text="Last Updated: Unknown")
                
            # Show track count if available
            if 'track_count' in db_info and db_info['track_count'] > 0:
                self.db_size_label.config(text=f"Database Size: {db_info['size_mb']}MB ({db_info['track_count']:,} tracks)")
        else:
            self.db_status_label.config(text="Not Downloaded")
            self.download_button.config(state='normal')
            self.check_updates_button.config(state='disabled')
            self.delete_db_button.config(state='disabled')
            self.reveal_location_button.config(state='disabled')
            self.db_size_label.config(text="Database Size: 0MB")
            self.db_updated_label.config(text="Last Updated: Never")
        
        # Respect provider selection
        provider = self.search_provider_var.get()
        if provider == "itunes":
            self.download_button.config(state="disabled")
            self.check_updates_button.config(state="disabled")
            self.delete_db_button.config(state="disabled")
            self.reveal_location_button.config(state="disabled")

    def download_database(self):
        def on_download_complete():
            """Callback to refresh database status after successful download."""
            self.update_database_status()
            # If MusicBrainz was not selected, switch to it automatically
            if not self.musicbrainz_var.get():
                self.musicbrainz_var.set(True)
                self.itunes_api_var.set(False)
        
        dialog = DatabaseDownloadDialog(self.root, self.music_search_service, on_download_complete)
        dialog.show()

    def check_for_updates(self):
        """Check for updates with proper loading indicators."""
        # Show loading indicator
        original_text = self.check_updates_button.cget("text")
        self.check_updates_button.config(text="Checking...", state="disabled")
        self.progress_label.config(text="🔍 Checking for database updates...")
        
        def check_updates_worker():
            """Worker function to check updates in background."""
            try:
                has_updates, message = self.music_search_service.check_for_updates()
                
                # Update UI on main thread
                def update_ui():
                    self.check_updates_button.config(text=original_text, state="normal")
                    self.progress_label.config(text="🎵 Ready to convert your Apple Music files")
                    
                    if has_updates:
                        if messagebox.askyesno("Updates Available", f"{message}\n\nWould you like to download the latest database?"):
                            self.download_database()
                    else:
                        # Clarify what "up to date" means
                        info_message = f"{message}\n\nYour MusicBrainz database is current and ready to use for fast offline searches."
                        messagebox.showinfo("Database Status", info_message)
                
                self.root.after(0, update_ui)
                
            except Exception as e:
                def show_error():
                    self.check_updates_button.config(text=original_text, state="normal")
                    self.progress_label.config(text="🎵 Ready to convert your Apple Music files")
                    messagebox.showerror("Update Check Failed", f"Failed to check for updates: {str(e)}")
                
                self.root.after(0, show_error)
        
        # Run update check in background thread
        import threading
        threading.Thread(target=check_updates_worker, daemon=True).start()

    def delete_database(self):
        if messagebox.askyesno("Delete Database", "Are you sure you want to delete the MusicBrainz database?\n\nThis will free up disk space but you'll need to re-download it to use MusicBrainz search."):
            success = self.music_search_service.delete_database()
            if success:
                messagebox.showinfo("Success", "Database deleted successfully.")
            else:
                messagebox.showerror("Error", "Failed to delete database.")
            self.update_database_status()

    def reveal_database_location(self):
        db_path = self.music_search_service.get_database_path()
        if db_path:
            if platform.system() == 'Windows':
                os.startfile(os.path.dirname(db_path))
            elif platform.system() == 'Darwin':  # macOS
                import subprocess
                subprocess.call(('open', os.path.dirname(db_path)))
            else:  # Linux
                import subprocess
                subprocess.call(('xdg-open', os.path.dirname(db_path)))
        else:
            messagebox.showerror("Error", "Database path not found.")

    def manual_import_database(self):
        """Open manual import dialog for MusicBrainz database."""
        try:
            dialog = ManualImportDialog(self.root, self.music_search_service)
            success = dialog.show_and_wait()
            if success:
                self.update_database_status()
                messagebox.showinfo("Success", "Database imported successfully!")
        except Exception as e:
            print(f"Error opening manual import dialog: {e}")
            messagebox.showerror("Error", f"Failed to open manual import dialog: {str(e)}")

    def reprocess_missing_artists(self):
        """Reprocess entries that have missing or empty artist values using iTunes API."""
        
        # Check if we have a processed file
        if not hasattr(self, 'last_output_file') or not self.last_output_file:
            messagebox.showerror("❌ No File", "Please convert a file first.")
            return
        
        if not os.path.exists(self.last_output_file):
            messagebox.showerror("❌ File Missing", "Output file not found. Please convert again.")
            return
        
        # Show confirmation dialog
        response = messagebox.askyesno(
            "🔍 Search for Missing Artists",
            f"This will search for missing artist information in your converted file:\n{os.path.basename(self.last_output_file)}\n\n" +
            "• Uses iTunes API to find missing artists\n" +
            "• Rate-limited (may take some time for large files)\n" +
            "• Creates a backup of your original file\n\n" +
            "Continue?",
            icon='question'
        )
        
        if response:
            # Start reprocessing in a separate thread
            self.reprocessing_thread = threading.Thread(target=self._reprocess_missing_artists_worker)
            self.reprocessing_thread.start()

    def _reprocess_missing_artists_worker(self):
        """Worker method to reprocess missing artists."""
        try:
            # Read the CSV file
            import pandas as pd
            df = pd.read_csv(self.last_output_file)
            
            # Find rows with missing artists (empty, None, or 'Unknown Artist')
            missing_mask = df['Artist'].isin(['', 'Unknown Artist']) | df['Artist'].isna()
            missing_rows = df[missing_mask]
            
            if missing_rows.empty:
                self.root.after(0, lambda: messagebox.showinfo("✅ All Good!", 
                    "No missing artists found in your converted file. All tracks already have artist information!"))
                return
            
            total_missing = len(missing_rows)
            self.root.after(0, lambda: self.progress_label.config(text=f"Reprocessing {total_missing} missing artists..."))
            self.root.after(0, lambda: self.progress_var.set(0))
            
            found_count = 0
            failed_count = 0
            
            for idx, (row_idx, row) in enumerate(missing_rows.iterrows()):
                track_name = row['Track']
                album_name = row.get('Album', '')
                
                # Update progress
                progress = (idx / total_missing) * 100
                self.root.after(0, lambda p=progress, t=track_name: 
                    self.progress_label.config(text=f"Searching iTunes for: {t} ({p:.0f}%)"))
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                try:
                    # Search using iTunes API
                    artist = self._search_itunes_api(track_name, album_name)
                    
                    if artist and artist != "Unknown Artist":
                        # Update the dataframe
                        df.at[row_idx, 'Artist'] = artist
                        df.at[row_idx, 'Album Artist'] = artist  # Also update album artist
                        found_count += 1
                        self.root.after(0, lambda t=track_name, a=artist: 
                            print(f"Found artist for '{t}': {a}"))
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    print(f"Error searching for '{track_name}': {e}")
            
            # Save the updated file
            backup_file = self.last_output_file.replace('.csv', '_backup.csv')
            
            # Create backup
            import shutil
            shutil.copy2(self.last_output_file, backup_file)
            
            # Save updated data
            df.to_csv(self.last_output_file, index=False)
            
            # Show completion message
            self.root.after(0, lambda: self.progress_label.config(text="Reprocessing complete"))
            self.root.after(0, lambda: self.progress_var.set(100))
            
            completion_msg = f"🎵 Artist search complete!\n\n" + \
                           f"✅ Found artists: {found_count}\n" + \
                           f"❓ Still missing: {failed_count}\n" + \
                           f"📊 Total searched: {total_missing}\n\n" + \
                           f"💾 Original file backed up as:\n{os.path.basename(backup_file)}"
            
            self.root.after(0, lambda: messagebox.showinfo("🔍 Artist Search Complete", completion_msg))
            
        except Exception as e:
            error_msg = f"Error during artist search: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("❌ Artist Search Error", error_msg))
            self.root.after(0, lambda: self.progress_label.config(text="Artist search failed"))

    def load_entire_csv(self, file_path, file_type):
        """Load entire CSV file and return processed data."""
        try:
            # Detect encoding for robust CSV reading
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            encoding_used = 'utf-8'
            
            for encoding in encodings_to_try:
                try:
                    pd.read_csv(file_path, nrows=5, encoding=encoding)
                    encoding_used = encoding
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception:
                    continue
            
            # Load entire CSV
            df = pd.read_csv(file_path, encoding=encoding_used, dtype=str, na_values=['', 'nan', 'NaN', 'null', None])
            
            # Convert to list of track data with normalized format
            all_tracks = []
            for index, row in df.iterrows():
                track_data = self.normalize_track_data(row, file_type, index)
                if track_data:
                    all_tracks.append(track_data)
            
            return all_tracks
            
        except Exception as e:
            self.progress_label.config(text=f"❌ Error loading CSV: {str(e)}")
            return None
    
    def normalize_track_data(self, row, file_type, index):
        """Normalize track data from different CSV formats."""
        try:
            if file_type == 'generic':
                artist = row.get('Artist', '').strip() if pd.notna(row.get('Artist')) else ''
                track = row.get('Track', '').strip() if pd.notna(row.get('Track')) else ''
                album = row.get('Album', '').strip() if pd.notna(row.get('Album')) else ''
                duration = 180  # Default duration
                
            elif file_type == 'play-history':
                track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                if len(track_info) == 2:
                    artist, track = track_info
                else:
                    artist, track = '', row['Track Description']
                album = ''
                duration = 180
                
            elif file_type == 'recently-played':
                track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                if len(track_info) == 2:
                    artist, track = track_info
                else:
                    artist, track = '', row['Track Description']
                album = row.get('Container Description', '').strip() if pd.notna(row.get('Container Description')) else ''
                duration = 180
                
            elif file_type == 'play-activity':
                artist = row.get('Artist Name', '').strip() if pd.notna(row.get('Artist Name')) else ''
                track = row.get('Song Name', '').strip() if pd.notna(row.get('Song Name')) else ''
                album = row.get('Album Name', '').strip() if pd.notna(row.get('Album Name')) else ''
                duration = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180
            
            return {
                'artist': artist.strip(),
                'track': track.strip(),
                'album': album.strip(),
                'duration': duration,
                'index': index,
                'found_artist': None  # Will be filled during processing
            }
            
        except Exception as e:
            print(f"Error normalizing track data at index {index}: {e}")
            return None
    
    def process_with_musicbrainz(self, all_tracks, total_tracks):
        """Process all tracks with MusicBrainz database."""
        results = []
        missing_tracks = []
        
        for i, track_data in enumerate(all_tracks):
            # Check for process control
            while self.process_paused and not self.process_stopped:
                time.sleep(0.1)
            
            if self.process_stopped:
                break
            
            # Update progress
            progress = (i / total_tracks) * 50  # First 50% for MusicBrainz
            self.progress_var.set(progress)
            elapsed_str = self._get_elapsed_time_str()
            self.progress_label.config(text=f"🗄️ MusicBrainz: {i+1:,}/{total_tracks:,} tracks processed{elapsed_str}")
            self.root.update_idletasks()
            
            # Search with MusicBrainz if artist is missing
            if not track_data['artist']:
                found_artist = self.search_artist(track_data['track'], track_data['album'], use_musicbrainz_first=True)
                if found_artist:
                    track_data['found_artist'] = found_artist
                    self.musicbrainz_found += 1
                else:
                    missing_tracks.append(track_data)
            
            # Convert to final format
            final_track = self.convert_to_final_format(track_data, i, total_tracks)
            results.append(final_track)
            
            # Update stats display
            self.update_stats_display()
        
        return results, missing_tracks
    
    def process_missing_with_itunes(self, missing_tracks, completed_count, total_tracks):
        """Process missing tracks with iTunes API."""
        results = []
        
        for i, track_data in enumerate(missing_tracks):
            # Check for process control
            while self.process_paused and not self.process_stopped:
                time.sleep(0.1)
            
            if self.process_stopped:
                break
            
            # Update progress
            progress = 50 + ((i / len(missing_tracks)) * 50)  # Second 50% for iTunes
            self.progress_var.set(progress)
            elapsed_str = self._get_elapsed_time_str()
            self.progress_label.config(text=f"🌐 iTunes: {i+1:,}/{len(missing_tracks):,} missing artists searched{elapsed_str}")
            self.root.update_idletasks()
            
            # Search with iTunes
            try:
                found_artist = self._search_itunes_api(track_data['track'], track_data['album'])
                if found_artist:
                    track_data['found_artist'] = found_artist
                    self.itunes_found += 1
            except Exception as e:
                # Individual track lookup failed, track for retry reporting
                found_artist = None
                failed_request = {
                    'track': track_data['track'],
                    'album': track_data['album'],
                    'row_index': track_data['index'],
                    'error': str(e)
                }
                self.failed_requests.append(failed_request)
            
            # Update the corresponding track in results
            final_track = self.convert_to_final_format(track_data, track_data['index'], total_tracks)
            results.append(final_track)
            
            # Update stats display
            self.update_stats_display()
        
        return results
    
    def convert_to_final_format(self, track_data, index, total_tracks):
        """Convert track data to final CSV format."""
        # Use found artist or original artist
        final_artist = track_data['found_artist'] or track_data['artist']
        
        # Calculate timestamp (reverse chronological)
        current_timestamp = pd.Timestamp.now() - pd.Timedelta(seconds=track_data['duration'] * index)
        
        return [
            final_artist,
            track_data['track'],
            track_data['album'],
            current_timestamp,
            final_artist,  # Album artist
            track_data['duration']
        ]
    
    def finalize_processing(self, final_results, start_time):
        """Finalize processing and display results."""
        try:
            # Create DataFrame
            columns = ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration']
            self.processed_df = pd.DataFrame(final_results, columns=columns)
            
            # Display results
            csv_buffer = io.StringIO()
            self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
            csv_string = csv_buffer.getvalue()
            
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, csv_string)
            self.display_preview(self.processed_df.head(15))
            
            # Final stats
            total_time = time.time() - start_time
            total_tracks = len(final_results)
            found_count = self.musicbrainz_found + self.itunes_found
            missing_count = total_tracks - found_count
            
            self.progress_var.set(100)
            self.progress_label.config(text=f"✅ Complete! {total_tracks:,} tracks processed in {total_time:.1f}s")
            
            # Disable process controls
            self.process_pause_button.config(state='disabled')
            self.process_stop_button.config(state='disabled')
            
            # Show summary message
            message = f"✅ Conversion completed successfully!\n"
            message += f"📊 Processed {total_tracks:,} tracks in {total_time:.1f} seconds\n"
            message += f"🗄️ MusicBrainz found: {self.musicbrainz_found:,} artists\n"
            message += f"🌐 iTunes found: {self.itunes_found:,} artists"
            
            if missing_count > 0:
                message += f"\n❓ {missing_count:,} tracks still missing artist info"
            
            # Add failed request reporting
            if self.failed_requests:
                message += f"\n⚠️ {len(self.failed_requests)} iTunes API requests failed (retryable)"
                
                # Optionally show details of failed requests
                if len(self.failed_requests) <= 5:  # Show details if small number
                    message += "\nFailed tracks:"
                    for req in self.failed_requests:
                        message += f"\n  • {req['track']} (Row {req['row_index'] + 1})"
                
                # Clear failed requests after reporting
                self.failed_requests.clear()
            
            self.message_label.config(text=message, foreground="green")
            
        except Exception as e:
            self.progress_label.config(text=f"❌ Error finalizing: {str(e)}")

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Apple Music Play History Converter")
    app = CSVProcessorApp(root)
    root.mainloop()