import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
import threading
import asyncio


class ProgressDialog:
    """HIG-compliant progress dialog for long-running operations."""

    def __init__(self, parent_app, title="Progress", message="Processing..."):
        self.parent_app = parent_app
        self.cancelled = False
        self.completed = False
        self.dialog = None

        # Create HIG-compliant dialog window
        self.dialog = toga.Window(
            title=title,
            size=(420, 180),  # HIG-appropriate dialog size
            resizable=False
        )

        self._create_widgets(message)

        # Handle window close
        self.dialog.on_close = self.cancel

    def _create_widgets(self, message):
        """Create HIG-compliant dialog widgets."""
        # Main container with HIG dialog padding (20pt)
        main_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin=20,  # Standard HIG dialog padding
                align_items=CENTER
            )
        )

        # Message label with HIG Body text style
        self.message_label = toga.Label(
            message,
            style=Pack(
                font_size=13,  # Body text size per HIG
                margin_bottom=16,  # 16pt spacing before progress
                text_align=CENTER
            )
        )
        main_container.add(self.message_label)

        # Progress bar with HIG-compliant styling
        self.progress_bar = toga.ProgressBar(
            style=Pack(
                width=320,  # Appropriate width for dialog
                margin_bottom=12  # 12pt spacing after progress
            )
        )
        main_container.add(self.progress_bar)

        # Status label with HIG Caption text style
        self.status_label = toga.Label(
            "Initializing...",
            style=Pack(
                font_size=12,  # Caption text size per HIG
                margin_bottom=16,  # 16pt spacing before buttons
                text_align=CENTER
            )
        )
        main_container.add(self.status_label)

        # Button container with HIG button layout
        button_container = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER
            )
        )

        # Cancel button with HIG button styling
        self.cancel_button = toga.Button(
            "Cancel",
            on_press=self.cancel,
            style=Pack(
                margin=8,  # Standard button padding
                width=80    # Consistent button width
            )
        )
        button_container.add(self.cancel_button)
        main_container.add(button_container)

        # Set dialog content
        self.dialog.content = main_container

    def update_progress(self, percentage, status_message):
        """Update progress bar and status message."""
        if self.dialog:
            self.progress_bar.value = percentage
            self.status_label.text = status_message

            if percentage >= 100:
                self.completed = True
                self.cancel_button.text = "Close"


    def cancel(self):
        """Cancel the operation."""
        if not self.completed:
            self.cancelled = True
        self.dialog.close()

    def is_cancelled(self):
        """Check if operation was cancelled."""
        return self.cancelled

    def is_completed(self):
        """Check if operation completed."""
        return self.completed

    def show(self):
        """Show the dialog."""
        self.dialog.show()
        return self.dialog


# Note: DatabaseDownloadDialog and FirstTimeSetupDialog have been moved to database_dialogs.py
# This file now only contains the generic Toga ProgressDialog
