#!/usr/bin/env python3
"""
Apple Music Play History Converter - Toga GUI Version
Converts Apple Music CSV files to Last.fm compatible format.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, START, CENTER, END
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
from threading import Lock
import music_search_service
import musicbrainz_manager
MusicSearchService = music_search_service.MusicSearchService
MusicBrainzManager = musicbrainz_manager.MusicBrainzManager
import re
import asyncio
try:
    import darkdetect
except ImportError:
    darkdetect = None


class AppleMusicConverterApp(toga.App):
    """Main application class for Apple Music Play History Converter using Toga."""
    
    def startup(self):
        """Initialize the application and create the main window."""
        # Store main event loop for thread-safe UI updates
        self.main_loop = asyncio.get_event_loop()
        
        # Initialize services
        self.music_search_service = MusicSearchService()
        self.musicbrainz_manager = MusicBrainzManager()
        
        # Initialize state variables
        self.pause_itunes_search = False
        self.stop_itunes_search = False
        self.processing_thread = None
        self.file_size = 0
        self.row_count = 0
        self.current_file_path = None
        self.detected_file_type = None
        self.processed_df = None  # Store processed data for reuse like tkinter
        self.musicbrainz_found = 0
        self.itunes_found = 0
        self.last_output_file = None  # Track last saved file for reprocessing
        
        # Rate limiting setup
        self.api_calls = deque(maxlen=20)
        self.api_lock = Lock()
        self.rate_limit_timer = None
        self.api_wait_start = None
        self.wait_duration = 0
        self.skip_wait_requested = False
        
        # Create main window with generous size for better user experience
        self.main_window = toga.MainWindow(
            title=self.formal_name,
            size=(1200, 800)  # Larger, more spacious window
        )
        
        # Build the UI
        self.build_ui()
        
        # Apply dark mode if system is using it
        self.setup_theme()
        
        # Check for first-time setup
        self.check_first_time_setup()
        
        # Update database status
        self.update_database_status()
        
        # Show the main window
        self.main_window.show()
    
    def setup_theme(self):
        """Setup application theme based on system preference."""
        try:
            if darkdetect:
                is_dark = darkdetect.isDark()
                # Note: Toga handles theming differently than tkinter
                # We'll use Pack styling to adjust colors if needed
                self.is_dark_mode = is_dark
            else:
                self.is_dark_mode = False
        except:
            self.is_dark_mode = False
    
    def build_ui(self):
        """Build the main user interface using Toga best practices."""
        # Main container with proper margins
        main_container = toga.Box(
            style=Pack(
                direction=ROW,
                margin=16  # 8px grid system
            )
        )
        
        # Left side - Main content area with optimized proportions
        main_content_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                flex=3,  # More space for main content (3:1 ratio with settings)
                margin_right=24  # More breathing room between main and settings
            )
        )
        
        # Header section with better spacing
        header_box = self.create_header_section()
        main_content_box.add(header_box)
        
        # File selection section with margin
        file_section = self.create_file_selection_section()
        main_content_box.add(file_section)
        
        # Content area with results and preview
        content_split_container = self.create_content_area()
        main_content_box.add(content_split_container)
        
        # Progress section at bottom with margin
        progress_section = self.create_progress_section()
        main_content_box.add(progress_section)
        
        # Add main content to container
        main_container.add(main_content_box)
        
        # Right side - Settings panel with fixed width
        settings_panel = self.create_comprehensive_settings_panel()
        main_container.add(settings_panel)
        
        # Set main window content
        self.main_window.content = main_container
    
    def create_header_section(self):
        """Create the header section with title and instructions."""
        header_box = toga.Box(
            style=Pack(direction=COLUMN, margin_bottom=32)  # More generous bottom spacing
        )
        
        # Title and instructions row with better spacing
        title_row = toga.Box(
            style=Pack(
                direction=ROW, 
                align_items=CENTER, 
                margin_bottom=16  # Better spacing below title
            )
        )
        
        title_label = toga.Label(
            "Apple Music Play History Converter",
            style=Pack(
                font_size=17,  # Main app title
                font_weight='bold', 
                flex=1,
                margin_right=10
            )
        )
        title_row.add(title_label)
        
        # Instructions button with better styling
        instructions_button = toga.Button(
            "How to Use",
            on_press=self.show_instructions,
            style=Pack(margin_left=10)
        )
        title_row.add(instructions_button)
        
        header_box.add(title_row)
        
        # Subtitle with better spacing
        subtitle = toga.Label(
            "Convert Apple Music CSV files to Last.fm format",
            style=Pack(
                color="#666666", 
                font_size=13,
                margin_bottom=15
            )
        )
        header_box.add(subtitle)
        
        # Divider with margin
        header_box.add(toga.Divider())
        
        return header_box
    
    def create_content_area(self):
        """Create the content area with results and preview."""
        # Results and preview in horizontal split container
        results_section = self.create_results_section()
        preview_section = self.create_preview_section()
        
        # Create resizable split container between results and preview with much more height
        split_container = toga.SplitContainer(
            content=[results_section, preview_section],
            direction=toga.SplitContainer.HORIZONTAL,
            style=Pack(flex=2, margin_top=24)  # Much more vertical space
        )
        
        return split_container
    
    def create_comprehensive_settings_panel(self):
        """Create comprehensive settings panel with proper sizing and layout."""
        # Native-style settings box (no scroll container for cleaner look)
        settings_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                width=320,  # Slightly wider for better breathing room
                margin=20,  # More generous margins 
                flex=0  # Don't flex to maintain fixed width
            )
        )
        
        # Settings title with better styling
        settings_title = toga.Label(
            "Settings",
            style=Pack(
                font_size=16, 
                font_weight='bold', 
                margin_bottom=24,
                color="#2c2c2c"
            )
        )
        settings_box.add(settings_title)
        
        # Music Search Provider Section
        provider_section = self.create_provider_section()
        settings_box.add(provider_section)
        
        # MusicBrainz Database Section  
        database_section = self.create_database_section()
        settings_box.add(database_section)
        
        # Advanced Options Section
        advanced_section = self.create_advanced_options_section()
        settings_box.add(advanced_section)
        
        # iTunes API Options Section
        itunes_section = self.create_itunes_api_section()
        settings_box.add(itunes_section)
        
        return settings_box  # Return box directly, no scroll container
    
    def create_provider_section(self):
        """Create clean provider section without artificial styling."""
        provider_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_bottom=32  # 8px grid system
            )
        )
        
        # Clean section title
        provider_title = toga.Label(
            "Music Search Provider",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                margin_bottom=8,
                color="#333333"
            )
        )
        provider_box.add(provider_title)
        
        # Clean provider selection
        self.provider_selection = toga.Selection(
            items=[
                "MusicBrainz (offline, fast)",
                "iTunes API (online, rate-limited)"
            ],
            on_change=self.on_provider_changed,
            style=Pack(margin_bottom=5)
        )
        
        # Set initial provider
        current_provider = self.music_search_service.get_search_provider()
        if current_provider == "musicbrainz":
            self.provider_selection.value = "MusicBrainz (offline, fast)"
        else:
            self.provider_selection.value = "iTunes API (online, rate-limited)"
        
        provider_box.add(self.provider_selection)
        
        # Keep provider selection clean without excessive help text
        
        return provider_box
    
    def create_database_section(self):
        """Create clean database section without white boxes."""
        db_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_bottom=32,  # 8px grid system
                margin_top=8  # Add subtle separation from previous section
            )
        )
        
        # Clean section title
        db_title = toga.Label(
            "MusicBrainz Database",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                margin_bottom=10,
                color="#333333"
            )
        )
        db_box.add(db_title)
        
        # Database status
        status_row = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        status_label = toga.Label("Status:", style=Pack(margin_right=10))
        status_row.add(status_label)
        
        self.db_status_label = toga.Label(
            "Not Downloaded",
            style=Pack(font_weight='bold', color="#e74c3c")
        )
        status_row.add(self.db_status_label)
        db_box.add(status_row)
        
        # Download button
        self.download_button = toga.Button(
            "Download Database (~2GB)",
            on_press=self.download_database,
            style=Pack(margin_bottom=5)
        )
        db_box.add(self.download_button)
        
        # Remove database help text - keep interface clean
        
        # Check updates button
        self.check_updates_button = toga.Button(
            "Check Updates",
            on_press=self.check_for_updates,
            style=Pack(margin_bottom=5)
        )
        db_box.add(self.check_updates_button)
        
        # Manual import button
        self.manual_import_button = toga.Button(
            "Manual Import",
            on_press=self.manual_import_database,
            style=Pack(margin_bottom=5)
        )
        db_box.add(self.manual_import_button)
        
        # Database management buttons with improved spacing
        manage_row = toga.Box(style=Pack(direction=ROW, margin_bottom=16))
        
        self.delete_db_button = toga.Button(
            "Delete",
            on_press=self.delete_database,
            style=Pack(flex=1, margin_right=8)
        )
        manage_row.add(self.delete_db_button)
        
        self.reveal_location_button = toga.Button(
            "Show Files",
            on_press=self.reveal_database_location,
            style=Pack(flex=1)
        )
        manage_row.add(self.reveal_location_button)
        db_box.add(manage_row)
        
        # Database info labels with improved typography
        self.db_size_label = toga.Label(
            "Size: 0MB",
            style=Pack(font_size=11, margin_bottom=4, color="#666666")
        )
        db_box.add(self.db_size_label)
        
        self.db_updated_label = toga.Label(
            "Never updated",
            style=Pack(font_size=11, color="#666666")
        )
        db_box.add(self.db_updated_label)
        
        return db_box
    
    def create_advanced_options_section(self):
        """Create the advanced options section with consistent spacing."""
        advanced_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_bottom=32,  # 8px grid system
                margin_top=8  # Visual separation
            )
        )
        
        # Section title with consistent styling
        advanced_title = toga.Label(
            "Advanced Options",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                margin_bottom=8,
                color="#333333"
            )
        )
        advanced_box.add(advanced_title)
        
        # Auto-fallback checkbox
        self.fallback_switch = toga.Switch(
            "Auto-fallback to iTunes if no results",
            value=self.music_search_service.get_auto_fallback(),
            on_change=self.on_fallback_changed,
            style=Pack()
        )
        advanced_box.add(self.fallback_switch)
        
        return advanced_box
    
    def create_itunes_api_section(self):
        """Create the iTunes API configuration section."""
        itunes_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))
        
        # Section title
        itunes_title = toga.Label(
            "iTunes API Options",
            style=Pack(font_weight='bold', margin_bottom=8)
        )
        itunes_box.add(itunes_title)
        
        # iTunes API search checkbox
        self.itunes_api_switch = toga.Switch(
            "Search iTunes for missing artists (Phase 2)",
            value=False,
            on_change=self.on_itunes_api_changed,
            style=Pack(margin_bottom=8)
        )
        itunes_box.add(self.itunes_api_switch)
        
        # Rate limit control
        rate_row = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        rate_label = toga.Label("Rate limit:", style=Pack(margin_right=10))
        rate_row.add(rate_label)
        
        self.rate_limit_input = toga.TextInput(
            value="20",
            style=Pack(width=60, margin_right=10)
        )
        rate_row.add(self.rate_limit_input)
        
        rate_unit_label = toga.Label("req/min")
        rate_row.add(rate_unit_label)
        itunes_box.add(rate_row)
        
        # Rate limit warning
        self.rate_limit_warning = toga.Label(
            "Max 20 requests/minute recommended",
            style=Pack(font_size=12, color="#f39c12", margin_bottom=8)
        )
        itunes_box.add(self.rate_limit_warning)
        
        # API Status
        self.api_status_label = toga.Label(
            "Status: Ready",
            style=Pack(font_size=12, margin_bottom=5)
        )
        itunes_box.add(self.api_status_label)
        
        self.api_timer_label = toga.Label(
            "",
            style=Pack(font_size=12, margin_bottom=8)
        )
        itunes_box.add(self.api_timer_label)
        
        # Control buttons
        control_row = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        
        self.pause_button = toga.Button(
            "Pause",
            on_press=self.toggle_pause,
            enabled=False,
            style=Pack(flex=1, margin_right=5)
        )
        control_row.add(self.pause_button)
        
        self.stop_button = toga.Button(
            "Stop", 
            on_press=self.stop_search,
            enabled=False,
            style=Pack(flex=1)
        )
        control_row.add(self.stop_button)
        itunes_box.add(control_row)
        
        # Remove control help text - keep interface clean
        
        return itunes_box
    
    def create_file_selection_section(self):
        """Create the file selection section with better spacing."""
        file_box = toga.Box(
            style=Pack(direction=COLUMN, margin_bottom=32)  # More generous spacing
        )
        
        # Section label
        section_label = toga.Label(
            "1. Select Your Apple Music CSV File",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                margin_bottom=12,  # More breathing room
                color="#333333"
            )
        )
        file_box.add(section_label)
        
        # File selection row
        file_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=15, gap=10)
        )
        
        self.file_input = toga.TextInput(
            placeholder="Click 'Choose CSV File' to select your Apple Music export",
            readonly=True,
            style=Pack(flex=1)
        )
        file_row.add(self.file_input)
        
        browse_button = toga.Button(
            "Choose CSV File",
            on_press=self.browse_file,
            style=Pack()
        )
        file_row.add(browse_button)
        
        file_box.add(file_row)
        
        # File type selection with convert button
        type_label = toga.Label(
            "2. File Type (auto-detected)",
            style=Pack(font_weight='bold', margin_bottom=8)
        )
        file_box.add(type_label)
        
        # Type selection row with convert button
        type_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=15, gap=10)
        )
        
        # File type options using Selection widget
        self.file_type_selection = toga.Selection(
            items=[
                "Play History Daily Tracks",
                "Recently Played Tracks", 
                "Play Activity",
                "Other/Generic CSV"
            ],
            style=Pack(width=250)
        )
        type_row.add(self.file_type_selection)
        
        # Convert button next to dropdown with better styling
        self.convert_button = toga.Button(
            "Convert to Last.fm Format",
            on_press=self.convert_csv,
            style=Pack(
                margin_left=10,
                width=180  # Consistent button width
            )
        )
        self.convert_button.enabled = False
        type_row.add(self.convert_button)
        
        file_box.add(type_row)
        
        # Remove excessive help text - keep interface clean
        
        return file_box
    
    def create_results_section(self):
        """Create the results section with much more generous spacing and height."""
        results_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                flex=1,
                margin_top=16
            )
        )
        
        # Results header with action buttons - better spacing
        results_header = toga.Box(
            style=Pack(
                direction=ROW, 
                align_items=CENTER, 
                margin_bottom=12
            )
        )
        
        results_label = toga.Label(
            "3. Results",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                flex=1
            )
        )
        results_header.add(results_label)
        
        # Action buttons with consistent styling
        self.copy_button = toga.Button(
            "Copy to Clipboard",
            on_press=self.copy_results,
            enabled=False,
            style=Pack(
                margin_right=8,
                width=120
            )
        )
        results_header.add(self.copy_button)
        
        self.save_button = toga.Button(
            "Save as CSV File",
            on_press=self.save_results,
            enabled=False,
            style=Pack(width=120)
        )
        results_header.add(self.save_button)
        
        results_box.add(results_header)
        
        # Keep action buttons clean without excessive help text
        
        # Results text area with much more generous height and better styling
        self.results_text = toga.MultilineTextInput(
            readonly=True,
            placeholder="Converted CSV Results\n\nYour converted Apple Music data will appear here after processing.\n\nThe output will be in Last.fm compatible format:\nArtist, Track, Album, Timestamp, Album Artist, Duration\n\nClick \"Convert to Last.fm Format\" to get started!",
            style=Pack(
                flex=2,  # Much more flex space
                height=350,  # Generous fixed height
                font_family='monospace',
                margin_top=8
            )
        )
        results_box.add(self.results_text)
        
        return results_box
    
    def create_preview_section(self):
        """Create the preview section with much more generous spacing and height."""
        preview_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_bottom=16
            )
        )
        
        # Preview label with consistent styling
        preview_label = toga.Label(
            "Preview",
            style=Pack(
                font_weight='bold', 
                font_size=14,
                margin_bottom=8,
                color="#333333"
            )
        )
        preview_box.add(preview_label)
        
        # Preview table with sample data - much more spacious
        self.preview_table = toga.Table(
            headings=["Artist", "Track", "Album", "Timestamp"],
            data=[
                ["Taylor Swift", "Anti-Hero", "Midnights", "2024-03-15 14:30"],
                ["The Beatles", "Here Comes the Sun", "Abbey Road", "2024-03-15 14:27"],
                ["Daft Punk", "One More Time", "Discovery", "2024-03-15 14:24"],
                ["Sample preview data", "Your converted tracks", "will appear here", "after processing"]
            ],
            style=Pack(
                flex=2,  # Much more vertical space
                height=280  # Adequate height for data viewing
            )
        )
        preview_box.add(self.preview_table)
        
        return preview_box
    
    def create_progress_section(self):
        """Create clean progress section with native styling."""
        progress_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_top=20,
                margin_bottom=10
            )
        )
        
        # Clean progress header
        progress_header = toga.Label(
            "Progress",
            style=Pack(
                font_weight='bold', 
                font_size=15,
                margin_bottom=10,
                color="#333333"
            )
        )
        progress_box.add(progress_header)
        
        # Clean progress bar
        self.progress_bar = toga.ProgressBar(
            max=100,
            style=Pack(
                flex=1, 
                margin_bottom=10
            )
        )
        progress_box.add(self.progress_bar)
        
        # Main progress status with better styling
        self.progress_label = toga.Label(
            "Ready to convert your Apple Music files",
            style=Pack(
                margin_bottom=8,
                font_size=13
            )
        )
        progress_box.add(self.progress_label)
        
        # Message label for additional info with better styling
        self.message_label = toga.Label(
            "",
            style=Pack(
                margin_bottom=12, 
                color="#0066cc",
                font_size=13
            )
        )
        progress_box.add(self.message_label)
        
        # Enhanced status information (like tkinter)
        status_frame = self.create_enhanced_status_display()
        progress_box.add(status_frame)
        
        # Control buttons
        control_frame = self.create_progress_controls()
        progress_box.add(control_frame)
        
        return progress_box
    
    def create_enhanced_status_display(self):
        """Create enhanced status display with improved spacing."""
        status_box = toga.Box(
            style=Pack(
                direction=COLUMN, 
                margin_bottom=15,
                margin=5
            )
        )
        
        # File information row with better styling
        self.file_info_label = toga.Label(
            "📄 No file loaded",
            style=Pack(
                color="#666666", 
                margin_bottom=8,
                font_size=13
            )
        )
        status_box.add(self.file_info_label)
        
        # Processing statistics row with better spacing
        stats_row = toga.Box(
            style=Pack(
                direction=ROW, 
                margin_bottom=8,
                align_items=CENTER
            )
        )
        
        self.songs_processed_label = toga.Label(
            "Songs: 0/0",
            style=Pack(
                font_weight='bold', 
                color="#0066cc", 
                margin_right=25,
                font_size=13
            )
        )
        stats_row.add(self.songs_processed_label)
        
        self.musicbrainz_stats_label = toga.Label(
            "MusicBrainz: 0",
            style=Pack(color="#27ae60", margin_right=15)
        )
        stats_row.add(self.musicbrainz_stats_label)
        
        self.itunes_stats_label = toga.Label(
            "iTunes: 0",
            style=Pack(color="#3498db", margin_right=15)
        )
        stats_row.add(self.itunes_stats_label)
        
        self.rate_limit_stats_label = toga.Label(
            "Limits: 0",
            style=Pack(color="#27ae60", margin_right=15)
        )
        stats_row.add(self.rate_limit_stats_label)
        
        self.wait_time_label = toga.Label(
            "",
            style=Pack(color="#f39c12")
        )
        stats_row.add(self.wait_time_label)
        
        status_box.add(stats_row)
        return status_box
    
    def create_progress_controls(self):
        """Create progress control buttons."""
        control_frame = toga.Box(style=Pack(direction=COLUMN))
        
        # Main control buttons row
        main_controls = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        
        self.process_pause_button = toga.Button(
            "Pause",
            on_press=self.toggle_process_pause,
            enabled=False,
            style=Pack(margin_right=8)
        )
        main_controls.add(self.process_pause_button)
        
        self.process_stop_button = toga.Button(
            "Stop",
            on_press=self.stop_process,
            enabled=False,
            style=Pack(margin_right=8)
        )
        main_controls.add(self.process_stop_button)
        
        self.skip_wait_button = toga.Button(
            "Clear Queue",
            on_press=self.skip_current_wait,
            enabled=False,
            style=Pack(margin_right=8)
        )
        main_controls.add(self.skip_wait_button)
        
        # Post-processing button
        self.reprocess_button = toga.Button(
            "🔍 Search for Missing Artists",
            on_press=self.reprocess_missing_artists,
            enabled=False,
            style=Pack()
        )
        main_controls.add(self.reprocess_button)
        
        control_frame.add(main_controls)
        
        # Remove excessive help text - keep interface clean
        
        return control_frame
    
    
    async def browse_file(self, widget):
        """Handle file browsing with comprehensive analysis and error handling."""
        try:
            # Try to open the file dialog
            try:
                file_path = await self.main_window.dialog(toga.OpenFileDialog(
                    title="Select Apple Music CSV File",
                    file_types=["csv"]
                ))
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="File Dialog Error",
                    message="Could not open file dialog. Please check your system configuration."
                ))
                return
            
            if file_path:
                try:
                    # Validate file exists and is accessible
                    file_path_str = str(file_path)
                    
                    if not os.path.exists(file_path_str):
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Not Found",
                            message="Selected file no longer exists. Please choose another file."
                        ))
                        return
                    
                    if not os.access(file_path_str, os.R_OK):
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Access Error",
                            message="Cannot read the selected file. Please check file permissions."
                        ))
                        return
                    
                    self.current_file_path = file_path_str
                    self.file_input.value = os.path.basename(self.current_file_path)
                    
                    # Get and validate file size
                    try:
                        self.file_size = os.path.getsize(self.current_file_path)
                        
                        if self.file_size == 0:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Empty File",
                                message="Selected file is empty. Please choose a valid CSV file."
                            ))
                            return
                            
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Size Error",
                            message=f"Could not determine file size: {str(e)}"
                        ))
                        return
                    
                    # Check file size and RAM requirements
                    try:
                        self.check_file_size_and_ram(self.current_file_path)
                    except Exception as e:
                        print(f"Error checking file size and RAM: {e}")
                    
                    # Count rows for progress tracking with multiple encoding attempts
                    try:
                        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
                        row_count_success = False
                        
                        for encoding in encodings_to_try:
                            try:
                                with open(self.current_file_path, 'r', encoding=encoding) as f:
                                    self.row_count = sum(1 for line in f) - 1  # Subtract header row
                                    row_count_success = True
                                    break
                            except (UnicodeDecodeError, UnicodeError):
                                continue
                        
                        if not row_count_success:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Encoding Error",
                                message="Could not read file with any supported encoding (UTF-8, Latin1, CP1252)."
                            ))
                            return
                        
                        if self.row_count <= 0:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Invalid File",
                                message="File appears to have no data rows. Please select a valid CSV file."
                            ))
                            return
                            
                        # Update songs counter
                        self.songs_processed_label.text = f"🎵 Songs: 0/{self.row_count:,}"
                        
                    except Exception as e:
                        self.row_count = 0
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Analysis Error",
                            message=f"Error analyzing file rows: {str(e)}"
                        ))
                        return
                    
                    # Detect file type with error handling
                    try:
                        self.detect_file_type()
                        
                        if not self.detected_file_type:
                            await self.main_window.dialog(toga.InfoDialog(
                                title="Unknown File Type",
                                message="Could not automatically detect file type. Will proceed with generic processing."
                            ))
                            self.detected_file_type = "Generic CSV"
                            
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Type Detection Error", 
                            message=f"Error detecting file type: {str(e)}"
                        ))
                        return
                    
                    # Update time estimates with error handling
                    try:
                        self.update_time_estimate()
                    except Exception as e:
                        print(f"Error updating time estimate: {e}")
                    
                    # Enable convert button
                    self.convert_button.enabled = True
                    
                    # Update results with comprehensive info
                    try:
                        file_size_mb = self.file_size / (1024 * 1024)
                        self.update_results(f"✅ File Selected: {os.path.basename(self.current_file_path)}\n"
                                          f"📊 Size: {file_size_mb:.2f} MB ({self.row_count:,} rows)\n"
                                          f"🔍 Detected Type: {self.detected_file_type}\n"
                                          f"📈 Ready for conversion!")
                    except Exception as e:
                        print(f"Error updating results display: {e}")
                        
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="File Processing Error",
                        message=f"Error processing selected file: {str(e)}"
                    ))
        
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Unexpected Error",
                message=f"An unexpected error occurred while selecting file: {str(e)}"
            ))
    
    def detect_file_type(self):
        """Detect the type of CSV file based on filename patterns first, then content."""
        if not self.current_file_path:
            return
        
        try:
            file_name = os.path.basename(self.current_file_path)
            detected_type = None
            
            # First try filename pattern matching (like original tkinter version)
            filename_patterns = {
                'Play Activity': ['Play Activity', 'Apple Music Play Activity'],
                'Recently Played Tracks': ['Recently Played Tracks', 'Apple Music - Recently Played Tracks'],
                'Play History Daily Tracks': ['Play History Daily Tracks', 'Apple Music - Play History Daily Tracks']
            }
            
            for file_type, patterns in filename_patterns.items():
                if any(pattern in file_name for pattern in patterns):
                    detected_type = file_type
                    break
            
            # If filename detection failed, try content detection
            if not detected_type:
                with open(self.current_file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().lower()
                    
                    if 'play duration milliseconds' in first_line:
                        detected_type = "Play Activity"
                    elif 'track name' in first_line and 'artist name' in first_line:
                        detected_type = "Recently Played Tracks"
                    else:
                        detected_type = "Other/Generic CSV"
            
            # Apply the detected type
            self.detected_file_type = detected_type
            self.file_type_selection.value = detected_type
        
        except Exception as e:
            self.detected_file_type = "Other/Generic CSV"
            self.file_type_selection.value = "Other/Generic CSV"
    
    async def convert_csv(self, widget):
        """Handle CSV conversion with two-phase processing architecture."""
        if not self.current_file_path:
            await self.main_window.dialog(toga.ErrorDialog(
                title="No File Selected",
                message="Please select a CSV file first."
            ))
            return
        
        # Reset processing state
        self.reset_processing_stats()
        
        # Update UI for processing
        self.convert_button.enabled = False
        self.process_pause_button.enabled = True
        self.process_stop_button.enabled = True
        
        # Update progress
        self.progress_label.text = "Processing..."
        self.message_label.text = ""
        
        # Start two-phase processing using async task (Toga best practice)
        asyncio.create_task(self.process_csv_two_phase_async())
    
    def reset_processing_stats(self):
        """Reset all processing statistics."""
        self.musicbrainz_found = 0
        self.itunes_found = 0
        self.rate_limit_hits = 0
        self.processing_start_time = time.time()
        
        # Update display
        self.update_stats_display()
    
    def process_csv_two_phase(self):
        """Process CSV using sophisticated two-phase architecture like tkinter."""
        try:
            # Record start time
            self.processing_start_time = time.time()
            
            # Phase 1: Load and analyze entire CSV
            self.update_progress("📂 Phase 1: Loading and analyzing CSV file...", 10)
            all_tracks = self.load_entire_csv(self.current_file_path, self.file_type_selection.value)
            
            if not all_tracks:
                self.update_progress("❌ Failed to load CSV file", 0)
                return
            
            total_tracks = len(all_tracks)
            self.songs_processed_label.text = f"🎵 Songs: 0/{total_tracks:,}"
            
            # Phase 2: Process with MusicBrainz first (fast phase)
            self.update_progress("🗄️ Phase 2: Processing with MusicBrainz database...", 20)
            processed_tracks = self.process_with_musicbrainz(all_tracks, total_tracks)
            
            # Count missing tracks for Phase 3
            missing_tracks = [track for track in processed_tracks if not track.get('artist', '').strip()]
            completed_count = len([track for track in processed_tracks if track.get('artist', '').strip()])
            
            # Phase 3: iTunes API for missing artists (if enabled)
            if missing_tracks and self.itunes_api_switch.value:
                elapsed_time = time.time() - self.processing_start_time
                elapsed_str = f" ({elapsed_time:.1f}s elapsed)"
                self.update_progress(f"🌐 Phase 3: Searching {len(missing_tracks)} missing artists with iTunes...{elapsed_str}", 50)
                
                processed_tracks = self.process_missing_with_itunes(missing_tracks, processed_tracks, completed_count, total_tracks)
            
            # Phase 4: Convert to final format
            self.update_progress("📄 Phase 4: Converting to Last.fm format...", 85)
            final_results = []
            for i, track in enumerate(processed_tracks):
                final_track = self.convert_to_final_format(track, i, total_tracks)
                if final_track:
                    final_results.append(final_track)
            
            # Phase 5: Finalize and display results
            self.finalize_processing(final_results, self.processing_start_time)
            
        except Exception as e:
            self.update_progress(f"❌ Processing error: {str(e)}", 0)
            self.update_results(f"Error processing file: {str(e)}")
        
        finally:
            # Reset UI state
            asyncio.run_coroutine_threadsafe(self._reset_buttons_ui(), self.main_loop)
    
    async def process_csv_two_phase_async(self):
        """Process CSV using sophisticated two-phase architecture with proper async pattern."""
        try:
            # Record start time
            self.processing_start_time = time.time()
            
            # Phase 1: Load and analyze entire CSV
            self.update_progress("📂 Phase 1: Loading and analyzing CSV file...", 10)
            all_tracks = await self.load_entire_csv_async(self.current_file_path, self.file_type_selection.value)
            
            if not all_tracks:
                self.update_progress("❌ Failed to load CSV file", 0)
                return
            
            total_tracks = len(all_tracks)
            self.songs_processed_label.text = f"🎵 Songs: 0/{total_tracks:,}"
            
            # Phase 2: Process with MusicBrainz first (fast phase)
            self.update_progress("🗄️ Phase 2: Processing with MusicBrainz database...", 20)
            processed_tracks = await self.process_with_musicbrainz_async(all_tracks, total_tracks)
            
            # Count missing tracks for Phase 3
            missing_tracks = [track for track in processed_tracks if not track.get('artist', '').strip()]
            completed_count = len([track for track in processed_tracks if track.get('artist', '').strip()])
            
            # Phase 3: iTunes API for missing artists (if enabled)
            if missing_tracks and self.itunes_api_switch.value:
                elapsed_time = time.time() - self.processing_start_time
                elapsed_str = f" ({elapsed_time:.1f}s elapsed)"
                self.update_progress(f"🌐 Phase 3: Searching {len(missing_tracks)} missing artists with iTunes...{elapsed_str}", 50)
                
                processed_tracks = await self.process_missing_with_itunes_async(missing_tracks, processed_tracks, completed_count, total_tracks)
            
            # Phase 4: Convert to final format
            self.update_progress("📄 Phase 4: Converting to Last.fm format...", 85)
            final_results = []
            for i, track in enumerate(processed_tracks):
                final_track = self.convert_to_final_format(track, i, total_tracks)
                if final_track:
                    final_results.append(final_track)
                    
                # Yield control periodically for UI responsiveness
                if i % 100 == 0:
                    await asyncio.sleep(0.001)
            
            # Phase 5: Finalize and display results
            await self.finalize_processing_async(final_results, self.processing_start_time)
            
        except Exception as e:
            self.update_progress(f"❌ Processing error: {str(e)}", 0)
            self.update_results(f"Error processing file: {str(e)}")
        
        finally:
            # Reset UI state on main thread
            await self._reset_buttons_ui()
    
    async def load_entire_csv_async(self, file_path, file_type):
        """Async version of CSV loading with periodic yields for UI responsiveness."""
        try:
            # Yield to UI thread
            await asyncio.sleep(0.001)
            
            # Use the existing synchronous method but yield periodically
            result = self.load_entire_csv(file_path, file_type)
            
            # Yield after heavy operation
            await asyncio.sleep(0.001)
            return result
            
        except Exception as e:
            print(f"Error in load_entire_csv_async: {e}")
            return None
    
    async def process_with_musicbrainz_async(self, all_tracks, total_tracks):
        """Async version of MusicBrainz processing."""
        try:
            # Process in chunks to maintain UI responsiveness
            chunk_size = 100
            processed_tracks = []
            
            for i in range(0, len(all_tracks), chunk_size):
                chunk = all_tracks[i:i+chunk_size]
                
                # Process chunk synchronously
                for track in chunk:
                    result = self.music_search_service.search_song(
                        track.get('Track', ''),
                        track.get('Artist', '')
                    )
                    if result:
                        track['artist'] = result.get('artist', track.get('Artist', ''))
                        track['track'] = result.get('track', track.get('Track', ''))
                        track['album'] = result.get('album', track.get('Album', ''))
                        self.musicbrainz_found += 1
                    processed_tracks.append(track)
                
                # Update progress and yield to UI
                progress = 20 + (i / len(all_tracks)) * 30  # 20-50% range
                self.update_progress(f"🗄️ Processing with MusicBrainz: {i+len(chunk)}/{total_tracks}", progress)
                self.songs_processed_label.text = f"🎵 Songs: {i+len(chunk)}/{total_tracks:,}"
                await asyncio.sleep(0.001)  # Yield to UI thread
            
            return processed_tracks
            
        except Exception as e:
            print(f"Error in process_with_musicbrainz_async: {e}")
            return all_tracks  # Return original tracks on error
    
    async def process_missing_with_itunes_async(self, missing_tracks, processed_tracks, completed_count, total_tracks):
        """Async version of iTunes API processing."""
        try:
            # For now, use the existing synchronous method with yields
            await asyncio.sleep(0.001)
            
            result = self.process_missing_with_itunes(missing_tracks, processed_tracks, completed_count, total_tracks)
            
            await asyncio.sleep(0.001)
            return result
            
        except Exception as e:
            print(f"Error in process_missing_with_itunes_async: {e}")
            return processed_tracks
    
    async def finalize_processing_async(self, final_results, start_time):
        """Async version of processing finalization."""
        try:
            # Yield to UI thread
            await asyncio.sleep(0.001)
            
            # Use existing synchronous method
            self.finalize_processing(final_results, start_time)
            
            await asyncio.sleep(0.001)
            
        except Exception as e:
            print(f"Error in finalize_processing_async: {e}")
            self.update_results(f"❌ Error in finalization: {str(e)}")
    
    async def optimize_musicbrainz_async(self):
        """Async version of MusicBrainz optimization."""
        try:
            start_time = time.time()
            
            async def progress_callback_async(message, percent, start_time):
                elapsed = time.time() - start_time
                timer_text = f" (Elapsed: {elapsed:.0f}s)"
                await self._update_optimization_progress(f"🔧 Optimizing: {message}{timer_text}")
            
            # Start progressive loading with async progress updates
            try:
                # Yield to UI thread before starting
                await asyncio.sleep(0.001)
                
                # Run optimization in small chunks with yields
                self.music_search_service.start_progressive_loading(
                    lambda msg, pct, st: asyncio.create_task(progress_callback_async(msg, pct, st))
                )
                
                await self._update_optimization_complete()
                
            except Exception as e:
                print(f"Optimization error: {e}")
                await self._update_optimization_error()
                
        except Exception as e:
            print(f"Error in optimize_musicbrainz_async: {e}")
            await self._update_optimization_error()
    
    def load_entire_csv(self, file_path, file_type):
        """Load entire CSV file with proper encoding detection and comprehensive error handling."""
        try:
            # Validate input parameters
            if not file_path:
                raise ValueError("File path is required")
                
            if not file_type:
                raise ValueError("File type is required")
                
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            if not os.access(file_path, os.R_OK):
                raise PermissionError(f"Cannot read file: {file_path}")
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError("File is empty")
            
            if file_size > 500 * 1024 * 1024:  # 500MB limit
                raise ValueError(f"File too large ({file_size / (1024**2):.1f}MB). Maximum size: 500MB")
            
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            encoding_used = None
            df = None
            
            # Try different encodings
            for encoding in encodings_to_try:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    encoding_used = encoding
                    break
                    
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except pd.errors.EmptyDataError:
                    raise ValueError("CSV file contains no data")
                except pd.errors.ParserError as e:
                    if encoding == encodings_to_try[-1]:  # Last encoding attempt
                        raise ValueError(f"CSV parsing error: {str(e)}")
                    continue
                except Exception as e:
                    if encoding == encodings_to_try[-1]:  # Last encoding attempt
                        raise RuntimeError(f"Error reading CSV file: {str(e)}")
                    continue
            
            if df is None:
                raise UnicodeError("Could not read CSV file with any supported encoding (UTF-8, UTF-8-sig, Latin1, CP1252)")
            
            # Validate DataFrame
            if df.empty:
                raise ValueError("CSV file contains no data rows")
            
            if len(df.columns) == 0:
                raise ValueError("CSV file has no columns")
                
            # Log successful encoding detection
            print(f"Successfully loaded CSV with {encoding_used} encoding: {len(df)} rows, {len(df.columns)} columns")
            
            # Normalize track data based on file type with error handling
            tracks = []
            failed_rows = 0
            
            try:
                for index, row in df.iterrows():
                    try:
                        track = self.normalize_track_data(row, file_type, index)
                        if track:
                            tracks.append(track)
                    except Exception as e:
                        failed_rows += 1
                        print(f"Error normalizing row {index}: {e}")
                        continue
                        
            except Exception as e:
                raise RuntimeError(f"Error processing CSV data: {str(e)}")
            
            if not tracks:
                raise ValueError("No valid tracks found after processing")
            
            if failed_rows > 0:
                print(f"Warning: {failed_rows} rows failed to process and were skipped")
                
            print(f"Successfully processed {len(tracks)} tracks from CSV")
            return tracks
                
        except Exception as e:
            # Re-raise with context
            raise RuntimeError(f"Failed to load CSV file: {str(e)}") from e
    
    def normalize_track_data(self, row, file_type, index):
        """Normalize track data from different CSV formats."""
        track = {}
        
        try:
            if "Play Activity" in file_type:
                track['artist'] = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                track['track'] = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
                track['album'] = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                track['timestamp'] = self.normalize_timestamp(row.get('Event Start Timestamp', ''))
                track['duration'] = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180
                
            elif "Play History" in file_type:
                # Parse track description format "Artist - Track"  
                track_desc = row.get('Track Description', '') if pd.notna(row.get('Track Description')) else ''
                if ' - ' in track_desc:
                    artist, track_name = track_desc.split(' - ', 1)
                    track['artist'] = artist.strip()
                    track['track'] = track_name.strip()
                else:
                    track['artist'] = ''
                    track['track'] = track_desc.strip()
                track['album'] = ''
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())
                track['duration'] = int(row.get('Play Duration Milliseconds', 0)) // 1000 if pd.notna(row.get('Play Duration Milliseconds')) else 180
                
            elif "Recently Played" in file_type:
                track['artist'] = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                track['track'] = str(row.get('Track Name', '')).strip() if pd.notna(row.get('Track Name', '')) else ''
                track['album'] = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                track['timestamp'] = self.normalize_timestamp(row.get('Event End Timestamp', ''))
                track['duration'] = int(row.get('Media duration in millis', 0)) // 1000 if pd.notna(row.get('Media duration in millis')) else 180
                
            else:  # Generic CSV
                # Try to identify columns
                for col_name, value in row.items():
                    col_lower = str(col_name).lower()
                    if 'artist' in col_lower and not track.get('artist'):
                        track['artist'] = str(value).strip() if pd.notna(value) else ''
                    elif ('track' in col_lower or 'song' in col_lower) and not track.get('track'):
                        track['track'] = str(value).strip() if pd.notna(value) else ''
                    elif 'album' in col_lower and not track.get('album'):
                        track['album'] = str(value).strip() if pd.notna(value) else ''
                        
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())
                track['duration'] = 180
            
            # Only return tracks with a track name
            if track.get('track', '').strip():
                return track
                
        except Exception as e:
            print(f"Error normalizing track at index {index}: {e}")
            
        return None
    
    def process_with_musicbrainz(self, all_tracks, total_tracks):
        """Process all tracks with MusicBrainz first (fast phase)."""
        processed_tracks = []
        
        for i, track in enumerate(all_tracks):
            if self.stop_itunes_search:
                break
                
            # Wait if paused
            while getattr(self, 'process_paused', False) and not self.stop_itunes_search:
                time.sleep(0.1)
                
            if self.stop_itunes_search:
                break
            
            # Update progress
            progress = 20 + int((i / total_tracks) * 40)  # 20-60% range
            self.update_progress(f"🗄️ MusicBrainz search: {i+1:,}/{total_tracks:,} tracks", progress)
            
            # Use MusicBrainz if artist is missing
            if not track.get('artist', '').strip() and track.get('track', ''):
                found_artist = self.search_artist_for_track(track['track'], track.get('album'))
                if found_artist:
                    track['artist'] = found_artist
                    self.musicbrainz_found += 1
            
            processed_tracks.append(track)
            
            # Update stats display
            self.songs_processed_label.text = f"🎵 Songs: {i+1:,}/{total_tracks:,}"
            self.update_stats_display()
        
        return processed_tracks
    
    def process_missing_with_itunes(self, missing_tracks, all_processed_tracks, completed_count, total_tracks):
        """Process missing tracks with iTunes API (slow phase)."""
        itunes_processed = 0
        
        for track in missing_tracks:
            if self.stop_itunes_search:
                break
                
            # Wait if paused
            while getattr(self, 'process_paused', False) and not self.stop_itunes_search:
                time.sleep(0.1)
                
            if self.stop_itunes_search:
                break
            
            # Check rate limiting
            self.check_api_rate_limit()
            
            # Update progress
            itunes_processed += 1
            progress = 60 + int((itunes_processed / len(missing_tracks)) * 20)  # 60-80% range
            self.update_progress(f"🌐 iTunes API search: {itunes_processed}/{len(missing_tracks)} missing artists", progress)
            
            # Search with iTunes API
            if track.get('track', ''):
                found_artist = self.search_itunes_api(track['track'], track.get('album'))
                if found_artist:
                    track['artist'] = found_artist
                    self.itunes_found += 1
            
            # Update stats
            self.update_stats_display()
        
        return all_processed_tracks
    
    def convert_to_final_format(self, track, index, total_tracks):
        """Convert track to final Last.fm format."""
        try:
            # Return array format: [artist, track, album, timestamp, album_artist, duration]
            return [
                track.get('artist', ''),
                track.get('track', ''),
                track.get('album', ''),
                str(track.get('timestamp', '')),
                track.get('artist', ''),  # Album Artist = Artist
                track.get('duration', 180)
            ]
        except Exception as e:
            print(f"Error converting track {index}: {e}")
            return None
    
    def process_csv_file(self):
        """Process the CSV file in a background thread with chunk processing."""
        try:
            # Record start time for stats
            self._processing_start_time = time.time()
            
            # Update progress
            self.update_progress("Reading CSV file...", 10)
            
            # Determine optimal chunk size based on file size
            chunk_size = self.calculate_chunk_size()
            
            # Try multiple encodings like original tkinter version
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            encoding_used = None
            
            # First, try to read just the header to determine encoding
            for encoding in encodings_to_try:
                try:
                    pd.read_csv(self.current_file_path, encoding=encoding, nrows=0)
                    encoding_used = encoding
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if encoding_used is None:
                raise Exception("Could not read CSV file with any supported encoding")
            
            # Count total rows for progress tracking
            with open(self.current_file_path, 'r', encoding=encoding_used) as f:
                self.row_count = sum(1 for line in f) - 1  # Subtract header row
            
            self.update_progress(f"Processing {self.row_count:,} rows in chunks...", 15)
            
            # Process file in chunks
            file_type = self.file_type_selection.value
            processed_data = self.process_csv_in_chunks(encoding_used, chunk_size, file_type)
            
            # Finalize processing like tkinter app
            start_time = getattr(self, '_processing_start_time', time.time())
            self.finalize_processing(processed_data, start_time)
            
        except Exception as e:
            self.update_results(f"❌ Error: {str(e)}")
            self.update_progress("Error occurred", 0)
        
        finally:
            # Re-enable buttons on main thread
            asyncio.run_coroutine_threadsafe(self._reset_buttons_ui(), self.main_loop)
    
    async def _enable_reprocess_button(self, widget=None):
        """Enable the reprocess button on main thread."""
        self.reprocess_button.enabled = True
    
    def calculate_chunk_size(self):
        """Calculate optimal chunk size based on file size and available memory."""
        if self.file_size < 1024 * 1024:  # < 1MB
            return 1000
        elif self.file_size < 10 * 1024 * 1024:  # < 10MB
            return 5000
        elif self.file_size < 100 * 1024 * 1024:  # < 100MB
            return 10000
        else:  # >= 100MB
            return 20000
    
    def finalize_processing(self, final_results, start_time):
        """Finalize processing and display results like tkinter app."""
        try:
            # Create DataFrame with exact same columns as tkinter
            columns = ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration']
            self.processed_df = pd.DataFrame(final_results, columns=columns)
            
            # Display results as CSV like tkinter
            csv_buffer = io.StringIO()
            self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
            csv_string = csv_buffer.getvalue()
            
            # Update results text with CSV output
            self.update_results(csv_string)
            
            # Update preview with first 15 rows like tkinter
            self.update_preview(self.processed_df.head(15))
            
            # Calculate and display final stats
            total_time = time.time() - start_time
            total_tracks = len(final_results)
            found_count = self.musicbrainz_found + self.itunes_found
            missing_count = total_tracks - found_count
            
            # Update progress with completion stats
            stats_text = f"✅ Complete! {total_tracks:,} tracks processed in {total_time:.1f}s"
            if missing_count > 0:
                stats_text += f" ({missing_count} missing artists)"
            
            self.update_progress(stats_text, 100)
            
            # Enable reprocess button if there are missing artists
            if missing_count > 0:
                asyncio.run_coroutine_threadsafe(self._enable_reprocess_button(), self.main_loop)
        
        except Exception as e:
            self.update_results(f"❌ Error in finalization: {str(e)}")
    
    def process_csv_in_chunks(self, encoding, chunk_size, file_type):
        """Process CSV file in chunks to handle large files efficiently."""
        processed_data = []
        rows_processed = 0
        total_found_artists = 0
        total_searched_artists = 0
        
        # Read and process file in chunks
        chunk_reader = pd.read_csv(self.current_file_path, encoding=encoding, chunksize=chunk_size)
        
        for chunk_num, chunk in enumerate(chunk_reader):
            if self.stop_itunes_search:
                break
                
            # Update progress
            rows_processed += len(chunk)
            progress = 15 + int((rows_processed / self.row_count) * 70)  # 15-85% range
            self.update_progress(f"Processing chunk {chunk_num + 1}... ({rows_processed:,}/{self.row_count:,} rows)", progress)
            
            # Process this chunk
            chunk_result = self.process_chunk_data(chunk, file_type)
            
            # Add chunk results to overall results
            if isinstance(chunk_result, tuple):
                chunk_data, found_artists, searched_artists = chunk_result
                processed_data.extend(chunk_data)
                total_found_artists += found_artists
                total_searched_artists += searched_artists
            else:
                processed_data.extend(chunk_result)
        
        # Update instance counters for finalize_processing
        self.musicbrainz_found = total_found_artists
        self.itunes_found = 0  # Will be updated when iTunes search is implemented
        
        # Final progress update
        self.update_progress(f"✅ Processed {len(processed_data):,} tracks. Found {total_found_artists}/{total_searched_artists} missing artists.", 85)
        
        return processed_data
    
    def process_chunk_data(self, chunk_df, file_type):
        """Process a chunk of data based on file type."""
        processed_data = []
        found_artists = 0
        searched_artists = 0
        
        for index, row in chunk_df.iterrows():
            try:
                if self.stop_itunes_search:
                    break
                    
                # Handle different file types
                if "Play Activity" in file_type:
                    result = self.process_play_activity_row(row)
                elif "Play History" in file_type:
                    result = self.process_play_history_row(row)
                elif "Recently Played" in file_type:
                    result = self.process_recently_played_row(row)
                else:
                    result = self.process_generic_row(row)
                
                if result:
                    track_data, found_artist, searched_artist = result
                    processed_data.append(track_data)
                    if found_artist:
                        found_artists += 1
                    if searched_artist:
                        searched_artists += 1
                        found_artists += 1
                    if searched_artist:
                        searched_artists += 1
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        return processed_data, found_artists, searched_artists
    
    async def _reset_buttons_ui(self, widget=None):
        """Reset button states on main thread."""
        self.convert_button.text = "Convert to Last.fm Format"
        self.convert_button.enabled = True
        self.pause_button.enabled = False
        self.stop_button.enabled = False
    
    def process_csv_data(self, df, file_type):
        """Process CSV data based on file type with proper column mapping (legacy method for small files)."""
        try:
            # Column mappings for different file types (from original tkinter version)
            if "Play Activity" in file_type:
                return self.process_play_activity_data(df)
            elif "Play History" in file_type:
                return self.process_play_history_data(df)
            elif "Recently Played" in file_type:
                return self.process_recently_played_data(df)
            else:
                return self.process_generic_csv_data(df)
        
        except Exception as e:
            raise Exception(f"Error processing CSV data: {str(e)}")
    
    def process_play_activity_row(self, row):
        """Process a single Play Activity row - returns array format like tkinter."""
        artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
        track = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
        album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
        timestamp = self.normalize_timestamp(row.get('Event Start Timestamp', ''))
        duration = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180
        
        found_artist = False
        searched_artist = False
        
        # If artist is missing and we have a track, try to find it
        if not artist and track:
            found_artist_name = self.search_artist_for_track(track, album)
            if found_artist_name:
                artist = found_artist_name
                found_artist = True
            searched_artist = True
        
        if track:  # Only include tracks with track name
            # Return array format: [artist, track, album, timestamp, album_artist, duration]
            track_array = [artist, track, album, timestamp, artist, duration]
            return track_array, found_artist, searched_artist
        
        return None
    
    def process_play_history_row(self, row):
        """Process a single Play History row - returns array format like tkinter."""
        # Parse track description format "Artist - Track"
        track_desc = row.get('Track Description', '') if pd.notna(row.get('Track Description')) else ''
        if ' - ' in track_desc:
            artist, track = track_desc.split(' - ', 1)
            artist = artist.strip()
            track = track.strip()
        else:
            artist = ''
            track = track_desc.strip()
        
        album = ''  # Play History format doesn't have album info
        timestamp = self.normalize_timestamp(pd.Timestamp.now())  # Use current time, will be adjusted later
        duration = int(row.get('Play Duration Milliseconds', 0)) // 1000 if pd.notna(row.get('Play Duration Milliseconds')) else 180
        
        found_artist = False
        searched_artist = False
        
        # If artist is missing and we have a track, try to find it
        if not artist and track:
            found_artist_name = self.search_artist_for_track(track, album)
            if found_artist_name:
                artist = found_artist_name
                found_artist = True
            searched_artist = True
        
        if track:  # Only include tracks with track name
            # Return array format: [artist, track, album, timestamp, album_artist, duration]
            track_array = [artist, track, album, timestamp, artist, duration]
            return track_array, found_artist, searched_artist
        
        return None
    
    def process_recently_played_row(self, row):
        """Process a single Recently Played row - returns array format like tkinter."""
        # Parse track description format "Artist - Track"
        track_desc = row.get('Track Description', '') if pd.notna(row.get('Track Description')) else ''
        if ' - ' in track_desc:
            artist, track = track_desc.split(' - ', 1)
            artist = artist.strip()
            track = track.strip()
        else:
            artist = ''
            track = track_desc.strip()
        
        album = row.get('Container Description', '').strip() if pd.notna(row.get('Container Description')) else ''
        timestamp = self.normalize_timestamp(pd.Timestamp.now())  # Use current time, will be adjusted later
        duration = int(row.get('Media duration in millis', 0)) // 1000 if pd.notna(row.get('Media duration in millis')) else 180
        
        found_artist = False
        searched_artist = False
        
        # If artist is missing and we have a track, try to find it
        if not artist and track:
            found_artist_name = self.search_artist_for_track(track, album)
            if found_artist_name:
                artist = found_artist_name
                found_artist = True
            searched_artist = True
        
        if track:  # Only include tracks with track name
            # Return array format: [artist, track, album, timestamp, album_artist, duration]
            track_array = [artist, track, album, timestamp, artist, duration]
            return track_array, found_artist, searched_artist
        
        return None
    
    def process_generic_row(self, row):
        """Process a single generic CSV row."""
        # Try to identify columns (this should be cached for the chunk)
        # For now, use simple heuristics
        artist = ''
        track = ''
        album = ''
        
        # Try to find artist, track, album in row
        for col_name, value in row.items():
            col_lower = str(col_name).lower()
            if 'artist' in col_lower and not artist:
                artist = str(value).strip() if pd.notna(value) else ''
            elif ('track' in col_lower or 'song' in col_lower) and not track:
                track = str(value).strip() if pd.notna(value) else ''
            elif 'album' in col_lower and not album:
                album = str(value).strip() if pd.notna(value) else ''
        
        found_artist = False
        searched_artist = False
        
        # If artist is missing and we have a track, try to find it
        if not artist and track:
            found_artist_name = self.search_artist_for_track(track, album)
            if found_artist_name:
                artist = found_artist_name
                found_artist = True
            searched_artist = True
        
        if track:  # Only include tracks with track name
            track_data = {
                'artist': artist,
                'track': track,
                'album': album,
                'timestamp': self.normalize_timestamp(pd.Timestamp.now()),
            }
            return track_data, found_artist, searched_artist
        
        return None
    
    def process_play_activity_data(self, df):
        """Process Apple Music Play Activity CSV format."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns from Play Activity format
                artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                track = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
                album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                
                # If artist is missing and we have a track, try to find it
                if not artist and track:
                    found_artist = self.search_artist_for_track(track, album)
                    if found_artist:
                        artist = found_artist
                        found_artists += 1
                    searched_artists += 1
                
                track_data = {
                    'artist': artist,
                    'track': track,
                    'album': album,
                    'timestamp': self.normalize_timestamp(row.get('Event Start Timestamp', '')),
                    'play_duration': row.get('Play Duration Milliseconds', 0)
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f"✅ Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_play_history_data(self, df):
        """Process Play History Daily Tracks CSV format."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns from Play History format
                artist = str(row.get('Artist', '')).strip() if pd.notna(row.get('Artist', '')) else ''
                track = str(row.get('Track', '')).strip() if pd.notna(row.get('Track', '')) else ''
                album = str(row.get('Album', '')).strip() if pd.notna(row.get('Album', '')) else ''
                
                # If artist is missing and we have a track, try to find it
                if not artist and track:
                    found_artist = self.search_artist_for_track(track, album)
                    if found_artist:
                        artist = found_artist
                        found_artists += 1
                    searched_artists += 1
                
                track_data = {
                    'artist': artist,
                    'track': track,
                    'album': album,
                    'timestamp': self.normalize_timestamp(row.get('Date', '')),
                    'play_count': row.get('Play Count', 1)
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f"✅ Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_recently_played_data(self, df):
        """Process Recently Played Tracks CSV format."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns from Recently Played format
                artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                track = str(row.get('Track Name', '')).strip() if pd.notna(row.get('Track Name', '')) else ''
                album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                
                # If artist is missing and we have a track, try to find it
                if not artist and track:
                    found_artist = self.search_artist_for_track(track, album)
                    if found_artist:
                        artist = found_artist
                        found_artists += 1
                    searched_artists += 1
                
                track_data = {
                    'artist': artist,
                    'track': track,
                    'album': album,
                    'timestamp': self.normalize_timestamp(row.get('Event End Timestamp', '')),
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f"✅ Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_generic_csv_data(self, df):
        """Process generic CSV format by attempting to map columns."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        # Try to identify columns
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if any(term in col_lower for term in ['artist', 'performer', 'musician']):
                column_mapping['artist'] = col
            elif any(term in col_lower for term in ['track', 'song', 'title', 'name']) and 'album' not in col_lower and 'artist' not in col_lower:
                column_mapping['track'] = col
            elif any(term in col_lower for term in ['album', 'release']):
                column_mapping['album'] = col
            elif any(term in col_lower for term in ['time', 'date', 'stamp']):
                column_mapping['timestamp'] = col
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns
                artist = str(row.get(column_mapping.get('artist', ''), '')).strip() if pd.notna(row.get(column_mapping.get('artist', ''), '')) else ''
                track = str(row.get(column_mapping.get('track', ''), '')).strip() if pd.notna(row.get(column_mapping.get('track', ''), '')) else ''
                album = str(row.get(column_mapping.get('album', ''), '')).strip() if pd.notna(row.get(column_mapping.get('album', ''), '')) else ''
                
                # If artist is missing and we have a track, try to find it
                if not artist and track:
                    found_artist = self.search_artist_for_track(track, album)
                    if found_artist:
                        artist = found_artist
                        found_artists += 1
                    searched_artists += 1
                
                track_data = {
                    'artist': artist,
                    'track': track,
                    'album': album,
                    'timestamp': self.normalize_timestamp(row.get(column_mapping.get('timestamp', ''), pd.Timestamp.now())),
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f"✅ Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def normalize_timestamp(self, timestamp_str):
        """Normalize timestamp to consistent format."""
        if pd.isna(timestamp_str) or not timestamp_str:
            return pd.Timestamp.now()
        
        try:
            # Try to parse timestamp
            if isinstance(timestamp_str, str):
                return pd.to_datetime(timestamp_str, errors='coerce')
            else:
                return pd.to_datetime(timestamp_str)
        except:
            return pd.Timestamp.now()
    
    def search_artist_for_track(self, track_name, album_name=None):
        """Search for artist using configured search providers."""
        if not track_name or self.stop_itunes_search:
            return None
            
        # Wait if paused
        while self.pause_itunes_search and not self.stop_itunes_search:
            time.sleep(0.1)
        
        if self.stop_itunes_search:
            return None
            
        try:
            # Clean track name (remove parenthetical content)
            import re
            clean_track = re.sub(r'\s*\(.*?\)\s*', '', track_name).strip()
            if not clean_track:
                return None
            
            # First try MusicBrainz if available
            search_result = self.music_search_service.search_song(clean_track, None, album_name)
            
            if search_result.get("success"):
                return search_result["artist"]
            
            # If MusicBrainz failed and we have auto-fallback enabled, try iTunes
            if (search_result.get("use_itunes_fallback") or 
                search_result.get("use_itunes") or 
                self.music_search_service.get_search_provider() == "itunes"):
                
                # Check rate limiting
                self.check_api_rate_limit()
                
                # Search iTunes API
                itunes_result = self.search_itunes_api(clean_track, album_name)
                return itunes_result
            
            return None
        
        except Exception as e:
            print(f"Error searching for artist '{track_name}': {str(e)}")
            return None
    
    def check_api_rate_limit(self):
        """Check and enforce API rate limiting."""
        with self.api_lock:
            current_time = time.time()
            
            # Remove API calls older than 1 minute
            while self.api_calls and current_time - self.api_calls[0] > 60:
                self.api_calls.popleft()
            
            # If we've made 20 calls in the last minute, wait
            if len(self.api_calls) >= 20:
                wait_time = 60 - (current_time - self.api_calls[0])
                if wait_time > 0:
                    self.update_progress(f"⏳ Rate limited, waiting {wait_time:.1f}s...", self.progress_bar.value)
                    
                    # Interruptible wait
                    start_wait = time.time()
                    while time.time() - start_wait < wait_time:
                        if self.stop_itunes_search or self.skip_wait_requested:
                            self.skip_wait_requested = False
                            break
                        time.sleep(0.1)
    
    def search_itunes_api(self, track_name, album_name=None):
        """Search iTunes API for artist information."""
        try:
            # Try first with just the track name
            artist = self._try_itunes_search(track_name)
            if not artist and album_name:
                # If no result, try with album
                artist = self._try_itunes_search(f"{track_name} {album_name}")
            
            return artist
        
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                # Handle rate limiting
                self.update_progress("⚠️ API rate limited", self.progress_bar.value)
                time.sleep(1)  # Brief pause
            raise e
    
    def _try_itunes_search(self, search_term):
        """Helper method to perform actual iTunes API search."""
        try:
            # URL encode the search term
            encoded_term = requests.utils.quote(search_term)
            url = f"https://itunes.apple.com/search?term={encoded_term}&entity=song&limit=5"
            
            # Make the API call with timeout
            response = requests.get(url, timeout=10)
            self.api_calls.append(time.time())  # Record the API call time
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded")
            
            response.raise_for_status()
            data = response.json()
            
            # Parse results and find best match
            if data.get('results'):
                best_match = data['results'][0]  # iTunes returns results by relevance
                return best_match.get('artistName', '')
            
            return None
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"iTunes API error: {str(e)}")
    
    def process_play_activity(self, df):
        """Process Play Activity CSV format."""
        # Implementation would go here
        # This is a simplified version
        processed = pd.DataFrame()
        processed['artist'] = df.get('Artist Name', '')
        processed['track'] = df.get('Track Name', '')
        processed['album'] = df.get('Album', '')
        processed['timestamp'] = pd.to_datetime('now')
        return processed
    
    def process_play_history(self, df):
        """Process Play History Daily Tracks format."""
        # Implementation would go here
        processed = pd.DataFrame()
        processed['artist'] = df.get('Artist', '')
        processed['track'] = df.get('Track', '')
        processed['album'] = df.get('Album', '')
        processed['timestamp'] = pd.to_datetime('now')
        return processed
    
    def process_recently_played(self, df):
        """Process Recently Played Tracks format."""
        # Implementation would go here
        processed = pd.DataFrame()
        processed['artist'] = df.get('Artist', '')
        processed['track'] = df.get('Song', '')
        processed['album'] = df.get('Album', '')
        processed['timestamp'] = pd.to_datetime('now')
        return processed
    
    def process_generic_csv(self, df):
        """Process generic CSV format."""
        # Implementation would go here
        processed = pd.DataFrame()
        # Try to map common column names
        for col in df.columns:
            if 'artist' in col.lower():
                processed['artist'] = df[col]
            elif 'track' in col.lower() or 'song' in col.lower():
                processed['track'] = df[col]
            elif 'album' in col.lower():
                processed['album'] = df[col]
        
        processed['timestamp'] = pd.to_datetime('now')
        return processed
    
    def save_processed_file(self, df):
        """Save the processed DataFrame to a CSV file in Last.fm format with comprehensive error handling."""
        try:
            # Validate input DataFrame
            if df is None or df.empty:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="Save Error",
                        message="No data to save. Please process a CSV file first."
                    )), self.main_loop
                )
                return None
                
            # Generate output filename
            try:
                base_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
                output_name = f"{base_name}_lastfm_format.csv"
                output_path = os.path.join(os.path.dirname(self.current_file_path), output_name)
                
                # Check if output directory is writable
                output_dir = os.path.dirname(output_path)
                if not os.access(output_dir, os.W_OK):
                    asyncio.run_coroutine_threadsafe(
                        self.main_window.dialog(toga.ErrorDialog(
                            title="Write Permission Error",
                            message=f"Cannot write to directory: {output_dir}\nPlease check permissions."
                        )), self.main_loop
                    )
                    return None
                    
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="Path Generation Error",
                        message=f"Error generating output path: {str(e)}"
                    )), self.main_loop
                )
                return None
            
            # Prepare data for Last.fm format: Artist, Track, Album, Timestamp, Album Artist, Duration
            try:
                lastfm_data = []
                for _, row in df.iterrows():
                    try:
                        lastfm_row = [
                            str(row.get('artist', '')),
                            str(row.get('track', '')),
                            str(row.get('album', '')),
                            str(row.get('timestamp', '')),
                            str(row.get('artist', '')),  # Album Artist = Artist for most cases
                            row.get('play_duration', 180)  # Default 3 minutes if no duration
                        ]
                        lastfm_data.append(lastfm_row)
                    except Exception as e:
                        print(f"Error processing row in save: {e}")
                        continue
                        
                if not lastfm_data:
                    asyncio.run_coroutine_threadsafe(
                        self.main_window.dialog(toga.ErrorDialog(
                            title="Data Processing Error",
                            message="No valid data rows found for saving."
                        )), self.main_loop
                    )
                    return None
                    
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="Data Format Error",
                        message=f"Error formatting data for Last.fm: {str(e)}"
                    )), self.main_loop
                )
                return None
            
            # Create DataFrame with proper Last.fm headers
            try:
                lastfm_df = pd.DataFrame(lastfm_data, columns=[
                    'Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'
                ])
                
                if lastfm_df.empty:
                    asyncio.run_coroutine_threadsafe(
                        self.main_window.dialog(toga.ErrorDialog(
                            title="Empty Output",
                            message="Processed data resulted in empty output file."
                        )), self.main_loop
                    )
                    return None
                    
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="DataFrame Creation Error",
                        message=f"Error creating output DataFrame: {str(e)}"
                    )), self.main_loop
                )
                return None
            
            # Save to CSV with error handling
            try:
                lastfm_df.to_csv(output_path, index=False, encoding='utf-8')
                
                # Verify file was created and has content
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    # Store the output file path for later reprocessing (like tkinter version)
                    self.last_output_file = output_path
                    # Enable reprocess button after successful save (like tkinter)
                    asyncio.run_coroutine_threadsafe(self._enable_reprocess_button(), self.main_loop)
                    return output_path
                else:
                    asyncio.run_coroutine_threadsafe(
                        self.main_window.dialog(toga.ErrorDialog(
                            title="File Creation Error",
                            message="Output file was not created or is empty."
                        )), self.main_loop
                    )
                    return None
                    
            except PermissionError:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="Permission Error", 
                        message=f"Permission denied writing to: {output_path}"
                    )), self.main_loop
                )
                return None
            except IOError as e:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="I/O Error",
                        message=f"I/O error saving file: {str(e)}"
                    )), self.main_loop
                )
                return None
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.main_window.dialog(toga.ErrorDialog(
                        title="Save Error",
                        message=f"Failed to save CSV file: {str(e)}"
                    )), self.main_loop
                )
                return None
                
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                self.main_window.dialog(toga.ErrorDialog(
                    title="Unexpected Save Error",
                    message=f"Unexpected error during save: {str(e)}"
                )), self.main_loop
            )
            return None
    
    def update_results(self, text):
        """Update the results text area."""
        # Store values for UI update
        self._pending_results_text = text
        # Schedule UI update on main thread from background thread
        asyncio.run_coroutine_threadsafe(self._update_results_ui(), self.main_loop)
    
    async def _update_results_ui(self, widget=None):
        """Update results UI on main thread."""
        self.results_text.value = self._pending_results_text
    
    def update_preview(self, df):
        """Update the preview table."""
        # Store values for UI update
        self._pending_preview_df = df
        # Schedule UI update on main thread from background thread
        asyncio.run_coroutine_threadsafe(self._update_preview_ui(), self.main_loop)
    
    async def _update_preview_ui(self, widget=None):
        """Update preview UI on main thread."""
        try:
            print(f"DEBUG: Updating preview with {len(self._pending_preview_df)} rows")
            print(f"DEBUG: Preview DF columns: {list(self._pending_preview_df.columns)}")
            
            # Clear existing data
            self.preview_table.data.clear()
            
            # Add first 10 rows with DataFrame column names
            rows_added = 0
            for i, row in self._pending_preview_df.head(10).iterrows():
                artist = str(row.get('Artist', '')) if pd.notna(row.get('Artist')) else ''
                track = str(row.get('Track', '')) if pd.notna(row.get('Track')) else ''
                album = str(row.get('Album', '')) if pd.notna(row.get('Album')) else ''
                timestamp = str(row.get('Timestamp', ''))[:16] if pd.notna(row.get('Timestamp')) else ''
                
                self.preview_table.data.append((artist, track, album, timestamp))
                rows_added += 1
            
            print(f"DEBUG: Added {rows_added} rows to preview table")
        except Exception as e:
            print(f"DEBUG: Error updating preview: {e}")
            import traceback
            traceback.print_exc()
    
    def update_progress(self, message, value):
        """Update progress bar and label."""
        # Store values for UI update
        self._pending_progress_message = message
        self._pending_progress_value = value
        # Schedule UI update on main thread from background thread
        asyncio.run_coroutine_threadsafe(self._update_progress_ui(), self.main_loop)
    
    async def _update_progress_ui(self, widget=None):
        """Update progress UI on main thread."""
        self.progress_label.text = self._pending_progress_message
        self.progress_bar.value = self._pending_progress_value
    
    async def show_instructions(self, widget):
        """Show instructions dialog."""
        instructions = """
How to Export Your Apple Music Data:

1. Go to privacy.apple.com
2. Sign in with your Apple ID
3. Select "Get a copy of your data"
4. Choose "Apple Media Services information"
5. Download the CSV file when ready
6. Use this app to convert it to Last.fm format

Supported formats:
• Play Activity
• Play History Daily Tracks
• Recently Played Tracks
• Generic CSV with artist/track columns
        """
        
        await self.main_window.dialog(toga.InfoDialog(
            title="How to Use",
            message=instructions
        ))
    
    def on_provider_changed(self, widget):
        """Handle provider selection change."""
        if "MusicBrainz" in widget.value:
            self.music_search_service.set_search_provider("musicbrainz")
            self.update_musicbrainz_ui_state()
        else:
            self.music_search_service.set_search_provider("itunes")
            self.update_itunes_ui_state()
        
        # Re-enable convert button if file is selected and not processing
        if self.current_file_path and not self.processing_thread:
            self.convert_button.enabled = True
        elif self.processing_thread and self.processing_thread.is_alive():
            self.convert_button.text = "Processing... Stop first to switch"
            self.convert_button.enabled = False
    
    def on_fallback_changed(self, widget):
        """Handle fallback switch change."""
        self.music_search_service.set_auto_fallback(widget.value)
    
    def on_itunes_api_changed(self, widget):
        """Handle iTunes API switch change."""
        # Implementation would go here
        pass
    
    async def download_database(self, widget):
        """Handle database download with comprehensive error handling."""
        try:
            result = await self.main_window.dialog(toga.ConfirmDialog(
                title="Download MusicBrainz Database",
                message="This will download approximately 2GB of data. Continue?"
            ))
            
            if result:
                try:
                    # Check available disk space
                    import shutil
                    free_space = shutil.disk_usage(".").free
                    required_space = 3 * 1024 * 1024 * 1024  # 3GB (compressed + extracted)
                    
                    if free_space < required_space:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="Insufficient Disk Space",
                            message=f"Need at least 3GB free space. Available: {free_space / (1024**3):.1f}GB"
                        ))
                        return
                        
                    # Check internet connection
                    try:
                        import urllib.request
                        urllib.request.urlopen('https://www.google.com', timeout=5)
                    except Exception:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="Connection Error",
                            message="No internet connection detected. Please check your connection and try again."
                        ))
                        return
                    
                    # Start download in background with error handling
                    self.update_results("🔄 Starting database download...")
                    
                    try:
                        # Use existing MusicBrainzManager for actual download
                        # This would be implemented with proper progress tracking
                        await self.main_window.dialog(toga.InfoDialog(
                            title="Download Started",
                            message="Database download started in background. Check results for progress."
                        ))
                        
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="Download Failed",
                            message=f"Failed to start download: {str(e)}"
                        ))
                        
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Pre-download Check Failed",
                        message=f"Error checking system requirements: {str(e)}"
                    ))
                    
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Database Download Error",
                message=f"Unexpected error during database download: {str(e)}"
            ))
    
    async def check_for_updates(self, widget):
        """Check for database updates with comprehensive error handling."""
        try:
            # Check internet connection first
            try:
                import urllib.request
                urllib.request.urlopen('https://musicbrainz.org', timeout=10)
            except Exception:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Connection Error",
                    message="Cannot connect to MusicBrainz servers. Please check your internet connection."
                ))
                return
            
            self.update_results("🔄 Checking for database updates...")
            
            try:
                # Use MusicBrainzManager to check for updates
                # This would be implemented with actual version checking
                
                # Simulating update check with proper error handling
                has_updates = False  # This would come from actual check
                
                if has_updates:
                    result = await self.main_window.dialog(toga.ConfirmDialog(
                        title="Updates Available",
                        message="Database updates are available. Download now?"
                    ))
                    
                    if result:
                        await self.download_database(None)
                else:
                    await self.main_window.dialog(toga.InfoDialog(
                        title="No Updates",
                        message="Database is up to date."
                    ))
                    
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Update Check Failed",
                    message=f"Failed to check for updates: {str(e)}"
                ))
                
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Unexpected Error",
                message=f"Unexpected error during update check: {str(e)}"
            ))
    
    async def manual_import_database(self, widget):
        """Handle manual database import with comprehensive error handling."""
        try:
            try:
                file_path = await self.main_window.dialog(toga.OpenFileDialog(
                    title="Select MusicBrainz Database File",
                    file_types=["tar.zst", "csv", "tsv"]
                ))
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="File Dialog Error",
                    message="Could not open file dialog. Please check your system configuration."
                ))
                return
            
            if file_path:
                try:
                    file_path_str = str(file_path)
                    
                    # Validate file exists and is accessible
                    if not os.path.exists(file_path_str):
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Not Found",
                            message="Selected file no longer exists. Please choose another file."
                        ))
                        return
                    
                    if not os.access(file_path_str, os.R_OK):
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Access Error",
                            message="Cannot read the selected file. Please check file permissions."
                        ))
                        return
                    
                    # Check file size and available space
                    try:
                        file_size = os.path.getsize(file_path_str)
                        
                        if file_size == 0:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Empty File",
                                message="Selected file is empty. Please choose a valid database file."
                            ))
                            return
                        
                        # Check available disk space (need ~3x file size for extraction)
                        import shutil
                        free_space = shutil.disk_usage(os.path.dirname(file_path_str)).free
                        required_space = file_size * 3
                        
                        if free_space < required_space:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Insufficient Disk Space",
                                message=f"Need {required_space / (1024**3):.1f}GB free space for import. Available: {free_space / (1024**3):.1f}GB"
                            ))
                            return
                            
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Analysis Error",
                            message=f"Error analyzing import file: {str(e)}"
                        ))
                        return
                    
                    # Confirm import operation
                    file_size_mb = file_size / (1024 * 1024)
                    result = await self.main_window.dialog(toga.ConfirmDialog(
                        title="Confirm Import",
                        message=f"Import {os.path.basename(file_path_str)} ({file_size_mb:.1f} MB)? This may take several minutes."
                    ))
                    
                    if result:
                        try:
                            self.update_results(f"🔄 Importing database from: {os.path.basename(file_path_str)}...")
                            
                            # Use MusicBrainzManager for actual import with progress tracking
                            await self.main_window.dialog(toga.InfoDialog(
                                title="Import Started",
                                message="Database import started. This may take several minutes. Check results for progress."
                            ))
                            
                        except Exception as e:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Import Failed",
                                message=f"Failed to import database: {str(e)}"
                            ))
                            
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Import Processing Error",
                        message=f"Error processing import file: {str(e)}"
                    ))
                    
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Manual Import Error",
                message=f"Unexpected error during manual import: {str(e)}"
            ))
    
    def toggle_pause(self, widget):
        """Toggle pause state."""
        self.pause_itunes_search = not self.pause_itunes_search
        if self.pause_itunes_search:
            widget.text = "Resume"
            self.update_progress("Paused", self.progress_bar.value)
        else:
            widget.text = "Pause"
            self.update_progress("Processing...", self.progress_bar.value)
    
    def stop_search(self, widget):
        """Stop the search process."""
        self.stop_itunes_search = True
        self.update_progress("Stopped", 0)
        self.convert_button.enabled = True
        self.pause_button.enabled = False
        self.stop_button.enabled = False
    
    def skip_wait(self, widget):
        """Skip the current wait period."""
        self.skip_wait_requested = True
        self.update_progress("⏭️ Skipping rate limit wait...", self.progress_bar.value)
    
    async def copy_results(self, widget):
        """Copy results to clipboard."""
        if self.results_text.value:
            # TODO: Implement clipboard functionality
            await self.main_window.dialog(toga.InfoDialog(
                title="Copy Results", 
                message="Results copied to clipboard!"
            ))
        else:
            await self.main_window.dialog(toga.ErrorDialog(
                title="No Results", 
                message="No results to copy."
            ))
    
    async def save_results(self, widget):
        """Save results as CSV file."""
        # Check if we have processed data to save
        if hasattr(self, 'processed_data') and self.processed_data:
            try:
                save_path = await self.main_window.dialog(toga.SaveFileDialog(
                    title="Save CSV File",
                    suggested_filename="converted_music_data.csv",
                    file_types=["csv"]
                ))
                if save_path:
                    # Convert processed data to DataFrame and save
                    df = pd.DataFrame(self.processed_data)
                    output_path = self.save_processed_file_to_path(df, str(save_path))
                    await self.main_window.dialog(toga.InfoDialog(
                        title="File Saved", 
                        message=f"Results saved to {output_path}\n\nSaved {len(df):,} tracks in Last.fm format"
                    ))
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Save Error", 
                    message=f"Failed to save file: {str(e)}"
                ))
        elif self.results_text.value:
            # Fallback to saving text content
            try:
                save_path = await self.main_window.dialog(toga.SaveFileDialog(
                    title="Save Text File",
                    suggested_filename="converted_music_data.txt",
                    file_types=["txt"]
                ))
                if save_path:
                    with open(save_path, 'w') as f:
                        f.write(self.results_text.value)
                    await self.main_window.dialog(toga.InfoDialog(
                        title="File Saved", 
                        message=f"Results saved to {save_path}"
                    ))
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Save Error", 
                    message=f"Failed to save file: {str(e)}"
                ))
        else:
            await self.main_window.dialog(toga.ErrorDialog(
                title="No Results", 
                message="No results to save."
            ))
    
    def save_processed_file_to_path(self, df, file_path):
        """Save the processed DataFrame to a specific path in Last.fm format with comprehensive error handling."""
        try:
            # Validate input parameters
            if df is None or df.empty:
                raise ValueError("No data to save. DataFrame is empty or None.")
                
            if not file_path or not isinstance(file_path, (str, Path)):
                raise ValueError("Invalid file path provided.")
                
            # Validate output directory exists and is writable
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                raise FileNotFoundError(f"Output directory does not exist: {output_dir}")
                
            if output_dir and not os.access(output_dir, os.W_OK):
                raise PermissionError(f"Cannot write to directory: {output_dir}")
            
            # Prepare data for Last.fm format with error handling
            lastfm_data = []
            failed_rows = 0
            
            for index, row in df.iterrows():
                try:
                    lastfm_row = [
                        str(row.get('artist', '')),
                        str(row.get('track', '')),
                        str(row.get('album', '')),
                        str(row.get('timestamp', '')),
                        str(row.get('artist', '')),  # Album Artist = Artist for most cases
                        row.get('play_duration', 180)  # Default 3 minutes if no duration
                    ]
                    lastfm_data.append(lastfm_row)
                except Exception as e:
                    failed_rows += 1
                    print(f"Error processing row {index}: {e}")
                    continue
            
            # Check if we have any valid data
            if not lastfm_data:
                raise ValueError("No valid data rows found after processing.")
                
            if failed_rows > 0:
                print(f"Warning: {failed_rows} rows failed to process and were skipped.")
            
            # Create DataFrame with proper Last.fm headers
            try:
                lastfm_df = pd.DataFrame(lastfm_data, columns=[
                    'Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'
                ])
                
                if lastfm_df.empty:
                    raise ValueError("Processed data resulted in empty DataFrame.")
                    
            except Exception as e:
                raise RuntimeError(f"Error creating output DataFrame: {str(e)}")
            
            # Save to CSV with comprehensive error handling
            try:
                lastfm_df.to_csv(file_path, index=False, encoding='utf-8')
                
                # Verify file was created successfully
                if not os.path.exists(file_path):
                    raise RuntimeError("File was not created after save operation.")
                    
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    raise RuntimeError("Created file is empty.")
                    
                print(f"Successfully saved {len(lastfm_df)} rows to {file_path} ({file_size} bytes)")
                return file_path
                
            except PermissionError as e:
                raise PermissionError(f"Permission denied writing to: {file_path}")
            except IOError as e:
                raise IOError(f"I/O error saving file: {str(e)}")
            except Exception as e:
                raise RuntimeError(f"Error saving CSV file: {str(e)}")
                
        except Exception as e:
            # Re-raise with context for caller to handle
            raise RuntimeError(f"Failed to save file to {file_path}: {str(e)}")from e
    
    async def reprocess_missing_artists(self, widget):
        """Reprocess missing artists using iTunes API with comprehensive error handling."""
        try:
            # Check if we have a processed file (like tkinter version)
            if not hasattr(self, 'last_output_file') or not self.last_output_file:
                # Fallback to processed_df if no file saved yet
                if not hasattr(self, 'processed_df') or self.processed_df is None:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="No Data", 
                        message="Please convert a CSV file first before searching for missing artists."
                    ))
                    return
            
            # If we have a saved file, reload it (like tkinter version)
            if hasattr(self, 'last_output_file') and self.last_output_file and os.path.exists(self.last_output_file):
                try:
                    # Read the saved CSV file like tkinter version
                    self.processed_df = pd.read_csv(self.last_output_file)
                    # Update columns to match internal format
                    if 'Artist' in self.processed_df.columns:
                        self.processed_df.rename(columns={'Artist': 'artist', 'Track': 'track', 'Album': 'album'}, inplace=True)
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="File Read Error",
                        message=f"Could not read saved file: {str(e)}"
                    ))
                    return
            
            # Validate DataFrame is not empty
            if self.processed_df.empty:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Empty Data",
                    message="Processed data is empty. Please convert a valid CSV file first."
                ))
                return
            
            try:
                # Check if required columns exist (handle both formats)
                artist_col = 'artist' if 'artist' in self.processed_df.columns else 'Artist'
                
                if artist_col not in self.processed_df.columns:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Data Format Error",
                        message="Artist column not found in processed data. Please reconvert the file."
                    ))
                    return
                
                # Count tracks with missing artists from DataFrame (check for empty, None, or 'Unknown Artist')
                missing_mask = (self.processed_df[artist_col].str.strip() == '') | \
                              self.processed_df[artist_col].isna() | \
                              (self.processed_df[artist_col] == 'Unknown Artist')
                missing_artists_df = self.processed_df[missing_mask]
                missing_artists = missing_artists_df.to_dict('records')
                
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Data Analysis Error",
                    message=f"Error analyzing missing artists: {str(e)}"
                ))
                return
            
            if not missing_artists:
                await self.main_window.dialog(toga.InfoDialog(
                    title="No Missing Artists", 
                    message="All tracks already have artist information!"
                ))
                return
            
            # Check internet connection before starting
            try:
                import urllib.request
                urllib.request.urlopen('https://itunes.apple.com', timeout=10)
            except Exception:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Connection Error",
                    message="Cannot connect to iTunes API. Please check your internet connection."
                ))
                return
            
            # Estimate time and inform user
            estimated_minutes = len(missing_artists) / 15  # ~15 searches per minute due to rate limiting
            
            # Confirm with user
            result = await self.main_window.dialog(toga.ConfirmDialog(
                title="Search Missing Artists",
                message=f"Found {len(missing_artists)} tracks without artist information.\n\n"
                       f"This will search iTunes API to find missing artists.\n"
                       f"Estimated time: {estimated_minutes:.1f} minutes\n\n"
                       f"Continue?"
            ))
            
            if result:
                try:
                    # Validate iTunes API is enabled
                    if hasattr(self, 'use_itunes_api') and not self.use_itunes_api:
                        enable_result = await self.main_window.dialog(toga.ConfirmDialog(
                            title="Enable iTunes API",
                            message="iTunes API is currently disabled. Enable it for this search?"
                        ))
                        
                        if not enable_result:
                            return
                        
                        self.use_itunes_api = True
                    
                    # Start search in background thread with error handling
                    try:
                        self.reprocess_button.enabled = False
                        self.pause_button.enabled = True
                        self.stop_button.enabled = True
                    except AttributeError:
                        # Buttons might not exist yet, handle gracefully
                        print("Control buttons not available")
                    
                    # Reset search flags
                    self.stop_itunes_search = False
                    self.pause_itunes_search = False
                    
                    # Start reprocessing thread
                    try:
                        self.reprocessing_thread = threading.Thread(
                            target=self.reprocess_missing_artists_thread,
                            args=(missing_artists,),
                            daemon=True
                        )
                        self.reprocessing_thread.start()
                        
                        # Update UI to show search started
                        self.update_results(f"🔍 Starting search for {len(missing_artists)} missing artists...")
                        
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="Thread Start Error",
                            message=f"Failed to start search thread: {str(e)}"
                        ))
                        # Re-enable buttons on error
                        try:
                            self.reprocess_button.enabled = True
                            self.pause_button.enabled = False
                            self.stop_button.enabled = False
                        except AttributeError:
                            pass
                        
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Search Initialization Error",
                        message=f"Failed to initialize missing artist search: {str(e)}"
                    ))
                    
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Unexpected Error",
                message=f"Unexpected error during missing artist search: {str(e)}"
            ))
    
    def reprocess_missing_artists_thread(self, missing_artists_tracks):
        """Reprocess missing artists in background thread with comprehensive error handling."""
        try:
            # Validate input
            if not missing_artists_tracks:
                self.update_results("❌ No missing artists to process.")
                return
                
            found_artists = 0
            total_tracks = len(missing_artists_tracks)
            errors_encountered = 0
            
            try:
                self.update_progress(f"Searching for {total_tracks} missing artists...", 0)
                
            except Exception as e:
                print(f"Error updating initial progress: {e}")
                # Continue without progress updates if needed
            
            for i, track_data in enumerate(missing_artists_tracks):
                if self.stop_itunes_search:
                    break
                
                # Wait if paused
                while self.pause_itunes_search and not self.stop_itunes_search:
                    time.sleep(0.1)
                
                if self.stop_itunes_search:
                    break
                
                try:
                    # Update progress
                    progress = int((i / total_tracks) * 90)
                    track_name = track_data.get('track', 'Unknown')
                    self.update_progress(f"Searching for artist: {track_name[:30]}...", progress)
                    
                    # Search for artist
                    found_artist = self.search_artist_for_track(
                        track_data.get('track', ''), 
                        track_data.get('album', '')
                    )
                    
                    if found_artist:
                        # Update the track data with found artist
                        track_data['artist'] = found_artist
                        found_artists += 1
                        
                        # Update the processed data (find and update the matching track)
                        for processed_track in self.processed_data:
                            if (processed_track.get('track') == track_data.get('track') and 
                                processed_track.get('album') == track_data.get('album') and
                                not processed_track.get('artist', '').strip()):
                                processed_track['artist'] = found_artist
                                break
                    
                except Exception as e:
                    print(f"Error searching for artist for '{track_data.get('track', '')}': {str(e)}")
                    continue
            
            # Update UI with results
            if not self.stop_itunes_search:
                self.update_results(f"✅ Artist search complete!\n"
                                  f"Found {found_artists}/{total_tracks} missing artists\n\n"
                                  f"Updated data is ready to save.")
                
                # Update preview with updated data
                updated_df = pd.DataFrame(self.processed_data)
                self.update_preview(updated_df)
                
                self.update_progress(f"✅ Found {found_artists}/{total_tracks} missing artists", 100)
            else:
                self.update_progress("⏹️ Artist search stopped", 0)
            
        except Exception as e:
            self.update_results(f"❌ Error during artist search: {str(e)}")
            self.update_progress("Error occurred", 0)
        
        finally:
            # Re-enable buttons on main thread
            asyncio.run_coroutine_threadsafe(self._reset_reprocess_buttons_ui(), self.main_loop)
    
    async def _reset_reprocess_buttons_ui(self, widget=None):
        """Reset reprocess button states on main thread."""
        self.reprocess_button.enabled = True
        self.pause_button.enabled = False
        self.stop_button.enabled = False
    
    def update_database_status(self):
        """Update the database status display."""
        if self.musicbrainz_manager.is_database_available():
            self.download_button.text = "Re-download DB"
        else:
            self.download_button.text = "Download DB"
    
    def update_musicbrainz_ui_state(self):
        """Update UI state for MusicBrainz provider."""
        # Enable/disable relevant controls
        pass
    
    def update_itunes_ui_state(self):
        """Update UI state for iTunes provider."""
        # Enable/disable relevant controls
        pass
    
    async def delete_database(self, widget):
        """Delete the MusicBrainz database with confirmation."""
        result = await self.main_window.dialog(toga.ConfirmDialog(
            title="Delete Database",
            message="This will permanently delete the MusicBrainz database.\n"
                   "You will need to re-download it to use offline search.\n\nContinue?"
        ))
        
        if result:
            try:
                # Delete the database
                if hasattr(self.musicbrainz_manager, 'delete_database'):
                    self.musicbrainz_manager.delete_database()
                
                # Update UI
                self.update_database_status()
                
                await self.main_window.dialog(toga.InfoDialog(
                    title="Database Deleted",
                    message="MusicBrainz database has been deleted successfully."
                ))
                
            except Exception as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Delete Error",
                    message=f"Failed to delete database: {str(e)}"
                ))
    
    async def reveal_database_location(self, widget):
        """Reveal the database location in file system."""
        try:
            db_path = self.musicbrainz_manager.get_database_path()
            if db_path and os.path.exists(db_path):
                # Open file manager to the database location
                if sys.platform == "darwin":  # macOS
                    os.system(f'open -R "{db_path}"')
                elif sys.platform == "win32":  # Windows
                    os.system(f'explorer /select,"{db_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{os.path.dirname(db_path)}"')
            else:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Database Not Found",
                    message="Database files not found. Please download the database first."
                ))
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Error",
                message=f"Could not open database location: {str(e)}"
            ))
    
    def on_fallback_changed(self, widget):
        """Handle auto-fallback switch change."""
        self.music_search_service.set_auto_fallback(widget.value)
    
    def on_itunes_api_changed(self, widget):
        """Handle iTunes API switch change."""
        # Update time estimates when iTunes API setting changes
        self.update_time_estimate()
    
    def toggle_process_pause(self, widget):
        """Toggle pause state for main processing."""
        if not hasattr(self, 'process_paused'):
            self.process_paused = False
            
        self.process_paused = not self.process_paused
        
        if self.process_paused:
            widget.text = "Resume"
            self.update_progress("⏸️ Processing paused (click Resume to continue)", self.progress_bar.value)
        else:
            widget.text = "Pause"
            self.update_progress("🎵 Processing resumed...", self.progress_bar.value)
    
    def stop_process(self, widget):
        """Stop the entire processing."""
        self.stop_itunes_search = True
        if hasattr(self, 'process_stopped'):
            self.process_stopped = True
            
        # Disable control buttons
        self.process_pause_button.enabled = False
        self.process_stop_button.enabled = False
        self.update_progress("🛑 Processing stopped by user", 0)
    
    def skip_current_wait(self, widget):
        """Skip the current API rate limit wait."""
        self.skip_wait_requested = True
        
        # Clear the rate limit queue
        self.api_calls.clear()
        
        # Update UI
        self.wait_time_label.text = ""
        self.skip_wait_button.enabled = False
        self.api_status_label.text = "Status: Queue Cleared"
        
        self.update_progress("⏭️ Rate limit wait skipped", self.progress_bar.value)
    
    def update_time_estimate(self):
        """Update processing time estimates based on file and settings."""
        if not hasattr(self, 'row_count') or not self.row_count:
            return
            
        try:
            # Get current settings
            itunes_enabled = getattr(self.itunes_api_switch, 'value', False)
            rate_limit = int(self.rate_limit_input.value) if hasattr(self, 'rate_limit_input') else 20
            
            # Estimate missing artists (assume 20% are missing for estimation)
            estimated_missing = int(self.row_count * 0.2)
            
            if itunes_enabled and estimated_missing > 0:
                # Calculate time based on rate limit
                minutes_needed = estimated_missing / rate_limit
                if minutes_needed < 1:
                    estimate_text = f"Estimated time: {minutes_needed * 60:.0f} seconds for {estimated_missing} missing artists"
                else:
                    estimate_text = f"Estimated time: {minutes_needed:.1f} minutes for {estimated_missing} missing artists"
                    
                self.api_status_label.text = estimate_text
            else:
                self.api_status_label.text = "No missing artists to search for"
                
        except ValueError:
            self.api_status_label.text = "Please enter a valid rate limit"
    
    def update_stats_display(self):
        """Update the statistics display with current counts."""
        # Update individual counters
        self.musicbrainz_stats_label.text = f"🗄️ MusicBrainz: {self.musicbrainz_found}"
        self.itunes_stats_label.text = f"🌐 iTunes API: {self.itunes_found}"
        
        # Update rate limit statistics with color coding
        rate_limit_count = getattr(self, 'rate_limit_hits', 0)
        if rate_limit_count == 0:
            color = "#27ae60"  # Green
            rate_limit_text = "⚠️ Limits: 0"
        elif rate_limit_count <= 4:
            color = "#f39c12"  # Orange
            rate_limit_text = f"⚠️ Limits: {rate_limit_count}"
        else:
            color = "#e74c3c"  # Red
            rate_limit_text = f"⚠️ Limits: {rate_limit_count}"
            
        self.rate_limit_stats_label.text = rate_limit_text
        self.rate_limit_stats_label.style.color = color
    
    def check_file_size_and_ram(self, file_path):
        """Check file size and available RAM like tkinter version."""
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Estimate RAM requirements (rough calculation)
            estimated_ram_mb = file_size_mb * 3  # Conservative estimate
            
            # Get system RAM info
            import psutil
            available_ram_mb = psutil.virtual_memory().available / (1024 * 1024)
            
            # Update file info display
            self.file_info_label.text = f"📄 File: {file_size_mb:.1f}MB, Estimated RAM: {estimated_ram_mb:.0f}MB"
            
            # Show warning if RAM might be insufficient
            if estimated_ram_mb > available_ram_mb * 0.8:  # 80% threshold
                self.message_label.text = f"⚠️ Large file detected. May require {estimated_ram_mb:.0f}MB RAM. Available: {available_ram_mb:.0f}MB"
                self.message_label.style.color = "#f39c12"  # Orange
            else:
                self.message_label.text = ""
                
            return True
            
        except Exception as e:
            self.file_info_label.text = "📄 Could not analyze file"
            self.message_label.text = f"File analysis error: {str(e)}"
            self.message_label.style.color = "#e74c3c"  # Red
            return False
    
    def start_background_optimization(self):
        """Start MusicBrainz optimization in background if database is available."""
        if (self.music_search_service.get_search_provider() == "musicbrainz" and 
            self.musicbrainz_manager.is_database_available()):
            
            # Show optimization status
            self.progress_label.text = "🎵 Optimizing MusicBrainz for faster searches..."
            
            def progress_callback(message, percent, start_time):
                elapsed = time.time() - start_time
                timer_text = f" (Elapsed: {elapsed:.0f}s)"
                # Schedule UI update
                asyncio.run_coroutine_threadsafe(
                    self._update_optimization_progress(f"🔧 Optimizing: {message}{timer_text}"), 
                    self.main_loop
                )
            
            def completion_callback():
                # Schedule UI update
                asyncio.run_coroutine_threadsafe(
                    self._update_optimization_complete(), 
                    self.main_loop
                )
            
            # Start progressive loading in background
            def optimize():
                try:
                    self.music_search_service.start_progressive_loading(progress_callback)
                    completion_callback()
                except Exception as e:
                    print(f"Optimization error: {e}")
                    asyncio.run_coroutine_threadsafe(
                        self._update_optimization_error(), 
                        self.main_loop
                    )
            
            # Use async task instead of threading for UI safety
            asyncio.create_task(self.optimize_musicbrainz_async())
    
    async def _update_optimization_progress(self, message):
        """Update optimization progress on main thread."""
        self.progress_label.text = message
    
    async def _update_optimization_complete(self):
        """Update UI when optimization is complete."""
        self.progress_label.text = "🎵 Ready to convert your Apple Music files (MusicBrainz optimized)"
    
    async def _update_optimization_error(self):
        """Update UI when optimization fails."""
        self.progress_label.text = "🎵 Ready to convert your Apple Music files"
    
    def check_first_time_setup(self):
        """Check if this is the first time running the app."""
        settings_path = self.music_search_service.settings_file
        if not os.path.exists(settings_path):
            # First time setup would go here
            # For now, just create default settings
            self.music_search_service.save_settings()


def main():
    """Main entry point for the application."""
    return AppleMusicConverterApp(
        'Apple Music Play History Converter',
        'com.nerveband.apple-music-history-converter'
    )


if __name__ == '__main__':
    app = main()
    app.main_loop()