# Toga Test Suite

This directory contains tests for the Toga-based Apple Music History Converter.

## Purpose

These tests verify:
1. **Security Fixes** - Shell injection prevention
2. **Core Functionality** - File type detection, CSV processing
3. **Cross-Platform Support** - Path handling, subprocess usage
4. **Data Safety** - Input validation, sanitization

## Running Tests

### Install Test Dependencies

```bash
pip install pytest pytest-asyncio
```

### Run All Tests

```bash
cd /path/to/Apple-Music-Play-History-Converter
pytest tests_toga/ -v
```

### Run Specific Test Files

```bash
# Security tests only
pytest tests_toga/test_security.py -v

# Basic functionality tests
pytest tests_toga/test_basic_functionality.py -v
```

### Run Specific Test

```bash
pytest tests_toga/test_security.py::TestShellInjectionPrevention::test_no_shell_execution_with_user_input -v
```

## Test Coverage

### ✅ Implemented Tests

**Security (test_security.py):**
- ✅ Shell injection prevention
- ✅ Subprocess with shell=False
- ✅ Path validation
- ✅ Input validation
- ✅ CSV special character handling
- ✅ File system safety

**Basic Functionality (test_basic_functionality.py):**
- ✅ File type detection
- ✅ CSV processing
- ✅ Security verification (no os.system)
- ✅ Data normalization
- ✅ Cross-platform path handling

### 📋 Planned Tests (Future)

**Async Processing:**
- [ ] CSV loading with executors
- [ ] Background task execution
- [ ] UI responsiveness during processing
- [ ] Pause/resume functionality

**Music Search:**
- [ ] MusicBrainz search
- [ ] iTunes API search with rate limiting
- [ ] Provider fallback
- [ ] Missing artist detection

**Integration:**
- [ ] Full conversion workflow
- [ ] Export to CSV
- [ ] Settings persistence
- [ ] Database management

## Test Philosophy

These tests focus on:
1. **Non-GUI Testing**: Tests run without launching Toga UI
2. **Security First**: Verify vulnerabilities are fixed
3. **Fast Execution**: Tests should complete in seconds
4. **Isolated**: Each test is independent
5. **Cross-Platform**: Tests work on macOS, Windows, Linux

## Notes

- Tests use pytest fixtures for temporary files
- No actual Toga app instance created (would require GUI)
- Tests verify source code directly for some checks
- Large file tests create 1000-row CSVs for chunking verification

## Continuous Integration

These tests are designed to run in CI/CD:
- No GUI required
- Fast execution
- Cross-platform compatible
- Exit codes indicate pass/fail

## Future Enhancements

1. **Async Test Support**: Add pytest-asyncio for async method testing
2. **Mock Toga Widgets**: Create mocks for UI testing without GUI
3. **Performance Tests**: Benchmark CSV processing speed
4. **Memory Tests**: Verify memory usage stays reasonable
5. **Integration Tests**: Full workflow from file selection to export
