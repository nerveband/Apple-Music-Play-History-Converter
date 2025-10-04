#!/usr/bin/env python3
"""
Apple Music Play History Converter - Toga GUI Version
Converts Apple Music CSV files to Last.fm compatible format.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, START, CENTER, END
import pandas as pd
import httpx
import time
import threading
from collections import deque
import json
import os
import sys
import csv
import io
import platform
import logging
import subprocess
from pathlib import Path
from threading import Lock
from datetime import datetime

logger = logging.getLogger(__name__)
try:
    from . import music_search_service_v2
    from . import optimization_modal
    from .trace_utils import TRACE_ENABLED, instrument_widget, trace_call, trace_log
    from .ultra_fast_csv_processor import UltraFastCSVProcessor
except ImportError:
    import music_search_service_v2
    import optimization_modal
    from trace_utils import TRACE_ENABLED, instrument_widget, trace_call, trace_log
    from ultra_fast_csv_processor import UltraFastCSVProcessor
MusicSearchService = music_search_service_v2.MusicSearchServiceV2
import re
import asyncio
try:
    import darkdetect
except ImportError:
    darkdetect = None


class AppleMusicConverterApp(toga.App):
    """Main application class for Apple Music Play History Converter using Toga."""
    
    def _schedule_ui_update(self, coro):
        """Helper to safely schedule async UI updates from sync code."""
        try:
            loop = asyncio.get_running_loop()
            return self._schedule_ui_update(coro, loop)
        except RuntimeError:
            # No loop running, create task directly
            return asyncio.create_task(coro)

    @trace_call("App.startup")
    def startup(self):
        """Initialize the application and create the main window."""
        if TRACE_ENABLED:
            trace_log.debug("Startup sequence initiated")
        # NOTE: Toga manages the event loop automatically - no manual storage needed
        # Removed: self.main_loop = asyncio.get_event_loop()

        # Initialize state variables
        self.pause_itunes_search_flag = False
        self.stop_itunes_search_flag = False
        # Removed: self.processing_thread = None (using async/await instead of threads)
        self.file_size = 0
        self.row_count = 0
        self.current_file_path = None
        self.detected_file_type = None
        self.processed_df = None  # Store processed data for reuse like tkinter
        self.musicbrainz_found = 0
        self.itunes_found = 0
        self.last_output_file = None  # Track last saved file for reprocessing
        
        # Rate limiting setup (iTunes API)
        self.api_calls = deque(maxlen=20)  # Track last 20 API calls
        self.api_lock = Lock()  # Thread-safe lock for API calls
        self.rate_limit_timer = None
        self.api_wait_start = None
        self.wait_duration = 0
        self.skip_wait_requested = False
        self.force_itunes_next = False  # Track when iTunes should be forced for next search
        self.active_search_provider = None  # Track what's currently running
        self.is_search_interrupted = False  # Track if search was stopped by user
        self.failed_requests = []  # Track failed iTunes requests for retry reporting

        # Processing counters
        self.musicbrainz_count = 0
        self.itunes_count = 0
        self.rate_limit_hits = 0
        self.last_rate_limit_time = None

        # Timing tracking
        self.musicbrainz_search_time = 0
        self.itunes_search_time = 0

        # Apply dark mode if system is using it (must be done before build_ui)
        self.setup_theme()
        self.setup_design_language()

        # Create main window following HIG size guidelines
        self.main_window = toga.MainWindow(
            title=self.formal_name,
            size=(1200, 900)  # Increased size to accommodate larger content areas
        )

        # Initialize V2 music search service with modal integration
        self.music_search_service = MusicSearchService()
        self.music_search_service.set_parent_window(self.main_window)
        # Set rate limit callbacks to update UI
        self.music_search_service.rate_limit_callback = self.on_rate_limit_hit
        self.music_search_service.rate_limit_wait_callback = self.on_rate_limit_wait
        self.music_search_service.rate_limit_hit_callback = self.on_actual_rate_limit_detected
        self.music_search_service.rate_limit_discovered_callback = self.on_rate_limit_discovered
        print(f"DEBUG: V2 MusicSearchService initialized with provider: {self.music_search_service.get_search_provider()}")

        # Build the UI
        self.build_ui()
        
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

    def setup_design_language(self):
        """Define shared spacing, typography, and color tokens for consistent UI design."""
        base_spacing = 8

        # Spacing scale aligned with the 8pt grid recommended by Apple HIG
        self.spacing = {
            "xxs": int(base_spacing / 2),  # 4pt
            "xs": base_spacing,            # 8pt
            "sm": base_spacing * 2,        # 16pt
            "md": base_spacing * 3,        # 24pt
            "lg": base_spacing * 4,        # 32pt
            "xl": base_spacing * 5         # 40pt
        }

        # Color palette - let system handle text colors for dark mode compatibility
        # Only set colors when absolutely necessary (like accents)
        # DO NOT set text colors - let Toga use system defaults for proper dark mode support
        self.colors = {
            "background": "#FFFFFF" if not getattr(self, "is_dark_mode", False) else "#1C1C1E",
            "sidebar": "#F2F2F7" if not getattr(self, "is_dark_mode", False) else "#2C2C2E",
            "card": "#FFFFFF" if not getattr(self, "is_dark_mode", False) else "#1C1C1E",
            "border": "#E5E5EA" if not getattr(self, "is_dark_mode", False) else "#38383A",
            "text_primary": "#000000" if not getattr(self, "is_dark_mode", False) else "#FFFFFF",
            "text_secondary": "#666666" if not getattr(self, "is_dark_mode", False) else "#98989D",
            "text_muted": "#999999" if not getattr(self, "is_dark_mode", False) else "#636366",
            "accent": "#007AFF" if not getattr(self, "is_dark_mode", False) else "#0A84FF"
        }

        # Typography scale for consistent hierarchy across platforms
        self.typography = {
            "large_title": {
                "font_size": 18,  # Reduced by 4 points
                "font_weight": "bold"
            },
            "title": {
                "font_size": 14,  # Minimum 10 points
                "font_weight": "bold"
            },
            "headline": {
                "font_size": 12,  # Minimum 10 points
                "font_weight": "bold"
            },
            "body": {
                "font_size": 10  # Minimum 10 points
            },
            "caption": {
                "font_size": 10  # Minimum 10 points
            }
        }

        # Shared layout tokens for margins and insets
        self.layout_tokens = {
            "window_margin": self.spacing["md"],
            "section_gap": self.spacing["sm"],
            "card_inset": self.spacing["xs"],
            "sidebar_width": 380  # Increase width to prevent text cutoff
        }

    def get_color(self, color_name):
        """Helper to safely get colors, returning None for background colors to prevent white artifacts."""
        color = self.colors.get(color_name)
        # Return None for background colors to prevent white artifacts during scrolling
        if color_name in ["background", "sidebar", "card"] or color is None:
            return None
        return color

    def get_style_with_color(self, base_style, color_name):
        """Helper to create style dict with safe color handling.

        Only adds color to style if it's not None - this allows system
        colors to be used automatically for dark mode compatibility.
        """
        style = base_style.copy()
        color = self.get_color(color_name)
        # Only add color if it's actually set (not None)
        # This lets Toga use system default colors for dark mode
        if color is not None:
            style["color"] = color
        return style

    def get_pack_style(self, **kwargs):
        """Create a Pack style, removing None color values.

        This prevents ValueError from Toga when color=None is passed.
        For dark mode compatibility, we don't set color at all (let system handle it).
        """
        # Remove color if it's None (let system handle text colors)
        if "color" in kwargs and kwargs["color"] is None:
            del kwargs["color"]
        return Pack(**kwargs)

    def create_section_header(self, step_number, title, subtitle=None):
        """Return a consistently styled section header with optional subtitle."""
        header_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        title_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER
            )
        )

        if step_number is not None:
            step_label = toga.Label(
                f"{step_number}.",
                style=self.get_pack_style(
                    **self.typography["headline"],
                    color=self.colors["text_secondary"],
                    margin_right=self.spacing["xs"]
                )
            )
            title_row.add(step_label)

        title_label = toga.Label(
            title,
            style=self.get_pack_style(
                **self.typography["headline"],
                color=self.colors["text_primary"]
            )
        )
        title_row.add(title_label)
        header_box.add(title_row)

        if subtitle:
            subtitle_label = toga.Label(
                subtitle,
                style=self.get_pack_style(
                    **self.typography["body"],
                    color=self.colors["text_secondary"],
                    margin_top=self.spacing["xxs"]
                )
            )
            header_box.add(subtitle_label)

        return header_box

    def sidebar_heading(self, title, description=None):
        """Return a sidebar heading with optional helper description."""
        heading_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        heading_box.add(
            toga.Label(
                title,
                style=self.get_pack_style(
                    **self.typography["title"],
                    color=self.colors["text_primary"]
                )
            )
        )

        if description:
            heading_box.add(
                toga.Label(
                    description,
                    style=self.get_pack_style(
                        **self.typography["caption"],
                        color=self.colors["text_secondary"]
                    )
                )
            )

        return heading_box

    def section_divider(self):
        """Return a subtle divider that respects the app's color palette."""
        return toga.Box(
            style=Pack(
                height=1,
                # Remove background_color to prevent white artifacts
                margin_top=self.spacing["sm"],
                margin_bottom=self.spacing["sm"]
            )
        )

    @trace_call("App.build_ui")
    def build_ui(self):
        """Build the main user interface following Apple's Human Interface Guidelines."""
        # Root container with themed background
        root_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1
                # Remove background_color to prevent white artifacts
            )
        )

        # Primary content row with shared window margin
        content_row = toga.Box(
            style=Pack(
                direction=ROW,
                flex=1,
                margin=self.layout_tokens["window_margin"]
            )
        )

        # Left side - scrollable main workflow area with inset content
        main_content_shell = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1,
                margin_right=self.spacing["md"]
                # Remove background_color to prevent white artifacts
            )
        )

        main_content_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1,
                margin=self.layout_tokens["card_inset"]
            )
        )

        # Header section with HIG-compliant spacing
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

        main_content_shell.add(main_content_box)

        content_row.add(main_content_shell)

        # Right side - Settings sidebar with HIG-compliant fixed width
        self.settings_tab = self.create_comprehensive_settings_panel()
        content_row.add(self.settings_tab)

        root_container.add(content_row)

        # Set main window content
        self.main_window.content = root_container
    
    def create_header_section(self):
        """Create the header section following HIG typography hierarchy."""
        header_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        title_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=self.spacing["xs"]
            )
        )

        title_label = toga.Label(
            "Apple Music Play History Converter",
            style=Pack(
                **self.get_style_with_color(self.typography["large_title"], "text_primary"),
                flex=1
            )
        )
        title_row.add(title_label)

        instructions_button = toga.Button(
            "How to Use",
            on_press=self.show_instructions,
            style=self.get_pack_style(
                margin_left=self.spacing["xxs"],
                margin_top=self.spacing["xxs"],
                margin_bottom=self.spacing["xxs"],
                color=self.colors["accent"]
            )
        )
        instrument_widget(instructions_button, "instructions_button")
        title_row.add(instructions_button)
        header_box.add(title_row)

        subtitle = toga.Label(
            "Convert Apple Music CSV exports into scrobble-ready data.",
            style=Pack(
                **self.get_style_with_color(self.typography["body"], "text_secondary"),
                margin_bottom=self.spacing["lg"]  # Extra space before next section
            )
        )
        header_box.add(subtitle)

        return header_box
    
    def create_content_area(self):
        """Create the content area with results and preview."""
        # Results and preview in horizontal split container
        preview_section = self.create_preview_section()
        results_section = self.create_results_section()

        split_container = toga.SplitContainer(
            content=[preview_section, results_section],
            direction=toga.SplitContainer.HORIZONTAL,
            style=Pack(
                flex=1,
                margin_bottom=self.layout_tokens["section_gap"]
                # Remove background_color to prevent white artifacts
            )
        )

        return split_container
    
    @trace_call("App.create_settings_panel")
    def create_comprehensive_settings_panel(self):
        """Create HIG-compliant settings sidebar with proper typography and spacing."""
        # Responsive settings panel - no fixed width or scroll container
        settings_shell = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_left=self.spacing["md"],
                margin_right=self.spacing["md"],
                margin_bottom=self.spacing["md"]
                # No margin_top to align Settings title with main title
                # No fixed width - allows content to size naturally
                # No background_color - transparent sidebar
            )
        )

        content = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_left=self.layout_tokens["card_inset"],
                margin_right=self.layout_tokens["card_inset"],
                margin_bottom=self.layout_tokens["card_inset"],
                # No margin_top to align with main title
            )
        )
        # Keep references for dynamic section toggling
        # self.settings_scroll = settings_scroll  # Removed
        self.settings_shell_box = settings_shell
        self.settings_content_box = content
        content.add(
            self.sidebar_heading("Settings", "")
        )

        content.add(self.create_provider_section())
        content.add(self.section_divider())

        # Always show both database and iTunes sections per user request
        self.database_section = self.create_database_section()
        content.add(self.database_section)

        content.add(self.section_divider())
        self.itunes_section = self.create_itunes_api_section()
        content.add(self.itunes_section)

        settings_shell.add(content)
        # settings_scroll.content = settings_shell  # Removed

        return settings_shell  # Return shell directly, not wrapped in scroll container
    
    def create_provider_section(self):
        """Create HIG-compliant provider section with proper form design."""
        provider_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["md"]
            )
        )

        provider_box.add(
            toga.Label(
                "Music search provider",
                style=self.get_pack_style(
                    **self.typography["headline"],
                    color=self.colors["text_primary"],
                    margin_bottom=self.spacing["xs"]
                )
            )
        )

        # Radio buttons for provider selection (using Switch widgets)
        provider_buttons_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=self.spacing["xs"]
            )
        )

        # Set initial provider
        current_provider = self.music_search_service.get_search_provider()
        self.current_provider = current_provider

        self.musicbrainz_radio = toga.Switch(
            "MusicBrainz",
            value=(current_provider == "musicbrainz"),
            on_change=self.on_musicbrainz_selected,
            style=Pack(margin_right=self.spacing["md"])
        )
        provider_buttons_box.add(self.musicbrainz_radio)

        self.itunes_radio = toga.Switch(
            "iTunes API",
            value=(current_provider == "itunes"),
            on_change=self.on_itunes_selected,
            style=Pack()
        )
        provider_buttons_box.add(self.itunes_radio)

        provider_box.add(provider_buttons_box)

        return provider_box
    
    def create_database_section(self):
        """Create HIG-compliant database section."""
        db_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["md"]
            )
        )

        db_box.add(
            toga.Label(
                "Offline database",
                style=Pack(
                    **self.typography["headline"],
                    margin_bottom=self.spacing["xxs"]
                )
            )
        )

        # Remove redundant description - it's implied by the title

        status_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        # Removed "Status" label per user request
        # status_container.add(
        #     toga.Label(
        #         "Status",
        #         style=self.get_pack_style(
        #             **self.typography["body"],
        #             color=self.colors["text_secondary"],
        #             margin_bottom=self.spacing["xxs"]
        #         )
        #     )
        # )

        self.db_status_label = toga.Label(
            "Not Downloaded",
            style=self.get_pack_style(
                **self.typography["body"],
                color=self.colors["text_primary"],
                font_weight="bold"
            )
        )
        status_container.add(self.db_status_label)
        db_box.add(status_container)

        self.download_button = toga.Button(
            "Download Database (~2GB)",
            on_press=self.download_database,
            style=Pack(
                margin_bottom=self.spacing["xs"],
                margin_right=self.spacing["xxs"]
            )
        )
        instrument_widget(self.download_button, "download_button")
        db_box.add(self.download_button)

        secondary_row = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=self.spacing["xs"]
            )
        )

        self.check_updates_button = toga.Button(
            "Check Updates",
            on_press=self.check_for_updates,
            style=Pack(
                flex=1,
                margin_right=self.spacing["xxs"]
            )
        )
        instrument_widget(self.check_updates_button, "check_updates_button")
        secondary_row.add(self.check_updates_button)

        self.manual_import_button = toga.Button(
            "Manual Import",
            on_press=self.manual_import_database,
            style=Pack(
                flex=1,
                margin_left=self.spacing["xxs"]
            )
        )
        instrument_widget(self.manual_import_button, "manual_import_button")
        secondary_row.add(self.manual_import_button)
        db_box.add(secondary_row)

        manage_row = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=self.spacing["xs"]
            )
        )

        self.delete_db_button = toga.Button(
            "Delete Database",
            on_press=self.delete_database,
            style=Pack(
                flex=1,
                margin_top=self.spacing["xxs"],
                margin_bottom=self.spacing["xxs"],
                margin_right=self.spacing["xxs"],
                color="#FF453A" if self.is_dark_mode else "#D70015"
            )
        )
        instrument_widget(self.delete_db_button, "delete_db_button")
        manage_row.add(self.delete_db_button)

        self.reveal_location_button = toga.Button(
            "Show Path of Database",
            on_press=self.reveal_database_location,
            style=Pack(
                flex=1,
                margin_top=self.spacing["xxs"],
                margin_bottom=self.spacing["xxs"],
                margin_left=self.spacing["xxs"]
            )
        )
        instrument_widget(self.reveal_location_button, "reveal_location_button")
        manage_row.add(self.reveal_location_button)
        db_box.add(manage_row)

        # Optimization status and button (for when DB is downloaded)
        self.optimization_status_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_top=self.spacing["xs"],
                margin_bottom=self.spacing["xs"]
            )
        )

        self.optimization_status_label = toga.Label(
            "",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        self.optimization_status_container.add(self.optimization_status_label)

        self.optimize_now_button = toga.Button(
            "Optimize Now",
            on_press=self.optimize_musicbrainz_handler,
            style=Pack(
                margin_bottom=self.spacing["xs"]
            )
        )
        instrument_widget(self.optimize_now_button, "optimize_now_button")
        self.optimization_status_container.add(self.optimize_now_button)
        db_box.add(self.optimization_status_container)

        info_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        info_inset = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_top=self.spacing["xs"],
                margin_bottom=self.spacing["xs"]
            )
        )

        self.db_size_label = toga.Label(
            "Size: 0 bytes",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        info_inset.add(self.db_size_label)

        # Add database location path - ensure full path is not truncated
        self.db_location_label = toga.Label(
            "Location: Not set",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"]
                # Allow text to wrap if needed to show full path
            )
        )
        info_inset.add(self.db_location_label)

        self.db_tracks_label = toga.Label(
            "",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        info_inset.add(self.db_tracks_label)

        self.db_updated_label = toga.Label(
            "Never updated",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"]
            )
        )
        info_inset.add(self.db_updated_label)

        info_container.add(info_inset)
        db_box.add(info_container)

        return db_box
    
    # Removed create_advanced_options_section - no placeholder sections
    
    def create_itunes_api_section(self):
        """Create HIG-compliant iTunes API configuration section."""
        itunes_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["md"]
            )
        )

        itunes_box.add(
            toga.Label(
                "iTunes API settings",
                style=self.get_pack_style(
                    **self.typography["headline"],
                    color=self.colors["text_primary"],
                    margin_bottom=self.spacing["xs"]  # Increased since description removed
                )
            )
        )

        # Description removed per user request
        # itunes_box.add(
        #     toga.Label(
        #         "Configure secondary search for missing artists.",
        #         style=self.get_pack_style(
        #             **self.typography["caption"],
        #             color=self.colors["text_secondary"],
        #             margin_bottom=self.spacing["xs"]
        #         )
        #     )
        # )

        # "Use iTunes for missing artists" switch removed per user request
        # self.itunes_api_switch = toga.Switch(
        #     "Use iTunes for missing artists",
        #     value=False,
        #     on_change=self.on_itunes_api_changed,
        #     style=Pack(
        #         margin_bottom=self.spacing["sm"]
        #     )
        # )
        # instrument_widget(self.itunes_api_switch, "itunes_api_switch")
        # itunes_box.add(self.itunes_api_switch)

        # Adaptive rate limit toggle
        use_adaptive = self.music_search_service.settings.get("use_adaptive_rate_limit", True)
        self.adaptive_rate_limit_switch = toga.Switch(
            "Use adaptive rate limit (learns from rate limit errors)",
            value=use_adaptive,
            on_change=self.on_adaptive_rate_limit_changed,
            style=Pack(
                margin_bottom=self.spacing["xs"]
            )
        )
        itunes_box.add(self.adaptive_rate_limit_switch)

        # Parallel processing toggle
        use_parallel = self.music_search_service.settings.get("use_parallel_requests", False)
        self.parallel_mode_switch = toga.Switch(
            "Use parallel requests (faster but more aggressive)",
            value=use_parallel,
            on_change=self.on_parallel_mode_changed,
            style=Pack(
                margin_bottom=self.spacing["xs"]
            )
        )
        itunes_box.add(self.parallel_mode_switch)

        # Rate limit control with HIG form layout
        rate_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=self.spacing["xs"]
            )
        )
        rate_label = toga.Label(
            "Rate limit:",
            style=self.get_pack_style(
                **self.typography["body"],
                color=self.colors["text_primary"],
                margin_right=self.spacing["xxs"]
            )
        )
        rate_row.add(rate_label)

        # Get current rate limit from settings
        current_rate_limit = self.music_search_service.settings.get("itunes_rate_limit", 20)

        self.rate_limit_input = toga.TextInput(
            value=str(current_rate_limit),
            style=Pack(
                width=60,
                margin_right=self.spacing["xxs"]
            )
        )
        rate_row.add(self.rate_limit_input)

        rate_unit_label = toga.Label(
            "req/min",
            style=self.get_pack_style(
                **self.typography["body"],
                color=self.colors["text_secondary"],
                margin_right=self.spacing["xs"]
            )
        )
        rate_row.add(rate_unit_label)

        # Save button
        self.save_rate_limit_button = toga.Button(
            "Save",
            on_press=self.save_rate_limit,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        rate_row.add(self.save_rate_limit_button)

        # Current rate limit display
        self.current_rate_label = toga.Label(
            f"Current: {current_rate_limit} req/min",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"]
            )
        )
        rate_row.add(self.current_rate_label)

        itunes_box.add(rate_row)

        # Discovered rate limit display
        discovered_limit = self.music_search_service.settings.get("discovered_rate_limit", None)
        use_adaptive = self.music_search_service.settings.get("use_adaptive_rate_limit", True)

        if discovered_limit:
            safety_margin = self.music_search_service.settings.get("rate_limit_safety_margin", 0.8)
            effective_limit = int(discovered_limit * safety_margin)
            discovered_text = f"Discovered: {discovered_limit} req/min (using {effective_limit})"
        else:
            if use_adaptive:
                discovered_text = "Discovery mode: Using 600 req/min until first rate limit (~10 req/sec)"
            else:
                discovered_text = "Discovered: None yet (adaptive mode off)"

        self.discovered_limit_label = toga.Label(
            discovered_text,
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["accent"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        itunes_box.add(self.discovered_limit_label)

        # Rate limit warning with HIG caption style
        itunes_box.add(
            toga.Label(
                "Official: ~20 req/min | Observed: 10-350 req/min (varies by IP)",
                style=self.get_pack_style(
                    **self.typography["caption"],
                    color=self.colors["text_secondary"],
                    margin_bottom=self.spacing["xs"]
                )
            )
        )

        # API Status with HIG typography
        status_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.spacing["xs"]
            )
        )

        self.api_status_label = toga.Label(
            "Status: Ready",
            style=self.get_pack_style(
                **self.typography["body"],
                color=self.colors["text_primary"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        status_container.add(self.api_status_label)

        self.api_timer_label = toga.Label(
            "",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"]
            )
        )
        status_container.add(self.api_timer_label)
        itunes_box.add(status_container)

        # Note: Control buttons are in the main processing section to avoid duplication
        
        # Remove control help text - keep interface clean
        
        return itunes_box
    
    def create_file_selection_section(self):
        """Create HIG-compliant file selection section."""
        file_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=self.layout_tokens["section_gap"]
            )
        )

        file_box.add(
            self.create_section_header(
                step_number=None,
                title="Select Apple Music Export"
            )
        )

        # Row 1: Browse CSV button, dropdown, then Convert button (with spacing)
        file_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=self.spacing["xxs"]
            )
        )

        browse_button = toga.Button(
            "Browse CSV",
            on_press=self.browse_file,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        instrument_widget(browse_button, "browse_button")
        file_row.add(browse_button)

        self.file_type_selection = toga.Selection(
            items=[
                "Play History Daily Tracks",
                "Recently Played Tracks",
                "Play Activity",
                "Other/Generic CSV"
            ],
            style=Pack(
                width=220,
                flex=1
            )
        )
        instrument_widget(self.file_type_selection, "file_type_selection")
        file_row.add(self.file_type_selection)

        self.convert_button = toga.Button(
            "Convert to Last.fm Format",
            on_press=self.convert_csv,
            style=Pack(
                margin_left=self.spacing["lg"]
            )
        )
        self.convert_button.enabled = False
        instrument_widget(self.convert_button, "convert_button")
        file_row.add(self.convert_button)

        file_box.add(file_row)

        # Row 2: File path label (similar to save status label)
        self.file_path_label = toga.Label(
            "No file selected",
            style=Pack(
                font_size=9,  # Smaller font to fit longer filenames
                color=self.colors["text_muted"],
                margin_bottom=self.spacing["sm"]
            )
        )
        file_box.add(self.file_path_label)

        # Remove redundant helper text - it's implied

        return file_box
    
    def create_results_section(self):
        """Create the results section with much more generous spacing and height."""
        results_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1
            )
        )

        # Save Output section - title and button on same row
        save_header_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=self.spacing["xs"]
            )
        )

        save_title = toga.Label(
            "Save CSV",
            style=self.get_pack_style(
                **self.typography["headline"],
                color=self.colors["text_primary"],
                margin_right=self.spacing["xs"]
            )
        )
        save_header_row.add(save_title)

        self.save_button = toga.Button(
            "Save CSV",
            on_press=self.save_results,
            enabled=False,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        instrument_widget(self.save_button, "save_button")
        save_header_row.add(self.save_button)

        self.copy_button = toga.Button(
            "Copy to Clipboard",
            on_press=self.copy_results,
            enabled=False,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        instrument_widget(self.copy_button, "copy_button")
        save_header_row.add(self.copy_button)

        # Save status indicator - inline
        self.save_status_label = toga.Label(
            "Save required to enable search",
            style=Pack(
                font_size=9,  # Smaller font to fit longer filenames
                color=self.colors["text_muted"],
                flex=1  # Allow text to use available space
            )
        )
        save_header_row.add(self.save_status_label)

        results_box.add(save_header_row)

        # Search for Missing Artists section - title on top, buttons below
        search_section = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_top=self.spacing["sm"],
                margin_bottom=self.spacing["xs"]
            )
        )

        # Title row
        search_title = toga.Label(
            "Search for Missing Artists",
            style=self.get_pack_style(
                **self.typography["headline"],
                color=self.colors["text_primary"],
                margin_bottom=self.spacing["xs"]
            )
        )
        search_section.add(search_title)

        # Buttons row - left group + spacer + right-aligned export button
        buttons_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER
            )
        )

        # Initialize with current provider in button text
        initial_provider = self.music_search_service.get_search_provider()
        button_text = "Search with MusicBrainz" if initial_provider == "musicbrainz" else "Search with iTunes"

        self.reprocess_button = toga.Button(
            button_text,
            on_press=self.reprocess_missing_artists,
            enabled=False,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        instrument_widget(self.reprocess_button, "reprocess_button")
        buttons_row.add(self.reprocess_button)

        # Stop button
        self.process_stop_button = toga.Button(
            "Stop",  # Will change to provider-specific text
            on_press=self.stop_process,
            enabled=False,
            style=Pack(
                margin_right=self.spacing["xs"],
                color="#FF453A" if self.is_dark_mode else "#D70015"
            )
        )
        instrument_widget(self.process_stop_button, "process_stop_button")
        buttons_row.add(self.process_stop_button)

        # Skip Rate Limit button
        self.skip_wait_button = toga.Button(
            "Skip Rate Limit Wait",
            on_press=self.skip_current_wait,
            enabled=False,
            style=Pack(
                margin_right=self.spacing["xs"]
            )
        )
        instrument_widget(self.skip_wait_button, "skip_wait_button")
        buttons_row.add(self.skip_wait_button)

        # Spacer to push Export button to the right
        spacer = toga.Box(style=Pack(flex=1))
        buttons_row.add(spacer)

        # Export Missing Artists button - right-aligned
        self.save_missing_button = toga.Button(
            "Export Missing Artists List",
            on_press=self.save_missing_artists_csv,
            enabled=False,
            style=Pack()
        )
        instrument_widget(self.save_missing_button, "save_missing_button")
        buttons_row.add(self.save_missing_button)

        search_section.add(buttons_row)
        results_box.add(search_section)

        # Log section
        preview_header_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_top=self.spacing["sm"],
                margin_bottom=self.spacing["xs"]
            )
        )

        preview_title = toga.Label(
            "Log",
            style=self.get_pack_style(
                **self.typography["headline"],
                color=self.colors["text_primary"]
            )
        )
        preview_header_row.add(preview_title)
        results_box.add(preview_header_row)

        # MultilineTextInput handles its own scrolling - no need for ScrollContainer wrapper
        # Create style for results text with safe color handling
        results_style = Pack(
            flex=1,
            font_family="monospace",
            font_size=10,  # Minimum 10 points
            margin_bottom=self.spacing["xs"]
        )
        text_color = self.get_color("text_primary")
        if text_color:
            results_style.color = text_color

        self.results_text = toga.MultilineTextInput(
            readonly=True,
            placeholder="Converted results will appear here once the file is processed.",
            style=results_style
        )
        results_box.add(self.results_text)

        return results_box
    
    def create_preview_section(self):
        """Create the preview section with proper scrolling support."""
        preview_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1
            )
        )

        # Use consistent section header
        preview_header_row = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=self.spacing["xs"]
            )
        )

        # Title label - use same headline style as other sections
        preview_title_label = toga.Label(
            "Preview",
            style=self.get_pack_style(
                **self.typography["headline"],
                color=self.colors["text_primary"],
                flex=1
            )
        )
        preview_header_row.add(preview_title_label)

        # Info label (right-aligned)
        self.preview_info_label = toga.Label(
            "Select a CSV to see the first rows.",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"]
            )
        )
        preview_header_row.add(self.preview_info_label)

        preview_box.add(preview_header_row)

        # Table handles its own scrolling - no need for ScrollContainer wrapper
        self.preview_table = toga.Table(
            headings=["Artist", "Track", "Album", "Timestamp", "Album Artist", "Duration"],
            data=[],
            style=Pack(
                flex=1,
                # Responsive height - no fixed constraint
                margin_bottom=self.spacing["xs"]
            )
        )

        preview_box.add(self.preview_table)

        return preview_box
    
    def create_progress_section(self):
        """Create clean progress section with clear organization and proper iconography."""
        progress_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_top=self.spacing["xs"],
                margin_bottom=self.spacing["xs"]
            )
        )

        progress_box.add(
            self.create_section_header(
                step_number=None,
                title="Progress",
                subtitle=None
            )
        )

        # Progress bar - no left or right padding per user request
        self.progress_bar = toga.ProgressBar(
            max=100,
            style=Pack(
                flex=0,
                height=12,
                margin_bottom=self.spacing["xxs"]
            )
        )
        progress_box.add(self.progress_bar)

        # Main status message - no left padding per user request
        self.progress_label = toga.Label(
            "Ready to convert your Apple Music history",
            style=self.get_pack_style(
                **self.typography["body"],
                color=self.colors["text_primary"],
                margin_right=self.spacing["sm"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        progress_box.add(self.progress_label)

        # Detailed processing stats (NEW)
        self.detailed_stats_label = toga.Label(
            "",
            style=self.get_pack_style(
                **self.typography["caption"],
                color=self.colors["text_secondary"],
                margin_left=self.spacing["sm"],
                margin_right=self.spacing["sm"],
                margin_bottom=self.spacing["xxs"]
            )
        )
        progress_box.add(self.detailed_stats_label)

        # Search provider stats with icons
        stats_frame = self.create_search_provider_stats()
        progress_box.add(stats_frame)

        # Processing control buttons moved to Search for Missing Artists section
        # control_frame = self.create_processing_controls()  # Removed - buttons now inline with search
        # progress_box.add(control_frame)

        return progress_box
    
    def create_search_provider_stats(self):
        """Create clear search provider statistics display with proper icons."""
        # Stats and rate limit warning removed - now shown inline in log
        stats_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_left=self.spacing["sm"],
                margin_right=self.spacing["sm"],
                margin_bottom=self.spacing["xs"]
            )
        )

        return stats_box

    # create_processing_controls() removed - buttons now inline with Search for Missing Artists
    # def create_processing_controls(self):
    #     """Create processing control buttons (Pause/Stop only during active processing)."""
    #     # Buttons moved to search_header_row for better UX grouping

    async def detect_and_handle_converted_csv(self, file_path, df):
        """Detect if CSV is already converted and offer resume if missing artists exist."""

        # Check if already converted (has Last.fm columns)
        required_cols = ['Artist', 'Track', 'Album', 'Timestamp']
        has_lastfm_columns = all(col in df.columns for col in required_cols)

        if not has_lastfm_columns:
            return False  # Not converted yet, continue normal flow

        # Count missing artists
        artist_col = 'Artist' if 'Artist' in df.columns else 'artist'

        # Convert to string and handle missing values safely
        artist_series = df[artist_col].fillna('').astype(str)
        missing_mask = (artist_series.str.strip() == '') | (artist_series == 'Unknown Artist')

        missing_count = missing_mask.sum()
        found_count = len(df) - missing_count

        if missing_count == 0:
            # Complete file
            await self.main_window.dialog(toga.InfoDialog(
                title="✅ File Complete",
                message=f"This file is already complete!\n\n"
                        f"Total tracks: {len(df):,}\n"
                        f"All artists found: {found_count:,}"
            ))
            return True

        # Has missing artists - offer resume
        result = await self.main_window.dialog(toga.ConfirmDialog(
            title="Resume Previous Search?",
            message=f"This file has already been converted:\n\n"
                    f"✅ Found: {found_count:,} artists\n"
                    f"❌ Missing: {missing_count:,} artists\n\n"
                    f"Continue searching for the missing ones?"
        ))

        if result:
            # User wants to resume
            self.processed_df = df
            self.current_save_path = Path(file_path)  # Resume to same file!

            # Track source filename for future saves
            self.source_filename = Path(file_path).stem

            # Update preview
            preview_rows = min(100, len(df))
            self.update_preview(df.head(preview_rows), total_rows=len(df))
            self.update_missing_artist_count()

            # Update save status indicator
            self.update_save_status()

            # Update search button state (enabled since path is set)
            self.update_search_button_state()

            # Enable Save and Copy buttons
            self.save_button.enabled = True
            self.copy_button.enabled = True

            print(f"📂 Resumed session from: {file_path}")
            print(f"💾 Progress will auto-save to: {file_path}")

            # Automatically start search
            await self.reprocess_missing_artists(None)

        return True

    @trace_call("App.browse_file")
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
                    # Update file path label with full path
                    self.file_path_label.text = str(self.current_file_path)

                    # Track source filename for auto-save naming
                    self.source_filename = Path(file_path_str).stem

                    # Reset progress message and search state when new file is selected
                    self.update_progress("Ready to convert your Apple Music history", 0)

                    # Reset search counters
                    self.musicbrainz_found = 0
                    self.itunes_found = 0
                    self.musicbrainz_count = 0

                    # Clear processed data so searches can run again
                    self.processed_df = None
                    self.last_output_file = None

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
                    
                    # Comprehensive file analysis like tkinter version
                    try:
                        success = self.analyze_file_comprehensive(self.current_file_path)
                        if not success:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="File Analysis Error",
                                message="Could not analyze file. Please select a valid CSV file."
                            ))
                            return
                        
                        if not hasattr(self, 'row_count') or self.row_count <= 0:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Invalid File",
                                message="File appears to have no data rows. Please select a valid CSV file."
                            ))
                            return
                        
                        # Update songs counter with comprehensive info
                        # self.songs_processed_label.text = f" Songs: 0/{self.row_count:,}"  # Stats removed
                        
                        # Update time estimates based on comprehensive analysis
                        self.update_time_estimate()
                        
                    except Exception as e:
                        await self.main_window.dialog(toga.ErrorDialog(
                            title="File Analysis Error",
                            message=f"Error analyzing file: {str(e)}"
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

                    # Check if this is an already converted CSV (resume detection)
                    try:
                        # Quick read to check if it's already converted
                        df_check = pd.read_csv(self.current_file_path, nrows=1)

                        # If it's already converted, handle it and return early
                        if await self.detect_and_handle_converted_csv(self.current_file_path,
                                                                        pd.read_csv(self.current_file_path)):
                            return  # Converted CSV was handled, don't continue with normal flow
                    except Exception as e:
                        print(f"Note: Could not check for converted CSV (will treat as new file): {e}")
                        # Continue with normal flow if detection fails

                    # Enable convert button
                    self.convert_button.enabled = True

                    # Load and show immediate CSV preview (enhancement over original tkinter version)
                    try:
                        await self.load_immediate_preview()
                    except Exception as e:
                        print(f"Error loading immediate preview: {e}")
                    
                    # Update results with comprehensive info
                    try:
                        file_size_formatted = self.format_file_size(self.file_size)
                        self.update_results(f" File Selected: {os.path.basename(self.current_file_path)}\n"
                                          f" Size: {file_size_formatted} ({self.row_count:,} rows)\n"
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
                    
                    if 'play duration milliseconds' in first_line and 'track description' in first_line:
                        detected_type = "Play History Daily Tracks"
                    elif 'play duration milliseconds' in first_line:
                        detected_type = "Play Activity"
                    elif 'track name' in first_line and 'artist name' in first_line:
                        detected_type = "Recently Played Tracks"
                    else:
                        detected_type = "Other/Generic CSV"
            
            # Apply the detected type
            self.detected_file_type = detected_type
            self.file_type_selection.value = detected_type
            # File type detected successfully
        
        except Exception as e:
            self.detected_file_type = "Other/Generic CSV"
            self.file_type_selection.value = "Other/Generic CSV"
    
    @trace_call("App.convert_csv")
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
        
        # Reset conversion start time for synthetic timestamps
        if hasattr(self, '_conversion_start_time'):
            delattr(self, '_conversion_start_time')
        
        # Update UI for processing
        self.convert_button.enabled = False
        # self.process_pause_button.enabled = True  # Pause button removed
        self.process_stop_button.enabled = True
        # Disable copy and save buttons during processing
        self.copy_button.enabled = False
        self.save_button.enabled = False
        
        # Update progress
        self.progress_label.text = "Processing..."
        if hasattr(self, 'detailed_stats_label'):
            self.detailed_stats_label.text = ""
        
        # Start two-phase processing using async task (Toga best practice)
        asyncio.create_task(self.process_csv_two_phase_async())
    
    def reset_processing_stats(self):
        """Reset all processing statistics."""
        self.musicbrainz_found = 0
        self.itunes_found = 0
        self.rate_limit_hits = 0
        self.processing_start_time = time.time()
        self.force_itunes_next = False  # Reset iTunes continuation flag
        self.active_search_provider = None  # Reset active search
        self.is_search_interrupted = False  # Reset interrupted flag

        # Reset search button text on main thread
        if hasattr(self, 'reprocess_button'):
            self._schedule_ui_update(self._reset_search_button_text())

        # Update display
        self.update_stats_display()
    
    def process_csv_two_phase(self):
        """Process CSV - ONLY loads and converts, does NOT search for missing artists."""
        try:
            # Record start time
            self.processing_start_time = time.time()

            # Phase 1: Load and convert CSV to Last.fm format
            self.update_progress("📁 Loading and converting CSV file...", 10)
            all_tracks = self.load_entire_csv(self.current_file_path, self.file_type_selection.value)

            if not all_tracks:
                self.update_progress("Error: Failed to load CSV file", 0)
                return

            total_tracks = len(all_tracks)
            # self.songs_processed_label.text = f" Songs: {total_tracks:,}/{total_tracks:,}"  # Stats removed

            # Phase 2: Convert to final format (NO artist search here!)
            self.update_progress("🎧 Converting to Last.fm format...", 50)
            final_results = []
            for i, track in enumerate(all_tracks):
                final_track = self.convert_to_final_format(track, i, total_tracks)
                if final_track:
                    final_results.append(final_track)

            # Phase 3: Finalize and display results
            self.update_progress("✅ Finalizing...", 90)
            self.finalize_processing(final_results, self.processing_start_time)
            
        except Exception as e:
            self.update_progress(f"Error: Processing error: {str(e)}", 0)
            self.update_results(f"Error processing file: {str(e)}")
        
        finally:
            # Reset UI state
            self._schedule_ui_update(self._reset_buttons_ui())
    
    async def process_csv_two_phase_async(self):
        """Process CSV - ONLY loads and converts, does NOT search for missing artists."""
        try:
            # Record start time
            self.processing_start_time = time.time()

            # Phase 1: Load and convert CSV to Last.fm format
            self.update_progress("📁 Loading and converting CSV file...", 10)
            all_tracks = await self.load_entire_csv_async(self.current_file_path, self.file_type_selection.value)

            if not all_tracks:
                self.update_progress("Error: Failed to load CSV file", 0)
                return

            total_tracks = len(all_tracks)
            # self.songs_processed_label.text = f" Songs: {total_tracks:,}/{total_tracks:,}"  # Stats removed

            # Phase 2: Final format preparation (data already in Last.fm format from DuckDB)
            self.update_progress("🎧 Finalizing Last.fm format...", 50)

            # Convert tracks to final format
            final_results = []
            for i, track in enumerate(all_tracks):
                final_track = self.convert_to_final_format(track, i, total_tracks)
                if final_track:
                    final_results.append(final_track)

                # Yield control periodically for UI responsiveness
                if i % 1000 == 0:
                    await asyncio.sleep(0.001)

            # Phase 3: Finalize and display results
            await self.finalize_processing_async(final_results, self.processing_start_time)
            
        except Exception as e:
            self.update_progress(f"Error: Processing error: {str(e)}", 0)
            self.update_results(f"Error processing file: {str(e)}")
        
        finally:
            # Reset UI state on main thread, but keep results buttons if processing succeeded
            # Check if we have processed results (indicating successful completion)
            has_results = hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0
            await self._reset_buttons_ui(keep_results_buttons=has_results)
    
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
                
                # Process chunk synchronously (no automatic music search)
                for track in chunk:
                    # Just pass through the track data without music search
                    # Music search should only happen when explicitly requested
                    processed_tracks.append(track)
                
                # Update progress and yield to UI
                progress = 20 + (i / len(all_tracks)) * 30  # 20-50% range
                self.update_progress(f" Processing CSV data: {i+len(chunk)}/{total_tracks}", progress)
                # Stats label removed per user request
                pass
                await asyncio.sleep(0.001)  # Yield to UI thread
            
            return processed_tracks
            
        except Exception as e:
            print(f"Error in process_with_musicbrainz_async: {e}")
            return all_tracks  # Return original tracks on error
    
    async def process_missing_with_musicbrainz_async(self, missing_tracks, processed_tracks, completed_count, total_tracks):
        """REMOVED: Old row-by-row implementation. Use reprocess_missing_artists instead."""
        print("❌ ERROR: process_missing_with_musicbrainz_async() is deprecated!")
        print("   Use the 'Search for Missing Artists' button instead.")
        return processed_tracks

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
    
    @trace_call("App.finalize_processing_async")
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
            self.update_results(f"Error: Error in finalization: {str(e)}")
    
    @trace_call("App.optimize_musicbrainz_async")
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
            
            # Use DuckDB processing for reliable and fast processing
            # This replaces the old row-by-row normalize_track_data approach
            try:
                processed_df = self.process_csv_data(df, file_type)
                if processed_df is None or processed_df.empty:
                    raise ValueError("No valid tracks found after processing")
                
                # Convert DataFrame to list of dicts for compatibility
                tracks = processed_df.to_dict('records')
                print(f"Successfully processed {len(tracks)} tracks from CSV")
                return tracks
                
            except Exception as e:
                raise RuntimeError(f"Error processing CSV data: {str(e)}")
                
        except Exception as e:
            print(f"Error in load_entire_csv: {e}")
            raise RuntimeError(f"Failed to load CSV file: {str(e)}") from e
    
    def normalize_track_data(self, row, file_type, index):
        """Normalize track data from different CSV formats or already-processed DuckDB results."""
        track = {}
        
        try:
            # Check if this is already processed data from DuckDB (has Artist, Track, Album columns)
            if 'Artist' in row and 'Track' in row and 'Album' in row:
                # This is already processed DuckDB data - just copy it
                track['artist'] = str(row.get('Artist', '')).strip() if pd.notna(row.get('Artist', '')) else ''
                track['track'] = str(row.get('Track', '')).strip() if pd.notna(row.get('Track', '')) else ''
                track['album'] = str(row.get('Album', '')).strip() if pd.notna(row.get('Album', '')) else ''
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())  # Synthetic timestamp
                
                # Set duration based on file type
                if "Play History" in file_type or "Recently Played" in file_type:
                    track['duration'] = 180  # Fixed duration for these formats
                else:
                    # For Play Activity, try to get from play_duration or default to 180
                    duration_ms = row.get('play_duration', 0) if pd.notna(row.get('play_duration')) else 0
                    track['duration'] = int(duration_ms) // 1000 if duration_ms > 0 else 180
            
            elif "Play Activity" in file_type:
                track['artist'] = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                track['track'] = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
                track['album'] = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())  # Synthetic timestamp (CSV timestamps ignored)
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
                # For Play History, we'll calculate reverse chronological timestamps in the processing phase
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())  # Temporary - will be recalculated
                # IMPORTANT: For Play History Daily Tracks, duration is ALWAYS 180 seconds (matches tkinter version)
                # Do NOT use "Play Duration Milliseconds" from CSV - it's ignored per original specification
                track['duration'] = 180
                track['row_index'] = index  # Store index for reverse chronological calculation
                
            elif "Recently Played" in file_type:
                # Parse track description format "Artist - Track" (same as Play History)
                track_desc = row.get('Track Description', '') if pd.notna(row.get('Track Description')) else ''
                if ' - ' in track_desc:
                    artist, track_name = track_desc.split(' - ', 1)
                    track['artist'] = artist.strip()
                    track['track'] = track_name.strip()
                else:
                    track['artist'] = ''
                    track['track'] = track_desc.strip()
                track['album'] = str(row.get('Container Description', '')).strip() if pd.notna(row.get('Container Description', '')) else ''
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())  # Synthetic timestamp
                # IMPORTANT: For Recently Played Tracks, duration is ALWAYS 180 seconds (matches tkinter version)
                track['duration'] = 180
                
            else:  # Generic CSV
                # Initialize with defaults
                track['artist'] = ''
                track['track'] = ''
                track['album'] = ''
                track['duration'] = 180  # Default duration
                
                # Try to identify columns
                for col_name, value in row.items():
                    col_lower = str(col_name).lower()
                    if 'artist' in col_lower and not track.get('artist'):
                        track['artist'] = str(value).strip() if pd.notna(value) else ''
                    elif ('track' in col_lower or 'song' in col_lower) and not track.get('track'):
                        track['track'] = str(value).strip() if pd.notna(value) else ''
                    elif 'album' in col_lower and not track.get('album'):
                        track['album'] = str(value).strip() if pd.notna(value) else ''
                    elif 'duration' in col_lower and pd.notna(value):
                        # Support numeric Duration column (if exists and is numeric)
                        try:
                            duration_val = float(value)
                            if duration_val > 0:
                                track['duration'] = int(duration_val)
                        except (ValueError, TypeError):
                            pass  # Keep default 180s duration
                        
                track['timestamp'] = self.normalize_timestamp(pd.Timestamp.now())  # Synthetic timestamp
            
            # Only return tracks with a track name
            if track.get('track', '').strip():
                return track
                
        except Exception as e:
            print(f"Error normalizing track at index {index}: {e}")
            
        return None
    
    def process_with_musicbrainz(self, all_tracks, total_tracks):
        """Phase 1: ULTRA-FAST MusicBrainz artist resolution using batch processing."""
        print(f"\n{'='*70}")
        print(f"🔍 DEBUG: process_with_musicbrainz() called")
        print(f"🔍 DEBUG: This is the ULTRA-FAST batch processing version!")
        print(f"{'='*70}\n")

        # Check if MusicBrainz is available
        musicbrainz_available = (
            hasattr(self.music_search_service, 'musicbrainz_manager') and
            self.music_search_service.musicbrainz_manager.is_database_available()
        )

        # For Play History, calculate reverse chronological timestamps using FIXED 180s duration
        if self.detected_file_type and "Play History" in self.detected_file_type:
            current_timestamp = pd.Timestamp.now()
            for i, track in enumerate(all_tracks):
                # CRITICAL: Use index-based calculation with fixed 180s duration (matches tkinter version)
                # This ensures proper reverse chronological order regardless of actual track duration
                track['timestamp'] = current_timestamp - pd.Timedelta(seconds=180 * i)

        # If MusicBrainz not available, just return tracks as-is
        if not musicbrainz_available:
            self.update_progress(f"⚠️  MusicBrainz not available - skipping artist search", 50)
            return all_tracks

        # Start timing for MusicBrainz phase
        musicbrainz_start_time = time.time()

        print(f"\n{'='*70}")
        print(f"🚀 ULTRA-FAST MUSICBRAINZ BATCH PROCESSING")
        print(f"{'='*70}")
        print(f"Total tracks: {total_tracks:,}")

        # Convert tracks to DataFrame for batch processing
        self.update_progress("🔄 Preparing data for batch search...", 22)
        df = pd.DataFrame(all_tracks)

        # Count tracks with missing artists
        artist_series = df['artist'].fillna('').astype(str)
        missing_mask = artist_series.str.strip() == ''
        missing_count = missing_mask.sum()
        has_artist_count = total_tracks - missing_count

        print(f"📊 Tracks with artists: {has_artist_count:,}")
        print(f"📊 Tracks missing artists: {missing_count:,}")

        if missing_count == 0:
            print("✅ No missing artists - skipping MusicBrainz search")
            self.update_progress("✅ All tracks have artists", 60)
            elapsed_time = time.time() - musicbrainz_start_time
            self.musicbrainz_search_time = elapsed_time
            return all_tracks

        # Use ultra-fast processor for batch searching
        try:
            self.update_progress(f"🔥 Batch searching {missing_count:,} tracks in MusicBrainz...", 25)

            # Initialize ultra-fast processor
            processor = UltraFastCSVProcessor(self.music_search_service.musicbrainz_manager)

            # Extract tracks that need searching
            missing_df = df[missing_mask].copy()

            # Batch search with progress callback
            search_start = time.time()
            def progress_cb(message, percent):
                # Map processor progress (0-100) to our range (25-60)
                gui_progress = 25 + int((percent / 100) * 35)

                # Calculate processing rate for detailed stats
                elapsed = time.time() - search_start
                if elapsed > 0 and percent > 0:
                    estimated_total = (elapsed / (percent / 100))
                    rate = missing_count / estimated_total if estimated_total > 0 else 0
                    detailed_stats = f"⚡ Processing rate: {rate:,.0f} tracks/sec"
                    self.update_progress(f"🔥 {message}", gui_progress, detailed_stats)
                else:
                    self.update_progress(f"🔥 {message}", gui_progress)

            # Perform batch search (this is the ultra-fast part!)
            track_to_artist = processor._batch_search(missing_df, progress_cb)

            # Update tracks with found artists
            found_count = 0
            for i, row in missing_df.iterrows():
                track_name = row.get('track', '')
                album_name = row.get('album', '')
                search_key = (
                    processor._clean_text(track_name),
                    processor._clean_text(album_name),
                    ''  # No artist for search key
                )

                if search_key in track_to_artist:
                    all_tracks[i]['found_artist'] = track_to_artist[search_key]
                    found_count += 1

            self.musicbrainz_count = found_count

            # Calculate and store timing
            elapsed_time = time.time() - musicbrainz_start_time
            self.musicbrainz_search_time = elapsed_time

            # Calculate throughput
            throughput = missing_count / elapsed_time if elapsed_time > 0 else 0

            print(f"\n{'='*70}")
            print(f"✅ MUSICBRAINZ BATCH SEARCH COMPLETE")
            print(f"{'='*70}")
            print(f"⏱️  Time: {elapsed_time:.1f}s")
            print(f"📊 Searched: {missing_count:,} tracks")
            print(f"✅ Found: {found_count:,} ({found_count/missing_count*100:.1f}%)")
            print(f"⚡ Throughput: {throughput:,.0f} tracks/sec")
            print(f"{'='*70}\n")

            self.update_progress(
                f"✅ MusicBrainz: Found {found_count:,}/{missing_count:,} artists in {elapsed_time:.1f}s",
                60
            )

            # Update missing artist count on Export button
            self.update_missing_artist_count()

        except Exception as e:
            print(f"❌ Error in batch MusicBrainz search: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to returning tracks as-is
            elapsed_time = time.time() - musicbrainz_start_time
            self.musicbrainz_search_time = elapsed_time

        return all_tracks
    
    def process_missing_with_itunes(self, missing_tracks, all_processed_tracks, completed_count, total_tracks):
        """Process missing tracks with iTunes API (Phase-2 batch processing)."""
        # Start timing for iTunes phase
        itunes_start_time = time.time()

        print(f"\n{'='*70}")
        print(f"🌐 ITUNES API SEARCH")
        print(f"{'='*70}")
        print(f"Missing tracks to search: {len(missing_tracks):,}")

        results = []
        itunes_processed = 0

        for i, track_data in enumerate(missing_tracks):
            # Check for process control (matches tkinter specs)
            if self.stop_itunes_search_flag:
                break

            # Wait if paused (matches tkinter specs)
            while getattr(self, 'process_paused', False) and not self.stop_itunes_search_flag:
                time.sleep(0.1)

            if self.stop_itunes_search_flag:
                break

            # Update progress (60-80% range for Phase-2)
            itunes_processed += 1
            progress = 60 + int((itunes_processed / len(missing_tracks)) * 20)
            elapsed_str = self._get_elapsed_time_str()
            self.update_progress(f"🌐 iTunes: {itunes_processed:,}/{len(missing_tracks):,} missing artists searched{elapsed_str}", progress)

            # Search with iTunes API (Phase-2)
            # Handle both dict formats: {'track': ...} and {'Track': ...}
            track_name = track_data.get('track') or track_data.get('Track', '')
            album_name = track_data.get('album') or track_data.get('Album', '')

            try:
                found_artist = self._search_itunes_api(track_name, album_name)
                if found_artist:
                    track_data['found_artist'] = found_artist
                    self.itunes_found += 1
            except Exception as e:
                # Individual track lookup failed, track for retry reporting
                found_artist = None
                failed_request = {
                    'track': track_name,
                    'album': album_name,
                    'row_index': track_data.get('index', i),
                    'error': str(e)
                }
                self.failed_requests.append(failed_request)

            # Update the corresponding track in results (matches tkinter specs)
            final_track = self.convert_to_final_format(track_data, track_data.get('index', i), total_tracks)
            results.append(final_track)

            # Update stats display
            self.update_stats_display()

        # Calculate and store timing
        elapsed_time = time.time() - itunes_start_time
        self.itunes_search_time = elapsed_time

        # Calculate throughput
        throughput = itunes_processed / elapsed_time if elapsed_time > 0 else 0

        print(f"\n{'='*70}")
        print(f"✅ ITUNES API SEARCH COMPLETE")
        print(f"{'='*70}")
        print(f"⏱️  Time: {elapsed_time:.1f}s")
        print(f"📊 Searched: {itunes_processed:,} tracks")
        print(f"✅ Found: {self.itunes_found:,} ({self.itunes_found/itunes_processed*100:.1f}% if itunes_processed > 0 else 0)")
        print(f"⚡ Throughput: {throughput:.1f} tracks/sec")
        print(f"{'='*70}\n")

        return results
    
    def _get_elapsed_time_str(self):
        """Get formatted elapsed time string since processing started."""
        if hasattr(self, 'processing_start_time') and self.processing_start_time:
            elapsed = time.time() - self.processing_start_time
            return f" ({elapsed:.1f}s elapsed)"
        return ""

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Convert ISO 8601 timestamp to user-friendly format."""
        if timestamp_str == "Unknown":
            return "Unknown"

        try:
            from datetime import datetime
            # Parse ISO format: 2025-10-04T00:29:52.421043Z
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # Format as: Oct 4, 2025 12:29 AM
            return dt.strftime("%b %d, %Y %I:%M %p")
        except:
            # If parsing fails, return original
            return timestamp_str

    def convert_to_final_format(self, track, index, total_tracks):
        """Convert track to final Last.fm format with synthetic timestamps."""
        try:
            # Handle both uppercase (DataFrame) and lowercase (dict) keys
            artist = track.get('Artist', track.get('artist', ''))
            track_name = track.get('Track', track.get('track', ''))
            album = track.get('Album', track.get('album', ''))
            duration = track.get('duration', 180)  # Default duration
            
            # Use found_artist if available (from Phase-1/Phase-2 iTunes search)
            found_artist = track.get('found_artist', '')
            final_artist = found_artist if found_artist else artist
            
            # Generate synthetic timestamp: now() - (duration * i) seconds
            # This creates reverse-chronological synthetic timeline anchored at "now"
            if not hasattr(self, '_conversion_start_time') or self._conversion_start_time is None:
                self._conversion_start_time = pd.Timestamp.now()
            
            synthetic_timestamp = self._conversion_start_time - pd.Timedelta(seconds=duration * index)
            
            # Return array format: [Artist, Track, Album, Timestamp, Album Artist, Duration]
            # This matches the exact Last.fm format specification
            return [
                final_artist,           # Artist (found_artist or original artist)
                track_name,             # Track  
                album,                  # Album (may be empty)
                str(synthetic_timestamp), # Timestamp (synthetic reverse-chronological)
                final_artist,           # Album Artist (equals final Artist)
                duration                # Duration (int seconds)
            ]
        except Exception as e:
            print(f"Error converting track {index}: {e}")
            print(f"Track data keys: {list(track.keys()) if hasattr(track, 'keys') else 'Not a dict'}")
            return None
    
    def process_csv_file(self):
        """Process the CSV file in a background thread with comprehensive timing and debugging."""
        import time

        try:
            # Record start time for comprehensive stats
            self._processing_start_time = time.time()
            print(f"\n📁 === CSV PROCESSING SESSION START ===\n")
            print(f"📁 File path: {self.current_file_path}")
            print(f"💾 File size: {self.format_file_size(self.file_size)}")
            print(f"🕐 Processing started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._processing_start_time))}")

            # Update progress
            self.update_progress(f"📁 Reading CSV file ({self.format_file_size(self.file_size)})...", 10)
            
            # Determine optimal chunk size based on file size
            chunk_size = self.calculate_chunk_size()
            print(f"📄 Calculated chunk size: {chunk_size:,} rows")

            # Try multiple encodings like original tkinter version with timing
            encoding_start = time.time()
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            encoding_used = None
            print(f"🔡 Testing file encodings: {encodings_to_try}")

            # First, try to read just the header to determine encoding
            for i, encoding in enumerate(encodings_to_try):
                try:
                    pd.read_csv(self.current_file_path, encoding=encoding, nrows=0)
                    encoding_used = encoding
                    encoding_time = time.time() - encoding_start
                    print(f"✅ Encoding detected: {encoding} (tried {i+1}/{len(encodings_to_try)} in {encoding_time*1000:.1f}ms)")
                    break
                except (UnicodeDecodeError, UnicodeError) as e:
                    print(f"❌ Encoding {encoding} failed: {str(e)[:50]}...")
                    continue

            if encoding_used is None:
                print(f"❌ FATAL: Could not read CSV file with any supported encoding")
                raise Exception("Could not read CSV file with any supported encoding")

            # Count total rows for progress tracking with timing
            row_count_start = time.time()
            print(f"📈 Counting total rows...")
            with open(self.current_file_path, 'r', encoding=encoding_used) as f:
                self.row_count = sum(1 for line in f) - 1  # Subtract header row
            row_count_time = time.time() - row_count_start
            print(f"📊 Total rows: {self.row_count:,} (counted in {row_count_time:.2f}s)")

            # Calculate estimated processing time
            estimated_processing_time = self.row_count / 10000  # ~10k rows per second estimate
            print(f"⏱️ Estimated processing time: {estimated_processing_time:.1f} seconds")

            self.update_progress(f"📄 Processing {self.row_count:,} rows in {chunk_size:,}-row chunks...", 15)
            
            # Process file in chunks with comprehensive timing
            file_type = self.file_type_selection.value
            print(f"📋 File type: {file_type}")
            print(f"🚀 Starting chunk processing...\n")

            chunk_processing_start = time.time()
            processed_data = self.process_csv_in_chunks(encoding_used, chunk_size, file_type)
            chunk_processing_time = time.time() - chunk_processing_start

            print(f"\n✅ Chunk processing completed in {chunk_processing_time:.2f} seconds")
            print(f"📊 Processed data: {len(processed_data) if processed_data else 0} items")

            # Finalize processing like tkinter app with timing
            finalization_start = time.time()
            start_time = getattr(self, '_processing_start_time', time.time())
            self.finalize_processing(processed_data, start_time)
            finalization_time = time.time() - finalization_start

            # Calculate total processing statistics
            total_processing_time = time.time() - self._processing_start_time
            rows_per_second = self.row_count / total_processing_time if total_processing_time > 0 else 0

            print(f"\n📊 === CSV PROCESSING COMPLETE ===\n")
            print(f"⏱️ Total processing time: {total_processing_time:.2f} seconds")
            print(f"📄 Chunk processing: {chunk_processing_time:.2f}s")
            print(f"🔄 Finalization: {finalization_time:.2f}s")
            print(f"⚡ Processing rate: {rows_per_second:.0f} rows/second")
            print(f"✅ Successfully processed: {len(processed_data) if processed_data else 0} items")
            print(f"\n=== END PROCESSING ===\n")

            # Mark processing as successful
            processing_successful = True

        except Exception as e:
            total_error_time = time.time() - self._processing_start_time
            print(f"\n❌ === CSV PROCESSING FAILED ===\n")
            print(f"⚠️ Error after {total_error_time:.2f} seconds: {str(e)}")
            print(f"🔍 Error type: {type(e).__name__}")
            print(f"\n=== END ERROR ===\n")

            self.update_results(f"Error: Error: {str(e)}")
            self.update_progress("❌ Processing failed", 0)
            processing_successful = False

        finally:
            # Re-enable buttons on main thread, preserve results buttons if successful
            keep_results = locals().get('processing_successful', False)
            async def reset_with_params():
                await self._reset_buttons_ui(keep_results_buttons=keep_results)
            self._schedule_ui_update(reset_with_params())
    
    def enable_copy_save_buttons(self):
        """Enable copy, save, and missing artists buttons - synchronous version."""
        print(f"DEBUG: enable_copy_save_buttons called")

        # Enable copy and save buttons
        if hasattr(self, 'copy_button'):
            self.copy_button.enabled = True
            print(f"DEBUG: copy_button enabled")

        if hasattr(self, 'save_button'):
            self.save_button.enabled = True
            print(f"DEBUG: save_button enabled")

        # Enable save missing artists button
        if hasattr(self, 'save_missing_button'):
            self.save_missing_button.enabled = True
            print(f"DEBUG: save_missing_button enabled")

        # Disable pause/stop buttons since processing is complete
        # if hasattr(self, 'process_pause_button'):  # Pause button removed
        #     self.process_pause_button.enabled = False
        #     print(f"DEBUG: process_pause_button disabled")

        if hasattr(self, 'process_stop_button'):
            self.process_stop_button.enabled = False
            print(f"DEBUG: process_stop_button disabled")

    async def _enable_copy_save_buttons(self):
        """Enable copy and save buttons on main thread."""
        self.enable_copy_save_buttons()

    async def _enable_copy_save_buttons_task(self, widget=None, **kwargs):
        """Background task to enable copy and save buttons on main thread."""
        self.enable_copy_save_buttons()

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
            print(f"DEBUG: finalize_processing called with {len(final_results)} results")
            if final_results:
                print(f"DEBUG: First result type: {type(final_results[0])}, content: {final_results[0]}")
            
            # Create DataFrame with exact same columns as tkinter
            columns = ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration']
            self.processed_df = pd.DataFrame(final_results, columns=columns)
            print(f"DEBUG: Created DataFrame with {len(self.processed_df)} rows")

            # No auto-save to temp - user must explicitly save before searching
            self.current_save_path = None

            # Update missing artist count on Export button
            self.update_missing_artist_count()

            # Update save status indicator
            self.update_save_status()

            # Update search button state (disabled until saved)
            self.update_search_button_state()
            
            # Display results as CSV like tkinter
            # For large files, limit the display to avoid UI slowdown
            total_rows = len(self.processed_df)
            display_limit = 1000  # Show first 1000 rows in UI for performance

            if total_rows > display_limit:
                # Show limited preview with note
                csv_buffer = io.StringIO()
                self.processed_df.head(display_limit).to_csv(csv_buffer, index=False, lineterminator='\n')
                csv_string = csv_buffer.getvalue()

                # Add informational note at the end
                csv_string += f"\n\n--- Showing first {display_limit:,} of {total_rows:,} rows ---\n"
                csv_string += "Use 'Save CSV' button to export the complete file.\n"
            else:
                # Show all rows for smaller files
                csv_buffer = io.StringIO()
                self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
                csv_string = csv_buffer.getvalue()

            # Update results text with CSV output
            self.update_results(csv_string)
            
            # Update preview with more rows for better visibility (unless performance is an issue)
            # Show up to 100 rows for reasonable performance vs visibility balance
            preview_rows = min(100, len(self.processed_df))
            self.update_preview(self.processed_df.head(preview_rows), total_rows=len(self.processed_df))
            
            # Calculate and display final stats with accurate missing data reporting
            total_time = time.time() - start_time
            total_tracks = len(final_results)

            # Count actual missing data from the final results
            missing_artists = 0
            missing_tracks = 0
            missing_albums = 0

            for track in final_results:
                if isinstance(track, list) and len(track) >= 6:
                    artist, track_name, album, timestamp, album_artist, duration = track[:6]
                    if not artist or artist.strip() == '':
                        missing_artists += 1
                    if not track_name or track_name.strip() == '':
                        missing_tracks += 1
                    if not album or album.strip() == '':
                        missing_albums += 1

            # Create accurate status message with detailed timing
            stats_text = f" Complete! {total_tracks:,} tracks processed in {total_time:.1f}s"

            # Add detailed timing breakdown
            timing_parts = []
            if hasattr(self, 'musicbrainz_search_time') and self.musicbrainz_search_time:
                mb_time = self.musicbrainz_search_time
                timing_parts.append(f"MusicBrainz: {mb_time:.1f}s")
            if hasattr(self, 'itunes_search_time') and self.itunes_search_time:
                itunes_time = self.itunes_search_time
                timing_parts.append(f"iTunes: {itunes_time:.1f}s")

            if timing_parts:
                stats_text += f"\n⏱️  Timing: {', '.join(timing_parts)}"

            # Build missing data report based on what's expected for each format
            missing_parts = []
            current_format = getattr(self, 'detected_file_type', '')

            if missing_artists > 0:
                missing_parts.append(f"{missing_artists} missing artists")
            if missing_tracks > 0:
                missing_parts.append(f"{missing_tracks} missing tracks")

            # Only report missing albums for formats that should have album data
            if missing_albums > 0:
                if "Play History Daily Tracks" in current_format:
                    # Don't report missing albums for Play History Daily Tracks (they never have albums)
                    pass
                elif "Recently Played Tracks" in current_format:
                    # Recently Played sometimes has albums, only report if significant portion missing
                    if missing_albums > total_tracks * 0.5:  # More than 50% missing
                        missing_parts.append(f"{missing_albums} missing albums")
                elif "Play Activity" in current_format:
                    # Play Activity should always have albums, report any missing
                    missing_parts.append(f"{missing_albums} missing albums")
                else:
                    # Generic/unknown format, report missing albums
                    missing_parts.append(f"{missing_albums} missing albums")

            if missing_parts:
                stats_text += f" ({', '.join(missing_parts)})"

            # Add helpful context about CSV format limitations and what data is expected
            format_info = ""
            current_format = getattr(self, 'detected_file_type', '')

            if "Play History Daily Tracks" in current_format:
                # Play History Daily Tracks: Never has albums, sometimes missing artists in track descriptions
                if missing_albums == total_tracks:  # All albums missing (expected for this format)
                    if missing_artists > 0:
                        format_info = f"\n\n💡 Note: Play History Daily Tracks format doesn't include album information.\n💡 Tip: Use 'Search for Missing Artists' to find {missing_artists} missing artist names."
                    else:
                        format_info = "\n\n💡 Note: Play History Daily Tracks format doesn't include album information."
                elif missing_artists > 0:
                    format_info = f"\n\n💡 Tip: Use 'Search for Missing Artists' to find {missing_artists} missing artist names."

            elif "Recently Played Tracks" in current_format:
                # Recently Played Tracks: Has some album info (Container Description), may have missing artists
                tips = []
                if missing_artists > 0:
                    tips.append(f"Use 'Search for Missing Artists' to find {missing_artists} missing artist names")
                if missing_albums > 0:
                    tips.append(f"{missing_albums} albums missing (some tracks may not have album info)")
                if tips:
                    format_info = f"\n\n💡 Tip: {' • '.join(tips)}."

            elif "Play Activity" in current_format:
                # Play Activity: Should have complete artist, track, and album info
                tips = []
                if missing_artists > 0:
                    tips.append(f"Use 'Search for Missing Artists' to find {missing_artists} missing artists")
                if missing_tracks > 0:
                    tips.append(f"{missing_tracks} tracks have missing names")
                if missing_albums > 0:
                    tips.append(f"{missing_albums} tracks missing album information")
                if tips:
                    format_info = f"\n\n💡 Tip: {' • '.join(tips)}."

            else:
                # Generic CSV or unknown format
                if missing_artists > 0:
                    format_info = f"\n\n💡 Tip: Use 'Search for Missing Artists' to find missing artist information."

            self.update_progress(stats_text + format_info, 100)
            
            # Update stats display with final counts
            print(f"DEBUG: Updating stats display")
            try:
                self.update_stats_display()
                print(f"DEBUG: Stats updated - MB: {self.musicbrainz_found}, iTunes: {self.itunes_found}")
            except Exception as e:
                print(f"ERROR: Failed to update stats: {e}")

            # Enable copy and save buttons after successful conversion (direct call since we're in main thread context)
            print(f"DEBUG: Enabling copy and save buttons")
            try:
                self.enable_copy_save_buttons()
                print(f"DEBUG: Buttons enabled successfully")
            except Exception as e:
                print(f"ERROR: Failed to enable buttons: {e}")
                import traceback
                traceback.print_exc()
            
            # Enable reprocess button if there are missing artists (only missing artists can be searched)
            print(f"DEBUG: finalize_processing missing_artists count: {missing_artists}")
            print(f"DEBUG: total_tracks: {total_tracks}")

            # Update button state based on save status (not force-enabled)
            self.update_search_button_state()
        
        except Exception as e:
            self.update_results(f"Error: Error in finalization: {str(e)}")
    
    def process_csv_in_chunks(self, encoding, chunk_size, file_type):
        """Process CSV file in chunks to handle large files efficiently."""
        processed_data = []
        rows_processed = 0
        total_found_artists = 0
        total_searched_artists = 0
        
        # Read and process file in chunks
        chunk_reader = pd.read_csv(self.current_file_path, encoding=encoding, chunksize=chunk_size)
        
        for chunk_num, chunk in enumerate(chunk_reader):
            if self.stop_itunes_search_flag:
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
        
        # Convert processed data to final Last.fm format with comprehensive timing
        conversion_start_time = time.time()
        print(f"\n🎧 === LAST.FM CONVERSION START ===\n")
        print(f"📊 Converting {len(processed_data):,} tracks to Last.fm format...")
        print(f"🕐 Conversion started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(conversion_start_time))}")

        self.update_progress(f"🎧 Converting {len(processed_data):,} tracks to Last.fm format...", 90)

        final_results = []
        conversion_errors = 0
        last_progress_update = time.time()
        progress_interval = 2.0  # Update every 2 seconds

        for index, track_data in enumerate(processed_data):
            if self.stop_itunes_search_flag:
                print(f"🛑 Last.fm conversion stopped by user at track {index+1}/{len(processed_data)}")
                break

            try:
                final_track = self.convert_to_final_format(track_data, index, len(processed_data))
                if final_track:
                    final_results.append(final_track)
                else:
                    conversion_errors += 1
                    if conversion_errors <= 5:  # Log first 5 errors
                        track_name = track_data.get('Track', track_data.get('track', 'Unknown'))
                        print(f"⚠️ Conversion error #{conversion_errors}: Failed to convert '{track_name}'")
            except Exception as e:
                conversion_errors += 1
                if conversion_errors <= 5:  # Log first 5 errors
                    track_name = track_data.get('Track', track_data.get('track', 'Unknown'))
                    print(f"❌ Conversion exception #{conversion_errors}: '{track_name}' - {str(e)}")

            # Update progress with timing info
            current_time = time.time()
            if current_time - last_progress_update >= progress_interval or index == len(processed_data) - 1:
                elapsed_time = current_time - conversion_start_time
                tracks_per_second = (index + 1) / elapsed_time if elapsed_time > 0 else 0
                remaining_tracks = len(processed_data) - (index + 1)
                eta_seconds = remaining_tracks / tracks_per_second if tracks_per_second > 0 else 0

                progress = 90 + int(((index + 1) / len(processed_data)) * 5)  # 90-95% range
                self.update_progress(
                    f"🎧 Converting {index+1:,}/{len(processed_data):,} | "
                    f"Rate: {tracks_per_second:.0f} tracks/sec | "
                    f"ETA: {eta_seconds:.1f}s | "
                    f"Errors: {conversion_errors}",
                    progress
                )
                last_progress_update = current_time

        # Calculate final conversion statistics
        conversion_time = time.time() - conversion_start_time
        conversion_rate = len(final_results) / conversion_time if conversion_time > 0 else 0
        success_rate = len(final_results) / len(processed_data) * 100 if processed_data else 0

        print(f"\n📊 === LAST.FM CONVERSION COMPLETE ===\n")
        print(f"⏱️ Conversion time: {conversion_time:.2f} seconds")
        print(f"⚡ Conversion rate: {conversion_rate:.0f} tracks/second")
        print(f"✅ Successfully converted: {len(final_results):,}/{len(processed_data):,} tracks ({success_rate:.1f}%)")
        print(f"❌ Conversion errors: {conversion_errors}")
        print(f"\n=== END CONVERSION ===\n")

        # Final progress update with comprehensive info
        self.update_progress(
            f"✅ Converted {len(final_results):,} tracks to Last.fm format in {conversion_time:.1f}s | "
            f"Found {total_found_artists}/{total_searched_artists} missing artists",
            95
        )
        
        return final_results
    
    def process_chunk_data(self, chunk_df, file_type):
        """Process a chunk of data based on file type."""
        processed_data = []
        found_artists = 0
        searched_artists = 0
        
        for index, row in chunk_df.iterrows():
            try:
                if self.stop_itunes_search_flag:
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
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        return processed_data, found_artists, searched_artists
    
    async def _reset_buttons_ui(self, widget=None, keep_results_buttons=False):
        """Reset button states on main thread."""
        print(f"DEBUG: _reset_buttons_ui called with keep_results_buttons={keep_results_buttons}")
        self.convert_button.text = "Convert to Last.fm Format"
        self.convert_button.enabled = True
        # Process control buttons are handled by main process controls
        # Only disable copy and save buttons if not preserving results
        if not keep_results_buttons:
            print("DEBUG: Disabling copy/save buttons (keep_results_buttons=False)")
            self.copy_button.enabled = False
            self.save_button.enabled = False
        else:
            print("DEBUG: Keeping copy/save buttons enabled (keep_results_buttons=True)")
    
    def process_csv_data(self, df, file_type):
        """Process CSV data using DuckDB for all file types (like tkinter version)."""
        try:
            # For preview/small files (<=20 rows), use pandas processing for speed
            if len(df) <= 20:
                return self.process_csv_data_small(df, file_type)
            
            # For all larger files, use DuckDB processing which is faster and more reliable
            return self.process_csv_data_with_duckdb(file_type)
        
        except Exception as e:
            print(f"Error processing CSV data: {e}")
            # Fallback to small file processing
            return self.process_csv_data_small(df, file_type)
    
    def process_csv_data_small(self, df, file_type):
        """Process small CSV files using pandas (for previews)."""
        try:
            # Route to appropriate small processing method
            if "Play Activity" in file_type:
                return self.process_play_activity_data_small(df)
            elif "Play History" in file_type:
                return self.process_play_history_data_small(df)
            elif "Recently Played" in file_type:
                return self.process_recently_played_data_small(df)
            else:
                return self.process_generic_csv_data_small(df)
        except Exception as e:
            raise Exception(f"Error processing small CSV data: {str(e)}")
    
    def process_csv_data_with_duckdb(self, file_type):
        """Process ALL CSV files using DuckDB for performance with comprehensive timing."""
        import time

        duckdb_start_time = time.time()
        print(f"\n🦆 === DUCKDB PROCESSING START ===\n")
        print(f"📁 File type: {file_type}")
        print(f"💾 File path: {self.current_file_path}")
        print(f"🕐 DuckDB processing started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(duckdb_start_time))}")

        try:
            import duckdb

            self.update_progress(f"🦆 Processing {file_type} with DuckDB...", 25)
            
            # Create DuckDB connection with timing
            connection_start = time.time()
            conn = duckdb.connect(':memory:')
            connection_time = time.time() - connection_start
            print(f"🔗 DuckDB connection established in {connection_time*1000:.1f}ms")

            # Get appropriate SQL query based on file type
            query_generation_start = time.time()
            query = self.get_duckdb_query_for_file_type(file_type)
            query_generation_time = time.time() - query_generation_start
            print(f"📝 SQL query generated in {query_generation_time*1000:.1f}ms")
            print(f"\n📊 Query preview:")
            print(f"   {query[:200]}{'...' if len(query) > 200 else ''}")

            self.update_progress(f"🦆 Executing DuckDB query for {file_type}...", 50)

            # Execute query and get results with timing
            query_start = time.time()
            result_df = conn.execute(query).fetchdf()
            query_time = time.time() - query_start
            print(f"\n✅ DuckDB query executed successfully")
            print(f"⏱️ Query execution time: {query_time:.2f} seconds")
            print(f"📊 Raw results: {len(result_df):,} rows")

            if len(result_df) > 0:
                print(f"📋 Sample columns: {list(result_df.columns)}")
                print(f"📈 Processing rate: {len(result_df)/query_time:.0f} rows/second")

            self.update_progress(f"🔄 Post-processing {len(result_df):,} results...", 75)

            # Post-process results (normalize timestamps, etc.) with timing
            postprocess_start = time.time()
            result_df = self.post_process_duckdb_results(result_df, file_type)
            postprocess_time = time.time() - postprocess_start
            print(f"🔄 Post-processing completed in {postprocess_time:.2f} seconds")
            print(f"🎧 Final Last.fm format: {len(result_df):,} tracks")

            conn.close()

            # Calculate total DuckDB processing time
            total_duckdb_time = time.time() - duckdb_start_time
            total_rate = len(result_df) / total_duckdb_time if total_duckdb_time > 0 else 0

            print(f"\n📊 === DUCKDB PROCESSING COMPLETE ===\n")
            print(f"⏱️ Total DuckDB time: {total_duckdb_time:.2f} seconds")
            print(f"⚡ Overall processing rate: {total_rate:.0f} tracks/second")
            print(f"✅ Successfully processed: {len(result_df):,} tracks")
            print(f"\n=== END DUCKDB PROCESSING ===\n")

            self.update_progress(f"✅ DuckDB processed {len(result_df):,} tracks in {total_duckdb_time:.1f}s", 100)
            return result_df
            
        except Exception as e:
            print(f"DuckDB processing failed for {file_type}: {e}")
            # Fallback to chunked processing
            return self.process_csv_data_chunked(file_type)
    
    def get_duckdb_query_for_file_type(self, file_type):
        """Get the appropriate DuckDB SQL query based on file type."""
        file_path = self.current_file_path
        
        if "Play Activity" in file_type:
            return f"""
            SELECT 
                COALESCE(NULLIF(TRIM("Container Artist Name"), ''), '') as Artist,
                COALESCE(NULLIF(TRIM("Song Name"), ''), '') as Track,
                COALESCE(NULLIF(TRIM("Album Name"), ''), NULLIF(TRIM("Container Album Name"), ''), '') as Album,
                COALESCE(TRY_CAST("Play Duration Milliseconds" AS INTEGER), 0) as play_duration
            FROM read_csv('{file_path}', header=true, all_varchar=true)
            WHERE COALESCE(NULLIF(TRIM("Song Name"), ''), '') != ''
            """
        elif "Play History" in file_type:
            return f"""
            SELECT 
                CASE 
                    WHEN POSITION(' - ' IN "Track Description") > 0 
                    THEN TRIM(SUBSTRING("Track Description", 1, POSITION(' - ' IN "Track Description") - 1))
                    ELSE ''
                END as Artist,
                CASE 
                    WHEN POSITION(' - ' IN "Track Description") > 0 
                    THEN TRIM(SUBSTRING("Track Description", POSITION(' - ' IN "Track Description") + 3))
                    ELSE COALESCE(NULLIF(TRIM("Track Description"), ''), '')
                END as Track,
                '' as Album,
                COALESCE(TRY_CAST("Play Duration Milliseconds" AS INTEGER), 0) as play_duration
            FROM read_csv('{file_path}', header=true, all_varchar=true)
            WHERE COALESCE(NULLIF(TRIM("Track Description"), ''), '') != ''
            """
        elif "Recently Played" in file_type:
            return f"""
            SELECT 
                CASE 
                    WHEN POSITION(' - ' IN "Track Description") > 0 
                    THEN TRIM(SUBSTRING("Track Description", 1, POSITION(' - ' IN "Track Description") - 1))
                    ELSE ''
                END as Artist,
                CASE 
                    WHEN POSITION(' - ' IN "Track Description") > 0 
                    THEN TRIM(SUBSTRING("Track Description", POSITION(' - ' IN "Track Description") + 3))
                    ELSE COALESCE(NULLIF(TRIM("Track Description"), ''), '')
                END as Track,
                COALESCE(NULLIF(TRIM("Container Description"), ''), '') as Album,
                COALESCE(TRY_CAST("Total play duration in millis" AS INTEGER), 0) as play_duration
            FROM read_csv('{file_path}', header=true, all_varchar=true)
            WHERE COALESCE(NULLIF(TRIM("Track Description"), ''), '') != ''
            """
        else:
            # Generic CSV - try to auto-detect columns
            # First, inspect available columns to avoid binding errors
            print(f"   📋 Reading CSV header to detect columns...")
            try:
                import pandas as pd
                header_df = pd.read_csv(file_path, nrows=0)
                available_cols = set(header_df.columns)
                print(f"   📋 Available columns: {list(available_cols)}")

                # Build column selection based on what's actually available
                artist_expr = []
                if "Artist Name" in available_cols:
                    artist_expr.append('NULLIF(TRIM("Artist Name"), \'\')')
                if "Artist" in available_cols:
                    artist_expr.append('NULLIF(TRIM("Artist"), \'\')')
                artist_select = f"COALESCE({', '.join(artist_expr)}, '') as Artist" if artist_expr else "'' as Artist"

                track_expr = []
                if "Song Name" in available_cols:
                    track_expr.append('NULLIF(TRIM("Song Name"), \'\')')
                if "Track Name" in available_cols:
                    track_expr.append('NULLIF(TRIM("Track Name"), \'\')')
                if "Track" in available_cols:
                    track_expr.append('NULLIF(TRIM("Track"), \'\')')
                track_select = f"COALESCE({', '.join(track_expr)}, '') as Track" if track_expr else "'' as Track"
                track_where = f"COALESCE({', '.join(track_expr)}, '') != ''" if track_expr else "1=1"

                album_expr = []
                if "Album Name" in available_cols:
                    album_expr.append('NULLIF(TRIM("Album Name"), \'\')')
                if "Album" in available_cols:
                    album_expr.append('NULLIF(TRIM("Album"), \'\')')
                album_select = f"COALESCE({', '.join(album_expr)}, '') as Album" if album_expr else "'' as Album"

                # Handle timestamp - check if file already has timestamps
                timestamp_expr = []
                if "Timestamp" in available_cols:
                    timestamp_expr.append('"Timestamp"')
                if "Date" in available_cols:
                    timestamp_expr.append('"Date"')
                if "Play Date" in available_cols:
                    timestamp_expr.append('"Play Date"')
                # If file has timestamp column, preserve it; otherwise DuckDB will use NULL
                timestamp_select = f"COALESCE({', '.join(timestamp_expr)}, NULL) as Timestamp" if timestamp_expr else "NULL as Timestamp"

                print(f"   📋 Generated query with dynamic columns")

                return f"""
                SELECT
                    {artist_select},
                    {track_select},
                    {album_select},
                    {timestamp_select},
                    0 as play_duration
                FROM read_csv('{file_path}', header=true, all_varchar=true)
                WHERE {track_where}
                """
            except Exception as e:
                print(f"   ⚠️  Error detecting columns: {e}, using fallback query")
                # Fallback to basic query
                return f"""
                SELECT
                    '' as Artist,
                    '' as Track,
                    '' as Album,
                    0 as play_duration
                FROM read_csv('{file_path}', header=true, all_varchar=true)
                LIMIT 0
                """
    
    def post_process_duckdb_results(self, df, file_type):
        """Post-process DuckDB results into Last.fm 6-column format."""
        if df.empty:
            return df

        # Check if file already has timestamps (e.g., Last.fm format files)
        has_existing_timestamps = 'Timestamp' in df.columns and df['Timestamp'].notna().any()

        # Convert to Last.fm format
        lastfm_data = []
        conversion_start_time = pd.Timestamp.now()

        # Calculate safe time intervals to avoid timestamp overflow (only if we need to generate timestamps)
        if not has_existing_timestamps:
            total_rows = len(df)
            if total_rows > 0:
                # Limit the time spread to a reasonable amount (e.g., 30 days max)
                max_days = 30
                max_seconds = max_days * 24 * 3600  # 30 days in seconds

                # Calculate seconds per track to spread evenly across time period
                seconds_per_track = min(180, max_seconds / total_rows) if total_rows > 0 else 180
            else:
                seconds_per_track = 180

        for index, row in df.iterrows():
            artist = str(row.get('Artist', '')).strip() if pd.notna(row.get('Artist')) else ''
            track = str(row.get('Track', '')).strip() if pd.notna(row.get('Track')) else ''
            album = str(row.get('Album', '')).strip() if pd.notna(row.get('Album')) else ''

            # Set duration based on file type
            if "Play History" in file_type or "Recently Played" in file_type:
                duration = 180  # Fixed duration for these formats
            else:
                # For Play Activity, extract from play_duration
                duration_ms = row.get('play_duration', 0) if pd.notna(row.get('play_duration')) else 0
                duration = int(duration_ms) // 1000 if duration_ms > 0 else 180

            # Use existing timestamp if available, otherwise generate one
            if has_existing_timestamps and pd.notna(row.get('Timestamp')):
                timestamp = str(row.get('Timestamp'))
            else:
                # Generate reverse-chronological timestamp with safe calculation
                try:
                    seconds_offset = seconds_per_track * index
                    # Use min to ensure we don't exceed reasonable limits
                    seconds_offset = min(seconds_offset, max_seconds)
                    synthetic_timestamp = conversion_start_time - pd.Timedelta(seconds=seconds_offset)
                    timestamp = str(synthetic_timestamp)
                except (OverflowError, ValueError) as e:
                    # Fallback to simple sequential timestamps if overflow occurs
                    synthetic_timestamp = conversion_start_time - pd.Timedelta(minutes=index)
                    timestamp = str(synthetic_timestamp)

            # Only include rows with track names
            if track:
                lastfm_data.append({
                    'Artist': artist,
                    'Track': track,
                    'Album': album,
                    'Timestamp': timestamp,
                    'Album Artist': artist,  # Same as Artist per Last.fm spec
                    'Duration': duration
                })

        return pd.DataFrame(lastfm_data)
    
    def process_csv_data_chunked(self, file_type):
        """Fallback chunked processing when DuckDB fails."""
        try:
            import pandas as pd
            
            self.update_progress(f" Using chunked processing for {file_type}...", 25)
            
            # Use chunked reading
            chunk_size = 5000 if "Play Activity" in file_type else 10000
            processed_data = []
            total_rows = getattr(self, 'row_count', 0)
            rows_processed = 0
            
            # Read and process file in chunks
            for chunk_num, chunk_df in enumerate(pd.read_csv(self.current_file_path, chunksize=chunk_size)):
                # Process each chunk using small processing method
                chunk_results = self.process_csv_data_small(chunk_df, file_type)
                if not chunk_results.empty:
                    processed_data.append(chunk_results)
                
                # Update progress
                rows_processed += len(chunk_df)
                if total_rows > 0:
                    progress = 25 + int((rows_processed / total_rows) * 70)  # 25-95% range
                    self.update_progress(f" Processed {rows_processed:,}/{total_rows:,} rows...", progress)
                else:
                    self.update_progress(f" Processed {rows_processed:,} rows...", 50)
            
            # Combine all chunks
            if processed_data:
                final_df = pd.concat(processed_data, ignore_index=True)
                self.update_progress(f" Chunked processing completed: {len(final_df)} tracks", 100)
                return final_df
            else:
                return pd.DataFrame(columns=['Artist', 'Track', 'Album', 'Timestamp'])
                
        except Exception as e:
            print(f"Chunked processing failed: {e}")
            return pd.DataFrame(columns=['Artist', 'Track', 'Album', 'Timestamp'])
    
    def process_play_activity_row(self, row):
        """Process a single Play Activity row - returns dict format preserving found_artist."""
        artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
        track = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
        album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
        timestamp = self.normalize_timestamp(pd.Timestamp.now())  # Synthetic timestamp (CSV timestamps ignored)
        duration = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180
        
        found_artist_name = None
        searched_artist = False
        
        # Skip automatic artist search during CSV conversion
        # Artist search should only happen when explicitly requested by user
        found_artist_name = None
        searched_artist = False
        
        if track:  # Only include tracks with track name
            # Return dict format preserving original artist and found_artist separately
            track_data = {
                'artist': artist,  # Original artist (may be empty)
                'track': track,
                'album': album,
                'timestamp': timestamp,
                'duration': duration
            }
            # Add found_artist only if we found one
            if found_artist_name:
                track_data['found_artist'] = found_artist_name
            
            return track_data, bool(found_artist_name), searched_artist
        
        return None
    
    def process_play_history_row(self, row):
        """Process a single Play History row - returns dict format preserving found_artist."""
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
        # IMPORTANT: For Play History Daily Tracks, duration is ALWAYS 180 seconds (matches tkinter version)
        # Do NOT use "Play Duration Milliseconds" from CSV - it's ignored per original specification
        duration = 180
        
        found_artist_name = None
        searched_artist = False
        
        # Skip automatic artist search during CSV conversion
        # Artist search should only happen when explicitly requested by user
        found_artist_name = None
        searched_artist = False
        
        if track:  # Only include tracks with track name
            # Return dict format preserving original artist and found_artist separately
            track_data = {
                'artist': artist,  # Original artist (may be empty)
                'track': track,
                'album': album,
                'timestamp': timestamp,
                'duration': duration
            }
            # Add found_artist only if we found one
            if found_artist_name:
                track_data['found_artist'] = found_artist_name
            
            return track_data, bool(found_artist_name), searched_artist
        
        return None
    
    def process_recently_played_row(self, row):
        """Process a single Recently Played row - returns dict format preserving found_artist."""
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
        # IMPORTANT: For Recently Played Tracks, duration is ALWAYS 180 seconds (matches tkinter version)
        duration = 180
        
        found_artist_name = None
        searched_artist = False
        
        # Skip automatic artist search during CSV conversion
        # Artist search should only happen when explicitly requested by user
        found_artist_name = None
        searched_artist = False
        
        if track:  # Only include tracks with track name
            # Return dict format preserving original artist and found_artist separately
            track_data = {
                'artist': artist,  # Original artist (may be empty)
                'track': track,
                'album': album,
                'timestamp': timestamp,
                'duration': duration
            }
            # Add found_artist only if we found one
            if found_artist_name:
                track_data['found_artist'] = found_artist_name
            
            return track_data, bool(found_artist_name), searched_artist
        
        return None
    
    def process_generic_row(self, row):
        """Process a single generic CSV row - returns dict format preserving found_artist."""
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
        
        found_artist_name = None
        searched_artist = False
        
        # Skip automatic artist search during CSV conversion
        # Artist search should only happen when explicitly requested by user
        found_artist_name = None
        searched_artist = False
        
        if track:  # Only include tracks with track name
            track_data = {
                'artist': artist,  # Original artist (may be empty)
                'track': track,
                'album': album,
                'timestamp': self.normalize_timestamp(pd.Timestamp.now()),
                'duration': 180  # Default duration
            }
            # Add found_artist only if we found one
            if found_artist_name:
                track_data['found_artist'] = found_artist_name
            
            return track_data, bool(found_artist_name), searched_artist
        
        return None
    
    def process_play_activity_data(self, df):
        """Process Apple Music Play Activity CSV format using DuckDB for large files."""
        try:
            # For small files (preview), use regular processing
            if len(df) <= 20:
                return self.process_play_activity_data_small(df)
            
            # For large files, use DuckDB processing
            return self.process_play_activity_data_with_duckdb()
            
        except Exception as e:
            print(f"Error in process_play_activity_data: {e}")
            # Fallback to regular processing
            return self.process_play_activity_data_small(df)
    
    def process_play_activity_data_small(self, df):
        """Process small Play Activity CSV format using regular pandas."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        for index, row in df.iterrows():
            try:
                # Update progress for small files
                if total_rows > 1:
                    progress = int((index / total_rows) * 80) + 20  # 20-100% range
                    self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns from Play Activity format (matches tkinter version)
                artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                
                track = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
                
                album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                
                # Skip automatic artist search during CSV conversion
                # Artist search should only happen when explicitly requested by user
                
                # Get duration from CSV and convert to seconds (matches Last.fm format)
                duration_ms = row.get('Media Duration In Milliseconds', 0) if pd.notna(row.get('Media Duration In Milliseconds')) else 0
                duration = int(duration_ms) // 1000 if duration_ms > 0 else 180
                
                # Generate synthetic timestamp (reverse-chronological)
                synthetic_timestamp = pd.Timestamp.now() - pd.Timedelta(seconds=duration * index)
                
                # Create Last.fm format data
                track_data = {
                    'Artist': artist,
                    'Track': track,
                    'Album': album,
                    'Timestamp': str(synthetic_timestamp),
                    'Album Artist': artist,  # Same as Artist per Last.fm spec
                    'Duration': duration
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['Track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f" Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_play_activity_data_with_duckdb(self):
        """Process large Play Activity CSV using DuckDB for performance."""
        try:
            import duckdb
            import pandas as pd
            
            self.update_progress(" Processing large Play Activity file...", 25)
            
            # First, check which columns exist in the CSV
            header_df = pd.read_csv(self.current_file_path, nrows=0)
            columns = list(header_df.columns)
            
            # Build dynamic artist selection based on available columns
            artist_parts = []
            if "Container Artist Name" in columns:
                artist_parts.append('NULLIF(TRIM("Container Artist Name"), \'\')')
            if "Artist Name" in columns:
                artist_parts.append('NULLIF(TRIM("Artist Name"), \'\')')
            
            artist_select = f"COALESCE({', '.join(artist_parts)}, '') as Artist" if artist_parts else "'' as Artist"
            
            # Build dynamic album selection based on available columns
            album_parts = []
            if "Album Name" in columns:
                album_parts.append('NULLIF(TRIM("Album Name"), \'\')')
            if "Container Album Name" in columns:
                album_parts.append('NULLIF(TRIM("Container Album Name"), \'\')')
            
            album_select = f"COALESCE({', '.join(album_parts)}, '') as Album" if album_parts else "'' as Album"
            
            # Create DuckDB connection
            conn = duckdb.connect(':memory:')
            
            # Query to extract and process Play Activity data efficiently
            # Note: Don't ORDER BY timestamp as it may contain invalid values that crash DuckDB
            query = f"""
            SELECT 
                {artist_select},
                COALESCE(NULLIF(TRIM("Song Name"), ''), '') as Track,
                {album_select},
                COALESCE("Play Duration Milliseconds", 0) as play_duration
            FROM read_csv_auto('{self.current_file_path}')
            WHERE COALESCE(NULLIF(TRIM("Song Name"), ''), '') != ''
            """
            
            self.update_progress(" Executing query on large CSV...", 50)
            
            # Execute query and get results
            result_df = conn.execute(query).fetchdf()
            
            self.update_progress(" Processing results...", 75)
            
            conn.close()
            
            self.update_progress(f" Processed {len(result_df)} tracks from large file", 100)
            return result_df
            
        except Exception as e:
            print(f"DuckDB processing failed: {e}, falling back to chunked processing")
            # Fallback to chunked processing if DuckDB fails
            return self.process_play_activity_data_chunked()
    
    def process_play_activity_data_chunked(self):
        """Fallback chunked processing for large Play Activity files when DuckDB fails."""
        try:
            import pandas as pd
            
            self.update_progress(" Using chunked processing for large Play Activity file...", 25)
            
            # Use chunked reading for very large files
            chunk_size = 5000  # Smaller chunks for Play Activity files (they're very wide)
            processed_data = []
            total_rows = getattr(self, 'row_count', 0)
            rows_processed = 0
            
            # Read and process file in chunks
            for chunk_num, chunk_df in enumerate(pd.read_csv(self.current_file_path, chunksize=chunk_size)):
                # Process each chunk
                chunk_results = self.process_play_activity_data_small(chunk_df)
                if not chunk_results.empty:
                    processed_data.append(chunk_results)
                
                # Update progress
                rows_processed += len(chunk_df)
                if total_rows > 0:
                    progress = 25 + int((rows_processed / total_rows) * 70)  # 25-95% range
                    self.update_progress(f" Processed {rows_processed:,}/{total_rows:,} rows in chunks...", progress)
                else:
                    self.update_progress(f" Processed {rows_processed:,} rows in chunks...", 50)
            
            # Combine all chunks
            if processed_data:
                final_df = pd.concat(processed_data, ignore_index=True)
                self.update_progress(f" Chunked processing completed: {len(final_df)} tracks", 100)
                return final_df
            else:
                self.update_progress("Warning: No valid tracks found in chunked processing", 100)
                return pd.DataFrame(columns=['Artist', 'Track', 'Album', 'Timestamp'])
                
        except Exception as e:
            print(f"Chunked processing also failed: {e}")
            # Return empty DataFrame with proper columns
            return pd.DataFrame(columns=['Artist', 'Track', 'Album', 'Timestamp'])
    
    def process_play_history_data_small(self, df):
        """Process small Play History Daily Tracks CSV format - matches tkinter implementation 1:1."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        # Start with current timestamp and go backwards like tkinter version
        current_timestamp = pd.Timestamp.now()
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Parse Track Description field exactly like tkinter version
                # Handle column name variations
                track_desc_col = None
                for col in df.columns:
                    if 'track description' in col.lower() or col.lower() == 'track':
                        track_desc_col = col
                        break
                
                if track_desc_col:
                    track_info = str(row.get(track_desc_col, '')).strip() if pd.notna(row.get(track_desc_col, '')) else ''
                else:
                    track_info = str(row.get('Track Description', '')).strip() if pd.notna(row.get('Track Description', '')) else ''
                
                # DEBUG: Print first few track descriptions to see what we're getting
                if index < 3:
                    print(f"DEBUG Play History Row {index}: Found column '{track_desc_col}', Track Description = '{track_info}'")
                    if index == 0:
                        print(f"DEBUG: Available columns: {list(df.columns)}")
                
                if ' - ' in track_info:
                    artist, track = track_info.split(' - ', 1)
                    artist = artist.strip()
                    track = track.strip()
                else:
                    artist = ''
                    track = track_info.strip()
                
                # IMPORTANT: For Play History Daily Tracks, duration is ALWAYS 180 seconds (matches tkinter version)
                # Do NOT use "Play Duration Milliseconds" from CSV - it's ignored per original specification
                duration = 180
                
                # Skip automatic artist search during CSV conversion
                # Artist search should only happen when explicitly requested by user
                
                # Create Last.fm format data (6 columns)
                track_data = {
                    'Artist': artist,
                    'Track': track,
                    'Album': '',  # Play History format doesn't have album info
                    'Timestamp': str(current_timestamp),
                    'Album Artist': artist,  # Same as Artist per Last.fm spec
                    'Duration': duration  # Always 180 for Play History per spec
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['Track']:
                    processed_data.append(track_data)
                    # Subtract duration for next track (reverse chronological like tkinter)
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f" Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_recently_played_data_small(self, df):
        """Process Recently Played Tracks CSV format."""
        processed_data = []
        total_rows = len(df)
        found_artists = 0
        searched_artists = 0
        
        # Find track description column
        track_desc_col = None
        for col in df.columns:
            if 'track description' in col.lower() or col.lower() == 'track':
                track_desc_col = col
                break
        
        print(f"DEBUG Recently Played: Using column '{track_desc_col}' for track data")
        print(f"DEBUG: Available columns: {list(df.columns)}")
        
        for index, row in df.iterrows():
            try:
                # Update progress
                progress = int((index / total_rows) * 80) + 20  # 20-100% range
                self.update_progress(f"Processing row {index+1}/{total_rows}...", progress)
                
                # Map columns from Recently Played format - parse Track Description
                if track_desc_col:
                    track_desc = str(row.get(track_desc_col, '')).strip() if pd.notna(row.get(track_desc_col, '')) else ''
                else:
                    track_desc = str(row.get('Track Description', '')).strip() if pd.notna(row.get('Track Description', '')) else ''
                
                if index < 3:
                    print(f"DEBUG Recently Played Row {index}: Track data = '{track_desc}'")
                
                # Parse "Artist - Track" format from Track Description (matches tkinter version)
                if ' - ' in track_desc:
                    artist, track = track_desc.split(' - ', 1)
                    artist = artist.strip()
                    track = track.strip()
                else:
                    artist = ''  # Empty artist if no delimiter found
                    track = track_desc.strip()
                
                # Find album column
                album_col = None
                for col in df.columns:
                    if 'container description' in col.lower() or 'album' in col.lower():
                        album_col = col
                        break
                
                if album_col:
                    album = str(row.get(album_col, '')).strip() if pd.notna(row.get(album_col, '')) else ''
                else:
                    album = str(row.get('Container Description', '')).strip() if pd.notna(row.get('Container Description', '')) else ''
                
                # Skip automatic artist search during CSV conversion
                # Artist search should only happen when explicitly requested by user
                
                # Generate synthetic timestamp (reverse-chronological)
                synthetic_timestamp = pd.Timestamp.now() - pd.Timedelta(seconds=180 * index)  # 180s default for Recently Played
                
                # Create Last.fm format data (6 columns)
                track_data = {
                    'Artist': artist,
                    'Track': track,
                    'Album': album,
                    'Timestamp': str(synthetic_timestamp),
                    'Album Artist': artist,  # Same as Artist per Last.fm spec
                    'Duration': 180  # Default 180 seconds for Recently Played
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['Track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f" Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
        return pd.DataFrame(processed_data)
    
    def process_generic_csv_data_small(self, df):
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
                
                # Skip automatic artist search during CSV conversion
                # Artist search should only happen when explicitly requested by user
                
                # Look for duration column or use default
                duration = 180  # Default
                for col in df.columns:
                    if 'duration' in col.lower():
                        try:
                            dur_val = row.get(col, 180)
                            if pd.notna(dur_val) and float(dur_val) > 0:
                                duration = int(float(dur_val))
                        except:
                            pass
                        break
                
                # Generate synthetic timestamp (reverse-chronological)
                synthetic_timestamp = pd.Timestamp.now() - pd.Timedelta(seconds=duration * index)
                
                # Create Last.fm format data (6 columns)
                track_data = {
                    'Artist': artist,
                    'Track': track,
                    'Album': album,
                    'Timestamp': str(synthetic_timestamp),
                    'Album Artist': artist,  # Same as Artist per Last.fm spec
                    'Duration': duration
                }
                
                # Only include tracks with track name (artist is optional)
                if track_data['Track']:
                    processed_data.append(track_data)
                    
            except Exception as e:
                continue  # Skip problematic rows
        
        # Update final progress
        self.update_progress(f" Processed {len(processed_data)} tracks. Found {found_artists}/{searched_artists} missing artists.", 100)
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
    
    @trace_call("App.search_artist_for_track")
    async def search_artist_for_track(self, track_name, album_name=None, strict_provider=False):
        """REMOVED: Old row-by-row MusicBrainz search. Use ultra-fast batch processor instead."""
        print(f"❌ ERROR: search_artist_for_track() is deprecated!")
        print(f"   This old row-by-row implementation has been replaced with ultra-fast batch processing.")
        print(f"   Use the 'Search for Missing Artists' button which uses batch processing.")
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
                    self.update_progress(f" Rate limited, waiting {wait_time:.1f}s...", self.progress_bar.value)
                    
                    # Interruptible wait
                    start_wait = time.time()
                    while time.time() - start_wait < wait_time:
                        if self.stop_itunes_search_flag or self.skip_wait_requested:
                            self.skip_wait_requested = False
                            break
                        time.sleep(0.1)
    
    def search_itunes_api(self, track_name, album_name=None):
        """Search iTunes API for artist information with proper rate limiting."""
        return self._search_itunes_api(track_name, album_name)
        
    def _search_itunes_api(self, track, album):
        """Search using iTunes API with rate limiting (matches tkinter implementation)."""

        print(f"\n🎵 === iTunes API Search Session ===")
        print(f"Input track: '{track}'")
        print(f"Input album: '{album}'")

        # Validate input - skip empty track names
        if not track or not track.strip():
            print(f"❌ iTunes API SEARCH SKIPPED: Empty track name")
            return None

        # Rate limiting: ensure no more than X calls per minute
        with self.api_lock:
            current_time = time.time()
            rate_limit = int(getattr(self.rate_limit_input, 'value', '20') or '20')

            print(f"🔄 RATE LIMIT CHECK START")
            print(f"  Current time: {time.strftime('%H:%M:%S', time.localtime(current_time))}")
            print(f"  Rate limit: {rate_limit} calls/minute")

            # Remove API calls older than 1 minute
            old_calls_count = len(self.api_calls)
            while self.api_calls and current_time - self.api_calls[0] > 60:
                self.api_calls.popleft()
            removed_calls = old_calls_count - len(self.api_calls)
            if removed_calls > 0:
                print(f"  🗑️  Removed {removed_calls} expired API calls")

            calls_in_window = len(self.api_calls)
            print(f"  📊 Current API calls in 60s window: {calls_in_window}/{rate_limit}")

            # If we've made rate_limit calls in the last minute, wait
            if calls_in_window >= rate_limit:
                self.wait_duration = 60 - (current_time - self.api_calls[0])
                if self.wait_duration > 0:
                    print(f"  ⏳ RATE LIMIT TRIGGERED: Must wait {self.wait_duration:.1f}s")
                    self.update_api_status("API Status: Rate Limited")
                    self.api_wait_start = current_time
                    self.skip_wait_requested = False  # Reset skip flag
                    self.show_skip_button()
                    self.update_rate_limit_timer()
                    self._interruptible_wait(self.wait_duration)
                    print(f"  ✅ RATE LIMIT WAIT COMPLETED, proceeding with search")
            else:
                print(f"  ✅ RATE LIMIT OK: {calls_in_window}/{rate_limit} calls used")

            try:
                print(f"🎯 SEARCH STRATEGY: Two-phase approach per spec")

                # Phase 1: Try track name only
                print(f"   🔍 Phase 1: Searching for '{track}' (track only)")
                artist = self._try_search(track)

                if not artist and album:
                    print(f"   🔍 Phase 2: Searching for '{track} {album}' (track + album)")
                    # If no result or artist not found, try with album
                    artist = self._try_search(f"{track} {album}")

                if artist:
                    print(f"✅ iTunes API SEARCH COMPLETE: Found artist = '{artist}'")
                    self.update_api_status("API Status: Success")
                    return artist
                else:
                    print(f"❌ iTunes API SEARCH COMPLETE: No matching artist found")
                    self.update_api_status("API Status: No match found")
                    return None

            except Exception as e:
                print(f"❌ iTunes API SEARCH ERROR: {str(e)}")
                self.update_api_status(f"API Status: Error - {str(e)}")
                raise
    
    def _try_search(self, search_term):
        """Helper method to perform the actual iTunes API search (matches tkinter implementation)."""
        import urllib.parse

        # API REQUEST START
        print(f"\n🌐 === API REQUEST START ===")
        print(f"Search term: '{search_term}'")

        try:
            # URL encode the search term
            encoded_term = urllib.parse.quote(search_term)
            url = f"https://itunes.apple.com/search?term={encoded_term}&entity=song&limit=5&country=US&media=music"  # Get top 5 results
            print(f"📝 URL encoding: '{search_term}' → '{encoded_term}'")
            print(f"🔗 Request URL: {url}")

            # Check rate limiting status before making request
            current_api_calls = len(self.api_calls)
            rate_limit = int(getattr(self.rate_limit_input, 'value', '20') or '20')
            print(f"📊 Pre-request call count: {current_api_calls}/{rate_limit}")

            # Record the API call time BEFORE making request (per spec)
            self.api_calls.append(time.time())
            print(f"📈 API call recorded (new count: {len(self.api_calls)})")

            # Make the API call with timeout
            print(f"🚀 Making iTunes API HTTP request...")
            start_time = time.time()
            response = httpx.get(url, timeout=10)
            request_duration = time.time() - start_time

            print(f"⏱️  Request completed in {request_duration:.3f}s")
            print(f"📋 HTTP Status Code: {response.status_code}")
            print(f"📋 Response headers: {dict(list(response.headers.items())[:3])}...")  # First 3 headers

            if response.status_code == 429:
                # Rate limit hit
                self.rate_limit_hits += 1
                self.last_rate_limit_time = time.time()
                print(f"🚨 HTTP 429 RATE LIMIT HIT for '{search_term}' - Hit #{self.rate_limit_hits} at {time.strftime('%H:%M:%S')}")
                print(f"📄 Response body preview: {response.text[:200]}")
                # Schedule UI update from main thread
                self.update_stats_display()
                print(f"🌐 === API REQUEST END (RATE LIMITED) ===")
                raise Exception(f"Rate limit exceeded (429) for search: {search_term}")

            if response.status_code == 200:
                print(f"✅ HTTP 200 OK - Processing JSON response...")
                try:
                    data = response.json()
                    result_count = len(data.get('results', []))
                    print(f"📊 JSON parsed: {result_count} results returned")

                    if data.get('results'):
                        print(f"📋 Results preview (first 3 of {result_count}):")
                        for i, result in enumerate(data['results'][:3]):  # Show first 3 results
                            print(f"  [{i+1}] Track: '{result.get('trackName', 'N/A')}'")
                            print(f"      Artist: '{result.get('artistName', 'N/A')}'")
                            print(f"      Album: '{result.get('collectionName', 'N/A')}'")
                            print(f"      Kind: '{result.get('kind', 'N/A')}'")
                        if result_count > 3:
                            print(f"      ... and {result_count - 3} more results")
                    else:
                        print(f"📊 No results in JSON response")

                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    print(f"📄 Response body: {response.text[:500]}")
                    print(f"🌐 === API REQUEST END (JSON ERROR) ===")
                    return None

                if data.get('results'):
                    print(f"🔍 RESULT SELECTION HEURISTIC: Applying spec-compliant matching...")

                    # Look for exact match first (prefer tracks that start with search term)
                    exact_matches = []
                    for i, result in enumerate(data['results']):
                        track_name = result.get('trackName', '').lower()
                        search_lower = search_term.lower()

                        print(f"  🔍 Checking result {i+1}: '{track_name}' vs '{search_lower}'")
                        if track_name.startswith(search_lower):
                            exact_matches.append((i, result))
                            print(f"    ✅ EXACT MATCH found!")
                        else:
                            print(f"    ❌ No exact match")

                    if exact_matches:
                        # Use first exact match
                        match_index, best_result = exact_matches[0]
                        selected_artist = best_result.get('artistName')
                        print(f"🎯 SELECTED: Exact match #{match_index+1}, Artist = '{selected_artist}'")
                        print(f"🌐 === API REQUEST END (SUCCESS - EXACT MATCH) ===")
                        return selected_artist

                    # Fall back to first result (iTunes returns results by relevance)
                    best_match = data['results'][0]
                    selected_artist = best_match.get('artistName')
                    print(f"🎯 SELECTED: Fallback to first result, Artist = '{selected_artist}'")
                    print(f"   Track: '{best_match.get('trackName', 'N/A')}'")
                    print(f"🌐 === API REQUEST END (SUCCESS - FALLBACK) ===")
                    return selected_artist
                else:
                    print(f"❌ No results returned from iTunes API")
                    print(f"🌐 === API REQUEST END (NO RESULTS) ===")
                    return None
            else:
                print(f"❌ Non-200 HTTP status: {response.status_code}")
                print(f"📄 Response body: {response.text[:200]}")
                print(f"🌐 === API REQUEST END (HTTP ERROR) ===")
                raise Exception(f"iTunes API returned status code: {response.status_code}")

        except httpx.TimeoutException:
            print(f"⏰ REQUEST TIMEOUT after 10 seconds")
            print(f"🌐 === API REQUEST END (TIMEOUT) ===")
            raise Exception("Request timed out")
        except (httpx.HTTPError, httpx.RequestError) as e:
            print(f"🌐 NETWORK ERROR: {str(e)}")
            print(f"🌐 === API REQUEST END (NETWORK ERROR) ===")
            raise Exception(f"Network error: {str(e)}")
        except ValueError as e:
            # JSON decoding error
            print(f"📄 JSON DECODE ERROR: {str(e)}")
            print(f"🌐 === API REQUEST END (JSON DECODE ERROR) ===")
            raise Exception("Invalid response format")
        except Exception as e:
            if "429" not in str(e) and "rate limit" not in str(e).lower():
                print(f"💥 UNEXPECTED ERROR for '{search_term}': {str(e)}")
            print(f"🌐 === API REQUEST END (UNEXPECTED ERROR) ===")
            raise
    
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
                    )))
                return None
                
            # Generate output filename
            try:
                base_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
                output_name = f"{base_name}_lastfm_format.csv"
                output_path = os.path.join(os.path.dirname(self.current_file_path), output_name)
                
                # Check if output directory is writable
                output_dir = os.path.dirname(output_path)
                if not os.access(output_dir, os.W_OK):
                    self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                            title="Write Permission Error",
                            message=f"Cannot write to directory: {output_dir}\nPlease check permissions."
                        )))
                    return None
                    
            except Exception as e:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="Path Generation Error",
                        message=f"Error generating output path: {str(e)}"
                    )))
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
                    self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                            title="Data Processing Error",
                            message="No valid data rows found for saving."
                        )))
                    return None
                    
            except Exception as e:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="Data Format Error",
                        message=f"Error formatting data for Last.fm: {str(e)}"
                    )))
                return None
            
            # Create DataFrame with proper Last.fm headers
            try:
                lastfm_df = pd.DataFrame(lastfm_data, columns=[
                    'Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'
                ])
                
                if lastfm_df.empty:
                    self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                            title="Empty Output",
                            message="Processed data resulted in empty output file."
                        )))
                    return None
                    
            except Exception as e:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="DataFrame Creation Error",
                        message=f"Error creating output DataFrame: {str(e)}"
                    )))
                return None
            
            # Save to CSV with error handling
            try:
                lastfm_df.to_csv(output_path, index=False, encoding='utf-8')
                
                # Verify file was created and has content
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    # Store the output file path for later reprocessing (like tkinter version)
                    self.last_output_file = output_path
                    # Enable reprocess button after successful save (like tkinter)
                    self._schedule_ui_update(self._enable_reprocess_button())
                    return output_path
                else:
                    self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                            title="File Creation Error",
                            message="Output file was not created or is empty."
                        )))
                    return None
                    
            except PermissionError:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="Permission Error", 
                        message=f"Permission denied writing to: {output_path}"
                    )))
                return None
            except IOError as e:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="I/O Error",
                        message=f"I/O error saving file: {str(e)}"
                    )))
                return None
            except Exception as e:
                self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                        title="Save Error",
                        message=f"Failed to save CSV file: {str(e)}"
                    )))
                return None
                
        except Exception as e:
            self._schedule_ui_update(self.main_window.dialog(toga.ErrorDialog(
                    title="Unexpected Save Error",
                    message=f"Unexpected error during save: {str(e)}"
                )))
            return None
    
    def update_results(self, text):
        """Update the results text area."""
        # Store values for UI update
        self._pending_results_text = text
        # Schedule UI update on main thread from background thread
        self._schedule_ui_update(self._update_results_ui())

    async def _update_results_ui(self, widget=None):
        """Update results UI on main thread."""
        self.results_text.value = self._pending_results_text

    def append_log(self, text):
        """Append text to the log area (for live updates during search)."""
        self._pending_log_append = text
        self._schedule_ui_update(self._append_log_ui())

    async def _append_log_ui(self):
        """Append to log UI on main thread (newest at top)."""
        try:
            current = self.results_text.value or ""
            # Prepend new entry at top instead of bottom
            new_log = self._pending_log_append + "\n" + current
            # Keep log size reasonable - trim to first 10000 characters if too long
            if len(new_log) > 10000:
                new_log = new_log[:10000]
            self.results_text.value = new_log
        except Exception as e:
            print(f"⚠️  Error appending to log: {e}")
    
    def update_preview(self, df, total_rows=None):
        """Update the preview table."""
        # Store values for UI update
        self._pending_preview_df = df
        self._pending_total_rows = total_rows if total_rows is not None else len(df)
        # Schedule UI update on main thread from background thread
        self._schedule_ui_update(self._update_preview_ui())
    
    async def _update_preview_ui(self, widget=None):
        """Update preview UI on main thread."""
        try:
            print(f"🔄 _update_preview_ui() called on main thread")
            print(f"   DataFrame rows: {len(self._pending_preview_df):,}")

            # Clear existing data
            self.preview_table.data.clear()
            print(f"   ✅ Cleared preview table")

            # Add more rows for better visibility - up to 200 for reasonable performance with scrolling
            rows_added = 0
            preview_limit = min(200, len(self._pending_preview_df))

            # Count artists with data for debug
            artists_with_data = 0

            for i, row in self._pending_preview_df.head(preview_limit).iterrows():
                artist = str(row.get('Artist', '')) if pd.notna(row.get('Artist')) else ''
                track = str(row.get('Track', '')) if pd.notna(row.get('Track')) else ''
                album = str(row.get('Album', '')) if pd.notna(row.get('Album')) else ''
                timestamp = str(row.get('Timestamp', ''))[:16] if pd.notna(row.get('Timestamp')) else ''
                album_artist = str(row.get('Album Artist', '')) if pd.notna(row.get('Album Artist')) else ''
                duration = str(row.get('Duration', '')) if pd.notna(row.get('Duration')) else ''

                if artist:
                    artists_with_data += 1

                self.preview_table.data.append((artist, track, album, timestamp, album_artist, duration))
                rows_added += 1

            print(f"   ✅ Added {rows_added} rows to preview table")
            print(f"   📊 Artists with data in preview: {artists_with_data}/{preview_limit}")

            # Update preview info label with row count information
            total_rows = getattr(self, '_pending_total_rows', len(self._pending_preview_df))
            if total_rows > preview_limit:
                self.preview_info_label.text = f"Showing first {preview_limit} of {total_rows:,} rows"
            else:
                self.preview_info_label.text = f"Showing all {total_rows:,} rows"

            print(f"   ✅ Updated preview info label")
            print(f"   ✅ UI table refresh complete!\n")
        except Exception as e:
            print(f"❌ Error updating preview: {e}")
            import traceback
            traceback.print_exc()
    
    async def load_immediate_preview(self):
        """Load and display immediate preview of CSV file when selected (optimized for large files)."""
        if not self.current_file_path:
            return
        
        try:
            import pandas as pd
            
            # For Play Activity files (which are massive), use optimized preview approach
            if "Play Activity" in self.detected_file_type:
                await self.load_play_activity_preview()
                return
            
            # For other file types, use standard preview loading
            # Load first 10 rows for immediate preview with encoding detection
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            preview_df = None
            
            for encoding in encodings_to_try:
                try:
                    # Read first 100 rows for preview (was 10)
                    preview_df = pd.read_csv(self.current_file_path, encoding=encoding, nrows=100)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    print(f"Error reading CSV with {encoding}: {e}")
                    continue
            
            if preview_df is None or preview_df.empty:
                print("Could not load CSV preview")
                return
            
            # Process the preview data through the same column mapping as the main processing
            # Processing preview data
            try:
                processed_preview = self.process_csv_data(preview_df, self.detected_file_type)
                if processed_preview is not None and not processed_preview.empty:
                    # Update preview with processed data - show total file rows if we know them
                    total_file_rows = getattr(self, 'row_count', len(processed_preview))
                    self.update_preview(processed_preview, total_rows=total_file_rows)
                    print(f"Loaded immediate preview: {len(processed_preview)} rows")
                else:
                    print("Processed preview data is empty")
            except Exception as e:
                # If processing fails, show raw data preview
                print(f"Error processing preview data, showing raw preview: {e}")
                # Map common columns for raw preview
                raw_preview = pd.DataFrame()
                
                # Try to map columns to standard format
                if 'Artist Name' in preview_df.columns:
                    raw_preview['Artist'] = preview_df['Artist Name']
                elif 'Artist' in preview_df.columns:
                    raw_preview['Artist'] = preview_df['Artist']
                else:
                    raw_preview['Artist'] = 'Unknown'
                
                if 'Track Name' in preview_df.columns:
                    raw_preview['Track'] = preview_df['Track Name']
                elif 'Song Name' in preview_df.columns:
                    raw_preview['Track'] = preview_df['Song Name'] 
                elif 'Track' in preview_df.columns:
                    raw_preview['Track'] = preview_df['Track']
                else:
                    raw_preview['Track'] = 'Unknown'
                
                if 'Album Name' in preview_df.columns:
                    raw_preview['Album'] = preview_df['Album Name']
                elif 'Album' in preview_df.columns:
                    raw_preview['Album'] = preview_df['Album']
                else:
                    raw_preview['Album'] = 'Unknown'
                
                # Add placeholder timestamp for raw preview
                raw_preview['Timestamp'] = 'Processing required'
                
                if not raw_preview.empty:
                    # Show total file rows if we know them
                    total_file_rows = getattr(self, 'row_count', len(raw_preview))
                    self.update_preview(raw_preview, total_rows=total_file_rows)
                    print(f"Loaded raw preview: {len(raw_preview)} rows")
                
        except Exception as e:
            print(f"Error in load_immediate_preview: {e}")
            import traceback
            traceback.print_exc()
    
    async def load_play_activity_preview(self):
        """Optimized preview loading for massive Play Activity CSV files."""
        try:
            import pandas as pd
            
            # Use lightweight approach - just read first few rows without processing
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            preview_df = None
            
            for encoding in encodings_to_try:
                try:
                    # Read first 100 rows for Play Activity preview (was 10)
                    preview_df = pd.read_csv(self.current_file_path, encoding=encoding, nrows=100)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    print(f"Error reading Play Activity CSV with {encoding}: {e}")
                    continue
            
            if preview_df is None or preview_df.empty:
                print("Could not load Play Activity preview")
                return
            
            # Create simplified preview for Play Activity files
            simplified_preview = pd.DataFrame()
            
            # Extract key columns directly without heavy processing
            for index, row in preview_df.iterrows():
                artist = str(row.get('Container Artist Name', '')).strip() if pd.notna(row.get('Container Artist Name', '')) else ''
                if not artist:
                    artist = str(row.get('Artist Name', '')).strip() if pd.notna(row.get('Artist Name', '')) else ''
                
                track = str(row.get('Song Name', '')).strip() if pd.notna(row.get('Song Name', '')) else ''
                album = str(row.get('Album Name', '')).strip() if pd.notna(row.get('Album Name', '')) else ''
                if not album:
                    album = str(row.get('Container Album Name', '')).strip() if pd.notna(row.get('Container Album Name', '')) else ''
                
                timestamp = str(row.get('Event Start Timestamp', ''))[:16] if pd.notna(row.get('Event Start Timestamp', '')) else 'Processing required'
                
                # Only add rows with actual track data
                if track or artist:
                    simplified_preview = pd.concat([simplified_preview, pd.DataFrame({
                        'Artist': [artist],
                        'Track': [track],
                        'Album': [album], 
                        'Timestamp': [timestamp]
                    })], ignore_index=True)
            
            if not simplified_preview.empty:
                # Show total file rows if we know them
                total_file_rows = getattr(self, 'row_count', len(simplified_preview))
                self.update_preview(simplified_preview, total_rows=total_file_rows)
                print(f"Loaded Play Activity preview: {len(simplified_preview)} rows (optimized for large file)")
            else:
                print("No trackable content found in Play Activity preview")
                
        except Exception as e:
            print(f"Error in load_play_activity_preview: {e}")
            import traceback
            traceback.print_exc()
    
    def update_progress(self, message, value, detailed_stats=None):
        """Update progress bar, label, and optional detailed stats."""
        # Store values for UI update
        self._pending_progress_message = message
        self._pending_progress_value = value
        self._pending_detailed_stats = detailed_stats
        # Schedule UI update on main thread from background thread
        self._schedule_ui_update(self._update_progress_ui())

    async def _update_progress_ui(self, widget=None):
        """Update progress UI on main thread."""
        self.progress_label.text = self._pending_progress_message
        self.progress_bar.value = self._pending_progress_value

        # Update detailed stats if provided
        if hasattr(self, '_pending_detailed_stats') and self._pending_detailed_stats:
            self.detailed_stats_label.text = self._pending_detailed_stats
        elif hasattr(self, '_pending_detailed_stats'):
            # Clear detailed stats if explicitly set to None
            self.detailed_stats_label.text = ""
    
    def update_api_status(self, status):
        """Update the iTunes API status label."""
        try:
            if hasattr(self, 'api_status_label'):
                # Schedule UI update on main thread
                self._schedule_ui_update(self._update_api_status_ui(status))
        except Exception as e:
            print(f"Error updating API status: {e}")
    
    async def _update_api_status_ui(self, status):
        """Update API status UI on main thread."""
        if hasattr(self, 'api_status_label'):
            self.api_status_label.text = status
    
    def show_skip_button(self):
        """Show the skip wait button during rate limiting."""
        try:
            if hasattr(self, 'skip_wait_button'):
                # Schedule UI update on main thread
                self._schedule_ui_update(self._show_skip_button_ui())
        except Exception as e:
            print(f"Error showing skip button: {e}")
    
    async def _show_skip_button_ui(self):
        """Show skip button UI on main thread."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.style.visibility = 'visible'
    
    def update_rate_limit_timer(self):
        """Update the rate limit timer display."""
        if self.api_wait_start is not None and not getattr(self, 'process_stopped', False):
            elapsed = time.time() - self.api_wait_start
            remaining = max(0, self.wait_duration - elapsed)
            # Update status bar wait time
            status_text = f" Wait: {remaining:.1f}s"
            self._schedule_ui_update(self._update_timer_ui(status_text))
            if remaining > 0 and not getattr(self, 'process_stopped', False) and not self.skip_wait_requested:
                # Schedule next update
                threading.Timer(0.1, self.update_rate_limit_timer).start()
            else:
                self.api_wait_start = None
                self._schedule_ui_update(self._update_timer_ui(""))
                self.hide_skip_button()
    
    async def _update_timer_ui(self, text):
        """Update timer UI on main thread."""
        if hasattr(self, 'api_timer_label'):
            self.api_timer_label.text = text
    
    def hide_skip_button(self):
        """Hide the skip wait button."""
        try:
            if hasattr(self, 'skip_wait_button'):
                self._schedule_ui_update(self._hide_skip_button_ui())
        except Exception as e:
            print(f"Error hiding skip button: {e}")
    
    async def _hide_skip_button_ui(self):
        """Hide skip button UI on main thread."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.style.visibility = 'hidden'
    
    def _interruptible_wait(self, duration):
        """Wait for the specified duration, but allow interruption via skip_wait_requested."""
        start_time = time.time()
        while time.time() - start_time < duration:
            if self.skip_wait_requested or getattr(self, 'process_stopped', False):
                break
            time.sleep(0.1)  # Sleep in small increments to allow interruption

    def _sync_search_itunes(self, track_name, album_name):
        """Synchronous wrapper for iTunes API search to avoid event loop issues in threads."""
        import time
        print(f"\n🔍 DEBUG: _sync_search_itunes called")
        print(f"   Track: '{track_name}'")
        print(f"   Album: '{album_name}'")
        try:
            # Call _search_itunes() directly (already synchronous, no event loop needed)
            print(f"   📝 Calling music_search_service._search_itunes() directly...")
            search_start = time.time()
            result = self.music_search_service._search_itunes(track_name, '', album_name)
            search_time = time.time() - search_start
            print(f"   ✅ _search_itunes() completed in {search_time:.2f}s")
            print(f"   📊 Result: {result}")
            return result
        except Exception as e:
            print(f"❌ Error in sync iTunes search: {e}")
            import traceback
            try:
                traceback.print_exc()
            except (BrokenPipeError, OSError):
                pass  # Ignore broken pipe errors in traceback printing
            return {'success': False, 'error': str(e)}

    def update_missing_artist_count(self):
        """Update the Export Missing Artists button with current count."""
        try:
            if hasattr(self, 'processed_df') and self.processed_df is not None:
                # Count rows with missing artists
                missing_count = len(self.processed_df[self.processed_df['Artist'].isna() | (self.processed_df['Artist'] == '')])

                # Schedule UI update on main thread
                self._schedule_ui_update(self._update_missing_artist_count_ui(missing_count))
        except Exception as e:
            print(f"⚠️  Error updating missing artist count: {e}")

    async def _update_missing_artist_count_ui(self, missing_count):
        """Update missing artist count UI on main thread."""
        if hasattr(self, 'save_missing_button'):
            if missing_count > 0:
                self.save_missing_button.text = f"Export {missing_count:,} Missing Artists"
                self.save_missing_button.enabled = True
            else:
                self.save_missing_button.text = "Export Missing Artists"
                self.save_missing_button.enabled = False

    def update_save_status(self):
        """Update the save status indicator label."""
        try:
            if hasattr(self, 'save_status_label'):
                if hasattr(self, 'current_save_path') and self.current_save_path:
                    filename = self.current_save_path.name
                    self.save_status_label.text = f"Progress saves to: {filename}"
                else:
                    self.save_status_label.text = "Save required to enable search"
        except Exception as e:
            print(f"Error updating save status: {e}")

    def update_search_button_state(self):
        """Enable/disable Search for Missing Artists button based on save status."""
        try:
            if hasattr(self, 'reprocess_button'):
                # Only enable if we have data AND it's been saved
                has_data = hasattr(self, 'processed_df') and self.processed_df is not None
                is_saved = hasattr(self, 'current_save_path') and self.current_save_path is not None
                self.reprocess_button.enabled = has_data and is_saved
        except Exception as e:
            print(f"⚠️  Error updating search button state: {e}")

    def on_rate_limit_hit(self, sleep_time):
        """Callback when rate limit is hit - updates UI and enables skip button."""
        try:
            # Enable skip button
            self._schedule_ui_update(self._enable_skip_button())
        except Exception as e:
            print(f"⚠️  Error in rate limit callback: {e}")

    def on_actual_rate_limit_detected(self):
        """Callback when iTunes API actually returns a 429 rate limit error."""
        self.append_log(f"⚠️  iTunes API rate limit hit! Discovering actual limit...")
        print(f"⚠️  ACTUAL rate limit detected from iTunes - discovering limit")

    def on_rate_limit_discovered(self, discovered_limit):
        """Callback when actual rate limit is discovered from 429 error."""
        safety_margin = self.music_search_service.settings.get("rate_limit_safety_margin", 0.8)
        effective_limit = int(discovered_limit * safety_margin)

        self.append_log(f"✅ Discovered iTunes rate limit: {discovered_limit} req/min (using {effective_limit} with {int(safety_margin*100)}% safety)")
        print(f"✅ Discovered rate limit: {discovered_limit}, will use {effective_limit} going forward")

        # Update the discovered limit display if it exists
        self._schedule_ui_update(self._update_discovered_limit_ui(discovered_limit, effective_limit))

    async def _update_discovered_limit_ui(self, discovered, effective):
        """Update UI to show discovered rate limit."""
        if hasattr(self, 'discovered_limit_label'):
            self.discovered_limit_label.text = f"Discovered: {discovered} req/min (using {effective})"

    async def _enable_skip_button(self):
        """Enable the skip wait button."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.enabled = True

    def on_rate_limit_wait(self, total_wait_time):
        """Interruptible wait with countdown display for rate limiting."""
        import time
        start_time = time.time()
        last_update = -1  # Force update on first iteration

        # Store rate limit state for progress updates
        self.rate_limit_remaining = total_wait_time
        self.in_rate_limit_wait = True

        # Show initial rate limit message
        initial_secs = int(total_wait_time)
        self.update_progress(f"⏸️  Rate limit hit - waiting {initial_secs}s", None)

        while True:
            elapsed = time.time() - start_time
            remaining = total_wait_time - elapsed

            # Check if wait is complete
            if remaining <= 0:
                break

            # Check if stop was requested
            if hasattr(self, 'stop_itunes_search_flag') and self.stop_itunes_search_flag:
                print(f"⏹️ Rate limit wait stopped due to stop button")
                self.skip_wait_requested = False  # Reset flag
                # Don't reset rate limit when stopping - just exit
                break

            # Check if skip was requested
            if self.skip_wait_requested:
                print(f"🚀 Rate limit wait skipped by user")
                self.skip_wait_requested = False  # Reset flag

                # Clear rate limit queue to force full 60-second wait before next batch
                # This prevents immediately hitting the rate limit again after skip
                if hasattr(self, 'music_search_service') and hasattr(self.music_search_service, 'itunes_requests'):
                    self.music_search_service.itunes_requests.clear()
                    print(f"   🔄 Cleared rate limit queue - forcing full 60s wait before next request")
                    self.append_log(f"✅ Skipped wait - will wait full 60s before next request batch")
                break

            # Update rate limit countdown every 0.5s
            current_second = int(elapsed * 2)  # Update twice per second
            if current_second != last_update:
                last_update = current_second
                self.rate_limit_remaining = remaining

                # Update button text and progress message with countdown
                remaining_secs = int(remaining)
                if remaining_secs > 0:
                    # Update button text to show countdown
                    self._schedule_ui_update(self._update_skip_button_text(f"Skip or Wait {remaining_secs}s"))
                    # Also update progress message
                    self.update_progress(f"⏸️  Rate limit: {remaining_secs}s", None)

            # Sleep in small increments to allow interruption
            time.sleep(0.1)

        # Clear rate limit state
        self.in_rate_limit_wait = False
        self.rate_limit_remaining = 0

        # Reset button text and disable after wait completes
        self._schedule_ui_update(self._reset_skip_button())

    async def _update_skip_button_text(self, text):
        """Update skip button text."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.text = text

    async def _reset_skip_button(self):
        """Reset skip button text and disable it."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.text = "Skip Rate Limit Wait"
            self.skip_wait_button.enabled = False

    async def _disable_skip_button(self):
        """Disable the skip wait button."""
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.enabled = False

    async def _update_rate_limit_warning_ui(self, sleep_time):
        """Update rate limit warning UI on main thread."""
        if hasattr(self, 'rate_limit_warning_label'):
            self.rate_limit_warning_label.text = f"⏸️ Rate limit hit - waiting {int(sleep_time)}s..."
        # Enable skip button if it exists
        if hasattr(self, 'skip_wait_button'):
            self.skip_wait_button.enabled = True

    async def _switch_to_itunes_ui(self, missing_count):
        """Switch UI to iTunes after MusicBrainz completes (radio buttons and search button)."""
        try:
            # Switch radio buttons
            if hasattr(self, 'itunes_radio') and hasattr(self, 'musicbrainz_radio'):
                self.itunes_radio.value = True
                self.musicbrainz_radio.value = False
                print(f"✅ Switched radio to iTunes")

            # Update search button text
            if hasattr(self, 'reprocess_button'):
                self.reprocess_button.text = "Search with iTunes"
                print(f"✅ Updated button text to 'Search with iTunes' ({missing_count:,} tracks remaining)")
        except Exception as e:
            print(f"⚠️  Error switching to iTunes UI: {e}")

    async def _reset_search_button_text(self):
        """Reset search button text to default."""
        try:
            if hasattr(self, 'reprocess_button'):
                self.reprocess_button.text = "Search for Missing Artists"
        except Exception as e:
            print(f"⚠️  Error resetting search button text: {e}")

    def skip_current_wait(self, widget=None):
        """Skip the current rate limit wait (Clear Queue functionality)."""
        self.skip_wait_requested = True
        self.api_wait_start = None
        self.hide_skip_button()
        
        # Clear the entire rate limit queue to reset rate limiting
        with self.api_lock:
            self.api_calls.clear()
            print(f"🚀 Rate limit queue cleared - skipping wait and resetting rate limiter")
        
        # Update API status to show queue was cleared
        self.update_api_status("API Status: Queue Cleared")
    
    def update_stats_display(self):
        """Update the statistics display in the UI."""
        try:
            # Update MusicBrainz stats
            # if hasattr(self, 'musicbrainz_stats_label'):  # Stats removed
            #     asyncio.run_coroutine_threadsafe(
            #         self._update_musicbrainz_stats_ui(f" MusicBrainz: {self.musicbrainz_found}"),
            #         self.main_loop
            #     )

            # Update iTunes stats
            # if hasattr(self, 'itunes_stats_label'):  # Stats removed
            #     asyncio.run_coroutine_threadsafe(
            #         self._update_itunes_stats_ui(f"🌐 iTunes: {self.itunes_found}"),
            #         self.main_loop
            #     )
            
            # Color-code rate limits based on frequency
            rate_limit_text = f"Warning: Limits: {self.rate_limit_hits}"
            if self.rate_limit_hits == 0:
                pass  # color = "green"
            elif self.rate_limit_hits < 5:
                pass  # color = "orange"  
            else:
                pass  # color = "red"
            
            # Add timing info if we hit rate limits recently
            if self.last_rate_limit_time and self.rate_limit_hits > 0:
                elapsed = time.time() - self.last_rate_limit_time
                if elapsed < 60:  # Show recent rate limit info
                    timing_text = f" (last: {elapsed:.0f}s ago)"
                    rate_limit_text += timing_text
                    
            # Update rate limit stats with color (note: Toga doesn't support colors the same way)
            if hasattr(self, 'rate_limit_stats_label'):
                self._schedule_ui_update(self._update_rate_limit_stats_ui(rate_limit_text))
        except Exception as e:
            print(f"Error updating stats display: {e}")
    
    async def _update_musicbrainz_stats_ui(self, text):
        """Update MusicBrainz stats UI on main thread."""
        # if hasattr(self, 'musicbrainz_stats_label'):  # Stats removed
            # self.musicbrainz_stats_label.text = text  # Stats removed
            
    async def _update_itunes_stats_ui(self, text):
        """Update iTunes stats UI on main thread.""" 
        # if hasattr(self, 'itunes_stats_label'):  # Stats removed
            # self.itunes_stats_label.text = text  # Stats removed
            
    async def _update_rate_limit_stats_ui(self, text):
        """Update rate limit stats UI on main thread."""
        if hasattr(self, 'rate_limit_stats_label'):
            self.rate_limit_stats_label.text = text
    
    def reset_processing_stats(self):
        """Reset processing statistics for a new conversion (matches tkinter implementation)."""
        self.musicbrainz_count = 0
        self.itunes_count = 0
        self.rate_limit_hits = 0
        self.last_rate_limit_time = None
        self.failed_requests.clear()

        # Reset timing tracking
        self.musicbrainz_search_time = 0
        self.itunes_search_time = 0

        self.update_stats_display()
    
    @trace_call("App.show_instructions")
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

    def on_musicbrainz_selected(self, widget):
        """Handle MusicBrainz radio button selection."""
        if widget.value:  # Only act when turned ON
            # Turn off iTunes radio
            self.itunes_radio.value = False
            self.current_provider = "musicbrainz"
            self.music_search_service.set_search_provider("musicbrainz")
            # Update search button text
            if hasattr(self, 'reprocess_button') and not self.is_search_interrupted:
                self.reprocess_button.text = "Search with MusicBrainz"
            print(f"🔍 Switched to MusicBrainz")

    def on_itunes_selected(self, widget):
        """Handle iTunes radio button selection."""
        if widget.value:  # Only act when turned ON
            # Turn off MusicBrainz radio
            self.musicbrainz_radio.value = False
            self.current_provider = "itunes"
            self.music_search_service.set_search_provider("itunes")
            # Update search button text
            if hasattr(self, 'reprocess_button') and not self.is_search_interrupted:
                self.reprocess_button.text = "Search with iTunes"
            print(f"🔍 Switched to iTunes API")

    def on_itunes_api_changed(self, widget):
        """Handle iTunes API switch change."""
        # Implementation would go here
        pass
    
    @trace_call("App.download_database")
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
                    
                    # Start download with progress tracking using async pattern
                    self.update_results("🔄 Starting database download...")

                    # Toggle button to "Stop Download"
                    self.download_button.text = "Stop Download"
                    self.download_button.on_press = self.stop_download

                    try:
                        # Start the download task using proper async pattern
                        asyncio.create_task(self.run_database_download())

                    except Exception as e:
                        # Reset button
                        self.download_button.text = "Download Database (~2GB)"
                        self.download_button.on_press = self.download_database

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
    
    def cancel_download(self):
        """Cancel the current download."""
        if hasattr(self.music_search_service, 'musicbrainz_manager'):
            self.music_search_service.musicbrainz_manager.cancel_download()

    async def stop_download(self, widget):
        """Stop the current download."""
        self.cancel_download()
        self.update_results("🛑 Stopping download...")

        # Reset button (will be confirmed when download actually stops)
        self.download_button.text = "Download Database (~2GB)"
        self.download_button.on_press = self.download_database

    async def download_complete(self, success, completion_time):
        """Handle download completion."""
        # Reset download button
        self.download_button.text = "Download Database (~2GB)"
        self.download_button.on_press = self.download_database

        if success:
            await self.main_window.dialog(toga.InfoDialog(
                title="Download Complete",
                message=f"MusicBrainz database downloaded successfully!\nTime taken: {completion_time}"
            ))
            self.update_results(f"✅ Database download completed successfully in {completion_time}")
            self.progress_label.text = "Ready to convert your Apple Music files"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = ""
            self.progress_bar.value = 0
            # Refresh database status
            await self.check_database_status()
        else:
            # Show dialog with manual import option
            result = await self.main_window.dialog(toga.QuestionDialog(
                title="Download Failed",
                message="Database download failed. Would you like to try manual import instead?"
            ))
            if result:
                await self.manual_import_database(None)
            self.update_results("❌ Error: Database download failed")
            self.progress_label.text = "Ready to convert your Apple Music files"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = ""
            self.progress_bar.value = 0
    
    async def download_failed(self, error_message):
        """Handle download failure."""
        # Reset download button
        self.download_button.text = "Download Database (~2GB)"
        self.download_button.on_press = self.download_database

        await self.main_window.dialog(toga.ErrorDialog(
            title="Download Error",
            message=f"Download failed: {error_message}"
        ))
        self.update_results(f"❌ Error: Database download error: {error_message}")
        self.progress_label.text = "Ready to convert your Apple Music files"
        if hasattr(self, 'detailed_stats_label'):
            self.detailed_stats_label.text = ""
        self.progress_bar.value = 0
    
    async def run_database_download(self):
        """Run database download with main UI progress integration."""
        import time
        download_start_time = time.time()
        
        try:
            # Show download path in progress section
            db_path = self.music_search_service.musicbrainz_manager.data_dir
            self.progress_label.text = f"Downloading to: {db_path}"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = "Initializing download..."
            self.progress_bar.value = 0
            
            # Use run_in_executor for thread-safe background work
            import concurrent.futures
            
            # Create a progress callback that's safe to call from background thread
            progress_data = {"message": "", "percent": 0, "speed": ""}
            
            def background_progress_callback(message, progress_percent, extra_data=None):
                progress_data["message"] = message
                if progress_percent is not None:
                    progress_data["percent"] = int(progress_percent)
            
            # Define the blocking download work
            def blocking_download():
                return self.music_search_service.download_database(background_progress_callback)
            
            # Create periodic UI update task with time tracking
            async def update_ui_periodically():
                while True:
                    try:
                        # Update progress and message
                        self.progress_bar.value = progress_data["percent"]
                        if hasattr(self, 'detailed_stats_label'):
                            self.detailed_stats_label.text = progress_data["message"]
                        
                        # Calculate and show elapsed time
                        elapsed_time = time.time() - download_start_time
                        hours, remainder = divmod(int(elapsed_time), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        if hours > 0:
                            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        else:
                            time_str = f"{minutes:02d}:{seconds:02d}"
                        
                        # Extract speed from message if present
                        message = progress_data["message"]
                        speed_info = ""
                        if "(" in message and ")" in message:
                            speed_part = message.split("(")[-1].split(")")[0]
                            if "KB/s" in speed_part or "MB/s" in speed_part:
                                speed_info = f" • {speed_part}"
                        
                        # Update progress label with time and speed
                        self.progress_label.text = f"Downloading to: {db_path} • Time: {time_str}{speed_info}"
                        
                    except Exception as e:
                        print(f"Error updating progress UI: {e}")
                    
                    await asyncio.sleep(0.5)  # Update every 500ms
            
            # Start UI update task
            ui_task = asyncio.create_task(update_ui_periodically())
            
            # Run download in background thread
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                success = await loop.run_in_executor(executor, blocking_download)
            
            # Cancel UI update task
            ui_task.cancel()
            
            # Calculate final time
            total_time = time.time() - download_start_time
            hours, remainder = divmod(int(total_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                final_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                final_time_str = f"{minutes:02d}:{seconds:02d}"
            
            # Handle completion
            await self.download_complete(success, final_time_str)
            
        except Exception as e:
            await self.download_failed(str(e))
    
    async def import_complete(self, success, progress_window):
        """Handle manual import completion."""
        # Close popup window if it exists (None when using main progress bar)
        if progress_window:
            try:
                progress_window.close()
            except:
                pass

        if success:
            await self.main_window.dialog(toga.InfoDialog(
                title="Import Complete",
                message="MusicBrainz database imported successfully!"
            ))
            self.update_results("✅ Database import completed successfully")
            # Reset progress bar
            self.progress_label.text = "Ready to convert your Apple Music files"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = ""
            self.progress_bar.value = 0
            # Refresh database status
            await self.check_database_status()
        else:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Import Failed",
                message="Database import failed. Please check the file format and try again."
            ))
            self.update_results("❌ Error: Database import failed")
            # Reset progress bar
            self.progress_label.text = "Ready to convert your Apple Music files"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = ""
            self.progress_bar.value = 0
    
    async def import_failed(self, error_message, progress_window):
        """Handle manual import failure."""
        # Close popup window if it exists (None when using main progress bar)
        if progress_window:
            try:
                progress_window.close()
            except:
                pass

        await self.main_window.dialog(toga.ErrorDialog(
            title="Import Error",
            message=f"Import failed: {error_message}"
        ))
        self.update_results(f"❌ Error: Database import error: {error_message}")
        # Reset progress bar
        self.progress_label.text = "Ready to convert your Apple Music files"
        if hasattr(self, 'detailed_stats_label'):
            self.detailed_stats_label.text = ""
        self.progress_bar.value = 0
    
    async def run_database_import(self, file_path_str):
        """Run database import using main progress bar (like download)."""
        try:
            # Use main progress bar instead of popup
            self.update_progress(f"🔄 Importing database from {os.path.basename(file_path_str)}...", 0)

            # Use run_in_executor for thread-safe background work
            import concurrent.futures

            # Create a progress callback that's safe to call from background thread
            progress_data = {"message": "", "percent": 0}

            def background_progress_callback(message, progress_percent, extra_data=None):
                progress_data["message"] = message
                if progress_percent is not None:
                    progress_data["percent"] = int(progress_percent)

            # Define the blocking import work
            def blocking_import():
                return self.music_search_service.musicbrainz_manager.manual_import_database(
                    file_path_str, background_progress_callback
                )

            # Create periodic UI update task using main progress bar
            async def update_ui_periodically():
                while True:
                    try:
                        if progress_data["message"]:
                            self.update_progress(progress_data["message"], progress_data["percent"])
                    except Exception as e:
                        print(f"Error updating import UI: {e}")

                    await asyncio.sleep(0.5)  # Update every 500ms

            # Start UI update task
            ui_task = asyncio.create_task(update_ui_periodically())

            # Run import in background thread
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                success = await loop.run_in_executor(executor, blocking_import)

            # Cancel UI update task
            ui_task.cancel()

            # Handle completion
            await self.import_complete(success, None)

        except Exception as e:
            await self.import_failed(str(e), None)
    
    async def check_for_updates(self, widget):
        """Check for database updates with comprehensive error handling and progress indication."""
        # Store original button state
        original_text = self.check_updates_button.text

        try:
            # Show progress indication
            self.check_updates_button.text = "Checking..."
            self.check_updates_button.enabled = False
            self.update_results("🔍 Connecting to MusicBrainz servers...")

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
                # Get current database info for detailed reporting
                db_info = self.music_search_service.musicbrainz_manager.get_database_info()
                current_version = db_info.get("last_updated", "Never")

                # Use service method to check for updates
                has_updates, message = self.music_search_service.check_for_updates()

                # Create detailed report of what was checked
                report_details = self._create_update_check_report(current_version, has_updates, message)

                if has_updates:
                    result = await self.main_window.dialog(toga.ConfirmDialog(
                        title="Updates Available",
                        message=f"{report_details}\n\nDownload now?"
                    ))

                    if result:
                        await self.download_database(None)
                else:
                    await self.main_window.dialog(toga.InfoDialog(
                        title="Database Status",
                        message=report_details
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
        finally:
            # Restore button state
            self.check_updates_button.text = original_text
            self.check_updates_button.enabled = True
            self.update_results("🎵 Ready to convert your Apple Music files")

    def _create_update_check_report(self, current_version, has_updates, message):
        """Create a detailed report of the update check process."""
        import datetime

        report = []

        # Report what was checked
        report.append("✅ Update Check Completed")
        report.append("")

        # Current database status
        if current_version == "Never":
            report.append("📊 Current Status: No local database found")
        else:
            try:
                # Parse and format the current version date
                if current_version.endswith('Z'):
                    current_date = datetime.datetime.fromisoformat(current_version.replace('Z', '+00:00'))
                else:
                    current_date = datetime.datetime.fromisoformat(current_version)

                # Remove timezone info for consistent handling
                if current_date.tzinfo:
                    current_date = current_date.replace(tzinfo=None)

                days_old = (datetime.datetime.now() - current_date).days
                report.append(f"📊 Current Database: {current_date.strftime('%Y-%m-%d %H:%M')} ({days_old} days old)")
            except Exception:
                report.append(f"📊 Current Database: {current_version}")

        # What was checked
        report.append("🔍 Checked: MusicBrainz canonical data repository")
        report.append("🌐 Server: https://data.metabrainz.org")

        # Results
        report.append("")
        if has_updates:
            report.append(f"🆕 Result: {message}")
            report.append("")
            report.append("The MusicBrainz database is updated weekly with new")
            report.append("releases, artist information, and metadata improvements.")
        else:
            report.append(f"✅ Result: {message}")
            if "up to date" in message.lower():
                report.append("")
                report.append("Your MusicBrainz database is current and ready")
                report.append("to use for fast offline music searches.")

        return "\n".join(report)

    def format_file_size(self, size_bytes):
        """Format file size in appropriate units (KB/MB/GB)."""
        if size_bytes < 1024:  # Less than 1 KB
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:  # Less than 1 MB
            size_kb = size_bytes / 1024
            return f"{size_kb:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:  # Less than 1 GB
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        else:  # 1 GB or larger
            size_gb = size_bytes / (1024 * 1024 * 1024)
            return f"{size_gb:.2f} GB"

    @trace_call("App.manual_import_database")
    async def manual_import_database(self, widget):
        """Handle manual database import with help and comprehensive error handling."""
        try:
            # Show help dialog first
            help_message = """Manual MusicBrainz Database Import

You can download the MusicBrainz canonical data from:
🌐 https://data.metabrainz.org/pub/musicbrainz/canonical_data/

Look for the latest dated folder (e.g., musicbrainz-canonical-dump-YYYYMMDD-080003/)
then download the .tar.zst file inside.

✅ Supported Formats:
• .tar.zst - Compressed archive (recommended, ~2GB)
• .csv - Uncompressed CSV (if available, ~28GB)

The .tar.zst file will be automatically extracted during import.

📋 Expected CSV Columns:
id, artist_credit_id, artist_mbids, artist_credit_name,
release_mbid, release_name, recording_mbid, recording_name,
combined_lookup, score

📦 File Size: ~2GB compressed, ~28GB extracted
🔄 Updates: Weekly (every Thursday)

The import will validate the file format and show progress."""

            # Show options dialog with Open URL button
            url_choice = await self.main_window.dialog(toga.ConfirmDialog(
                title="Manual Database Import",
                message=help_message + "\n\nWould you like to open the download URL in your browser first?"
            ))

            if url_choice:
                # Open the URL in browser
                try:
                    import webbrowser
                    webbrowser.open("https://data.metabrainz.org/pub/musicbrainz/canonical_data/")
                except Exception:
                    pass  # Browser opening might fail on some systems

            # Ask if user wants to continue with file selection
            show_help = await self.main_window.dialog(toga.ConfirmDialog(
                title="Manual Database Import",
                message="Ready to select your downloaded database file?"
            ))
            
            if not show_help:
                return
                
            try:
                file_path = await self.main_window.dialog(toga.OpenFileDialog(
                    title="Select MusicBrainz Database File (.tar.zst, .csv, or .tsv)",
                    file_types=["zst", "csv", "tsv"]
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
                    
                    # Check file size
                    file_size = os.path.getsize(file_path_str)
                    if file_size < 1024 * 1024:  # Less than 1MB
                        result = await self.main_window.dialog(toga.ConfirmDialog(
                            title="Small File Warning",
                            message=f"Selected file is only {file_size / 1024:.1f} KB. MusicBrainz database files are typically much larger (>100MB). Continue anyway?"
                        ))
                        if not result:
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
                            
                            # Start the import task using proper async pattern
                            asyncio.create_task(self.run_database_import(file_path_str))
                            
                        except Exception as e:
                            await self.main_window.dialog(toga.ErrorDialog(
                                title="Import Failed",
                                message=f"Failed to start import: {str(e)}"
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
    
    # Removed toggle_pause - using unified process controls
    
    # Removed stop_search - using unified process controls
    
    def skip_wait(self, widget):
        """Skip the current wait period."""
        self.skip_wait_requested = True
        self.update_progress("⏭️ Skipping rate limit wait...", self.progress_bar.value)
    
    async def copy_results(self, widget):
        """Copy CSV data to clipboard like tkinter version."""
        # Check if we have processed data to copy
        if not hasattr(self, 'processed_df') or self.processed_df is None or self.processed_df.empty:
            await self.main_window.dialog(toga.ErrorDialog(
                title="No Data",
                message="No CSV data available to copy. Please convert a file first."
            ))
            return

        # Check for large data warning with improved thresholds
        num_rows = len(self.processed_df)
        if num_rows > 10000:
            should_continue = await self.main_window.dialog(toga.ConfirmDialog(
                title="Large Dataset Warning",
                message=f"You're about to copy {num_rows:,} rows of CSV data to the clipboard.\n\n"
                       f"This may use significant memory and could slow down your system.\n"
                       f"For large datasets, we recommend using 'Save CSV' instead.\n\n"
                       f"Continue with copying to clipboard?"
            ))
            if not should_continue:
                return
        elif num_rows > 5000:
            should_continue = await self.main_window.dialog(toga.ConfirmDialog(
                title="Copy Large Dataset",
                message=f"Copying {num_rows:,} rows to clipboard may take a moment.\n\nContinue?"
            ))
            if not should_continue:
                return

        try:
            # Generate CSV data from the processed DataFrame
            import io
            csv_buffer = io.StringIO()
            self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
            data_to_copy = csv_buffer.getvalue()

            # Use pyperclip for cross-platform clipboard support
            import pyperclip
            pyperclip.copy(data_to_copy)

            await self.main_window.dialog(toga.InfoDialog(
                title="Success",
                message=f"CSV data successfully copied to clipboard!\n\n"
                       f"📊 {num_rows:,} rows copied\n"
                       f"📋 Ready to paste into Excel, Sheets, or any text editor"
            ))
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Copy Error",
                message=f"Failed to copy to clipboard: {str(e)}"
            ))
    
    async def save_missing_artists_csv(self, widget):
        """Save missing artists as a separate CSV file."""
        try:
            # Check if we have processed data
            if not hasattr(self, 'processed_df') or self.processed_df is None:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="No Data",
                    message="Please convert a CSV file first before saving missing artists."
                ))
                return

            # Find missing artists
            artist_col = 'Artist' if 'Artist' in self.processed_df.columns else 'artist'
            track_col = 'Track' if 'Track' in self.processed_df.columns else 'track'

            # Convert to string and handle missing values safely
            artist_series = self.processed_df[artist_col].fillna('').astype(str)
            track_series = self.processed_df[track_col].fillna('').astype(str)

            missing_mask = (artist_series.str.strip() == '') | \
                          (artist_series == 'Unknown Artist')

            has_track_name = track_series.str.strip() != ''

            final_mask = missing_mask & has_track_name
            missing_df = self.processed_df[final_mask].copy()

            if missing_df.empty:
                await self.main_window.dialog(toga.InfoDialog(
                    title="No Missing Artists",
                    message="All tracks already have artist information!"
                ))
                return

            # Show save dialog
            save_path = await self.main_window.dialog(toga.SaveFileDialog(
                title="Save Missing Artists List",
                suggested_filename=f"missing_artists_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                file_types=["csv"]
            ))

            if save_path:
                # Ensure proper column names
                columns_to_save = ['Artist', 'Track', 'Album', 'Timestamp']
                if all(col in missing_df.columns for col in columns_to_save):
                    missing_df[columns_to_save].to_csv(save_path, index=False, encoding='utf-8')
                else:
                    # Handle case-insensitive column names
                    col_mapping = {}
                    for col in columns_to_save:
                        for df_col in missing_df.columns:
                            if df_col.lower() == col.lower():
                                col_mapping[df_col] = col
                    missing_df = missing_df.rename(columns=col_mapping)
                    missing_df[columns_to_save].to_csv(save_path, index=False, encoding='utf-8')

                await self.main_window.dialog(toga.InfoDialog(
                    title="💾 Missing Artists Saved",
                    message=f"Saved {len(missing_df):,} tracks with missing artists to:\n{Path(save_path).name}\n\n"
                           f"You can now:\n"
                           f"• Use 'Search Missing Artists' to find them automatically\n"
                           f"• Edit the CSV manually and re-import it"
                ))

        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Save Error",
                message=f"Could not save missing artists list: {str(e)}"
            ))

    async def save_results(self, widget):
        """Save results as CSV file like tkinter version."""
        if not hasattr(self, 'processed_df'):
            await self.main_window.dialog(toga.ErrorDialog(
                title="Error",
                message="No data to save. Please process a CSV file first."
            ))
            return

        # Generate smart filename suggestion with source name and timestamp
        source_name = getattr(self, 'source_filename', 'Converted_Data')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Determine file type suffix
        file_type = self.file_type_selection.value if hasattr(self, 'file_type_selection') else 'unknown'
        if file_type == 'play-history':
            suggested_filename = f"{source_name}_Play_History_{timestamp}.csv"
        elif file_type == 'recently-played':
            suggested_filename = f"{source_name}_Recently_Played_{timestamp}.csv"
        else:
            suggested_filename = f"{source_name}_Converted_{timestamp}.csv"

        try:
            save_path = await self.main_window.dialog(toga.SaveFileDialog(
                title="Save CSV File",
                suggested_filename=suggested_filename,
                file_types=["csv"]
            ))

            if save_path:
                try:
                    # Save using UTF-8 with BOM for Excel compatibility like tkinter version
                    self.processed_df.to_csv(
                        save_path,
                        index=False,
                        encoding='utf-8-sig',
                        lineterminator='\n'  # Consistent line endings across platforms
                    )

                    # Update current save path for future auto-saves
                    self.current_save_path = Path(save_path)

                    # Update save status indicator
                    self.update_save_status()

                    # Update search button state (now enabled since saved)
                    self.update_search_button_state()

                    # Get file size and missing artist count
                    try:
                        file_size = os.path.getsize(save_path)
                        file_size_formatted = self.format_file_size(file_size)
                        rows_saved = len(self.processed_df)

                        # Count missing artists for the message
                        missing_count = len(self.processed_df[
                            self.processed_df['Artist'].isna() |
                            (self.processed_df['Artist'] == '')
                        ])

                        message_text = (
                            f"CSV file saved to:\n{Path(save_path).name}\n\n"
                            f"📊 {rows_saved:,} rows • {file_size_formatted}\n\n"
                            f"💾 Future progress will auto-save to this location"
                        )

                        if missing_count > 0:
                            message_text += f"\n\n💡 Tip: Use 'Search for Missing Artists' to find {missing_count:,} missing artists"

                        await self.main_window.dialog(toga.InfoDialog(
                            title="✅ Saved Successfully",
                            message=message_text
                        ))

                        print(f"💾 Saved to: {save_path}")
                        print(f"   Future auto-saves will update this file")
                    except Exception as size_error:
                        # Fallback if we can't get file size
                        await self.main_window.dialog(toga.InfoDialog(
                            title="💾 Saved Successfully",
                            message=f"CSV file saved to:\n{Path(save_path).name}\n\n"
                                   f"💡 Tip: Use 'Search for Missing Artists' to find any missing artist information."
                        ))
                except Exception as e:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Error", 
                        message=f"Failed to save CSV file:\n{str(e)}"
                    ))
        except Exception as e:
            await self.main_window.dialog(toga.ErrorDialog(
                title="Save Error", 
                message=f"Could not open save dialog: {str(e)}"
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
                    
                file_size_formatted = self.format_file_size(file_size)
                print(f"Successfully saved {len(lastfm_df)} rows to {file_path} ({file_size_formatted})")
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

    async def show_missing_artists_dialog(self, missing_count, provider_name, time_estimate):
        """Show custom dialog for missing artists with proper action buttons."""
        import asyncio

        # Create a modal window
        dialog_window = toga.Window(title="Missing Artists Found", size=(500, 300))
        dialog_result = None

        def on_search(widget):
            nonlocal dialog_result
            dialog_result = "search"
            dialog_window.close()

        def on_export(widget):
            nonlocal dialog_result
            dialog_result = "export"
            dialog_window.close()

        def on_cancel(widget):
            nonlocal dialog_result
            dialog_result = "cancel"
            dialog_window.close()

        # Create dialog content
        content_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin=20
            )
        )

        # Message
        message_label = toga.Label(
            f"Found {missing_count:,} tracks without artist information.\n\n"
            f"Search provider: {provider_name}\n"
            f"Estimated time: {time_estimate}",
            style=Pack(
                margin_bottom=20,
                font_size=12
            )
        )
        content_box.add(message_label)

        # Buttons box
        buttons_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_top=10
            )
        )

        # Search button (primary action)
        search_button = toga.Button(
            "Search for Missing Artists",
            on_press=on_search,
            style=Pack(
                margin_bottom=10,
                width=300
            )
        )
        buttons_box.add(search_button)

        # Export button
        export_button = toga.Button(
            "Export Missing Artists List",
            on_press=on_export,
            style=Pack(
                margin_bottom=10,
                width=300
            )
        )
        buttons_box.add(export_button)

        # Cancel button
        cancel_button = toga.Button(
            "Cancel",
            on_press=on_cancel,
            style=Pack(
                width=300
            )
        )
        buttons_box.add(cancel_button)

        content_box.add(buttons_box)
        dialog_window.content = content_box

        # Show dialog and wait for result
        dialog_window.show()

        # Wait for user to make a choice
        while dialog_result is None:
            await asyncio.sleep(0.1)

        return dialog_result

    @trace_call("App.reprocess_missing_artists")
    async def reprocess_missing_artists(self, widget, force_provider=None):
        """Reprocess missing artists using iTunes API with comprehensive error handling."""
        try:
            # Check if this is a resume operation
            is_resume = self.is_search_interrupted and self.active_search_provider is not None

            if is_resume:
                # Resuming interrupted search - skip confirmation
                print(f"📝 Resuming {self.active_search_provider} search...")
            else:
                # New search - show confirmation dialog
                confirm = await self.main_window.dialog(toga.ConfirmDialog(
                    title="Start search?",
                    message="Start searching for missing artists?"
                ))

                if not confirm:
                    return  # User clicked No

            # Check if we have processed data
            if not hasattr(self, 'processed_df') or self.processed_df is None:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="No Data",
                    message="Please convert a CSV file first before searching for missing artists."
                ))
                return

            # REQUIRE SAVE BEFORE SEARCH - user must explicitly save their work
            if not hasattr(self, 'current_save_path') or not self.current_save_path:
                result = await self.main_window.dialog(toga.ConfirmDialog(
                    title="Save Required",
                    message="You need to save your work before searching.\n\n"
                            "This ensures:\n"
                            "• Your progress is protected\n"
                            "• You can resume later if needed\n"
                            "• All progress saves to your chosen file\n\n"
                            "Save now?"
                ))

                if not result:
                    return  # User cancelled

                # Trigger save dialog
                await self.save_results(None)

                # Check if user actually saved (they might have cancelled the save dialog)
                if not hasattr(self, 'current_save_path') or not self.current_save_path:
                    return  # User cancelled save, abort search
            
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

                print(f"DEBUG: Available columns: {list(self.processed_df.columns)}")
                print(f"DEBUG: Using artist column: {artist_col}")
                print(f"DEBUG: Total rows in dataframe: {len(self.processed_df)}")

                if artist_col not in self.processed_df.columns:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Data Format Error",
                        message="Artist column not found in processed data. Please reconvert the file."
                    ))
                    return

                # Count tracks with missing artists from DataFrame (check for empty, None, or 'Unknown Artist')
                # Also exclude tracks with empty track names since they can't be searched
                track_col = 'track' if 'track' in self.processed_df.columns else 'Track'

                # Convert to string and handle missing values safely
                artist_series = self.processed_df[artist_col].fillna('').astype(str)
                track_series = self.processed_df[track_col].fillna('').astype(str)

                missing_mask = (artist_series.str.strip() == '') | \
                              (artist_series == 'Unknown Artist')

                # Additional filter: exclude tracks with empty track names
                has_track_name = track_series.str.strip() != ''

                # Combine filters: missing artist AND has track name
                final_mask = missing_mask & has_track_name

                missing_artists_df = self.processed_df[final_mask]
                # Preserve the original DataFrame index when converting to dict
                missing_artists = missing_artists_df.reset_index().to_dict('records')

                print(f"DEBUG: Missing artists found: {len(missing_artists)}")
                if len(missing_artists) > 0:
                    print(f"DEBUG: First few missing artist entries:")
                    for i, entry in enumerate(missing_artists[:3]):
                        print(f"  {i+1}: {entry}")
                else:
                    print(f"DEBUG: Sample artist values from dataframe:")
                    sample_artists = self.processed_df[artist_col].head(10).tolist()
                    for i, artist in enumerate(sample_artists):
                        is_empty = (pd.isna(artist) or str(artist).strip() == '' or artist == 'Unknown Artist')
                        print(f"  {i+1}: '{artist}' (empty: {is_empty})")
                
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
            
            # Determine provider: check resume first, then force flags, then dropdown
            if is_resume:
                # Resuming interrupted search - use the provider that was running
                current_provider = self.active_search_provider
                self.music_search_service.set_search_provider(current_provider)
                provider_name = "iTunes API" if current_provider == "itunes" else "MusicBrainz"
                print(f"🔄 Resuming {provider_name} search...")
            elif self.force_itunes_next:
                # MusicBrainz completed with remaining artists - force iTunes
                current_provider = "itunes"
                self.music_search_service.set_search_provider("itunes")
                provider_name = "iTunes API"
                self.force_itunes_next = False  # Reset flag after use
                print(f"🔍 Using iTunes for remaining artists after MusicBrainz")
            elif force_provider:
                current_provider = force_provider
                self.music_search_service.set_search_provider(force_provider)
                provider_name = "iTunes API" if force_provider == "itunes" else "MusicBrainz"
                print(f"🔍 Using FORCED search provider: {provider_name}")
            else:
                # Get current provider from the radio button state
                current_provider = self.current_provider
                self.music_search_service.set_search_provider(current_provider)
                provider_name = "iTunes API" if current_provider == "itunes" else "MusicBrainz"
                print(f"🔍 Using search provider: {provider_name}")

            # Check provider-specific prerequisites
            if current_provider == "itunes":
                # Check internet connection for iTunes API
                try:
                    import urllib.request
                    urllib.request.urlopen('https://itunes.apple.com', timeout=10)
                except Exception:
                    await self.main_window.dialog(toga.ErrorDialog(
                        title="Connection Error",
                        message="Cannot connect to iTunes API. Please check your internet connection."
                    ))
                    return
            else:
                # Check MusicBrainz database availability
                if not self.music_search_service.musicbrainz_manager.is_database_available():
                    # Offer options to the user
                    result = await self.main_window.dialog(toga.ConfirmDialog(
                        title="MusicBrainz Database Not Found",
                        message="MusicBrainz database is not available.\n\n"
                                "Options:\n"
                                "1. Download the database (~2GB) using the 'Download DB' button\n"
                                "2. Manually import a downloaded database file\n"
                                "3. Switch to iTunes API search (requires internet)\n\n"
                                "Would you like to switch to iTunes API for now?"
                    ))

                    if result:
                        # Switch to iTunes
                        self.music_search_service.set_search_provider("itunes")
                        self.current_provider = "itunes"
                        # Update radio buttons
                        self.itunes_radio.value = True
                        self.musicbrainz_radio.value = False
                        current_provider = "itunes"
                        provider_name = "iTunes API"
                        print(f"🔍 Switched to: {provider_name}")
                        # Don't return - continue with the search using iTunes
                    else:
                        # User declined to switch, abort
                        return

            # Estimate time based on provider
            if current_provider == "musicbrainz":
                # ULTRA-FAST batch processor: ~20,000 tracks/second (1,200,000/minute)
                # Conservative estimate: 10,000 tracks/second to account for overhead
                estimated_seconds = len(missing_artists) / 10000
                if estimated_seconds < 1:
                    time_display = "< 1 second"
                elif estimated_seconds < 60:
                    time_display = f"{estimated_seconds:.0f} seconds"
                else:
                    estimated_minutes = estimated_seconds / 60
                    time_display = f"{estimated_minutes:.1f} minutes"
            else:
                # iTunes API is slower due to rate limiting (~15 searches per minute)
                estimated_minutes = len(missing_artists) / 15
                time_display = f"{estimated_minutes:.1f} minutes"

            # Show search info in progress area with current provider
            self.update_progress(
                f"🔍 Searching with {provider_name} | {len(missing_artists):,} tracks | Est. {time_display}",
                0
            )

            # Start search immediately (no redundant dialog)
            try:
                # Validate provider-specific requirements
                if current_provider == "itunes":
                    # Only check iTunes API settings when iTunes is selected
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
                    # Track active search provider and clear interrupted flag
                    self.active_search_provider = current_provider
                    self.is_search_interrupted = False

                    self.reprocess_button.enabled = False
                    # Keep current button text (might be "Search Remaining with iTunes")
                    # self.reprocess_button.text = "Search for Missing Artists"  # Don't reset here
                    # self.process_pause_button.enabled = True  # Pause button removed
                    self.process_stop_button.enabled = True
                    # Update stop button text based on provider
                    if current_provider == "itunes":
                        self.process_stop_button.text = "Stop iTunes API"
                    elif current_provider == "musicbrainz":
                        self.process_stop_button.text = "Stop MusicBrainz"
                    else:
                        self.process_stop_button.text = "Stop"
                except AttributeError:
                    # Buttons might not exist yet, handle gracefully
                    print("Control buttons not available")

                # Reset search flags
                self.stop_itunes_search_flag = False
                self.pause_itunes_search_flag = False

                # Start reprocessing thread - PASS PROVIDER to ensure thread uses correct one
                try:
                    self.reprocessing_thread = threading.Thread(
                        target=self.reprocess_missing_artists_thread,
                        args=(missing_artists, current_provider),
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
                        # self.process_pause_button.enabled = False  # Pause button removed
                        self.process_stop_button.enabled = False
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
    
    @trace_call("App.reprocess_missing_artists_thread")
    def reprocess_missing_artists_thread(self, missing_artists_tracks, provider=None):
        """ULTRA-FAST batch search for missing artists using specified provider."""
        import time

        # Initialize timing
        search_start_time = time.time()

        print(f"\n{'='*70}")
        print(f"🚀 ULTRA-FAST MISSING ARTISTS SEARCH")
        print(f"{'='*70}")
        print(f"📊 Total tracks to search: {len(missing_artists_tracks):,}")
        print(f"🕐 Search started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(search_start_time))}")

        try:
            # Validate input
            if not missing_artists_tracks:
                print(f"❌ ERROR: No missing artists to process")
                self.update_results("Error: No missing artists to process.")
                return

            total_tracks = len(missing_artists_tracks)

            # Use provider passed from main thread (ensures correct provider)
            current_provider = provider if provider else self.music_search_service.get_search_provider()
            print(f"🔍 Search provider: {current_provider}")

            if current_provider == "musicbrainz":
                # Check MusicBrainz database status
                mb_manager = self.music_search_service.musicbrainz_manager
                if mb_manager and mb_manager.is_database_available():
                    db_info = mb_manager.get_database_info()
                    print(f"💾 MusicBrainz DB: {db_info.get('size_mb', 0):.1f} MB, {db_info.get('track_count', 0):,} tracks")
                    print(f"📅 Last updated: {db_info.get('last_updated', 'Unknown')}")

                    # Use ULTRA-FAST batch processor!
                    print(f"\n🔥 Using ULTRA-FAST batch processor")
                    self.update_progress(f"🔥 Batch searching {total_tracks:,} tracks in MusicBrainz...", 10)

                    # Convert track data to DataFrame
                    df = pd.DataFrame(missing_artists_tracks)

                    # Rename columns to match what processor expects
                    if 'Track' in df.columns:
                        df['track'] = df['Track']
                    if 'Album' in df.columns:
                        df['album'] = df['Album']

                    # Initialize ultra-fast processor
                    processor = UltraFastCSVProcessor(mb_manager)

                    # Clean and prepare data (add track_clean column)
                    print(f"🧹 Cleaning track names...")
                    # Manually add track_clean since _vectorized_clean expects specific column names
                    df['track_clean'] = (
                        df['track']
                        .fillna('')
                        .astype(str)
                        .str.normalize('NFKC')
                        .str.replace(r'\s*[\(\[].*?[\)\]]', '', regex=True)
                        .str.replace(r'\bfeat(?:\.|uring)?\b.*', '', regex=True, case=False)
                        .str.lower()
                        .str.replace(r'[^\w\s]', '', regex=True)
                        .str.replace(r'\s+', ' ', regex=True)
                        .str.strip()
                    )
                    df['album_clean'] = df['album'].fillna('').astype(str).str.lower().str.strip() if 'album' in df.columns else ''

                    # Batch search with progress callback
                    def progress_cb(message, percent):
                        gui_progress = 10 + int((percent / 100) * 80)  # Map to 10-90%
                        self.update_progress(f"🔥 {message}", gui_progress)

                    # Perform ultra-fast batch search
                    track_to_artist = processor._batch_search(df, progress_cb)

                    # Update DataFrame with found artists
                    print(f"\n{'='*70}")
                    print(f"📝 UPDATING DATAFRAME WITH FOUND ARTISTS")
                    print(f"{'='*70}")

                    found_count = 0
                    for loop_idx, row in df.iterrows():
                        # _batch_search returns Dict[str, str] with track_clean as key
                        track_clean = row.get('track_clean', '')
                        # Get the original DataFrame index from the 'index' column
                        original_idx = row.get('index', loop_idx)

                        if track_clean in track_to_artist:
                            artist = track_to_artist[track_clean]
                            # Update in processed_df (using the ORIGINAL index, not loop index)
                            if hasattr(self, 'processed_df'):
                                self.processed_df.at[original_idx, 'Artist'] = artist
                                self.processed_df.at[original_idx, 'Album Artist'] = artist
                            found_count += 1

                        # Progress update every 10,000 rows
                        if loop_idx > 0 and loop_idx % 10000 == 0:
                            print(f"   Updated {loop_idx:,}/{total_tracks:,} rows...")

                    print(f"✅ Updated {found_count:,} artists in DataFrame")
                    print(f"{'='*70}\n")

                    # Calculate timing
                    elapsed_time = time.time() - search_start_time
                    throughput = total_tracks / elapsed_time if elapsed_time > 0 else 0

                    print(f"\n{'='*70}")
                    print(f"✅ ULTRA-FAST SEARCH COMPLETE")
                    print(f"{'='*70}")
                    print(f"⏱️  Time: {elapsed_time:.1f}s")
                    print(f"📊 Searched: {total_tracks:,} tracks")
                    print(f"✅ Found: {found_count:,} ({found_count/total_tracks*100:.1f}%)")
                    print(f"⚡ Throughput: {throughput:,.0f} tracks/sec")
                    print(f"{'='*70}\n")

                    self.musicbrainz_count = found_count

                    # Auto-save after MusicBrainz search completes
                    if hasattr(self, 'current_save_path') and self.current_save_path:
                        try:
                            self.processed_df.to_csv(
                                self.current_save_path,
                                index=False,
                                encoding='utf-8-sig'
                            )
                            save_msg = f"💾 Auto-saved progress to: {self.current_save_path.name}"
                            print(f"💾 Auto-saved progress after MusicBrainz search to: {self.current_save_path}")
                            self.append_log(save_msg)
                        except Exception as e:
                            error_msg = f"⚠️  Auto-save failed: {e}"
                            print(error_msg)
                            self.append_log(error_msg)

                    # Check for remaining missing artists
                    missing_after_mb = total_tracks - found_count
                    if missing_after_mb > 0:
                        print(f"\n⚠️  {missing_after_mb:,} artists still missing after MusicBrainz")

                        # Set flags SYNCHRONOUSLY before async UI updates
                        # This ensures they're set before the finally block runs
                        self.force_itunes_next = True
                        self.current_provider = "itunes"
                        self.music_search_service.set_search_provider("itunes")
                        print(f"✅ Set force_itunes_next=True and switched provider to iTunes")

                        # Update progress message with results and suggestion
                        self.update_progress(
                            f"✅ MusicBrainz: Found {found_count:,} | Still missing {missing_after_mb:,} | Click 'Search with iTunes' to search remaining",
                            100
                        )

                        # Update missing artist count on Export button
                        self.update_missing_artist_count()

                        # Update UI asynchronously (radio buttons and button text)
                        self._schedule_ui_update(self._switch_to_itunes_ui(missing_after_mb))
                    else:
                        # All artists found
                        self.update_progress(
                            f"✅ MusicBrainz: Found all {found_count:,} artists in {elapsed_time:.1f}s ({throughput:,.0f} tracks/sec)",
                            100
                        )

                        # Update missing artist count on Export button (should be 0)
                        self.update_missing_artist_count()

                    # Refresh the UI table to show updated artists
                    print(f"{'='*70}")
                    print(f"🔄 REFRESHING UI WITH UPDATED DATA")
                    print(f"{'='*70}")
                    print(f"📊 DataFrame shape: {self.processed_df.shape if hasattr(self, 'processed_df') else 'N/A'}")
                    print(f"📊 Artists filled: {self.processed_df['Artist'].notna().sum() if hasattr(self, 'processed_df') else 0:,}")

                    if hasattr(self, 'processed_df') and self.processed_df is not None:
                        print(f"🔄 Calling update_preview() to refresh UI table...")
                        self.update_preview(self.processed_df, len(self.processed_df))
                        print(f"✅ UI table refresh complete!")

                        # Regenerate CSV output for the converted output text box
                        print(f"📝 Regenerating CSV output for text box...")
                        total_rows = len(self.processed_df)
                        display_limit = 1000

                        if total_rows > display_limit:
                            csv_buffer = io.StringIO()
                            self.processed_df.head(display_limit).to_csv(csv_buffer, index=False, lineterminator='\n')
                            csv_string = csv_buffer.getvalue()
                            csv_string += f"\n\n--- Showing first {display_limit:,} of {total_rows:,} rows ---\n"
                            csv_string += "Use 'Save CSV' button to export the complete file.\n"
                        else:
                            csv_buffer = io.StringIO()
                            self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
                            csv_string = csv_buffer.getvalue()

                        self.update_results(csv_string)
                        print(f"✅ CSV text output updated!")
                        print(f"✅ CSV data is ready for Copy to Clipboard / Save CSV")
                    else:
                        print(f"⚠️  Warning: processed_df not available for UI update")

                    print(f"{'='*70}\n")

                else:
                    print(f"❌ MusicBrainz database not available")
                    self.update_progress("❌ MusicBrainz not available", 0)
                    return
            else:
                # iTunes API - row-by-row fallback (slower but works)
                print(f"🌐 Using iTunes API (row-by-row, slower)")
                self.update_progress(f"🌐 Searching {total_tracks:,} tracks with iTunes API...", 10)

                # Clear log for fresh start
                self.update_results("")
                self.append_log(f"Starting iTunes search for {total_tracks:,} tracks...")

                found_artists = 0
                for i, track_data in enumerate(missing_artists_tracks):
                    # Check for cancellation/pause
                    if self.stop_itunes_search_flag:
                        print(f"🛑 Search cancelled by user after {i} searches")
                        break

                    while self.pause_itunes_search_flag and not self.stop_itunes_search_flag:
                        time.sleep(0.1)

                    if self.stop_itunes_search_flag:
                        break

                    # Get the original DataFrame index (preserved from reset_index())
                    original_idx = track_data.get('index', i)

                    # Search iTunes API
                    track_name = track_data.get('Track', track_data.get('track', ''))
                    album_name = track_data.get('Album', track_data.get('album', ''))

                    try:
                        print(f"🔍 Searching iTunes for: '{track_name}' (track {i+1}/{total_tracks})")
                        self.append_log(f"🔍 Searching: {track_name}")

                        # Use synchronous search wrapper
                        search_result = self._sync_search_itunes(track_name, album_name)

                        print(f"   Result: {search_result}")

                        if search_result and search_result.get('success'):
                            artist = search_result.get('artist')
                            if artist:
                                print(f"   ✅ Found artist: {artist} for track: '{track_name}'")
                                self.append_log(f"  ✅ Found: {artist}")
                                # Update in processed_df (using the ORIGINAL index, not loop index)
                                if hasattr(self, 'processed_df'):
                                    self.processed_df.at[original_idx, 'Artist'] = artist
                                    self.processed_df.at[original_idx, 'Album Artist'] = artist
                                found_artists += 1

                                # Save immediately after each successful find
                                if hasattr(self, 'current_save_path') and self.current_save_path:
                                    try:
                                        self.processed_df.to_csv(
                                            self.current_save_path,
                                            index=False,
                                            encoding='utf-8-sig'
                                        )
                                    except Exception as e:
                                        print(f"⚠️  Auto-save failed: {e}")
                        else:
                            print(f"   ❌ No artist found for track: '{track_name}'")
                            self.append_log(f"  ❌ Not found")
                    except Exception as e:
                        print(f"⚠️  iTunes search failed for '{track_name}': {e}")
                        import traceback
                        try:
                            traceback.print_exc()
                        except (BrokenPipeError, OSError):
                            pass  # Ignore broken pipe errors in traceback printing

                    # Update progress every track with live timer and rate limit info
                    elapsed = time.time() - search_start_time
                    elapsed_mins = int(elapsed // 60)
                    elapsed_secs = int(elapsed % 60)
                    time_str = f"{elapsed_mins}m {elapsed_secs}s" if elapsed_mins > 0 else f"{elapsed_secs}s"

                    progress = 10 + int((i / total_tracks) * 80)

                    # Build progress message with rate limit countdown if active
                    progress_msg = f"🌐 iTunes: {i+1:,}/{total_tracks:,} | Found: {found_artists} | {time_str} elapsed"
                    if hasattr(self, 'in_rate_limit_wait') and self.in_rate_limit_wait and hasattr(self, 'rate_limit_remaining'):
                        rate_limit_secs = int(self.rate_limit_remaining)
                        progress_msg += f" | ⏸️  Rate limit: {rate_limit_secs}s"

                    self.update_progress(progress_msg, progress)

                    # Update missing artist count every 10 tracks
                    if i % 10 == 0:
                        self.update_missing_artist_count()

                    # Auto-save checkpoint every 50 tracks
                    if (i + 1) % 50 == 0 and hasattr(self, 'current_save_path') and self.current_save_path:
                        try:
                            self.processed_df.to_csv(
                                self.current_save_path,
                                index=False,
                                encoding='utf-8-sig'
                            )
                            print(f"💾 Auto-saved progress: {i+1}/{total_tracks} tracks")
                        except Exception as e:
                            print(f"⚠️  Auto-save failed: {e}")

                elapsed_time = time.time() - search_start_time
                print(f"\n✅ iTunes API search complete:")
                print(f"   Found: {found_artists}/{total_tracks}")
                print(f"   Time: {elapsed_time:.1f}s")
                self.itunes_found = found_artists
                self.update_progress(
                    f"✅ iTunes: Found {found_artists}/{total_tracks} in {elapsed_time:.1f}s",
                    100
                )

                # Update missing artist count on Export button
                self.update_missing_artist_count()

                # Final auto-save after iTunes search completes
                if hasattr(self, 'current_save_path') and self.current_save_path:
                    try:
                        self.processed_df.to_csv(
                            self.current_save_path,
                            index=False,
                            encoding='utf-8-sig'
                        )
                        print(f"💾 Final auto-save after iTunes search to: {self.current_save_path}")
                    except Exception as e:
                        print(f"⚠️  Final auto-save failed: {e}")

                # Update missing artist count on Export button
                self.update_missing_artist_count()

                # Refresh the UI table to show updated artists
                if hasattr(self, 'processed_df') and self.processed_df is not None:
                    self.update_preview(self.processed_df, len(self.processed_df))

                    # Regenerate CSV output for the converted output text box
                    print(f"📝 Regenerating CSV output for text box...")
                    total_rows = len(self.processed_df)
                    display_limit = 1000

                    if total_rows > display_limit:
                        csv_buffer = io.StringIO()
                        self.processed_df.head(display_limit).to_csv(csv_buffer, index=False, lineterminator='\n')
                        csv_string = csv_buffer.getvalue()
                        csv_string += f"\n\n--- Showing first {display_limit:,} of {total_rows:,} rows ---\n"
                        csv_string += "Use 'Save CSV' button to export the complete file.\n"
                    else:
                        csv_buffer = io.StringIO()
                        self.processed_df.to_csv(csv_buffer, index=False, lineterminator='\n')
                        csv_string = csv_buffer.getvalue()

                    self.update_results(csv_string)
                    print(f"✅ CSV text output updated!")
                    print(f"✅ CSV data is ready for Copy to Clipboard / Save CSV")
        except Exception as e:
            self.update_results(f"Error: Error during artist search: {str(e)}")
            self.update_progress("Error occurred", 0)
        
        finally:
            # Re-enable buttons on main thread
            self._schedule_ui_update(self._reset_reprocess_buttons_ui())
    
    async def _reset_reprocess_buttons_ui(self, widget=None):
        """Reset reprocess button states on main thread."""
        self.reprocess_button.enabled = True

        # Disable Stop button since search is complete
        if hasattr(self, 'process_stop_button'):
            self.process_stop_button.enabled = False

        # Only reset text if search completed successfully AND not forcing iTunes continuation
        if not self.is_search_interrupted and not self.force_itunes_next:
            # Normal completion - reset to provider-specific text
            provider_text = "MusicBrainz" if self.current_provider == "musicbrainz" else "iTunes"
            self.reprocess_button.text = f"Search with {provider_text}"
            self.active_search_provider = None
        # If force_itunes_next is True, button text was already set by _update_search_button_for_itunes
        # If interrupted, keep the current resume text
    
    async def check_database_status(self):
        """Check and update the database status display (async version)."""
        self.update_database_status()
    
    def update_database_status(self):
        """Update the database status display."""
        # Get comprehensive database info through the service
        db_info = self.music_search_service.get_database_info()

        if db_info["exists"]:
            self.download_button.text = "Re-download DB"
            # Format status with comprehensive info as per documentation
            size_mb = db_info.get("size_mb", 0)
            last_updated = db_info.get("last_updated", "Unknown")
            track_count = db_info.get("track_count", 0)

            # Set status with readable formatting
            self.db_status_label.text = "Ready"
            size_bytes = size_mb * 1024 * 1024  # Convert back to bytes for proper formatting
            self.db_size_label.text = f"Size: {self.format_file_size(size_bytes)}"

            # Update database location path
            try:
                db_path = self.music_search_service.get_database_path()
                if db_path:
                    from pathlib import Path
                    path_obj = Path(db_path)
                    self.db_location_label.text = f"Location: {path_obj.parent}"
                else:
                    self.db_location_label.text = "Location: Not set"
            except:
                self.db_location_label.text = "Location: Not set"

            # Format the timestamp for user-friendly display
            formatted_date = self._format_timestamp(last_updated)

            if track_count > 0:
                self.db_tracks_label.text = f"{track_count:,} tracks"
                self.db_updated_label.text = f"Updated: {formatted_date}"
            else:
                self.db_tracks_label.text = ""
                self.db_updated_label.text = f"Updated: {formatted_date}"

            # Auto-select MusicBrainz provider when database is found
            if hasattr(self, 'musicbrainz_radio'):
                self.musicbrainz_radio.value = True
                self.itunes_radio.value = False
                self.current_provider = "musicbrainz"
                self.music_search_service.set_search_provider("musicbrainz")
                # Update search button text if not interrupted
                if hasattr(self, 'reprocess_button') and not self.is_search_interrupted:
                    self.reprocess_button.text = "Search with MusicBrainz"

            # Update optimization status
            if hasattr(self, 'optimization_status_label'):
                is_optimized = self.music_search_service.is_musicbrainz_optimized()
                if is_optimized:
                    self.optimization_status_label.text = "✅ Database optimized"
                    self.optimize_now_button.enabled = False
                else:
                    self.optimization_status_label.text = "⚠️ Database not optimized"
                    self.optimize_now_button.enabled = True
                self.optimization_status_container.style.visibility = "visible"

            # Enable database management buttons when database exists
            if hasattr(self, 'delete_db_button'):
                self.delete_db_button.enabled = True
            if hasattr(self, 'check_updates_button'):
                self.check_updates_button.enabled = True
            if hasattr(self, 'reveal_location_button'):
                self.reveal_location_button.enabled = True
        else:
            self.download_button.text = "Download DB"
            self.db_status_label.text = "Not downloaded"
            self.db_size_label.text = "Size: 0 bytes"
            self.db_location_label.text = "Location: Not set"
            self.db_tracks_label.text = ""
            self.db_updated_label.text = "Never updated"

            # Hide optimization status when no database
            if hasattr(self, 'optimization_status_container'):
                self.optimization_status_container.style.visibility = "hidden"

            # Disable database management buttons when no database
            if hasattr(self, 'delete_db_button'):
                self.delete_db_button.enabled = False
            if hasattr(self, 'check_updates_button'):
                self.check_updates_button.enabled = False
            if hasattr(self, 'reveal_location_button'):
                self.reveal_location_button.enabled = False
    
    def update_musicbrainz_ui_state(self):
        """Update UI state for MusicBrainz provider."""
        # Enable/disable relevant controls
        pass
    
    def update_itunes_ui_state(self):
        """Update UI state for iTunes provider."""
        # Enable/disable relevant controls
        pass
    
    @trace_call("App.delete_database")
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
                # Use service method instead of direct manager access
                self.music_search_service.delete_database()
                
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
        """Reveal the database location in file system (secure subprocess version)."""
        try:
            db_path = self.music_search_service.get_database_path()
            if not db_path or not os.path.exists(db_path):
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Database Not Found",
                    message="Database files not found. Please download the database first."
                ))
                return

            # Convert to Path object for safety and resolve to absolute path
            db_path = Path(db_path).resolve()

            # Platform-specific secure commands (shell=False prevents injection)
            try:
                if sys.platform == "darwin":  # macOS
                    subprocess.run(
                        ["open", "-R", str(db_path)],
                        check=True,
                        shell=False,  # Critical: prevents shell injection
                        timeout=5  # Prevent hanging
                    )
                elif sys.platform == "win32":  # Windows
                    subprocess.run(
                        ["explorer", "/select,", str(db_path)],
                        check=True,
                        shell=False,
                        timeout=5
                    )
                else:  # Linux
                    subprocess.run(
                        ["xdg-open", str(db_path.parent)],
                        check=True,
                        shell=False,
                        timeout=5
                    )
            except subprocess.CalledProcessError as e:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Error Opening Location",
                    message=f"Failed to open file location: {e}"
                ))
            except subprocess.TimeoutExpired:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Timeout",
                    message="File manager took too long to respond."
                ))
        except Exception as e:
            logger.error(f"Error revealing database location: {e}")
            await self.main_window.dialog(toga.ErrorDialog(
                title="Error",
                message=f"Could not open database location: {str(e)}"
            ))

    async def optimize_musicbrainz_handler(self, widget):
        """Handle manual optimization request."""
        try:
            # Check if database exists
            db_info = self.music_search_service.get_database_info()
            if not db_info["exists"]:
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Database Not Found",
                    message="Please download the MusicBrainz database first."
                ))
                return

            # Disable buttons during optimization
            self.optimize_now_button.enabled = False
            if hasattr(self, 'reprocess_button'):
                self.reprocess_button.enabled = False
            self.optimization_status_label.text = "⏳ Starting optimization..."

            # Start optimization with modal
            # Note: ensure_musicbrainz_ready uses self._parent_window internally
            try:
                success = await self.music_search_service.ensure_musicbrainz_ready()

                if success:
                    # Update UI to reflect optimized state
                    self.optimization_status_label.text = "✅ Database optimized"
                    self.optimize_now_button.enabled = False
                    # Re-enable reprocess button if it was disabled
                    if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0:
                        self.reprocess_button.enabled = True

                    await self.main_window.dialog(toga.InfoDialog(
                        title="Optimization Complete",
                        message="MusicBrainz database has been optimized successfully."
                    ))
                else:
                    # Optimization failed or cancelled
                    # Check if it was cancelled by user
                    is_optimized = self.music_search_service.is_musicbrainz_optimized()
                    if not is_optimized:
                        self.optimization_status_label.text = "⚠️ Database not optimized"
                        self.optimize_now_button.enabled = True
                        # Re-enable reprocess button if we have data
                        if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0:
                            self.reprocess_button.enabled = True
                    else:
                        # Should not happen but handle gracefully
                        self.optimization_status_label.text = "✅ Database optimized"
                        self.optimize_now_button.enabled = False
                        if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0:
                            self.reprocess_button.enabled = True
            except Exception as e:
                # Check if it was a user cancellation
                if "cancelled by user" in str(e).lower():
                    logger.info("Optimization cancelled by user")
                    self.optimization_status_label.text = "⚠️ Optimization cancelled"
                    self.optimize_now_button.enabled = True
                    # Re-enable reprocess button if we have data
                    if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0:
                        self.reprocess_button.enabled = True
                    # Don't show error dialog for user cancellation
                    return
                else:
                    # Re-enable buttons on error
                    self.optimization_status_label.text = "❌ Optimization failed"
                    self.optimize_now_button.enabled = True
                    if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None and len(self.processed_df) > 0:
                        self.reprocess_button.enabled = True
                    logger.error(f"Optimization failed: {e}")
                    raise

        except Exception as e:
            # Only show error dialog for non-cancellation errors
            if "cancelled by user" not in str(e).lower():
                logger.error(f"Optimization error: {e}")
                await self.main_window.dialog(toga.ErrorDialog(
                    title="Optimization Error",
                    message=f"Error during optimization: {str(e)}"
                ))

    def on_fallback_changed(self, widget):
        """Handle auto-fallback switch change."""
        self.music_search_service.set_auto_fallback(widget.value)
    
    def on_itunes_api_changed(self, widget):
        """Handle iTunes API switch change."""
        # Update time estimates when iTunes API setting changes
        self.update_time_estimate()
        
    def on_adaptive_rate_limit_changed(self, widget):
        """Handle adaptive rate limit toggle."""
        enabled = widget.value
        if hasattr(self, 'music_search_service'):
            self.music_search_service.settings["use_adaptive_rate_limit"] = enabled
            self.music_search_service.save_settings()

            if enabled:
                discovered = self.music_search_service.settings.get("discovered_rate_limit", None)
                if discovered:
                    safety_margin = self.music_search_service.settings.get("rate_limit_safety_margin", 0.8)
                    effective = int(discovered * safety_margin)
                    self.append_log(f"✅ Adaptive rate limiting enabled (using discovered limit: {effective} req/min)")
                else:
                    self.append_log(f"✅ Adaptive rate limiting enabled (discovery mode: 600 req/min until first rate limit)")

                # Update discovered limit label
                if hasattr(self, 'discovered_limit_label'):
                    if discovered:
                        safety_margin = self.music_search_service.settings.get("rate_limit_safety_margin", 0.8)
                        effective = int(discovered * safety_margin)
                        self.discovered_limit_label.text = f"Discovered: {discovered} req/min (using {effective})"
                    else:
                        self.discovered_limit_label.text = "Discovery mode: Using 600 req/min until first rate limit (~10 req/sec)"
            else:
                manual_limit = self.music_search_service.settings.get("itunes_rate_limit", 20)
                self.append_log(f"❌ Adaptive rate limiting disabled (using manual limit: {manual_limit} req/min)")

                # Update discovered limit label
                if hasattr(self, 'discovered_limit_label'):
                    self.discovered_limit_label.text = "Discovered: None yet (adaptive mode off)"

    def on_parallel_mode_changed(self, widget):
        """Handle parallel mode toggle."""
        enabled = widget.value
        if hasattr(self, 'music_search_service'):
            self.music_search_service.settings["use_parallel_requests"] = enabled
            self.music_search_service.save_settings()

            workers = self.music_search_service.settings.get("parallel_workers", 10)
            if enabled:
                self.append_log(f"✅ Parallel mode enabled ({workers} workers) - faster but more aggressive on API")
            else:
                self.append_log(f"❌ Parallel mode disabled - using sequential requests (safer)")

    def save_rate_limit(self, widget):
        """Save the rate limit setting."""
        try:
            # Parse and validate the rate limit value
            new_rate_limit = int(self.rate_limit_input.value)
            if new_rate_limit <= 0:
                self.append_log("❌ Rate limit must be greater than 0")
                return

            # Update the music search service settings
            if hasattr(self, 'music_search_service'):
                old_rate_limit = self.music_search_service.settings.get("itunes_rate_limit", 20)
                self.music_search_service.settings["itunes_rate_limit"] = new_rate_limit
                self.music_search_service.save_settings()

                # Update current rate label
                if hasattr(self, 'current_rate_label'):
                    self.current_rate_label.text = f"Current: {new_rate_limit} req/min"

                # Check if adaptive mode is enabled
                use_adaptive = self.music_search_service.settings.get("use_adaptive_rate_limit", True)
                adaptive_note = " (only used if adaptive mode is off)" if use_adaptive else ""

                # Show feedback about when the change takes effect
                if hasattr(self, 'in_rate_limit_wait') and self.in_rate_limit_wait:
                    # Currently in a rate limit wait - will apply after current wait
                    self.append_log(f"✅ Rate limit changed from {old_rate_limit} to {new_rate_limit} req/min{adaptive_note} (applies after current wait)")
                elif hasattr(self, 'active_search_provider') and self.active_search_provider == "itunes":
                    # iTunes search is active - will apply on next rate limit check
                    self.append_log(f"✅ Rate limit changed from {old_rate_limit} to {new_rate_limit} req/min{adaptive_note} (applies on next rate limit check)")
                else:
                    # No active search - will apply to next search
                    self.append_log(f"✅ Rate limit saved: {new_rate_limit} req/min{adaptive_note}")
        except ValueError:
            self.append_log("❌ Invalid rate limit value - must be a number")

        # Update time estimates when rate limit changes
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
            self.update_progress(" Processing resumed...", self.progress_bar.value)
    
    def stop_process(self, widget):
        """Stop the entire processing."""
        self.stop_itunes_search_flag = True
        if hasattr(self, 'process_stopped'):
            self.process_stopped = True

        # Mark search as interrupted
        self.is_search_interrupted = True

        # Stop any ongoing rate limit wait
        if hasattr(self, 'in_rate_limit_wait') and self.in_rate_limit_wait:
            self.skip_wait_requested = True
            print(f"⏹️ Stopping active rate limit wait...")

        # Auto-save current progress when stopped
        saved_path = None
        if hasattr(self, 'current_save_path') and self.current_save_path and hasattr(self, 'processed_df'):
            try:
                self.processed_df.to_csv(
                    self.current_save_path,
                    index=False,
                    encoding='utf-8-sig'
                )
                saved_path = self.current_save_path.name
                print(f"💾 Auto-saved progress to: {self.current_save_path}")
                self.append_log(f"💾 Auto-saved to: {saved_path}")
            except Exception as e:
                print(f"⚠️  Auto-save failed: {e}")

        # Disable control buttons
        # self.process_pause_button.enabled = False  # Pause button removed
        self.process_stop_button.enabled = False

        # Re-enable search button with appropriate resume text based on what was running
        if hasattr(self, 'reprocess_button') and hasattr(self, 'processed_df') and self.processed_df is not None:
            self.reprocess_button.enabled = True

            # Set resume text based on what was interrupted
            if self.active_search_provider == "itunes":
                # iTunes search was interrupted
                self.reprocess_button.text = "Resume iTunes Search"
            elif self.active_search_provider == "musicbrainz":
                # MusicBrainz search was interrupted
                self.reprocess_button.text = "Resume MusicBrainz Search"
            else:
                # Fallback for unknown state
                self.reprocess_button.text = f"Resume Search with {self.current_provider.title()}"

        # Update progress with save info
        if saved_path:
            self.update_progress(f"⏹️ Stopped | Auto-saved to: {saved_path}", 0)
        else:
            self.update_progress("⏹️ Stopped", 0)
    
    def skip_current_wait(self, widget):
        """Skip the current API rate limit wait."""
        print(f"🚀 Skip button clicked - setting skip_wait_requested flag")
        self.skip_wait_requested = True

        # The actual queue clearing happens in on_rate_limit_wait when skip is detected
        # This ensures the wait loop actually exits immediately

        # Append to log
        self.append_log(f"🚀 Skipping current wait - next request will wait full 60s...")
    
    def update_time_estimate(self):
        """Update processing time estimates based on file and settings like tkinter version."""
        if not hasattr(self, 'row_count') or not self.row_count:
            return
            
        try:
            # Get current settings
            itunes_enabled = getattr(self, 'itunes_api_switch', None)
            itunes_enabled = itunes_enabled.value if itunes_enabled else False
            rate_limit = int(self.rate_limit_input.value) if hasattr(self, 'rate_limit_input') else 20
            
            # Use actual missing artists count like tkinter version
            if hasattr(self, 'estimated_missing_artists'):
                # Use pre-calculated estimate from file analysis
                estimated_missing = self.estimated_missing_artists
            else:
                # Fallback to counting if not already calculated
                estimated_missing = self.count_missing_artists()
            
            if itunes_enabled and estimated_missing > 0:
                # Calculate time based on rate limit like tkinter version
                total_minutes = estimated_missing / rate_limit
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                seconds = int((total_minutes * 60) % 60)
                
                if hours > 0:
                    time_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
                
                estimate_text = f"Estimated time: {time_str} for {estimated_missing} missing artists"
                
                # Show warning if rate limit > 20 like tkinter version
                if hasattr(self, 'rate_limit_warning'):
                    if rate_limit > 20:
                        # self.rate_limit_warning.style.color = "e74c3c"  # Red
                        self.rate_limit_warning.text = "Warning: Rate limits above 20/minute may cause API errors"
                    else:
                        # self.rate_limit_warning.style.color = "27ae60"  # Green
                        self.rate_limit_warning.text = " Rate limit within safe range"
                    
                if hasattr(self, 'api_status_label'):
                    self.api_status_label.text = estimate_text
            else:
                if hasattr(self, 'api_status_label'):
                    self.api_status_label.text = "Status: Ready"
                if hasattr(self, 'rate_limit_warning'):
                    self.rate_limit_warning.text = ""
                
        except ValueError:
            if hasattr(self, 'api_status_label'):
                self.api_status_label.text = "Please enter a valid rate limit"
        except Exception as e:
            print(f"Error updating time estimate: {e}")
            if hasattr(self, 'api_status_label'):
                self.api_status_label.text = "Could not calculate time estimate"
    
    def update_stats_display(self):
        """Update the statistics display with current counts and proper icons."""
        # Update track count
        # if hasattr(self, 'songs_processed_label'):  # Stats removed
        #     processed = getattr(self, 'musicbrainz_found', 0) + getattr(self, 'itunes_found', 0)
        #     total = getattr(self, 'row_count', 0)
        #     # self.songs_processed_label.text = f"📊 Tracks: {processed:,}/{total:,}"  # Stats removed

        # Update search provider counters
        # if hasattr(self, 'musicbrainz_stats_label'):  # Stats removed
        #     # self.musicbrainz_stats_label.text = f"MusicBrainz: {self.musicbrainz_found:,}"  # Stats removed
        pass

        # if hasattr(self, 'itunes_stats_label'):  # Stats removed
        #     # self.itunes_stats_label.text = f"iTunes: {self.itunes_found:,}"  # Stats removed

        # Update rate limiting warning (only show when rate limit hits occur)
        rate_limit_count = getattr(self, 'rate_limit_hits', 0)
        if hasattr(self, 'rate_limit_warning_label'):
            if rate_limit_count > 0:
                self.rate_limit_warning_label.text = f"⚠️ Rate limit warnings: {rate_limit_count}"
            else:
                self.rate_limit_warning_label.text = ""
    
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
            
            # Update detailed stats with file info
            file_size_formatted = self.format_file_size(file_size)
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = f"📄 File: {file_size_formatted} • Estimated RAM: {estimated_ram_mb:.0f}MB"

            # Show warning if RAM might be insufficient
            if estimated_ram_mb > available_ram_mb * 0.8:  # 80% threshold
                if hasattr(self, 'rate_limit_warning_label'):
                    self.rate_limit_warning_label.text = f"⚠️ Large file: May require {estimated_ram_mb:.0f}MB RAM (Available: {available_ram_mb:.0f}MB)"
            else:
                if hasattr(self, 'rate_limit_warning_label'):
                    self.rate_limit_warning_label.text = ""

            return True

        except Exception as e:
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = "📄 Could not analyze file"
            if hasattr(self, 'rate_limit_warning_label'):
                self.rate_limit_warning_label.text = f"⚠️ File analysis error: {str(e)}"
            return False
    
    def has_missing_artist(self, row, headers):
        """Estimate if a row has missing artist information like tkinter version."""
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

    def count_missing_artists(self):
        """Count how many rows are missing artist information like tkinter version."""
        try:
            if not hasattr(self, 'current_file_path') or not self.current_file_path:
                return 0
                
            # Read CSV with proper settings to handle mixed types
            df = pd.read_csv(self.current_file_path, 
                           low_memory=False,
                           dtype=str,  # Read all columns as strings
                           na_values=['', 'nan', 'NaN', 'null', None],
                           keep_default_na=True)
            
            file_type = self.file_type_selection.value if hasattr(self, 'file_type_selection') else 'auto-detect'
            missing_count = 0
            
            # First check what columns we actually have
            columns = set(df.columns)
            
            if 'play-activity' in file_type.lower():
                # For play activity, check if we have a song but missing artist info
                if 'Song Name' in columns and 'Artist Name' in columns:
                    # Has both columns, check for actual missing artists
                    # Convert to string and handle missing values safely
                    artist_name_series = df['Artist Name'].fillna('').astype(str)
                    missing_mask = (
                        df['Song Name'].notna() &
                        ((artist_name_series.str.strip() == '') |
                         artist_name_series.str.lower().isin(['unknown', 'various']))
                    )
                    missing_count = missing_mask.sum()
            elif 'recently-played' in file_type.lower():
                # For recently played tracks
                if 'Track Description' in columns:
                    # Check for missing or blank track descriptions (which contain artist info)
                    # Convert to string and handle missing values safely
                    track_desc_series = df['Track Description'].fillna('').astype(str)
                    missing_mask = track_desc_series.str.strip() == ''
                    missing_count = missing_mask.sum()
            else:
                # For generic CSV, try to detect artist columns
                artist_cols = [col for col in df.columns if any(term in col.lower() for term in ['artist', 'performer', 'musician'])]
                if artist_cols:
                    artist_col = artist_cols[0]
                    # Convert to string and handle missing values safely
                    artist_series = df[artist_col].fillna('').astype(str)
                    missing_mask = (
                        (artist_series.str.strip() == '') |
                        artist_series.str.lower().isin(['unknown', 'various'])
                    )
                    missing_count = missing_mask.sum()
                else:
                    # No artist column found, assume all are missing
                    missing_count = len(df)
            
            return int(missing_count)
            
        except Exception as e:
            print(f"Error counting missing artists: {e}")
            return 0

    def analyze_file_comprehensive(self, file_path):
        """Analyze file comprehensively like tkinter version - size, rows, missing artists."""
        try:
            # Get file size in bytes
            self.file_size = os.path.getsize(file_path)  # Keep in bytes for proper formatting
            
            # Get row count and estimate missing artists
            missing_artists = 0
            row_count = 0
            
            # Try different encodings to read the file
            encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        import csv
                        reader = csv.reader(file)
                        headers = next(reader)  # First row is headers
                        
                        # Count rows and missing artists (sample first 1000 for large files)
                        for i, row in enumerate(reader):
                            row_count = i + 1
                            if i < 1000:  # Sample first 1000 rows
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
            
            # Update comprehensive file information like tkinter version
            file_size_formatted = self.format_file_size(self.file_size)
            file_info = f"📄 {self.row_count:,} tracks • {file_size_formatted} • ~{missing_artists:,} missing artists"
            if hasattr(self, 'detailed_stats_label'):
                self.detailed_stats_label.text = file_info
            
            return True
            
        except Exception as e:
            print(f"Error in comprehensive file analysis: {e}")
            return False
    
    def start_background_optimization(self):
        """Start MusicBrainz optimization in background if database is available."""
        if (self.music_search_service.get_search_provider() == "musicbrainz" and 
            self.music_search_service.musicbrainz_manager.is_database_available()):
            
            # Show optimization status
            self.progress_label.text = " Optimizing MusicBrainz for faster searches..."
            
            def progress_callback(message, percent, start_time):
                elapsed = time.time() - start_time
                timer_text = f" (Elapsed: {elapsed:.0f}s)"
                # Schedule UI update
                self._schedule_ui_update(self._update_optimization_progress(f"🔧 Optimizing: {message}{timer_text}"))
            
            def completion_callback():
                # Schedule UI update
                self._schedule_ui_update(self._update_optimization_complete())
            
            # Start progressive loading in background
            def optimize():
                try:
                    self.music_search_service.start_progressive_loading(progress_callback)
                    completion_callback()
                except Exception as e:
                    print(f"Optimization error: {e}")
                    self._schedule_ui_update(self._update_optimization_error())
            
            # Use async task instead of threading for UI safety
            asyncio.create_task(self.optimize_musicbrainz_async())
    
    async def _update_optimization_progress(self, message):
        """Update optimization progress on main thread."""
        self.progress_label.text = message
    
    async def _update_optimization_complete(self):
        """Update UI when optimization is complete."""
        self.progress_label.text = " Ready to convert your Apple Music files (MusicBrainz optimized)"
    
    async def _update_optimization_error(self):
        """Update UI when optimization fails."""
        self.progress_label.text = " Ready to convert your Apple Music files"
    
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
