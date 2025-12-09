#!/usr/bin/env python3
"""
Briefcase Build Script for Apple Music History Converter

This script provides a simple interface for building the application
across different platforms using Briefcase.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"🔨 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=False)
        print(f"[OK] {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[X] {description} failed with exit code {e.returncode}")
        return False


def build_dev():
    """Run the application in development mode."""
    return run_command("briefcase dev", "Running application in development mode")


def build_create():
    """Create the application bundle."""
    return run_command("briefcase create", "Creating application bundle")


def build_build():
    """Build the application."""
    return run_command("briefcase build", "Building application")


def build_run():
    """Run the built application."""
    return run_command("briefcase run", "Running built application")


def build_package():
    """Package the application for distribution."""
    return run_command("briefcase package", "Packaging application for distribution")


def build_all():
    """Complete build pipeline: create, build, and package."""
    print("[>] Starting complete build pipeline...")
    
    steps = [
        (build_create, "Create"),
        (build_build, "Build"),
        (build_package, "Package")
    ]
    
    for step_func, step_name in steps:
        if not step_func():
            print(f"\n[X] Build pipeline failed at {step_name} step")
            return False
    
    print("\n[YAY] Complete build pipeline finished successfully!")
    return True


def clean():
    """Clean build artifacts."""
    return run_command("rm -rf build dist", "Cleaning build artifacts")


def main():
    parser = argparse.ArgumentParser(description="Build Apple Music History Converter")
    parser.add_argument("command", choices=[
        "dev", "create", "build", "run", "package", "all", "clean"
    ], help="Build command to execute")
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("[X] Error: pyproject.toml not found. Please run this script from the project root.")
        sys.exit(1)
    
    commands = {
        "dev": build_dev,
        "create": build_create,
        "build": build_build,
        "run": build_run,
        "package": build_package,
        "all": build_all,
        "clean": clean
    }
    
    success = commands[args.command]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()