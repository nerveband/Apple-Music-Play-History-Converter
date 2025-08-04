#!/usr/bin/env python3
"""
Fix tkinter in Briefcase app bundle by copying system tkinter files.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def find_system_tkinter():
    """Find tkinter in system Python."""
    result = subprocess.run([sys.executable, "-c", "import tkinter; print(tkinter.__file__)"], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("tkinter not found in system Python")
    
    tkinter_path = Path(result.stdout.strip()).parent
    tkinter_so = None
    
    # Find _tkinter.so
    python_dir = tkinter_path.parent.parent
    lib_dynload = python_dir / "lib-dynload"
    for f in lib_dynload.glob("_tkinter*.so"):
        tkinter_so = f
        break
    
    return tkinter_path, tkinter_so

def fix_briefcase_tkinter(app_path):
    """Copy tkinter files to Briefcase app bundle."""
    app_path = Path(app_path)
    
    # Find Python framework in app
    python_lib = app_path / "Contents/Frameworks/Python.framework/Versions/3.12/lib/python3.12"
    
    if not python_lib.exists():
        raise RuntimeError(f"Python lib not found in app: {python_lib}")
    
    # Get system tkinter
    tkinter_path, tkinter_so = find_system_tkinter()
    
    print(f"Found system tkinter: {tkinter_path}")
    print(f"Found tkinter binary: {tkinter_so}")
    
    # Copy tkinter module
    dest_tkinter = python_lib / "tkinter"
    if dest_tkinter.exists():
        shutil.rmtree(dest_tkinter)
    shutil.copytree(tkinter_path, dest_tkinter)
    print(f"Copied tkinter to: {dest_tkinter}")
    
    # Copy _tkinter.so
    if tkinter_so:
        dest_dynload = python_lib / "lib-dynload"
        dest_dynload.mkdir(exist_ok=True)
        dest_so = dest_dynload / tkinter_so.name
        shutil.copy2(tkinter_so, dest_so)
        print(f"Copied _tkinter.so to: {dest_so}")
    
    # Also check for tcl/tk libraries
    tcl_tk_libs = [
        "/opt/homebrew/lib/libtcl8.6.dylib",
        "/opt/homebrew/lib/libtk8.6.dylib",
        "/usr/local/lib/libtcl8.6.dylib",
        "/usr/local/lib/libtk8.6.dylib",
    ]
    
    for lib_path in tcl_tk_libs:
        if os.path.exists(lib_path):
            dest_lib = app_path / "Contents/Frameworks/Python.framework/Versions/3.12/lib" / os.path.basename(lib_path)
            if not dest_lib.exists():
                shutil.copy2(lib_path, dest_lib)
                print(f"Copied {lib_path} to app bundle")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: fix_tkinter.py <app_path>")
        sys.exit(1)
    
    app_path = sys.argv[1]
    try:
        fix_briefcase_tkinter(app_path)
        print("\ntkinter fix applied successfully!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)