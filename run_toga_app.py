#!/usr/bin/env python3
"""
Apple Music Play History Converter - Toga Version Runner
Runs the Toga-based GUI version of the application.

Usage:
    python run_toga_app.py              # Normal mode
    python run_toga_app.py --test-mode  # Enable testing infrastructure
    python run_toga_app.py --test-mode --test-verbose  # Verbose test logging

Environment Variables:
    TEST_MODE=1        # Enable testing mode
    TEST_VERBOSE=1     # Enable verbose test logging
"""

import sys
import os
import argparse
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_dir = project_root / "src" / "apple_music_history_converter"
sys.path.insert(0, str(src_dir))


def _enable_test_mode(verbose: bool = False) -> None:
    """
    Enable testing mode by setting environment variables.

    This activates the testing infrastructure which includes:
    - Widget registry for programmatic access
    - Action/state logging for observability
    - Injection points for file dialogs
    - Human handoff API for manual verification

    Args:
        verbose: If True, enable verbose test logging
    """
    os.environ['TEST_MODE'] = '1'
    if verbose:
        os.environ['TEST_VERBOSE'] = '1'
    print("[TEST MODE] Testing infrastructure enabled")
    if verbose:
        print("[TEST MODE] Verbose logging enabled")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Apple Music Play History Converter - Toga GUI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_toga_app.py                        # Normal mode
  python run_toga_app.py --test-mode            # Enable testing
  python run_toga_app.py --test-mode --test-verbose  # Verbose testing

Testing Mode:
  When enabled, the app exposes a TestHarness for programmatic UI interaction:
  - Widget discovery and access by name
  - Simulate button presses, switch toggles, text input
  - Query widget states and values
  - Inject file paths to bypass file dialogs
  - Human handoff for manual verification steps
        """
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Enable testing infrastructure for programmatic UI control'
    )
    parser.add_argument(
        '--test-verbose',
        action='store_true',
        help='Enable verbose test logging (implies --test-mode)'
    )
    return parser.parse_args()


def main():
    """Run the Toga version of Apple Music Play History Converter."""
    args = parse_args()

    # Enable test mode if requested
    if args.test_verbose:
        _enable_test_mode(verbose=True)
    elif args.test_mode:
        _enable_test_mode(verbose=False)

    try:
        # Import and run the Toga app
        from apple_music_play_history_converter import main as create_app
        print("Starting Apple Music Play History Converter (Toga Version)...")
        print("-" * 60)

        app = create_app()
        app.main_loop()

    except ImportError as e:
        print(f"Import error: {e}")
        print("\nMake sure you have installed the required dependencies:")
        print("   pip install toga pandas requests darkdetect")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()