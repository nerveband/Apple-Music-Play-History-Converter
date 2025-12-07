# Apple Music Play History Converter Wiki

Welcome to the Apple Music Play History Converter documentation!

## Quick Start

New to the app? Start here:

1. **[Installation](Installation)** - Download and install (5 minutes)
2. **[User Guide](User-Guide)** - Learn how to use the app (10 minutes)
3. **[MusicBrainz Database](MusicBrainz-Database)** - Optional: Setup offline database for 100x faster searches

## Documentation

### For Users

- **[User Guide](User-Guide)** - Complete step-by-step usage instructions
- **[Installation](Installation)** - Download, install, and first launch
- **[FAQ](FAQ)** - Quick answers to common questions
- **[Troubleshooting](Troubleshooting)** - Solve problems and errors
- **[MusicBrainz Database](MusicBrainz-Database)** - Setup offline search database (recommended for large files)

### For Developers

- **[Development Guide](Development)** - Contributing to the project
- **[Building from Source](Building-from-Source)** - Compile the app yourself
- **[Matching Algorithm](Matching-Algorithm)** - Technical details of the MusicBrainz matching algorithm
- **[CLAUDE.md](https://github.com/nerveband/Apple-Music-Play-History-Converter/blob/main/CLAUDE.md)** - Comprehensive technical documentation

## What is This Tool?

Apple Music Play History Converter transforms your Apple Music CSV export files into a format compatible with Last.fm and Universal Scrobbler, allowing you to:

- **Import your complete Apple Music listening history into Last.fm**
- **Preserve your scrobble history** when switching music services
- **Analyze your music listening habits** with structured data
- **Process large CSV files** (100,000+ tracks) efficiently and reliably

## Version 2.0.2 Highlights

The latest release includes critical stability improvements:

### Critical Fixes
- **macOS Exit Crash Fixed** - Eliminated GIL crash when quitting the app
- **Proper thread cleanup** with tracked executors and interruptible sleeps
- **Clean exit every time** - No more "Abort trap 6" errors

### New Features
- **Three search providers**:
  - MusicBrainz (Local DB) - Offline, 10,000+ tracks/sec, requires 2GB download
  - MusicBrainz API (Online) - Direct API access, 1 req/sec, no download needed
  - iTunes API - Online fallback, adaptive rate limiting (20-120 req/min)
- **Windows builds automated** via GitHub Actions
- **Comprehensive documentation** (983 lines) covering build practices and development workflow
- **Rate-limited track management** with retry and export features
- **Live progress updates** as searches complete
- **Modern Toga UI** that never freezes
- **Auto-save checkpoints** every 50 tracks
- **Cross-platform native apps** for Windows, macOS, and Linux

### Technical Improvements
- **Pure Toga framework** - No tkinter dependencies
- **Thread-safe architecture** - Proper async/await patterns
- **DuckDB backend** - Optimized queries with vectorized pandas operations
- **Zero-overhead logging** - SmartLogger system with feature flags

## Common Questions

**Q: How long does it take to convert my music history?**
A: Depends on your search provider. MusicBrainz (Local): 1,000 tracks in under 1 minute. MusicBrainz API: 1,000 tracks in ~17 minutes (1 req/sec). iTunes API: 1,000 tracks in 10-50 minutes (20-120 req/min adaptive rate limiting).

**Q: Which search provider should I use?**
A: MusicBrainz (Local) for large files (fastest but requires 2GB download). MusicBrainz API for moderate files without the download. iTunes API for quick tests or when other providers don't find results.

**Q: Is my data sent anywhere?**
A: No. All processing happens locally on your computer. Your data never leaves your machine.

**Q: What formats are supported?**
A: Play Activity, Recently Played Tracks, and Play History Daily Tracks (auto-detected).

See the complete [FAQ](FAQ) for more answers.

## Getting Help

### Need Help Using the App?

1. **[FAQ](FAQ)** - Quick answers to common questions
2. **[User Guide](User-Guide)** - Detailed usage instructions
3. **[Troubleshooting](Troubleshooting)** - Fix specific errors
4. **[GitHub Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)** - Ask the community

### Found a Bug?

1. Check [existing issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues) first
2. If it's new, [open an issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues/new) with:
   - Your OS and version
   - App version
   - Steps to reproduce
   - Expected vs actual behavior

### Want to Contribute?

Contributions are welcome! See the [Development Guide](Development) for:

- Setting up a development environment
- Understanding the codebase architecture
- Code style and standards
- Submitting pull requests
- Testing your changes

## Downloads

**Latest Release**: v2.0.2 (October 2025)

- **macOS**: [DMG Installer](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest) (Universal Binary - Apple Silicon + Intel)
- **Windows**: [MSI Installer](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest) (x86_64)
- **Linux**: [Build from Source](Building-from-Source) (no pre-built binaries)

All releases include:
- Code signed and notarized (macOS)
- No Python installation required
- Complete offline documentation
- Auto-update notifications

## System Requirements

**Minimum**:
- **RAM**: 4GB (iTunes API) or 8GB (MusicBrainz)
- **Storage**: 200MB app + 3GB for MusicBrainz database (optional)
- **OS**: macOS 11+, Windows 10+, or modern Linux

**Recommended**:
- **RAM**: 8GB or more
- **Storage**: SSD for faster database operations
- **Internet**: Broadband for database download (one-time, ~2GB)

## Technology Stack

Built with:
- **[BeeWare Toga](https://beeware.org/)** - Cross-platform Python UI framework
- **[Pandas](https://pandas.pydata.org/)** - Fast data processing and CSV handling
- **[DuckDB](https://duckdb.org/)** - High-performance analytical database
- **[MusicBrainz](https://musicbrainz.org/)** - Open music encyclopedia

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/nerveband/Apple-Music-Play-History-Converter/blob/main/LICENSE) file for details.

---

**Last Updated**: October 2025 | **Version**: 2.0.2 | **[Changelog](https://github.com/nerveband/Apple-Music-Play-History-Converter/blob/main/CHANGELOG.md)**
