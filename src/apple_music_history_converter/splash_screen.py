#!/usr/bin/env python3
"""
Splash screen for Apple Music History Converter.

Shows a loading screen with app icon and progress indicator while
heavy dependencies load. Cross-platform compatible.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, CENTER
import asyncio
from pathlib import Path

try:
    from .logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger(__name__)


class SplashScreen:
    """
    Cross-platform splash screen with progress indicator.

    Shows app icon, title, and loading progress while main app initializes.
    """

    def __init__(self, app):
        """
        Initialize splash screen.

        Args:
            app: Toga application instance
        """
        self.app = app
        self.window = None
        self.progress_label = None
        self.current_step = 0
        self.total_steps = 5  # Loading steps to track

    def create(self):
        """Create and show the splash screen window."""
        try:
            # Create splash window (smaller, centered)
            self.window = toga.Window(
                title="Loading...",
                size=(400, 300),
                resizable=False
            )

            # Main container
            container = toga.Box(
                style=Pack(
                    direction=COLUMN,
                    align_items=CENTER,
                    margin=40
                )
            )

            # App icon (if available)
            try:
                icon_path = Path(__file__).parent / "resources" / "appicon.icns"
                if icon_path.exists():
                    # Toga doesn't support direct image display in Box yet,
                    # so we'll just show text-based branding
                    pass
            except Exception as e:
                logger.debug(f"Could not load icon: {e}")

            # App title
            title_label = toga.Label(
                "Apple Music Play History Converter",
                style=Pack(
                    text_align=CENTER,
                    font_size=18,
                    font_weight="bold",
                    margin_bottom=10
                )
            )
            container.add(title_label)

            # Version info
            version_label = toga.Label(
                "Version 2.0.0",
                style=Pack(
                    text_align=CENTER,
                    font_size=12,
                    margin_bottom=30
                )
            )
            container.add(version_label)

            # Progress indicator
            self.progress_bar = toga.ProgressBar(
                max=self.total_steps,
                style=Pack(
                    width=300,
                    margin_bottom=15
                )
            )
            container.add(self.progress_bar)

            # Status message
            self.progress_label = toga.Label(
                "Initializing...",
                style=Pack(
                    text_align=CENTER,
                    font_size=11,
                    margin_bottom=10
                )
            )
            container.add(self.progress_label)

            # Tip message
            tip_label = toga.Label(
                "💡 Tip: First launch may take a moment on slower computers",
                style=Pack(
                    text_align=CENTER,
                    font_size=10,
                    color="#666666"
                )
            )
            container.add(tip_label)

            self.window.content = container
            self.window.show()

            logger.info("Splash screen displayed")

        except Exception as e:
            logger.error(f"Failed to create splash screen: {e}")
            # Don't fail startup if splash screen fails

    async def update_progress(self, message: str, step: int = None):
        """
        Update splash screen progress.

        Args:
            message: Status message to display
            step: Current step number (auto-increments if None)
        """
        try:
            if step is not None:
                self.current_step = step
            else:
                self.current_step += 1

            if self.progress_label:
                self.progress_label.text = message

            if self.progress_bar:
                self.progress_bar.value = self.current_step

            # Give UI time to update
            await asyncio.sleep(0.05)

            logger.debug(f"Splash progress: [{self.current_step}/{self.total_steps}] {message}")

        except Exception as e:
            logger.error(f"Failed to update splash progress: {e}")

    def close(self):
        """Close the splash screen."""
        try:
            if self.window:
                self.window.close()
                logger.info("Splash screen closed")
        except Exception as e:
            logger.error(f"Failed to close splash screen: {e}")
