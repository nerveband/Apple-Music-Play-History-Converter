# Tests Directory

This directory contains various test scripts for the Apple Music Play History Converter application.

## Test Categories

### Core Application Tests
- `test_app.py` - Basic application functionality tests
- `test_app_workflow.py` - Complete workflow tests  
- `test_full_integration.py` - Integration tests for all components

### Cross-Platform Compatibility
- `test_cross_platform.py` - Cross-platform compatibility tests
- `verify_compatibility.py` - Compatibility verification script

### MusicBrainz Database Tests
- `test_musicbrainz_build.py` - Database building tests
- `test_database_debug.py` - Database debugging utilities
- `test_csv_query_simulation.py` - CSV query simulation tests

### Import/Export Tests
- `test_manual_import.py` - Manual import functionality tests
- `test_manual_import_button.py` - Manual import UI tests
- `test_manual_import_fixes.py` - Import fixes verification
- `test_import_function.py` - Core import function tests
- `test_import_with_progress.py` - Import progress tracking tests

### Download/Extract Tests
- `test_download.py` - Download functionality tests
- `test_extract.py` - File extraction tests

### UI Tests  
- `test_ui_layout.py` - UI layout and component tests
- `test_dialog_crash.py` - Dialog crash testing and debugging

### Utility Tests
- `test_path_issue.py` - Path handling tests
- `manual_import_safe.py` - Safe manual import testing

## Running Tests

To run individual tests:
```bash
python tests/test_app.py
```

To run all tests:
```bash
python -m pytest tests/
```

## Notes

- Some tests require the MusicBrainz database to be available
- Cross-platform tests may behave differently on different operating systems
- UI tests may require a display (won't work in headless environments)
