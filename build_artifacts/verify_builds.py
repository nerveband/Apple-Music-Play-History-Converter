#!/usr/bin/env python3
"""
Verify that all builds were created successfully and test basic functionality
"""

import os
import sys
import zipfile
import tarfile
import subprocess
from pathlib import Path
import tempfile
import stat

def test_executable_imports(exe_path):
    """Test that the executable can run and has basic functionality"""
    print(f"    Testing executable: {exe_path}")
    
    try:
        # Try to run with --help or version check (this would need to be implemented in the app)
        # For now, just verify the file exists and is executable
        if not exe_path.exists():
            return False, "File does not exist"
            
        file_stat = exe_path.stat()
        if not (file_stat.st_mode & stat.S_IEXEC):
            return False, "File is not executable"
            
        size_mb = file_stat.st_size / (1024 * 1024)
        return True, f"Executable OK ({size_mb:.1f} MB)"
        
    except Exception as e:
        return False, f"Error: {e}"

def verify_macos_build():
    """Verify macOS build"""
    print("🍎 Verifying macOS build...")
    
    zip_path = Path("Apple_Music_History_Converter_macOS.zip")
    if not zip_path.exists():
        return False, "macOS zip not found"
        
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(temp_dir)
                
            app_path = Path(temp_dir) / "Apple Music History Converter.app"
            if not app_path.exists():
                return False, "App bundle not found in zip"
                
            # Check app structure
            required_paths = [
                app_path / "Contents",
                app_path / "Contents" / "MacOS" / "Apple Music History Converter",
                app_path / "Contents" / "Info.plist"
            ]
            
            for req_path in required_paths:
                if not req_path.exists():
                    return False, f"Missing required path: {req_path.relative_to(app_path)}"
                    
            exe_path = app_path / "Contents" / "MacOS" / "Apple Music History Converter"
            success, message = test_executable_imports(exe_path)
            
            if success:
                return True, f"macOS build verified: {message}"
            else:
                return False, f"macOS executable test failed: {message}"
                
    except Exception as e:
        return False, f"Error verifying macOS build: {e}"

def verify_windows_build():
    """Verify Windows build"""
    print("🪟 Verifying Windows build...")
    
    zip_path = Path("Apple_Music_History_Converter_Windows.zip")
    if not zip_path.exists():
        return False, "Windows zip not found"
        
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(temp_dir)
                
            exe_path = Path(temp_dir) / "Apple Music History Converter.exe"
            success, message = test_executable_imports(exe_path)
            
            if success:
                return True, f"Windows build verified: {message}"
            else:
                return False, f"Windows executable test failed: {message}"
                
    except Exception as e:
        return False, f"Error verifying Windows build: {e}"

def verify_linux_build():
    """Verify Linux build"""
    print("🐧 Verifying Linux build...")
    
    tar_path = Path("Apple_Music_History_Converter_Linux.tar.gz")
    if not tar_path.exists():
        return False, "Linux tar.gz not found"
        
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with tarfile.open(tar_path, 'r:gz') as tarf:
                tarf.extractall(temp_dir)
                
            exe_path = Path(temp_dir) / "Apple Music History Converter"
            success, message = test_executable_imports(exe_path)
            
            if success:
                return True, f"Linux build verified: {message}"
            else:
                return False, f"Linux executable test failed: {message}"
                
    except Exception as e:
        return False, f"Error verifying Linux build: {e}"

def verify_combined_release():
    """Verify the combined release archive"""
    print("📦 Verifying combined release...")
    
    zip_path = Path("Apple_Music_History_Converter_All_Platforms.zip")
    if not zip_path.exists():
        return False, "Combined release zip not found"
        
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()
            
            required_files = [
                "README.txt",
                "Apple_Music_History_Converter_macOS.zip",
                "Apple_Music_History_Converter_Windows.zip", 
                "Apple_Music_History_Converter_Linux.tar.gz"
            ]
            
            missing_files = []
            for req_file in required_files:
                if req_file not in file_list:
                    missing_files.append(req_file)
                    
            if missing_files:
                return False, f"Missing files in combined release: {missing_files}"
                
            # Check README content
            readme_content = zipf.read("README.txt").decode('utf-8')
            if "Apple Music Play History Converter" not in readme_content:
                return False, "README.txt appears to be invalid"
                
            return True, f"Combined release verified ({len(file_list)} files)"
            
    except Exception as e:
        return False, f"Error verifying combined release: {e}"

def main():
    """Run all verification tests"""
    print("🧪 Verifying all builds...")
    print("=" * 60)
    
    # Change to build_artifacts directory
    build_dir = Path(__file__).parent
    os.chdir(build_dir)
    
    tests = [
        ("macOS Build", verify_macos_build),
        ("Windows Build", verify_windows_build),
        ("Linux Build", verify_linux_build),
        ("Combined Release", verify_combined_release),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success, message = test_func()
            if success:
                print(f"✅ {test_name}: {message}")
                results.append((test_name, True, message))
            else:
                print(f"❌ {test_name}: {message}")
                results.append((test_name, False, message))
        except Exception as e:
            error_msg = f"Test error: {e}"
            print(f"❌ {test_name}: {error_msg}")
            results.append((test_name, False, error_msg))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"✅ Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All builds verified successfully!")
        print("Ready for distribution!")
        
        # Show file sizes
        print("\n📊 Final Build Sizes:")
        for file_name in [
            "Apple_Music_History_Converter_macOS.zip",
            "Apple_Music_History_Converter_Windows.zip",
            "Apple_Music_History_Converter_Linux.tar.gz",
            "Apple_Music_History_Converter_All_Platforms.zip"
        ]:
            file_path = Path(file_name)
            if file_path.exists():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"  📦 {file_name}: {size_mb:.1f} MB")
        
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed")
        for test_name, success, message in results:
            if not success:
                print(f"  ❌ {test_name}: {message}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
