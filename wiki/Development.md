# Development Guide

Comprehensive guide for developers contributing to Apple Music Play History Converter.

## Quick Start for Contributors

1. **Fork and clone** the repository
2. **Install dependencies** (`pip install -r requirements.txt`)
3. **Run the app** (`python run_toga_app.py`)
4. **Make changes** following our coding standards
5. **Test thoroughly** (`python -m pytest tests_toga/ -v`)
6. **Submit PR** with clear description

For detailed instructions, continue reading below.

## Development Environment Setup

### Prerequisites

**Required Software**:
- Python 3.8+ (3.12 recommended)
- Git for version control
- Code editor (VS Code or PyCharm recommended)

**Platform-Specific Requirements**:

**macOS**:
- Xcode Command Line Tools: `xcode-select --install`
- Homebrew (optional but recommended): `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

**Windows**:
- Microsoft C++ Build Tools (for compiling native extensions)
- Git for Windows

**Linux** (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install python3.12 python3-pip python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-webkit2-4.0 libgirepository1.0-dev git build-essential
```

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter

# 2. Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install development dependencies
pip install briefcase pytest pytest-cov black

# 5. Verify installation
python run_toga_app.py  # Should launch app
python -m pytest tests_toga/ -v  # Should pass all tests

# 6. Configure development settings (optional)
mkdir -p ~/.apple_music_converter
cat > ~/.apple_music_converter/settings.json <<EOF
{
  "logging": {
    "enabled": true,
    "file_logging": true,
    "console_logging": true,
    "level": "DEBUG"
  }
}
EOF
```

## Project Structure

```
Apple-Music-Play-History-Converter/
├── src/                        # Source code
│   └── apple_music_history_converter/
│       ├── app.py              # Briefcase entry point
│       ├── apple_music_play_history_converter.py  # Main UI (6,973 lines)
│       ├── music_search_service_v2.py  # Search routing
│       ├── musicbrainz_manager_v2.py   # MusicBrainz DB
│       ├── progress_dialog.py          # Toga dialogs
│       └── logging_config.py           # Centralized logging
├── tests_toga/                 # Test suite (44+ tests)
├── docs/                       # Documentation
├── wiki/                       # GitHub wiki (local copy)
├── images/                     # Screenshots and assets
├── build.py                    # Build helper script
├── run_toga_app.py             # Development entry point
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # AI assistant instructions
├── README.md                   # Main documentation
└── CHANGELOG.md                # Version history
```

## Development Workflow

### Branch Strategy

**Main Branches**:
- `main`: Production-ready code, always stable, all releases tagged from here
- `develop`: Integration branch (optional for team workflow)

**Feature Branches**:
```bash
# Create feature branch
git checkout -b feature/descriptive-name main

# Work on feature with incremental commits
git add <files>
git commit -m "feat: add [feature description]"

# Keep branch up to date
git fetch origin
git rebase origin/main

# Push feature branch
git push origin feature/descriptive-name

# Create pull request
gh pr create --title "Add [feature]" --body "Description..."
```

**Branch Naming Conventions**:
- `feature/description`: New features
- `fix/description`: Bug fixes
- `refactor/description`: Code refactoring
- `docs/description`: Documentation updates
- `test/description`: Test additions/fixes
- `hotfix/vX.Y.Z`: Critical production fixes

### Commit Message Standards

Follow conventional commits format:

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks (dependencies, build, release)
- `style`: Code style changes (formatting, no logic change)

**Examples**:
```bash
# Good commits
git commit -m "feat(csv): add support for Daily Tracks format"
git commit -m "fix(itunes): handle 403 rate limit errors gracefully"
git commit -m "perf(search): optimize MusicBrainz query with index"
git commit -m "docs(build): update macOS signing instructions"

# Multi-line commit
git commit -m "feat(search): add batch search optimization

- Implement parallel search for multiple tracks
- Add caching layer for repeated queries
- Reduce search time by 80% for large CSVs

Closes #123"
```

## Code Style and Standards

### Python Style Guide

Follow PEP 8 with these conventions:

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces (not tabs)
- **Quotes**: Double quotes for strings
- **Imports**: Grouped (stdlib, third-party, local), alphabetically sorted
- **Type hints**: Use where practical (function signatures)
- **Docstrings**: Required for public functions/classes

**Automatic formatting with Black**:
```bash
# Format all source code
black src/apple_music_history_converter/

# Check formatting without modifying
black --check src/

# Format specific file
black src/apple_music_history_converter/module.py
```

### Code Documentation

**Function docstring example**:
```python
def search_track(artist: str, track: str, provider: str = "musicbrainz") -> dict:
    """Search for a track using the specified music provider.

    Args:
        artist: Artist name to search for
        track: Track title to search for
        provider: Music provider to use ("musicbrainz" or "itunes")

    Returns:
        Dictionary containing track metadata:
        {
            "artist": str,
            "track": str,
            "album": str,
            "year": int,
            "mbid": str or None
        }

    Raises:
        ValueError: If provider is invalid
        RateLimitError: If API rate limit exceeded
        NetworkError: If network request fails

    Example:
        >>> result = search_track("The Beatles", "Hey Jude")
        >>> print(result["album"])
        "Hey Jude"
    """
    # Implementation...
```

### Code Review Checklist

Before submitting PR:

- [ ] All tests pass (`pytest tests_toga/ -v`)
- [ ] No debug print statements (use `logger` instead)
- [ ] No hardcoded paths or credentials
- [ ] Error handling for all external calls (API, file I/O, database)
- [ ] Type hints for function signatures
- [ ] Docstrings for public functions/classes
- [ ] No commented-out code blocks
- [ ] No `TODO` comments without GitHub issue reference
- [ ] Dependencies added to `pyproject.toml` if needed
- [ ] Performance tested for operations on large datasets

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests_toga/ -v

# Run specific test file
python -m pytest tests_toga/test_csv_processing.py -v

# Run with coverage report
python -m pytest tests_toga/ --cov=src/apple_music_history_converter --cov-report=html

# Run tests matching a pattern
python -m pytest tests_toga/ -k "test_csv" -v

# Run with verbose output
python -m pytest tests_toga/ -vv

# Stop on first failure
python -m pytest tests_toga/ -x
```

### Writing Tests

**Test structure**:
```python
# tests_toga/test_new_feature.py
import pytest
from apple_music_history_converter.module import function

class TestNewFeature:
    """Test the new feature implementation"""

    def test_basic_functionality(self):
        """Test basic use case"""
        result = function(input_data)
        assert result == expected_output

    def test_edge_case(self):
        """Test edge case handling"""
        with pytest.raises(ValueError):
            function(invalid_input)

    def test_performance(self):
        """Test performance requirements"""
        import time
        start = time.time()
        function(large_dataset)
        duration = time.time() - start
        assert duration < 1.0  # Should complete in <1 second
```

### Test Coverage Goals

- **Minimum**: 70% overall coverage
- **Target**: 80%+ coverage for business logic
- **Critical paths**: 100% coverage (CSV parsing, music search, export)

### Test Categories

1. **Unit Tests**: Test individual functions/methods
   - Location: `tests_toga/test_*.py`
   - Fast execution (<1 second per test)
   - No external dependencies (mock APIs, databases)

2. **Integration Tests**: Test component interactions
   - Test CSV parsing → music search → export
   - Test database download → optimization → search
   - May use real files/APIs with rate limiting

3. **UI Tests**: Test Toga UI components
   - Test button clicks, input validation
   - Test dialog flows
   - Use Toga's testing utilities

## Building and Packaging

### Local Development Build

```bash
# Run directly from source (fastest for development)
python run_toga_app.py

# Or use Briefcase development mode
briefcase dev
```

### Platform Builds

**macOS**:
```bash
# Clean previous builds
python build.py clean

# Create app scaffold
python build.py create  # ~1-3 minutes

# Build app bundle
python build.py build  # ~30 seconds

# Sign and package (requires Apple Developer ID)
briefcase package --identity "Developer ID Application: Your Name (TEAMID)"
# Output: dist/Apple Music History Converter-X.Y.Z.dmg
```

**Windows** (automated via GitHub Actions):
```bash
# Automatic build on tag push
git tag v2.0.3
git push origin v2.0.3
# GitHub Actions builds MSI automatically

# Or trigger manual build
gh workflow run build-windows.yml
```

**Linux** (manual compilation):
```bash
briefcase create linux app
briefcase build linux app
briefcase package linux app --adhoc-sign
```

For complete build instructions, see [Building from Source](Building-from-Source) and `CLAUDE.md`.

## Debugging

### Enable Debug Logging

Edit `~/.apple_music_converter/settings.json`:
```json
{
  "logging": {
    "enabled": true,
    "file_logging": true,
    "console_logging": true,
    "level": "DEBUG"
  }
}
```

### View Logs

**macOS**:
```bash
# View live logs
tail -f ~/Library/Logs/AppleMusicConverter/apple_music_converter.log

# View all logs
ls -lt ~/Library/Logs/AppleMusicConverter/
```

**Windows**:
```cmd
# View current log
notepad %LOCALAPPDATA%\AppleMusicConverter\Logs\apple_music_converter.log
```

### Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use IDE debugger (VS Code, PyCharm)
```

### Performance Profiling

```bash
# CPU profiling
python -m cProfile -o profile.stats run_toga_app.py

# Analyze results
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"

# Memory profiling
pip install memory_profiler
python -m memory_profiler script.py
```

## Architecture Overview

### Core Components

**app.py**: Briefcase entry point
- Initializes Toga application
- Sets up main window
- Handles app lifecycle

**apple_music_play_history_converter.py**: Main UI (6,973 lines)
- Toga-based user interface
- CSV file processing
- Search coordination
- Progress tracking
- Export functionality

**music_search_service_v2.py**: Search routing
- Routes lookups between MusicBrainz and iTunes
- Handles fallback logic
- Rate limiting management
- Result caching

**musicbrainz_manager_v2.py**: MusicBrainz database
- DuckDB database management
- Optimized search indices
- Batch query processing
- Database download and optimization

**progress_dialog.py**: Progress UI
- HIG-compliant Toga dialogs
- Real-time progress updates
- Pause/resume functionality

**logging_config.py**: Centralized logging
- SmartLogger system with feature flags
- Zero-overhead when disabled
- Dual output (file and console)
- Thread-safe operation

### Data Flow

1. **CSV Loading**: User selects CSV file
   - Auto-detect format (Play Activity, Recently Played, Daily Tracks)
   - Parse with pandas (chunked for large files)
   - Extract artist/track information

2. **Music Search**: Find artist/track metadata
   - Route through MusicSearchServiceV2
   - Try MusicBrainz first (if available)
   - Fall back to iTunes API if needed
   - Cache results to avoid duplicate queries

3. **Progress Tracking**: Real-time updates
   - Background thread for processing
   - Queue-based communication with UI
   - Auto-save checkpoints every 50 tracks

4. **Export**: Generate Last.fm compatible CSV
   - Calculate reverse-chronological timestamps
   - Format artist, track, album, timestamp columns
   - Save to user-specified location

### Threading Model

**UI Thread**: Toga main loop
- Handles user interactions
- Updates UI elements
- Non-blocking async/await

**Background Threads**: Processing tasks
- CSV parsing (pandas chunks)
- Music searches (parallel workers for iTunes)
- Database queries (DuckDB connection pool)
- File I/O operations

**Thread Safety**:
- Queue-based communication (UI ← background)
- Proper async/await with tracked executors
- threading.Event for interruptible sleeps
- Clean shutdown sequence with os._exit()

## Common Development Tasks

### Adding New CSV Format Support

1. Update format detection in `detect_file_type()`:
```python
def detect_file_type(df: pd.DataFrame, filename: str) -> str:
    # Add detection logic
    if "New Column Name" in df.columns:
        return "new_format_type"
```

2. Add column mapping in `process_csv_data()`:
```python
if file_type == "new_format_type":
    df_renamed = df.rename(columns={
        "New Artist Column": "artist",
        "New Track Column": "track"
    })
```

3. Add tests in `tests_toga/test_csv_processing.py`

### Adding New Search Provider

1. Create provider manager class:
```python
class NewProviderManager:
    def search_track(self, artist: str, track: str) -> dict:
        # Implementation
        pass
```

2. Integrate in `MusicSearchServiceV2`:
```python
if self.provider == "new_provider":
    return self.new_provider_manager.search_track(artist, track)
```

3. Add UI controls for provider selection
4. Add tests for new provider
5. Update documentation

### Modifying UI Layout

1. All UI uses Toga's Pack layout system
2. Reference existing layouts in `apple_music_play_history_converter.py`
3. Use `toga.Box` with Pack styling
4. Test on all platforms (macOS, Windows, Linux)

Example:
```python
# Create layout container
box = toga.Box(style=Pack(direction=COLUMN, padding=10))

# Add widgets
label = toga.Label("Text", style=Pack(padding=(0, 5)))
button = toga.Button("Click", on_press=self.handler, style=Pack(padding=5))

box.add(label)
box.add(button)
```

## Performance Optimization

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| CSV parsing (10k rows) | <5s | Use pandas chunking |
| MusicBrainz search | <5ms | DuckDB indexed search |
| iTunes API search | <200ms | Network dependent |
| Database optimization | <5min | Download + build indices |
| App startup time | <3s | Cold start |

### Optimization Checklist

- [ ] Use pandas chunking for large CSV files (`chunksize=10000`)
- [ ] Batch database queries instead of N+1 queries
- [ ] Use DuckDB indices for frequently queried columns
- [ ] Cache expensive computations (`functools.lru_cache`)
- [ ] Use threading for I/O-bound tasks (API calls, file I/O)
- [ ] Use async/await for Toga UI to prevent blocking
- [ ] Profile before optimizing (don't guess bottlenecks)
- [ ] Benchmark before and after changes

### Profiling Tools

```python
# Time a function
import time
start = time.perf_counter()
result = expensive_function()
print(f"Took {time.perf_counter() - start:.3f}s")

# Memory usage
import psutil
process = psutil.Process()
print(f"RAM: {process.memory_info().rss / 1024**2:.1f} MB")

# CPU profiling
python -m cProfile -s cumulative script.py
```

## Contributing Guidelines

### Before You Start

1. **Check existing issues**: Avoid duplicate work
2. **Discuss major changes**: Open an issue first for big features
3. **Read CLAUDE.md**: Comprehensive technical documentation
4. **Review recent PRs**: Understand current development patterns

### Pull Request Process

1. **Fork and branch**:
   ```bash
   git checkout -b feature/my-feature main
   ```

2. **Make changes**:
   - Follow code style guidelines
   - Add tests for new functionality
   - Update documentation

3. **Test thoroughly**:
   ```bash
   python -m pytest tests_toga/ -v
   black --check src/
   ```

4. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add new feature

   - Detailed change 1
   - Detailed change 2

   Closes #123"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/my-feature
   gh pr create --title "Add new feature" --body "Description"
   ```

6. **Address review feedback**:
   - Make requested changes
   - Push updates to same branch
   - PR updates automatically

### Code Review Guidelines

**For Contributors**:
- Be open to feedback
- Ask questions if unclear
- Update PR based on comments
- Be patient with review process

**For Reviewers**:
- Be constructive and respectful
- Explain "why" behind suggestions
- Approve when meets standards
- Merge when ready

## Getting Help

### Documentation

- **CLAUDE.md**: Complete technical documentation (2,000+ lines)
- **User Guide**: [User-Guide](User-Guide) - End-user instructions
- **This Guide**: Developer-focused information
- **Code Comments**: Inline documentation in source

### Support Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Code Review**: Ask questions in PR comments

### Key Contacts

- **Project Maintainer**: nerveband (GitHub)
- **Issues**: [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)

## Release Process

See [CLAUDE.md](../CLAUDE.md) for complete release documentation including:

- Version management (3 locations to update)
- macOS build process (clean, create, build, sign, notarize)
- Windows automated builds (GitHub Actions)
- Release checklist (pre-release, release day, post-release)
- Rollback procedures

**Quick summary**:
1. Update version in `pyproject.toml` (3 locations)
2. Build and sign macOS DMG
3. Commit and tag: `git tag v2.0.3 && git push origin v2.0.3`
4. GitHub Actions builds Windows MSI automatically
5. Create GitHub release with both installers

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/nerveband/Apple-Music-Play-History-Converter/blob/main/LICENSE) file for details.

## Credits

Built with:
- [BeeWare Toga](https://beeware.org/) - Cross-platform Python UI
- [Pandas](https://pandas.pydata.org/) - Data processing
- [DuckDB](https://duckdb.org/) - Fast analytical database
- [MusicBrainz](https://musicbrainz.org/) - Open music encyclopedia

---

**Last Updated**: October 2025 | **Version**: 2.0.2

**Questions?** → [Open an Issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues/new) | [Start a Discussion](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)
