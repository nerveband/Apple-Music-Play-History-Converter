#!/usr/bin/env python3
"""
Database management dialogs for MusicBrainz integration - Toga version.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
import threading
import time
import os
import asyncio


class FirstTimeSetupDialog:
    """Dialog shown when MusicBrainz database is not available."""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.choice = None
        self.dialog_window = None

    async def show_and_wait(self):
        """Show dialog and wait for user choice."""
        # Create dialog content
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20,
                alignment=CENTER
            )
        )

        # Title
        title_label = toga.Label(
            "🎵 Music Search Setup",
            style=Pack(
                font_size=16,
                font_weight="bold",
                padding_bottom=15,
                text_align=CENTER
            )
        )
        main_box.add(title_label)

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

        desc_label = toga.Label(
            desc_text,
            style=Pack(
                padding_bottom=25,
                text_align=CENTER,
                font_size=11
            )
        )
        main_box.add(desc_label)

        # Buttons container
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
                padding=5,
                alignment=CENTER
            )
        )

        # Download button
        download_btn = toga.Button(
            "📥 Download MusicBrainz (~2GB)",
            on_press=self.choose_download,
            style=Pack(padding_right=10, width=220)
        )
        button_box.add(download_btn)

        # iTunes button
        itunes_btn = toga.Button(
            "🌐 Use iTunes API",
            on_press=self.choose_itunes,
            style=Pack(padding_right=10, width=180)
        )
        button_box.add(itunes_btn)

        # Manual import button
        manual_btn = toga.Button(
            "📁 Manual Import",
            on_press=self.choose_manual,
            style=Pack(width=160)
        )
        button_box.add(manual_btn)

        main_box.add(button_box)

        # Create dialog window
        self.dialog_window = toga.Window(
            title="MusicBrainz Setup",
            size=(600, 500),
            resizable=False,
            on_close=self.on_close
        )
        self.dialog_window.content = main_box
        self.dialog_window.show()

        # Wait for user choice
        while self.choice is None:
            await asyncio.sleep(0.1)

        return self.choice

    def choose_download(self, widget):
        """User chose to download database."""
        self.choice = "download"
        if self.dialog_window:
            self.dialog_window.close()

    def choose_itunes(self, widget):
        """User chose iTunes API."""
        self.choice = "itunes"
        if self.dialog_window:
            self.dialog_window.close()

    def choose_manual(self, widget):
        """User chose manual import."""
        self.choice = "manual"
        if self.dialog_window:
            self.dialog_window.close()

    def on_close(self, widget):
        """User cancelled."""
        self.choice = "cancel"
        return True


class DatabaseDownloadDialog:
    """Dialog for downloading MusicBrainz database with progress."""

    def __init__(self, parent_window, music_search_service, on_complete_callback=None):
        self.parent_window = parent_window
        self.music_search_service = music_search_service
        self.on_complete_callback = on_complete_callback
        self.dialog_window = None
        self.cancelled = False
        self.download_thread = None
        self.start_time = None
        self.download_url = None
        self.last_downloaded = 0
        self.last_time = None
        self.last_speed_update = None
        self.speed_samples = []
        self.speed_update_interval = 1.5

        # UI elements
        self.status_label = None
        self.progress_bar = None
        self.progress_label = None
        self.elapsed_label = None
        self.speed_label = None
        self.url_input = None
        self.copy_url_button = None
        self.cancel_button = None

    async def show(self):
        """Show the download dialog."""
        # Create dialog content
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20,
                alignment=CENTER
            )
        )

        # Title
        title_label = toga.Label(
            "Downloading MusicBrainz Database",
            style=Pack(
                font_size=12,
                font_weight="bold",
                padding_bottom=10,
                text_align=CENTER
            )
        )
        main_box.add(title_label)

        # Warning about file size
        warning_label = toga.Label(
            "⚠️ This will download approximately 2GB of data",
            style=Pack(padding_bottom=5, text_align=CENTER)
        )
        main_box.add(warning_label)

        # System requirements warning
        req_label = toga.Label(
            "💾 System Requirements: 8GB RAM recommended (6GB minimum)",
            style=Pack(
                padding_bottom=10,
                text_align=CENTER,
                font_weight="bold"
            )
        )
        main_box.add(req_label)

        # Status label
        self.status_label = toga.Label(
            "Preparing download...",
            style=Pack(padding_bottom=10, text_align=CENTER)
        )
        main_box.add(self.status_label)

        # Progress bar
        self.progress_bar = toga.ProgressBar(
            max=100,
            value=0,
            style=Pack(width=400, padding_bottom=10)
        )
        main_box.add(self.progress_bar)

        # Progress text
        self.progress_label = toga.Label(
            "0%",
            style=Pack(padding_bottom=10, text_align=CENTER)
        )
        main_box.add(self.progress_label)

        # Download details frame
        details_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=10,
                alignment=CENTER
            )
        )

        # URL display
        url_label = toga.Label(
            "Source URL:",
            style=Pack(padding_bottom=5, font_weight="bold")
        )
        details_box.add(url_label)

        self.url_input = toga.TextInput(
            readonly=True,
            style=Pack(width=500, padding_bottom=5)
        )
        details_box.add(self.url_input)

        # URL buttons
        url_button_box = toga.Box(
            style=Pack(direction=ROW, padding_bottom=5)
        )

        self.copy_url_button = toga.Button(
            "Copy URL",
            on_press=self.copy_url,
            enabled=False,
            style=Pack(padding_right=5)
        )
        url_button_box.add(self.copy_url_button)

        details_box.add(url_button_box)

        # Statistics
        stats_box = toga.Box(
            style=Pack(direction=ROW, padding_top=5)
        )

        self.elapsed_label = toga.Label(
            "Elapsed: 0s",
            style=Pack(padding_right=20)
        )
        stats_box.add(self.elapsed_label)

        self.speed_label = toga.Label(
            "Speed: 0 MB/s",
            style=Pack()
        )
        stats_box.add(self.speed_label)

        details_box.add(stats_box)
        main_box.add(details_box)

        # Cancel button
        self.cancel_button = toga.Button(
            "Cancel",
            on_press=self.cancel,
            style=Pack(padding_top=10)
        )
        main_box.add(self.cancel_button)

        # Create dialog window
        self.dialog_window = toga.Window(
            title="Downloading MusicBrainz Database",
            size=(600, 500),
            resizable=False,
            on_close=self.cancel
        )
        self.dialog_window.content = main_box
        self.dialog_window.show()

        # Start download
        self.start_download()

    def start_download(self):
        """Start the download in a separate thread."""
        self.start_time = time.time()
        self.last_time = self.start_time
        self.download_thread = threading.Thread(target=self.download_worker, daemon=True)
        self.download_thread.start()

    def copy_url(self, widget):
        """Copy the download URL to clipboard."""
        if self.download_url:
            # Use Toga's clipboard API (cross-platform)
            import pyperclip
            pyperclip.copy(self.download_url)
            self.copy_url_button.text = "Copied!"
            self.copy_url_button.enabled = False
            # Re-enable after 2 seconds
            threading.Timer(2.0, lambda: self._reset_copy_button()).start()

    def _reset_copy_button(self):
        """Reset the copy button."""
        if self.copy_url_button:
            self.copy_url_button.text = "Copy URL"
            self.copy_url_button.enabled = True

    def download_worker(self):
        """Worker thread for downloading."""
        try:
            # Create progress callback
            def progress_callback(message, progress, extra_data=None):
                if not self.cancelled:
                    asyncio.run_coroutine_threadsafe(
                        self.update_status(message, progress, extra_data),
                        asyncio.get_event_loop()
                    )

            # Perform actual download
            success = self.music_search_service.download_database(progress_callback)

            if success and not self.cancelled:
                asyncio.run_coroutine_threadsafe(
                    self.download_complete(),
                    asyncio.get_event_loop()
                )
            elif not self.cancelled:
                asyncio.run_coroutine_threadsafe(
                    self.download_error("Download failed"),
                    asyncio.get_event_loop()
                )

        except Exception as e:
            if not self.cancelled:
                asyncio.run_coroutine_threadsafe(
                    self.download_error(str(e)),
                    asyncio.get_event_loop()
                )

    async def update_status(self, message, progress, extra_data=None):
        """Update status message and progress."""
        if self.cancelled or not self.dialog_window:
            return

        self.status_label.text = message

        # Handle URL from extra_data
        if extra_data and "url" in extra_data:
            self.download_url = extra_data["url"]
            self.url_input.value = self.download_url
            self.copy_url_button.enabled = True

        # Update progress
        try:
            progress_num = float(progress) if progress is not None else 0
        except (ValueError, TypeError):
            progress_num = 0

        self.progress_bar.value = progress_num

        # Calculate elapsed time and speed
        current_time = time.time()
        if self.start_time:
            elapsed = current_time - self.start_time
            elapsed_text = f"Elapsed: {int(elapsed//60):02d}:{int(elapsed%60):02d}"
            self.elapsed_label.text = elapsed_text

            # Calculate download speed
            if "MB downloaded" in message:
                try:
                    import re
                    mb_match = re.search(r'(\d+(?:\.\d+)?)\s*MB', message)
                    if mb_match:
                        current_mb = float(mb_match.group(1))

                        if self.last_speed_update is None:
                            self.last_speed_update = current_time
                            self.last_downloaded = current_mb
                            self.speed_label.text = "Speed: Calculating..."
                            return

                        time_since_last_update = current_time - self.last_speed_update
                        if time_since_last_update >= self.speed_update_interval:
                            mb_diff = current_mb - self.last_downloaded
                            current_speed = mb_diff / time_since_last_update

                            self.speed_samples.append(current_speed)
                            if len(self.speed_samples) > 3:
                                self.speed_samples.pop(0)

                            avg_speed = sum(self.speed_samples) / len(self.speed_samples)

                            if avg_speed > 0:
                                self.speed_label.text = f"Speed: {avg_speed:.1f} MB/s"

                            self.last_speed_update = current_time
                            self.last_downloaded = current_mb
                except Exception:
                    pass
            elif "Extracting" in message or "Decompressing" in message:
                self.speed_label.text = "Speed: N/A"

        # Update progress label
        if progress_num > 0:
            progress_text = f"{progress_num:.1f}%"

            if "MB" in message:
                try:
                    import re
                    mb_match = re.search(r'(\d+(?:\.\d+)?)\s*MB', message)
                    if mb_match:
                        mb_downloaded = float(mb_match.group(1))
                        total_mb = mb_downloaded / (progress_num / 100) if progress_num > 0 else 2048
                        progress_text = f"{progress_num:.1f}% • {mb_downloaded:.0f} MB / {total_mb:.0f} MB"
                except:
                    pass

            self.progress_label.text = progress_text
        else:
            self.progress_label.text = "Starting..."

    async def download_complete(self):
        """Handle successful download completion."""
        if self.cancelled or not self.dialog_window:
            return

        await self.parent_window.dialog(toga.InfoDialog(
            title="Download Complete",
            message="MusicBrainz database downloaded successfully!"
        ))

        if self.dialog_window:
            self.dialog_window.close()

        # Call the completion callback
        if self.on_complete_callback:
            try:
                self.on_complete_callback()
            except Exception as e:
                print(f"Error calling download completion callback: {e}")

    async def download_error(self, error_message):
        """Handle download error."""
        if self.cancelled or not self.dialog_window:
            return

        await self.parent_window.dialog(toga.ErrorDialog(
            title="Download Error",
            message=f"Failed to download database:\n{error_message}"
        ))

        if self.dialog_window:
            self.dialog_window.close()

    def cancel(self, widget=None):
        """Cancel the download."""
        self.cancelled = True
        if self.music_search_service:
            self.music_search_service.cancel_download()

        if self.dialog_window:
            self.dialog_window.close()

        return True

    def is_cancelled(self):
        """Check if download was cancelled."""
        return self.cancelled


class ManualImportDialog:
    """Dialog for manual database import with instructions."""

    def __init__(self, parent_window, music_search_service):
        self.parent_window = parent_window
        self.music_search_service = music_search_service
        self.dialog_window = None
        self.success = False
        self.status_label = None
        self.progress_bar = None

    async def show_and_wait(self):
        """Show dialog and wait for user action."""
        # Create dialog content
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20,
                alignment=CENTER
            )
        )

        # Title
        title_label = toga.Label(
            "Manual Database Import",
            style=Pack(
                font_size=14,
                font_weight="bold",
                padding_bottom=10,
                text_align=CENTER
            )
        )
        main_box.add(title_label)

        # Instructions
        instructions_text = """To manually download and import the MusicBrainz database:

1. Visit: https://musicbrainz.org/doc/MusicBrainz_Database/Download

2. Look for the latest "mb_artist_credit_name" dump file
   (Named like: mb_artist_credit_name-20241124-235959.tar.zst)

3. Download this file (approximately 2GB)

4. Click "Import File" below to select the downloaded file

Note: The file must be a .tar.zst file containing the MusicBrainz
artist data. Import may take several minutes."""

        inst_label = toga.Label(
            instructions_text,
            style=Pack(
                padding_bottom=20,
                text_align=CENTER
            )
        )
        main_box.add(inst_label)

        # Status display
        status_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=10,
                alignment=CENTER
            )
        )

        self.status_label = toga.Label(
            "No file selected",
            style=Pack(padding_bottom=10, text_align=CENTER)
        )
        status_box.add(self.status_label)

        self.progress_bar = toga.ProgressBar(
            style=Pack(width=400)
        )
        status_box.add(self.progress_bar)

        main_box.add(status_box)

        # Buttons
        button_box = toga.Box(
            style=Pack(direction=ROW, padding_top=20)
        )

        import_btn = toga.Button(
            "Import File",
            on_press=self.import_file,
            style=Pack(padding_right=10)
        )
        button_box.add(import_btn)

        close_btn = toga.Button(
            "Close",
            on_press=self.close,
            style=Pack()
        )
        button_box.add(close_btn)

        main_box.add(button_box)

        # Create dialog window
        self.dialog_window = toga.Window(
            title="Manual Database Import",
            size=(600, 500),
            resizable=False,
            on_close=self.close
        )
        self.dialog_window.content = main_box
        self.dialog_window.show()

        # Wait for dialog to close
        while self.dialog_window and not self.dialog_window._closed:
            await asyncio.sleep(0.1)

        return self.success

    async def import_file(self, widget):
        """Handle file import."""
        try:
            # Use Toga's file dialog
            file_path = await self.parent_window.dialog(
                toga.OpenFileDialog(
                    title="Select MusicBrainz Database File (.tar.zst or .tar)",
                    file_types=['tar.zst', 'tar']
                )
            )
        except Exception as e:
            print(f"File dialog error: {e}")
            await self.parent_window.dialog(toga.ErrorDialog(
                title="Error",
                message="Could not open file dialog. Please check your system configuration."
            ))
            return

        if not file_path:
            return

        # Validate file type
        if not (str(file_path).lower().endswith('.tar.zst') or str(file_path).lower().endswith('.tar')):
            result = await self.parent_window.dialog(toga.ConfirmDialog(
                title="File Type Warning",
                message=f"Selected file '{os.path.basename(str(file_path))}' does not appear to be a MusicBrainz database file (.tar.zst or .tar).\n\nDo you want to proceed anyway?"
            ))
            if not result:
                return

        self.status_label.text = f"Selected: {os.path.basename(str(file_path))}"
        self.progress_bar.start()

        # Start import in thread
        threading.Thread(target=self.import_worker, args=(str(file_path),), daemon=True).start()

    def import_worker(self, file_path):
        """Worker thread for importing."""
        try:
            # Create a progress callback
            def progress_callback(progress, message):
                asyncio.run_coroutine_threadsafe(
                    self.update_status(message, progress),
                    asyncio.get_event_loop()
                )

            # Use the music search service to import the file
            success = self.music_search_service.import_database_file(file_path, progress_callback)

            if success:
                asyncio.run_coroutine_threadsafe(
                    self.import_complete(),
                    asyncio.get_event_loop()
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    self.import_error("Import failed. Please check the file and try again."),
                    asyncio.get_event_loop()
                )

        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                self.import_error(str(e)),
                asyncio.get_event_loop()
            )

    async def update_status(self, message, progress):
        """Update status message."""
        self.status_label.text = message
        if progress > 0:
            self.progress_bar.stop()
            self.progress_bar.max = 100
            self.progress_bar.value = progress

    async def import_complete(self):
        """Handle successful import."""
        self.progress_bar.stop()
        self.progress_bar.value = 100
        self.status_label.text = "Import completed successfully!"
        self.success = True

        await self.parent_window.dialog(toga.InfoDialog(
            title="Success",
            message="MusicBrainz database imported successfully!"
        ))

        if self.dialog_window:
            self.dialog_window.close()

    async def import_error(self, error_message):
        """Handle import error."""
        self.progress_bar.stop()
        self.status_label.text = "Import failed"

        await self.parent_window.dialog(toga.ErrorDialog(
            title="Import Error",
            message=error_message
        ))

    def close(self, widget=None):
        """Close dialog."""
        if self.dialog_window:
            self.dialog_window.close()
        return True
