#!/usr/bin/env python3
"""
MusicBrainz Optimization Modal for Toga
Blocks UI during one-time optimization with progress, elapsed time, and ETA.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
import time
import threading
import asyncio
from typing import Optional, Callable

try:
    from .logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger(__name__)


class OptimizationModal:
    """
    Modal dialog for MusicBrainz optimization progress.
    Shows progress bar, elapsed time, ETA, and blocks user interaction.
    """

    def __init__(self, parent_window: toga.Window, cancellation_callback: Optional[Callable] = None):
        self.parent_window = parent_window
        self.modal_window = None
        self.cancellation_callback = cancellation_callback

        # Progress tracking
        self.progress = 0.0
        self.start_time = None
        self.message = "Starting..."
        self.is_active = False
        self.cancelled = False

        # UI components
        self.progress_bar = None
        self.message_label = None
        self.time_label = None

        # Update timer
        self._update_task = None

    async def show(self, optimization_function: Callable, *args, **kwargs):
        """
        Show modal and run optimization function.

        Args:
            optimization_function: Function to run for optimization
            *args, **kwargs: Arguments for optimization function
        """
        if self.is_active:
            return

        self.is_active = True
        self.start_time = time.time()
        self.progress = 0.0

        # Create modal window
        self._create_modal()

        # Start progress updates
        self._start_progress_updates()

        try:
            # Run optimization in background thread
            await self._run_optimization_async(optimization_function, *args, **kwargs)
        finally:
            # Clean up
            await self._close_modal()

    def _create_modal(self):
        """Create the modal dialog."""
        self.modal_window = toga.Window(
            title="Preparing MusicBrainz",
            size=(520, 220),
            resizable=False,
            on_close=self._handle_close_request
        )

        # Main container
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin=20,
                align_items=CENTER
            )
        )

        # Title and description
        title_label = toga.Label(
            "Optimizing MusicBrainz Database",
            style=Pack(
                text_align=CENTER,
                font_size=16,
                font_weight="bold",
                margin_bottom=10
            )
        )

        description_label = toga.Label(
            "Creating indexes for instant searches (~2-3 minutes)\n"
            "Please wait for completion to use MusicBrainz.\n"
            "Future searches will be 100x faster!",
            style=Pack(
                text_align=CENTER,
                margin_bottom=15
            )
        )

        # Progress bar
        self.progress_bar = toga.ProgressBar(
            max=100,
            style=Pack(
                width=400,
                margin_bottom=10
            )
        )

        # Status message
        self.message_label = toga.Label(
            self.message,
            style=Pack(
                text_align=CENTER,
                margin_bottom=5
            )
        )

        # Time information
        self.time_label = toga.Label(
            "Elapsed: 0s • ETA: —",
            style=Pack(
                text_align=CENTER,
                font_size=12
            )
        )

        # Add all components
        main_box.add(title_label)
        main_box.add(description_label)
        main_box.add(self.progress_bar)
        main_box.add(self.message_label)
        main_box.add(self.time_label)

        self.modal_window.content = main_box
        self.modal_window.show()

    def _start_progress_updates(self):
        """Start the progress update timer."""
        async def update_progress():
            while self.is_active and self.modal_window:
                try:
                    await self._update_display()
                    await asyncio.sleep(0.25)  # Update every 250ms
                except Exception as e:
                    logger.error(f"Error updating progress display: {e}")
                    break

        # Start the update task
        self._update_task = asyncio.create_task(update_progress())

    async def _update_display(self):
        """Update the modal display with current progress."""
        if not self.modal_window or not self.start_time:
            return

        # Update progress bar
        self.progress_bar.value = min(100, max(0, self.progress))

        # Update message with percentage
        if self.progress > 0:
            self.message_label.text = f"{self.message} ({int(self.progress)}%)"
        else:
            self.message_label.text = self.message

        # Calculate and display timing
        elapsed = int(time.time() - self.start_time)

        if self.progress > 5:  # Only show ETA after some progress
            remaining = int(elapsed * (100 - self.progress) / self.progress)
            if remaining >= 60:
                eta_str = f"{remaining//60}m {remaining%60}s"
            else:
                eta_str = f"{remaining}s"
        else:
            eta_str = "—"

        if elapsed >= 60:
            elapsed_str = f"{elapsed//60}m {elapsed%60}s"
        else:
            elapsed_str = f"{elapsed}s"

        self.time_label.text = f"Elapsed: {elapsed_str} • ETA: {eta_str}"

    async def _run_optimization_async(self, optimization_function: Callable, *args, **kwargs):
        """Run optimization function in background thread."""

        def progress_callback(message: str, percent: float, start_time: float):
            """Update progress from optimization thread."""
            self.message = message
            self.progress = percent

        # Add progress callback to kwargs
        kwargs['progress_callback'] = progress_callback

        # Run in thread to avoid blocking UI
        def run_optimization():
            try:
                optimization_function(*args, **kwargs)
            except Exception as e:
                self.message = f"Optimization failed: {e}"
                logger.error(f"Optimization error: {e}")

        # Start optimization thread
        thread = threading.Thread(target=run_optimization, daemon=True)
        thread.start()

        # Wait for completion (check every 100ms)
        while thread.is_alive():
            await asyncio.sleep(0.1)

        # Small delay to ensure final progress update
        await asyncio.sleep(0.5)

    async def _handle_close_request(self, widget):
        """Handle window close request with confirmation dialog."""
        # If already cancelled or not active, allow close
        if self.cancelled or not self.is_active:
            return True

        # Show confirmation dialog
        result = await self.modal_window.dialog(toga.ConfirmDialog(
            title="Cancel Optimization?",
            message="Do you want to cancel optimization?\n\n"
                   "You will have to restart from the beginning if you cancel.\n\n"
                   "Continue?"
        ))

        if result:
            # User confirmed cancellation
            logger.warning("⚠️ User confirmed optimization cancellation")
            self.cancelled = True

            # Call the cancellation callback to stop the optimization
            if self.cancellation_callback:
                self.cancellation_callback()

            # Allow window to close
            return True
        else:
            # User wants to continue - prevent close
            return False

    async def _close_modal(self):
        """Close the modal and clean up."""
        self.is_active = False

        # Cancel update task
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Close window
        if self.modal_window:
            self.modal_window.close()
            self.modal_window = None

    def update_progress(self, message: str, percent: float):
        """External method to update progress (thread-safe)."""
        self.message = message
        self.progress = percent


# Convenience function for easy integration
async def run_with_optimization_modal(parent_window: toga.Window,
                                    optimization_function: Callable,
                                    cancellation_callback: Optional[Callable] = None,
                                    *args, **kwargs):
    """
    Convenience function to run optimization with modal.

    Args:
        parent_window: The parent window for the modal
        optimization_function: The function to run for optimization
        cancellation_callback: Optional callback to invoke when user cancels
        *args, **kwargs: Arguments to pass to optimization_function

    Usage:
        await run_with_optimization_modal(
            self.main_window,
            musicbrainz_manager.run_optimization_synchronously,
            cancellation_callback=musicbrainz_manager.cancel_optimization
        )
    """
    modal = OptimizationModal(parent_window, cancellation_callback)
    await modal.show(optimization_function, *args, **kwargs)