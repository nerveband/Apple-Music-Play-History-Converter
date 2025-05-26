#!/usr/bin/env python3
"""
Test script to isolate the file dialog crash issue on macOS.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import traceback

def test_file_dialogs():
    """Test different file dialog configurations to identify the problematic one."""
    
    root = tk.Tk()
    root.title("File Dialog Crash Test")
    root.geometry("400x300")
    
    results = []
    
    def test_dialog_1():
        """Test basic file dialog."""
        try:
            print("Testing basic filedialog.askopenfilename()...")
            file_path = filedialog.askopenfilename()
            print(f"✅ Basic dialog worked: {file_path}")
            results.append("✅ Basic dialog: PASSED")
        except Exception as e:
            print(f"❌ Basic dialog failed: {e}")
            results.append(f"❌ Basic dialog: FAILED - {e}")
            traceback.print_exc()
    
    def test_dialog_2():
        """Test dialog with CSV filetypes."""
        try:
            print("Testing CSV filetypes...")
            file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            print(f"✅ CSV dialog worked: {file_path}")
            results.append("✅ CSV dialog: PASSED")
        except Exception as e:
            print(f"❌ CSV dialog failed: {e}")
            results.append(f"❌ CSV dialog: FAILED - {e}")
            traceback.print_exc()
    
    def test_dialog_3():
        """Test dialog with tar.zst filetypes."""
        try:
            print("Testing TAR.ZST filetypes...")
            file_path = filedialog.askopenfilename(filetypes=[("TAR.ZST files", "*.tar.zst")])
            print(f"✅ TAR.ZST dialog worked: {file_path}")
            results.append("✅ TAR.ZST dialog: PASSED")
        except Exception as e:
            print(f"❌ TAR.ZST dialog failed: {e}")
            results.append(f"❌ TAR.ZST dialog: FAILED - {e}")
            traceback.print_exc()
    
    def test_dialog_4():
        """Test dialog with multiple filetypes."""
        try:
            print("Testing multiple filetypes...")
            file_path = filedialog.askopenfilename(
                filetypes=[("TAR.ZST files", "*.tar.zst"), ("All files", "*")]
            )
            print(f"✅ Multiple types dialog worked: {file_path}")
            results.append("✅ Multiple types dialog: PASSED")
        except Exception as e:
            print(f"❌ Multiple types dialog failed: {e}")
            results.append(f"❌ Multiple types dialog: FAILED - {e}")
            traceback.print_exc()
    
    def test_dialog_5():
        """Test dialog with parent parameter."""
        try:
            print("Testing dialog with parent...")
            file_path = filedialog.askopenfilename(
                parent=root,
                title="Test Dialog",
                filetypes=[("All files", "*")]
            )
            print(f"✅ Parent dialog worked: {file_path}")
            results.append("✅ Parent dialog: PASSED")
        except Exception as e:
            print(f"❌ Parent dialog failed: {e}")
            results.append(f"❌ Parent dialog: FAILED - {e}")
            traceback.print_exc()
    
    def show_results():
        """Show test results."""
        result_text = "\n".join(results)
        messagebox.showinfo("Test Results", f"File Dialog Test Results:\n\n{result_text}")
        print("\n" + "="*50)
        print("FINAL RESULTS:")
        print("="*50)
        for result in results:
            print(result)
    
    # Create test buttons
    tk.Label(root, text="File Dialog Crash Test", font=("Arial", 16, "bold")).pack(pady=10)
    tk.Label(root, text="Click each button to test different dialog configurations").pack(pady=5)
    
    tk.Button(root, text="1. Test Basic Dialog", command=test_dialog_1, width=30).pack(pady=2)
    tk.Button(root, text="2. Test CSV Dialog", command=test_dialog_2, width=30).pack(pady=2)
    tk.Button(root, text="3. Test TAR.ZST Dialog", command=test_dialog_3, width=30).pack(pady=2)
    tk.Button(root, text="4. Test Multiple Types", command=test_dialog_4, width=30).pack(pady=2)
    tk.Button(root, text="5. Test With Parent", command=test_dialog_5, width=30).pack(pady=2)
    
    tk.Label(root, text="").pack(pady=5)  # Spacer
    tk.Button(root, text="Show Results", command=show_results, width=30, bg="lightblue").pack(pady=5)
    
    print("File Dialog Crash Test Started")
    print("Click the buttons to test different dialog configurations")
    print("Close each dialog that opens (or press Cancel)")
    
    root.mainloop()

if __name__ == "__main__":
    test_file_dialogs()
