#!/usr/bin/env python3
"""
Test runner for Apple Music Play History Converter
Run all tests or specific test categories.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_test(test_file):
    """Run a single test file."""
    print(f"\n{'='*50}")
    print(f"Running: {test_file}")
    print('='*50)
    
    result = subprocess.run([sys.executable, str(test_file)], 
                          capture_output=False, 
                          cwd=Path(__file__).parent)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description='Run tests for Apple Music Play History Converter')
    parser.add_argument('--category', '-c', 
                       choices=['core', 'ui', 'import', 'platform', 'all'],
                       default='all',
                       help='Test category to run')
    parser.add_argument('--file', '-f', 
                       help='Run specific test file')
    
    args = parser.parse_args()
    
    tests_dir = Path(__file__).parent / 'tests'
    
    if args.file:
        # Run specific file
        test_file = tests_dir / args.file
        if not test_file.exists():
            test_file = tests_dir / f"{args.file}.py"
        if test_file.exists():
            run_test(test_file)
        else:
            print(f"Test file not found: {args.file}")
        return
    
    # Define test categories
    test_categories = {
        'core': ['test_app.py', 'test_app_workflow.py', 'test_full_integration.py'],
        'ui': ['test_ui_layout.py', 'test_dialog_crash.py'],
        'import': ['test_manual_import.py', 'test_manual_import_button.py', 
                  'test_import_function.py', 'test_import_with_progress.py'],
        'platform': ['test_cross_platform.py', 'verify_compatibility.py'],
    }
    
    if args.category == 'all':
        # Run all tests
        all_tests = []
        for category_tests in test_categories.values():
            all_tests.extend(category_tests)
        tests_to_run = sorted(set(all_tests))
    else:
        tests_to_run = test_categories.get(args.category, [])
    
    print(f"Running {len(tests_to_run)} tests in category: {args.category}")
    
    success_count = 0
    total_count = len(tests_to_run)
    
    for test_name in tests_to_run:
        test_file = tests_dir / test_name
        if test_file.exists():
            if run_test(test_file):
                success_count += 1
        else:
            print(f"Warning: Test file not found: {test_name}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {success_count}/{total_count} passed")
    print('='*50)
    
    if success_count == total_count:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
