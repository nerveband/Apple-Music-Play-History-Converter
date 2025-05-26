#!/usr/bin/env python3
"""
Test build environment for Apple Music Play History Converter
Verifies all dependencies and imports work correctly before building
"""

import sys
import importlib
import platform
from pathlib import Path

def test_python_version():
    """Test Python version compatibility"""
    print(f"🐍 Python version: {sys.version}")
    version_info = sys.version_info
    
    if version_info.major != 3 or version_info.minor < 8:
        print("❌ Python 3.8+ required")
        return False
    else:
        print("✅ Python version compatible")
        return True

def test_required_modules():
    """Test if all required modules can be imported"""
    print("\n📦 Testing required modules...")
    
    required_modules = [
        ("tkinter", "tkinter"),
        ("pandas", "pandas"),
        ("requests", "requests"),
        ("sv_ttk", "sv-ttk"),
        ("zstandard", "zstandard"),
        ("duckdb", "duckdb"),
        ("PyInstaller", "pyinstaller"),
    ]
    
    all_good = True
    
    for module_name, package_name in required_modules:
        try:
            importlib.import_module(module_name)
            print(f"✅ {module_name} - OK")
        except ImportError:
            print(f"❌ {module_name} - MISSING (install with: pip install {package_name})")
            all_good = False
            
    return all_good

def test_project_modules():
    """Test if project modules can be imported"""
    print("\n🔧 Testing project modules...")
    
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    project_modules = [
        "apple_music_play_history_converter",
        "musicbrainz_manager",
        "music_search_service", 
        "database_dialogs",
        "progress_dialog"
    ]
    
    all_good = True
    
    for module in project_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - FAILED: {e}")
            all_good = False
            
    return all_good

def test_build_tools():
    """Test PyInstaller and build tools"""
    print("\n🔨 Testing build tools...")
    
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__} - OK")
        return True
    except ImportError:
        print("❌ PyInstaller - MISSING (install with: pip install pyinstaller)")
        return False

def test_file_structure():
    """Test required files and directories exist"""
    print("\n📁 Testing file structure...")
    
    project_root = Path(__file__).parent.parent
    required_files = [
        "apple_music_play_history_converter.py",
        "requirements.txt",
        "musicbrainz_manager.py",
        "music_search_service.py",
        "database_dialogs.py",
        "progress_dialog.py"
    ]
    
    build_files = [
        "build_artifacts/build_macos.spec",
        "build_artifacts/build_windows.spec", 
        "build_artifacts/build_linux.spec"
    ]
    
    all_good = True
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path} - OK")
        else:
            print(f"❌ {file_path} - MISSING")
            all_good = False
            
    for file_path in build_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path} - OK")
        else:
            print(f"❌ {file_path} - MISSING")
            all_good = False
            
    return all_good

def main():
    """Run all tests"""
    print("🧪 Testing build environment for Apple Music Play History Converter")
    print("=" * 60)
    
    print(f"🖥️  Platform: {platform.system()} {platform.release()}")
    print(f"🏗️  Architecture: {platform.machine()}")
    
    tests = [
        ("Python Version", test_python_version),
        ("Required Modules", test_required_modules),
        ("Project Modules", test_project_modules),
        ("Build Tools", test_build_tools),
        ("File Structure", test_file_structure),
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! Build environment is ready.")
        print("🚀 You can now run the build scripts:")
        print("   • macOS: ./build_artifacts/build_macos.sh")
        print("   • Windows: build_artifacts\\build_windows.bat")
        print("   • Linux: ./build_artifacts/build_linux.sh")
        print("   • All platforms: python build_artifacts/build_all.py")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above before building.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
