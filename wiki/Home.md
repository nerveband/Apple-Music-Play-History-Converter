# Apple Music Play History Converter Wiki

Welcome to the Apple Music Play History Converter documentation!

## Quick Links

- **[Installation](Installation)** - Get started with pre-built binaries or source install
- **[User Guide](User-Guide)** - Learn how to use the application
- **[MusicBrainz Database](MusicBrainz-Database)** - Setup offline search database
- **[Building from Source](Building-from-Source)** - Developer build instructions
- **[Troubleshooting](Troubleshooting)** - Common issues and solutions

## What is This Tool?

Apple Music Play History Converter transforms your Apple Music CSV export files into a format compatible with Last.fm and Universal Scrobbler, allowing you to:

- Import your complete Apple Music listening history into Last.fm
- Analyze your music listening habits
- Preserve your scrobble history when switching between services
- Process large CSV files (100,000+ tracks) efficiently

## Version 2.0 Highlights

The latest release represents a complete rewrite with major improvements:

- **100x faster processing** with batch operations
- **Parallel iTunes search** with 10 concurrent workers
- **Rate-limited track management** with retry and export features
- **Live progress updates** as searches complete
- **Modern Toga UI** that never freezes
- **Auto-save checkpoints** every 50 tracks
- **Cross-platform native apps** for Windows and macOS
- **Automated Windows builds** via GitHub Actions

## Getting Help

- **Common Issues**: Check the [Troubleshooting](Troubleshooting) page
- **Bug Reports**: [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)

## Contributing

Contributions are welcome! See the [Development Guide](Development) for information on:

- Setting up a development environment
- Understanding the codebase architecture
- Submitting pull requests
- Testing your changes

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/nerveband/Apple-Music-Play-History-Converter/blob/main/LICENSE) file for details.
