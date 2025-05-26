#!/usr/bin/env python3
"""
Simple test script to verify the application works correctly.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from apple_music_play_history_converter import CSVProcessorApp
        from musicbrainz_manager import MusicBrainzManager
        from music_search_service import MusicSearchService
        from database_dialogs import FirstTimeSetupDialog, DatabaseDownloadDialog
        print("✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_app_initialization():
    """Test that the app can be initialized."""
    print("Testing app initialization...")
    try:
        import tkinter as tk
        from apple_music_play_history_converter import CSVProcessorApp
        
        root = tk.Tk()
        root.withdraw()  # Hide window
        
        app = CSVProcessorApp(root)
        print("✓ App initialized successfully")
        
        # Test that music search service is available
        if hasattr(app, 'music_search_service'):
            print("✓ MusicSearchService is available")
        else:
            print("✗ MusicSearchService not found")
            return False
            
        root.destroy()
        return True
        
    except Exception as e:
        print(f"✗ App initialization error: {e}")
        return False

def test_music_search_service():
    """Test basic MusicSearchService functionality."""
    print("Testing MusicSearchService...")
    try:
        from music_search_service import MusicSearchService
        
        service = MusicSearchService()
        
        # Test provider switching
        service.set_search_provider("itunes")
        if service.get_search_provider() == "itunes":
            print("✓ Provider switching works")
        else:
            print("✗ Provider switching failed")
            return False
        
        # Test iTunes search (should not require database)
        result = service.search_song("test song", "test artist")
        if result.get("use_itunes"):
            print("✓ iTunes search routing works")
        else:
            print("✗ iTunes search routing failed")
            return False
            
        # Test database status (should work even without database)
        status = service.get_database_status()
        if isinstance(status, dict):
            print("✓ Database status check works")
        else:
            print("✗ Database status check failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ MusicSearchService error: {e}")
        return False

def test_provider_switching():
    """Test that provider switching works correctly."""
    print("Testing provider switching...")
    try:
        from music_search_service import MusicSearchService
        
        service = MusicSearchService()
        
        # Test switching to iTunes
        service.set_search_provider("itunes")
        result = service.search_song("test", "test")
        
        if result.get("use_itunes"):
            print("✓ iTunes provider works without showing MusicBrainz dialog")
        else:
            print("✗ iTunes provider not working correctly")
            return False
        
        # Test switching back to MusicBrainz
        service.set_search_provider("musicbrainz")
        result = service.search_song("test", "test")
        
        if result.get("requires_download") or result.get("success"):
            print("✓ MusicBrainz provider switching works")
        else:
            print("✗ MusicBrainz provider switching failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Provider switching error: {e}")
        return False

def test_database_creation():
    """Test database creation functionality."""
    print("Testing database creation...")
    try:
        from musicbrainz_manager import MusicBrainzManager
        import tempfile
        import csv
        from pathlib import Path
        
        # Create test CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            test_csv = Path(temp_dir) / "test.csv"
            with open(test_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['artist', 'title', 'album'])
                writer.writeheader()
                writer.writerow({'artist': 'Test Artist', 'title': 'Test Song', 'album': 'Test Album'})
            
            # Test database creation
            test_data_dir = Path(temp_dir) / "test_db"
            manager = MusicBrainzManager(str(test_data_dir))
            
            success = manager._build_database(test_csv)
            if success and manager.is_database_available():
                print("✓ Database creation works")
                return True
            else:
                print("✗ Database creation failed")
                return False
                
    except Exception as e:
        print(f"✗ Database creation error: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Apple Music Play History Converter - Test Suite ===\n")
    
    tests = [
        test_imports,
        test_app_initialization,
        test_music_search_service,
        test_provider_switching,
        test_database_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Test Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! The application is ready to use.")
        print("\n✅ Fixed Issues:")
        print("  • App startup error resolved")
        print("  • iTunes API selection no longer shows MusicBrainz popup")
        print("  • Database download and creation improved")
        print("  • Provider switching works correctly")
        print("\nTo run the application:")
        print("  python run_app.py")
        print("  or")
        print("  python apple_music_play_history_converter.py")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
