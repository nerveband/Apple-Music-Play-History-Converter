#!/usr/bin/env python3
"""
Testing Infrastructure for Apple Music Play History Converter.

This module provides programmatic control of the Toga UI for automated testing.
It enables Claude Code to interact with the app, simulate user actions, and
verify UI state without manual intervention.

Usage:
    # Enable test mode
    python run_toga_app.py --test-mode

    # Access test harness from running app
    app.test.press_button("download_button")
    app.test.set_switch("musicbrainz_radio", True)
    state = app.test.get_state()

Features:
    - Widget discovery and access by name
    - Simulate button presses, switch toggles, text input
    - Query widget states and values
    - Inject file paths to bypass file dialogs
    - Human handoff for manual verification steps

Note:
    This module is only loaded when testing.enabled=True in settings.
    When testing is disabled, there is zero overhead.
"""

from typing import TYPE_CHECKING, Dict, List, Any, Optional, Type, Union
import time

try:
    import toga
except ImportError:
    toga = None  # Allow module to load even without toga for documentation

try:
    from .logging_config import get_logger
    from .app_directories import get_testing_settings
except ImportError:
    from logging_config import get_logger
    from app_directories import get_testing_settings

if TYPE_CHECKING:
    from .apple_music_play_history_converter import AppleMusicConverterApp


# ============================================================================
# Exceptions
# ============================================================================

class TestingError(Exception):
    """Base exception for testing infrastructure errors."""
    pass


class TestingNotEnabledError(TestingError):
    """Raised when attempting to use testing features without enabling test mode."""
    pass


class WidgetNotFoundError(TestingError):
    """Raised when a requested widget cannot be found in the registry."""

    def __init__(self, name: str, available: List[str] = None):
        self.name = name
        self.available = available or []
        msg = f"Widget '{name}' not found."
        if self.available:
            # Show similar names if any
            similar = [w for w in self.available if name.lower() in w.lower()]
            if similar:
                msg += f" Similar: {similar[:5]}"
            else:
                msg += f" Available: {len(self.available)} widgets. Use list_all() to see them."
        super().__init__(msg)


class WidgetTypeMismatchError(TestingError):
    """Raised when a widget is not of the expected type."""

    def __init__(self, name: str, expected: str, actual: str):
        self.name = name
        self.expected = expected
        self.actual = actual
        super().__init__(f"Widget '{name}' is {actual}, expected {expected}")


class AssertionFailedError(TestingError):
    """Raised when a test assertion fails."""
    pass


# ============================================================================
# Widget Registry
# ============================================================================

class WidgetRegistry:
    """
    Discovers and indexes all Toga widgets for programmatic access.

    The registry scans the app instance after startup to find all widgets
    assigned as instance attributes. This allows access by attribute name
    (e.g., 'download_button', 'musicbrainz_radio').

    Usage:
        registry = WidgetRegistry(app)
        button = registry.get("download_button")
        all_widgets = registry.list_all()
        buttons = registry.list_by_type(toga.Button)
    """

    def __init__(self, app: 'AppleMusicConverterApp'):
        """
        Initialize registry and scan app for widgets.

        Args:
            app: The Toga application instance to scan
        """
        self.app = app
        self.widgets: Dict[str, toga.Widget] = {}
        self.logger = get_logger(__name__)
        self._scan_time: float = 0.0

        # Perform initial scan
        self._scan_app()

    def _scan_app(self) -> None:
        """
        Scan app instance for all toga.Widget attributes.

        This discovers widgets assigned as instance attributes like:
            self.download_button = toga.Button(...)
            self.musicbrainz_radio = toga.Switch(...)
        """
        if toga is None:
            self.logger.test_verbose("Toga not available, skipping widget scan")
            return

        start_time = time.perf_counter()

        for attr_name in dir(self.app):
            # Skip private/magic attributes
            if attr_name.startswith('_'):
                continue

            try:
                attr = getattr(self.app, attr_name, None)
                if attr is not None and isinstance(attr, toga.Widget):
                    self.widgets[attr_name] = attr
                    self.logger.test_verbose(
                        f"Discovered widget: {attr_name} ({type(attr).__name__})"
                    )
            except Exception as e:
                # Some properties may raise errors when accessed
                self.logger.test_verbose(f"Could not access {attr_name}: {e}")

        self._scan_time = time.perf_counter() - start_time

        self.logger.test_action(
            f"Widget registry initialized: {len(self.widgets)} widgets found in {self._scan_time:.3f}s"
        )

    def rescan(self) -> int:
        """
        Rescan app for widgets (useful after dynamic widget creation).

        Returns:
            int: Number of widgets found
        """
        self.widgets.clear()
        self._scan_app()
        return len(self.widgets)

    def get(self, name: str) -> toga.Widget:
        """
        Get widget by attribute name.

        Args:
            name: The attribute name of the widget (e.g., 'download_button')

        Returns:
            The Toga widget instance

        Raises:
            WidgetNotFoundError: If widget not found in registry
        """
        if name not in self.widgets:
            raise WidgetNotFoundError(name, list(self.widgets.keys()))
        return self.widgets[name]

    def get_typed(self, name: str, widget_type: Type) -> toga.Widget:
        """
        Get widget by name with type checking.

        Args:
            name: The attribute name of the widget
            widget_type: Expected widget type (e.g., toga.Button)

        Returns:
            The Toga widget instance

        Raises:
            WidgetNotFoundError: If widget not found
            WidgetTypeMismatchError: If widget is wrong type
        """
        widget = self.get(name)
        if not isinstance(widget, widget_type):
            raise WidgetTypeMismatchError(
                name,
                widget_type.__name__,
                type(widget).__name__
            )
        return widget

    def list_all(self) -> List[str]:
        """
        List all discovered widget names.

        Returns:
            List of widget attribute names
        """
        return sorted(self.widgets.keys())

    def list_by_type(self, widget_type: Type) -> List[str]:
        """
        List widgets of a specific type.

        Args:
            widget_type: The type to filter by (e.g., toga.Button)

        Returns:
            List of widget names matching the type
        """
        return sorted([
            name for name, widget in self.widgets.items()
            if isinstance(widget, widget_type)
        ])

    def list_buttons(self) -> List[str]:
        """List all Button widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.Button)

    def list_switches(self) -> List[str]:
        """List all Switch widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.Switch)

    def list_text_inputs(self) -> List[str]:
        """List all TextInput widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.TextInput)

    def list_labels(self) -> List[str]:
        """List all Label widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.Label)

    def list_selections(self) -> List[str]:
        """List all Selection (dropdown) widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.Selection)

    def list_tables(self) -> List[str]:
        """List all Table widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.Table)

    def list_progress_bars(self) -> List[str]:
        """List all ProgressBar widgets."""
        if toga is None:
            return []
        return self.list_by_type(toga.ProgressBar)

    def get_summary(self) -> Dict[str, int]:
        """
        Get a summary of widgets by type.

        Returns:
            Dict mapping type names to counts
        """
        summary: Dict[str, int] = {}
        for widget in self.widgets.values():
            type_name = type(widget).__name__
            summary[type_name] = summary.get(type_name, 0) + 1
        return dict(sorted(summary.items()))

    def __len__(self) -> int:
        return len(self.widgets)

    def __contains__(self, name: str) -> bool:
        return name in self.widgets


# ============================================================================
# Test Harness
# ============================================================================

class TestHarness:
    """
    Programmatic control interface for Toga app testing.

    This class provides methods to:
    - Access widgets by name
    - Simulate user interactions (press buttons, toggle switches, enter text)
    - Query widget states and values
    - Wait for human verification
    - Make assertions about UI state
    - Track state changes (enabled/disabled, value changes)

    Usage:
        # Access via app.test when test mode is enabled
        app.test.press_button("download_button")
        app.test.set_switch("musicbrainz_radio", True)

        value = app.test.get_widget_value("progress_bar")
        state = app.test.get_state()

        app.test.wait_for_human("Please verify the table shows 100 tracks")
        app.test.assert_enabled("convert_button")

        # State tracking
        app.test.start_tracking()  # Begin monitoring state changes
        # ... do some actions ...
        changes = app.test.get_state_changes()  # Get all changes since start
        app.test.stop_tracking()
    """

    def __init__(self, app: 'AppleMusicConverterApp'):
        """
        Initialize test harness for the given app.

        Args:
            app: The Toga application instance
        """
        self.app = app
        self.registry = WidgetRegistry(app)
        self.logger = get_logger(__name__)
        self._settings = get_testing_settings()

        # State tracking
        self._tracking_enabled = False
        self._tracked_state: Dict[str, Dict[str, Any]] = {}
        self._state_changes: List[Dict[str, Any]] = []
        self._tracking_interval = 0.1  # Check every 100ms

        self.logger.test_action("TestHarness initialized")

    # ========================================================================
    # Widget Access
    # ========================================================================

    def get_widget(self, name: str) -> toga.Widget:
        """
        Get a widget by its attribute name.

        Args:
            name: Widget attribute name (e.g., 'download_button')

        Returns:
            The Toga widget instance

        Raises:
            WidgetNotFoundError: If widget not found
        """
        return self.registry.get(name)

    def get_button(self, name: str) -> toga.Button:
        """Get a Button widget by name."""
        return self.registry.get_typed(name, toga.Button)

    def get_switch(self, name: str) -> toga.Switch:
        """Get a Switch widget by name."""
        return self.registry.get_typed(name, toga.Switch)

    def get_text_input(self, name: str) -> toga.TextInput:
        """Get a TextInput widget by name."""
        return self.registry.get_typed(name, toga.TextInput)

    def get_label(self, name: str) -> toga.Label:
        """Get a Label widget by name."""
        return self.registry.get_typed(name, toga.Label)

    def get_selection(self, name: str) -> toga.Selection:
        """Get a Selection (dropdown) widget by name."""
        return self.registry.get_typed(name, toga.Selection)

    def get_table(self, name: str) -> toga.Table:
        """Get a Table widget by name."""
        return self.registry.get_typed(name, toga.Table)

    def get_progress_bar(self, name: str) -> toga.ProgressBar:
        """Get a ProgressBar widget by name."""
        return self.registry.get_typed(name, toga.ProgressBar)

    # ========================================================================
    # Widget Actions
    # ========================================================================

    def press_button(self, name: str) -> None:
        """
        Simulate pressing a button.

        Args:
            name: Button widget name

        Raises:
            WidgetNotFoundError: If button not found
            WidgetTypeMismatchError: If widget is not a Button
        """
        button = self.get_button(name)
        self.logger.test_action(f"Pressing button '{name}'")

        # Trigger the on_press handler if it exists
        if hasattr(button, 'on_press') and button.on_press:
            button.on_press(button)

        self._log_state_if_enabled()

    def set_switch(self, name: str, value: bool) -> None:
        """
        Set a switch value.

        Args:
            name: Switch widget name
            value: True for on, False for off
        """
        switch = self.get_switch(name)
        old_value = switch.value
        self.logger.test_action(f"Setting switch '{name}': {old_value} -> {value}")

        switch.value = value

        # Trigger on_change if value actually changed
        if old_value != value and hasattr(switch, 'on_change') and switch.on_change:
            switch.on_change(switch)

        self._log_state_if_enabled()

    def set_text(self, name: str, value: str) -> None:
        """
        Set text input value.

        Args:
            name: TextInput widget name
            value: Text to set
        """
        text_input = self.get_text_input(name)
        self.logger.test_action(f"Setting text '{name}': '{value}'")

        text_input.value = value

        self._log_state_if_enabled()

    def select_option(self, name: str, value: str) -> None:
        """
        Select an option in a Selection (dropdown) widget.

        Args:
            name: Selection widget name
            value: Option value to select
        """
        selection = self.get_selection(name)
        self.logger.test_action(f"Selecting option in '{name}': '{value}'")

        selection.value = value

        if hasattr(selection, 'on_change') and selection.on_change:
            selection.on_change(selection)

        self._log_state_if_enabled()

    # ========================================================================
    # State Queries
    # ========================================================================

    def get_widget_value(self, name: str) -> Any:
        """
        Get the current value of a widget.

        Works with widgets that have a 'value' attribute:
        - Switch: bool
        - TextInput: str
        - ProgressBar: float
        - Selection: selected item
        - Label: text content

        Args:
            name: Widget name

        Returns:
            The widget's current value
        """
        widget = self.get_widget(name)

        # Try common value properties
        if hasattr(widget, 'value'):
            return widget.value
        if hasattr(widget, 'text'):
            return widget.text

        return None

    def is_enabled(self, name: str) -> bool:
        """
        Check if a widget is enabled.

        Args:
            name: Widget name

        Returns:
            True if widget is enabled
        """
        widget = self.get_widget(name)
        return getattr(widget, 'enabled', True)

    def is_visible(self, name: str) -> bool:
        """
        Check if a widget is visible (not hidden).

        Args:
            name: Widget name

        Returns:
            True if widget is visible
        """
        widget = self.get_widget(name)
        # Check style for visibility
        if hasattr(widget, 'style') and hasattr(widget.style, 'visibility'):
            return widget.style.visibility != 'hidden'
        return True

    def get_state(self) -> Dict[str, Any]:
        """
        Get a snapshot of all widget states.

        Returns:
            Dict mapping widget names to their current values/states
        """
        state = {}

        for name in self.registry.list_all():
            try:
                widget = self.registry.get(name)
                widget_state = {
                    'type': type(widget).__name__,
                    'enabled': getattr(widget, 'enabled', True),
                }

                # Add value if applicable
                if hasattr(widget, 'value'):
                    widget_state['value'] = widget.value
                elif hasattr(widget, 'text'):
                    widget_state['value'] = widget.text

                state[name] = widget_state

            except Exception as e:
                state[name] = {'error': str(e)}

        return state

    def _log_state_if_enabled(self) -> None:
        """Log current state if state logging is enabled."""
        if self._settings.get('log_state', True):
            # Log a simplified state (just values, not full state)
            simple_state = {}
            for name in self.registry.list_all():
                try:
                    value = self.get_widget_value(name)
                    if value is not None:
                        simple_state[name] = value
                except Exception:
                    pass
            # Only log if we have some state
            if simple_state:
                self.logger.test_state(simple_state)

    # ========================================================================
    # Human Handoff
    # ========================================================================

    def wait_for_human(self, message: str) -> str:
        """
        Pause execution and wait for human input.

        Use this when you need manual verification or interaction
        that cannot be automated.

        Args:
            message: Instructions for the human

        Returns:
            Any text the human entered (empty string if just pressed Enter)

        Example:
            app.test.wait_for_human("Please verify the preview table looks correct")
            app.test.wait_for_human("Manually select a file, then press Enter")
        """
        self.logger.test_action(f"Waiting for human: {message}")

        print("\n" + "=" * 60)
        print("[HUMAN HANDOFF]")
        print(message)
        print("=" * 60)

        response = input("Press Enter to continue (or type a response): ")

        self.logger.test_action(f"Human responded: '{response}' (continuing)")

        return response

    # ========================================================================
    # Assertions
    # ========================================================================

    def assert_widget_exists(self, name: str) -> None:
        """Assert that a widget exists in the registry."""
        if name not in self.registry:
            raise AssertionFailedError(f"Widget '{name}' does not exist")

    def assert_enabled(self, name: str) -> None:
        """Assert that a widget is enabled."""
        if not self.is_enabled(name):
            raise AssertionFailedError(f"Widget '{name}' is not enabled")

    def assert_disabled(self, name: str) -> None:
        """Assert that a widget is disabled."""
        if self.is_enabled(name):
            raise AssertionFailedError(f"Widget '{name}' is not disabled")

    def assert_value(self, name: str, expected: Any) -> None:
        """Assert that a widget has the expected value."""
        actual = self.get_widget_value(name)
        if actual != expected:
            raise AssertionFailedError(
                f"Widget '{name}' value mismatch: expected {expected!r}, got {actual!r}"
            )

    def assert_text_contains(self, name: str, text: str) -> None:
        """Assert that a widget's text contains the given substring."""
        value = self.get_widget_value(name)
        if value is None:
            raise AssertionFailedError(f"Widget '{name}' has no text value")
        if text not in str(value):
            raise AssertionFailedError(
                f"Widget '{name}' text does not contain '{text}'. Actual: '{value}'"
            )

    def assert_progress(self, name: str, expected: float, tolerance: float = 0.1) -> None:
        """
        Assert that a progress bar is at the expected value.

        Args:
            name: ProgressBar widget name
            expected: Expected progress value (0.0 to 1.0)
            tolerance: Acceptable difference from expected
        """
        progress_bar = self.get_progress_bar(name)
        actual = progress_bar.value or 0.0

        if abs(actual - expected) > tolerance:
            raise AssertionFailedError(
                f"Progress '{name}' mismatch: expected {expected:.2f} "
                f"(+/-{tolerance}), got {actual:.2f}"
            )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def list_widgets(self) -> List[str]:
        """List all discovered widget names."""
        return self.registry.list_all()

    def widget_summary(self) -> Dict[str, int]:
        """Get a summary of widgets by type."""
        return self.registry.get_summary()

    def print_widgets(self) -> None:
        """Print all discovered widgets (for debugging)."""
        print("\n" + "=" * 60)
        print("Discovered Widgets:")
        print("=" * 60)

        summary = self.widget_summary()
        for type_name, count in summary.items():
            print(f"  {type_name}: {count}")

        print("-" * 60)
        for name in self.list_widgets():
            widget = self.get_widget(name)
            value = self.get_widget_value(name)
            print(f"  {name}: {type(widget).__name__} = {value!r}")

        print("=" * 60 + "\n")

    # ========================================================================
    # State Change Tracking
    # ========================================================================

    def _capture_widget_state(self, name: str) -> Dict[str, Any]:
        """Capture current state of a single widget."""
        try:
            widget = self.registry.get(name)
            state = {
                'enabled': getattr(widget, 'enabled', True),
                'value': None,
                'text': None,
            }
            if hasattr(widget, 'value'):
                state['value'] = widget.value
            if hasattr(widget, 'text'):
                state['text'] = widget.text
            return state
        except Exception as e:
            return {'error': str(e)}

    def _capture_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Capture states of all tracked widgets (buttons and switches)."""
        states = {}
        # Track buttons and switches primarily
        for name in self.registry.list_buttons() + self.registry.list_switches():
            states[name] = self._capture_widget_state(name)
        return states

    def _detect_changes(self, old_state: Dict, new_state: Dict) -> List[Dict[str, Any]]:
        """Detect differences between two state snapshots."""
        changes = []
        timestamp = time.time()

        for name, new_widget_state in new_state.items():
            old_widget_state = old_state.get(name, {})

            # Check enabled state changes
            old_enabled = old_widget_state.get('enabled')
            new_enabled = new_widget_state.get('enabled')
            if old_enabled != new_enabled and old_enabled is not None:
                change = {
                    'timestamp': timestamp,
                    'widget': name,
                    'property': 'enabled',
                    'old_value': old_enabled,
                    'new_value': new_enabled,
                }
                changes.append(change)
                self.logger.test_action(
                    f"STATE CHANGE: {name}.enabled: {old_enabled} -> {new_enabled}"
                )

            # Check value changes
            old_value = old_widget_state.get('value')
            new_value = new_widget_state.get('value')
            if old_value != new_value and old_value is not None:
                change = {
                    'timestamp': timestamp,
                    'widget': name,
                    'property': 'value',
                    'old_value': old_value,
                    'new_value': new_value,
                }
                changes.append(change)
                self.logger.test_action(
                    f"STATE CHANGE: {name}.value: {old_value} -> {new_value}"
                )

        return changes

    def start_tracking(self) -> None:
        """
        Start tracking widget state changes.

        After calling this, any changes to button enabled states or
        switch values will be logged and stored in the changes list.

        Example:
            app.test.start_tracking()
            # Load a CSV, do some actions
            changes = app.test.get_state_changes()
            # changes = [{'widget': 'reprocess_button', 'property': 'enabled', ...}]
        """
        self._tracking_enabled = True
        self._state_changes = []
        self._tracked_state = self._capture_all_states()
        self.logger.test_action("State tracking STARTED - monitoring button/switch states")

    def stop_tracking(self) -> List[Dict[str, Any]]:
        """
        Stop tracking state changes.

        Returns:
            List of all state changes detected since start_tracking()
        """
        self._tracking_enabled = False
        final_changes = self.check_for_changes()
        self.logger.test_action(
            f"State tracking STOPPED - {len(self._state_changes)} total changes detected"
        )
        return self._state_changes

    def check_for_changes(self) -> List[Dict[str, Any]]:
        """
        Check for state changes since last check.

        Call this periodically to detect changes. Changes are logged
        automatically and accumulated in the changes list.

        Returns:
            List of new changes detected in this check
        """
        if not self._tracking_enabled:
            return []

        new_state = self._capture_all_states()
        changes = self._detect_changes(self._tracked_state, new_state)
        self._state_changes.extend(changes)
        self._tracked_state = new_state
        return changes

    def get_state_changes(self) -> List[Dict[str, Any]]:
        """
        Get all state changes detected since tracking started.

        Returns:
            List of state change records, each containing:
            - timestamp: When the change was detected
            - widget: Widget name
            - property: 'enabled' or 'value'
            - old_value: Previous value
            - new_value: New value
        """
        # Check for any pending changes first
        if self._tracking_enabled:
            self.check_for_changes()
        return self._state_changes.copy()

    def clear_state_changes(self) -> None:
        """Clear the accumulated state changes."""
        self._state_changes = []
        self._tracked_state = self._capture_all_states()

    def get_button_states(self) -> Dict[str, bool]:
        """
        Get enabled state of all buttons.

        Returns:
            Dict mapping button names to their enabled state
        """
        states = {}
        for name in self.registry.list_buttons():
            try:
                widget = self.registry.get(name)
                states[name] = getattr(widget, 'enabled', True)
            except Exception:
                states[name] = None
        return states

    def get_switch_states(self) -> Dict[str, bool]:
        """
        Get value of all switches.

        Returns:
            Dict mapping switch names to their on/off value
        """
        states = {}
        for name in self.registry.list_switches():
            try:
                widget = self.registry.get(name)
                states[name] = getattr(widget, 'value', False)
            except Exception:
                states[name] = None
        return states

    def print_button_states(self) -> None:
        """Print current enabled state of all buttons."""
        print("\n" + "=" * 60)
        print("Button States:")
        print("=" * 60)
        for name, enabled in sorted(self.get_button_states().items()):
            status = "ENABLED" if enabled else "DISABLED"
            symbol = "[OK]" if enabled else "[X]"
            print(f"  {symbol} {name}: {status}")
        print("=" * 60 + "\n")

    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get a complete snapshot of current app state.

        Returns comprehensive state info including:
        - All button enabled states
        - All switch values
        - Key app attributes (processed_df, current_save_path, etc.)
        """
        snapshot = {
            'timestamp': time.time(),
            'buttons': self.get_button_states(),
            'switches': self.get_switch_states(),
            'app_state': {}
        }

        # Capture key app attributes
        key_attrs = [
            'processed_df', 'current_save_path', 'active_search_provider',
            'is_search_interrupted', 'optimization_running'
        ]
        for attr in key_attrs:
            if hasattr(self.app, attr):
                value = getattr(self.app, attr)
                # Convert non-serializable types
                if hasattr(value, '__len__') and not isinstance(value, str):
                    snapshot['app_state'][attr] = f"<{type(value).__name__} len={len(value)}>"
                elif value is None:
                    snapshot['app_state'][attr] = None
                else:
                    snapshot['app_state'][attr] = str(value)

        return snapshot
