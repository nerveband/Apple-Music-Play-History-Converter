#!/usr/bin/env python3
"""
Run Apple Music Play History Converter Application
"""
import os
import sys
import subprocess

def main():
    """
    Runs the Apple Music Play History Converter application
    """
    print("Starting Apple Music Play History Converter...")
    
    # Check if running in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_venv:
        # Create venv if it doesn't exist
        if not os.path.exists("venv"):
            print("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        
        # Activate venv and install requirements
        venv_python = os.path.join("venv", "bin", "python")
        if not os.path.exists(venv_python):
            print("Error: Virtual environment creation failed.")
            return
        
        # Install requirements if needed
        print("Installing requirements...")
        subprocess.run([venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        
        # Run the application with the venv python
        print("Launching application...")
        subprocess.run([venv_python, "apple_music_play_history_converter.py"], check=True)
    else:
        # Already in venv, just run the app
        print("Launching application...")
        import apple_music_play_history_converter

if __name__ == "__main__":
    main()
