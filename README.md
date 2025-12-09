# Apple Music Play History Converter

![Apple Music Play History Converter](images/aphc_logo.png)

![Version 2.0.3 built with Toga/Briefcase](images/screenshot-v5.png)

A modern desktop application that converts Apple Music play history CSV files into Last.fm and Universal Scrobbler compatible format.

> **New in v2.0.3**: Major matching algorithm improvements with new MusicBrainz optimizer, and comprehensive documentation. [See what's new](#whats-new-in-v203)

## Features

- **Multi-Format Support**: Works with "Play Activity", "Recently Played Tracks", and "Play History Daily Tracks" CSV files
- **Three Search Providers**:
  - **MusicBrainz (Local DB)**: Offline database (~2GB) with 10,000+ tracks/sec search speed
  - **MusicBrainz API (Online)**: Direct API access with 1 req/sec rate limit (no database download needed)
  - **iTunes API**: Online fallback with adaptive rate limiting (20-120 req/min)
- **Ultra-Fast Processing**: Batch processing handles large files 100x faster than previous versions
- **Live Progress Tracking**: Real-time updates showing exactly what's happening during searches
- **Smart Auto-Save**: Automatic checkpoints every 50 tracks protect your progress
- **Rate-Limited Track Management**: Separate retry and export system for iTunes 403 rate limit errors
  - Retry button for tracks that hit rate limits
  - Export rate-limited tracks to CSV for manual review
  - Smart separation of temporary (rate-limited) vs permanent failures
- **Cross-Platform**: Native apps for Windows, macOS, and Linux
- **100% Local Processing**: Your music data never leaves your computer

## Quick Start

### Download & Install

**No Python required.** Download the ready-to-run app for your platform:

#### macOS (Universal Binary)
**[Download Apple Music History Converter-2.0.3.dmg](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest)**

**Fully signed and notarized** by Apple Developer ID
**No security warnings**, opens immediately
**Works on Apple Silicon (M1/M2/M3) and Intel Macs**

**Installation:**
1. Download the DMG file
2. Open the DMG and drag the app to your Applications folder
3. Double-click to run, no configuration needed

---

#### Windows (MSI Installer)
**[Download Apple-Music-History-Converter-2.0.3.msi](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest)**

**Professional MSI installer**
**No Python installation required**
**Works on Windows 10 and Windows 11**

**Installation:**
1. Download the MSI file
2. Double-click to install
3. App appears in Start Menu: "Apple Music History Converter"

---

#### Linux (Compile from Source)
**No pre-built binaries available**, Linux users must compile from source

**Installation:**
```bash
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter
pip install -r requirements.txt
python run_toga_app.py
```

**Requirements:**
- Python 3.12+
- GTK 3 development libraries
- See [Linux Build Guide](../../wiki/Linux-Installation) for distribution-specific instructions

### Run from Source

```bash
git clone https://github.com/nerveband/Apple-Music-Play-History-Converter.git
cd Apple-Music-Play-History-Converter
pip install -r requirements.txt
python run_toga_app.py
```

## Usage

1. **Select your CSV file** from Apple Music
2. **Choose search provider**:
   - MusicBrainz (recommended for large files, requires 2GB database download)
   - iTunes API (slower but works immediately)
3. **Click "Search for Missing Artists"** to find missing artist information
4. **Save** the converted CSV file for Last.fm or Universal Scrobbler

## Artist Matching: What to Expect

The app achieves **** on typical music libraries, but some tracks may not match correctly. Here's what you should know:

### What Works Well
- **Popular music**: Mainstream tracks match instantly (The Weeknd, Taylor Swift, etc.)
- **Albums you've listened to completely**: The app detects album "sessions" and applies consistent artist credits
- **Tracks with artist info in your CSV**: When Apple provides artist names, matching is highly accurate

### What May Not Match
| Scenario | Why It Happens | Workaround |
|----------|----------------|------------|
| **Generic titles** ("Intro", "Home", "Escape") | Many artists have songs with these names | App needs artist hint from your CSV |
| **Japanese/Korean/non-Latin text** | Different romanizations exist | iTunes API often works better |
| **Typos in your data** ("fuckk" vs "fuck") | Exact matching fails | iTunes API handles fuzzy matching |
| **Obscure indie releases** | Not in MusicBrainz database | Try iTunes API or manual entry |
| **Soundtracks** ("Scott Pilgrim", video game music) | Often missing from databases | iTunes API usually finds these |
| **Classical music** with movement numbers | Naming conventions vary wildly | May require manual correction |
| **Mashups/medleys** | Combined tracks don't exist as single entries | Usually won't match |

### Tips for Best Results
1. **Use MusicBrainz first** - it's fast and handles most tracks
2. **Use iTunes API for leftovers** - it has better fuzzy matching but is rate-limited
3. **Review your results** - spot-check the output before importing to Last.fm
4. **Export failures for manual review** - use the "Export Missing" button

For technical details on how matching works, see:
- [Matching Algorithm Wiki](../../wiki/Matching-Algorithm) - Full technical documentation
- [MusicBrainz Matching Algorithm](docs/MUSICBRAINZ_MATCHING_ALGORITHM.md) - Database and search details

## What's New in v2.0.3

### Enhanced Matching Algorithm 

- **Improved artist matching**: New scoring system prioritizes established tracks over covers
- **Edge case handling**: Better detection of generic titles ("Intro", "Home") and short titles
- **Unicode normalization**: Handles curly quotes, apostrophe variants, and special characters (A$AP, Ke$ha)
- **Artist tokenization**: Properly handles collaborations ("feat.", "&", "with", "vs")
- **Phonetic matching**: Soundex-based matching for artist name misspellings (Jon/John, Smith/Smyth)
- **Album-session alignment**: Consecutive tracks from same album get consistent artist credits

### New MusicBrainz Optimizer

- **Background optimization**: Database optimization runs without blocking the UI
- **Progress tracking**: Real-time progress updates during optimization
- **Memory efficiency**: Optimized for systems with 4GB+ RAM

### Hardware-Adaptive Performance Modes

The app now automatically detects your system's capabilities and adjusts its optimization strategy:

| Mode | Requirements | What It Does |
|------|--------------|--------------|
| **Performance** | 8GB+ RAM, fast SSD | Full optimization with HOT/COLD tables and all indexes |
| **Efficiency** | 4GB RAM, any disk | Minimal schema for slower systems (tested on AWS t2.medium) |

- **Automatic detection**: Probes RAM, CPU cores, and disk speed at startup
- **Works on budget hardware**: Efficiency mode tested on AWS t2.medium (2 vCPUs, 4GB RAM, slow EBS)
- **No configuration needed**: The app picks the right mode automatically

### Code Quality & Performance

- **Dead code removal**: Cleaned up legacy debug scripts and unused code
- **Windows compatibility**: Fixed console encoding issues with emojis (replaced with ASCII indicators)
- **Test suite**: 204 tests passing with comprehensive coverage
- **Documentation**: New [Matching Algorithm](docs/MUSICBRAINZ_MATCHING_ALGORITHM.md) technical documentation

### Previous Release (v2.0.2)

## What's New in v2.0.2

### Critical macOS Exit Crash Fixed

- **Toga/Rubicon GIL Crash Resolved**: Eliminated fatal Python GIL crash that occurred when quitting the app on macOS
  - Crash occurred in Toga's event loop shutdown during `NSApplication.terminate()`
  - Implemented proper cleanup sequence with `os._exit()` workaround for framework limitation
  - Replaced asyncio's default executor with tracked custom executor for proper shutdown
  - Added threading.Event for interruptible sleeps in rate limiting code
  - All ThreadPoolExecutors now properly tracked and shut down before exit
  - App now quits cleanly every time without "Abort trap 6" errors
  - See `TOGA_EXIT_CRASH_WORKAROUND.md` for complete technical documentation

### Comprehensive Documentation

- **Build & Release Guide**: Complete documentation in CLAUDE.md (983 lines added)
  - Step-by-step macOS build process with expected durations
  - Windows automated build workflow and monitoring commands
  - Complete release checklist (pre-release, release day, post-release)
  - Rollback procedures for handling bad releases
  - Common build issues and solutions table

- **Development Workflow**: Standard practices for future development
  - Branch strategy and naming conventions
  - Commit message standards (conventional commits)
  - Testing requirements with coverage goals
  - Code quality standards and review checklist
  - Feature development 6-phase workflow
  - Performance optimization guidelines
  - Debugging techniques for development and production

### v2.0.1 Previous Fixes

- **Search Resume Fixed**: Resolved "search already in progress" error that prevented resuming searches
- **Rate Limit Sleep Improved**: Replaced blocking 60-second sleeps with interruptible system

### v2.0 Major Features

- **100x Faster**: Batch processing with DuckDB replaces old row-by-row searches
- **Smart Rate Limiting**: Adaptive iTunes API rate limiting (20-120 req/min)
- **Live Updates**: See results as they arrive, not after everything completes
- **Never Freezes**: Fully async UI stays responsive during processing
- **Auto-Save**: Progress automatically saved every 50 tracks
- **Better Architecture**: Clean separation of UI and processing threads

### Technical Changes

- **Toga Framework**: Modern cross-platform native UI (replaces tkinter)
- **Thread-Safe**: Enhanced async/await patterns with comprehensive cleanup
- **DuckDB Backend**: Optimized MusicBrainz queries with vectorized pandas operations
- **Code Quality**: Removed 1,051 lines of dead code and legacy methods

[See full changelog](CHANGELOG.md)

## Documentation

- [Installation Guide](../../wiki/Installation)
- [User Guide](../../wiki/User-Guide)
- [MusicBrainz Database Setup](../../wiki/MusicBrainz-Database)
- [Building from Source](../../wiki/Building-from-Source)
- [Development Guide](../../wiki/Development)
- [Troubleshooting](../../wiki/Troubleshooting)

## System Requirements

### Minimum
- **RAM**: 4GB (iTunes API) or 8GB (MusicBrainz)
- **Storage**: 200MB app + 3GB for MusicBrainz database (optional)
- **OS**: macOS 10.13+, Windows 10+, or modern Linux

### Recommended
- **RAM**: 8GB or more
- **Storage**: SSD for faster database operations
- **Internet**: Broadband for database download

## Support

- **Issues**: [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
- **Wiki**: [Documentation](../../wiki)
- **Releases**: [Download Page](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases)

## License

MIT License - see [LICENSE](LICENSE) file for details

## Credits

Built with [BeeWare Toga](https://beeware.org/) • [Pandas](https://pandas.pydata.org/) • [DuckDB](https://duckdb.org/)

---

**Version 2.0.3** | [Changelog](CHANGELOG.md) | [Wiki](../../wiki) | [Report Issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
