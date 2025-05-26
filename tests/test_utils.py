"""
Test utilities and common setup for all test files.
"""

import sys
import os

def setup_imports():
    """Add parent directory to sys.path for importing main modules."""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# Automatically setup imports when this module is imported
setup_imports()
