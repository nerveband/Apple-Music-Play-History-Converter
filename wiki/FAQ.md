# Frequently Asked Questions (FAQ)

Get quick answers to common questions about Apple Music Play History Converter.

## General Questions

### What does this application do?

Apple Music Play History Converter transforms your Apple Music CSV export files into a Last.fm-compatible format. This allows you to:

- Import your complete Apple Music listening history into Last.fm
- Preserve your scrobble history when switching music services
- Analyze your music listening habits
- Process large CSV files (100,000+ tracks) efficiently

### Is my data sent to any servers?

No. All processing happens locally on your computer. Your music data never leaves your machine. The only network connections are:

- MusicBrainz database download (optional, one-time, ~2GB)
- iTunes API searches (if you choose iTunes as your search provider)

### What file formats are supported?

The application supports these Apple Music CSV export formats:

- **Play Activity**: Standard Apple Music export format
- **Recently Played Tracks**: Alternative export format
- **Play History Daily Tracks**: Daily aggregated format

The app automatically detects which format you have.

### How do I get my Apple Music CSV file?

1. Open Apple Music on your Mac
2. Go to **Account → View My Account**
3. Scroll to **Request a copy of your data**
4. Select **Play Activity** or **Play History**
5. Wait for Apple to email you the download link (usually 24-72 hours)
6. Download and extract the ZIP file

### What's the difference between the search providers?

The app offers three search providers to find artist information:

| Feature | MusicBrainz (Local DB) | MusicBrainz API (Online) | iTunes API (Online) |
|---------|------------------------|--------------------------|---------------------|
| **Speed** | Ultra-fast (10,000+ tracks/sec) | Moderate (1 req/sec) | Slow (20-120 req/min) |
| **Setup** | Requires 2GB database download | Works immediately | Works immediately |
| **Internet** | Only for initial download | Required for every search | Required for every search |
| **Accuracy** | Very high (comprehensive) | Very high (same database) | Good (Apple's data) |
| **Rate Limits** | None | 1 request/second | 20-120 requests/minute (adaptive) |
| **Best For** | Large files (10k+ tracks) | Medium files, no download | Small files, fallback |

**Recommendation**: MusicBrainz (Local) for large files. MusicBrainz API for moderate files if you don't want to download the database. iTunes API as a fallback or for tracks not in MusicBrainz.

## Installation Questions

### Do I need Python installed?

**No.** The pre-built apps for macOS and Windows include everything you need. Just download the installer and run it.

### Why does macOS say the app is "damaged"?

This usually means:

1. **You used `zip` to extract the app** - Use macOS's built-in Archive Utility or download a fresh copy from GitHub
2. **Corrupted download** - Re-download the DMG file
3. **Not properly signed** - Make sure you downloaded from the official GitHub releases page

**Fix**: Download the official DMG from [GitHub Releases](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest) and drag it to Applications.

### Can I run this on Linux?

Yes, but you need to compile from source. Linux pre-built binaries are not currently available. See [Building from Source](Building-from-Source) for instructions.

### How much disk space do I need?

- **App only**: 200MB
- **With MusicBrainz database**: 3GB total (2GB database + 1GB temporary files)
- **Recommended free space**: 5GB for comfortable operation

### How much RAM do I need?

- **Minimum**: 4GB (for iTunes API only)
- **Recommended**: 8GB or more (for MusicBrainz database)
- **Large files (100k+ tracks)**: 16GB recommended

## Usage Questions

### How long does processing take?

Processing time depends on your CSV file size and search provider:

| File Size | MusicBrainz (Local) | MusicBrainz API | iTunes API |
|-----------|---------------------|-----------------|------------|
| 1,000 tracks | Under 1 minute | ~17 minutes | 10-50 minutes |
| 10,000 tracks | 1-2 minutes | ~3 hours | 1.5-8 hours |
| 100,000 tracks | 10-15 minutes | ~28 hours | 14-83 hours |

**MusicBrainz (Local) is 100x faster** than MusicBrainz API and significantly faster than iTunes API for large files.

### Can I pause and resume processing?

**Yes!** The app includes auto-save checkpoints every 50 tracks. If you need to stop:

1. Close the app (your progress is automatically saved)
2. Re-open and load the same CSV file
3. Click "Resume Search" to continue where you left off

### What if some tracks aren't found?

This is normal. The app will:

1. Mark unfound tracks with a placeholder artist
2. Show you the count of missing tracks
3. Still export a valid CSV file for Last.fm

You can:

- Try a different search provider (MusicBrainz Local, MusicBrainz API, or iTunes)
- Manually edit the output CSV to add missing information
- Export the list of failed tracks for review

### What does "rate limited" mean for iTunes API?

iTunes API limits requests to 20 per minute. When you hit this limit:

- The app automatically pauses and waits 60 seconds
- You'll see a "⏸️ Rate limited" message in the progress
- Processing resumes automatically after the cooldown

**Tip**: Use the "Retry Rate-Limited" button after waiting to retry tracks that hit the limit.

### Can I search multiple CSV files at once?

No, the app processes one CSV file at a time. For multiple files:

1. Process each file separately
2. Combine the output CSV files using a spreadsheet or text editor
3. Import the combined file to Last.fm

### Will this overwrite my existing Last.fm scrobbles?

No. Last.fm imports are additive - new scrobbles are added without affecting existing ones. However:

- Last.fm may reject duplicate scrobbles (same artist/track/timestamp)
- Recent scrobbles (within 14 days) are more likely to be accepted
- Very old scrobbles (years ago) may be rejected by Last.fm

## Troubleshooting

### The app won't start on macOS

**Cause**: Gatekeeper security or corrupted app bundle.

**Fix**:
1. Right-click the app and select "Open" (not double-click)
2. Click "Open" in the security dialog
3. If that fails, run: `xattr -cr "/Applications/Apple Music History Converter.app"`

### The app crashes on exit (macOS)

**Fixed in v2.0.2!** This was a known issue with the Toga framework. Update to the latest version from [GitHub Releases](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest).

### MusicBrainz database download fails

**Common causes**:
- Slow internet connection (2GB download takes time)
- Network timeout
- Not enough disk space (need 3GB free)

**Fix**:
1. Check your internet connection
2. Free up disk space (need 3GB)
3. Try downloading during off-peak hours
4. Use iTunes API instead (no download required)

### iTunes API searches are very slow

This is normal. iTunes API is rate-limited to 20 requests per minute. For large files:

- Use MusicBrainz instead (100x faster)
- Let it run overnight for very large files
- Use the pause/resume feature to process in batches

### The output CSV is empty or incomplete

**Check**:
1. Did the search complete? Look for "Search complete" message
2. Did you click "Save" or "Export" after searching?
3. Check the file size - should be at least a few KB

**Fix**:
1. Re-run the search
2. Make sure to click "Save" after search completes
3. Try a different output location with write permissions

### App shows "Search already in progress" error

**Fixed in v2.0.1!** Update to the latest version. If you're on an old version:

1. Close the app completely
2. Re-open and try again
3. If it persists, restart your computer

## Performance Questions

### Why is the app using so much RAM?

For large CSV files (100k+ rows), the app loads the entire file into memory for fast processing. This is normal and expected. RAM usage scales with file size:

- 10k tracks: ~500MB RAM
- 100k tracks: ~2-3GB RAM
- 250k tracks: ~5-6GB RAM

**Tip**: Close other applications when processing very large files.

### Can I speed up processing?

**Yes:**

1. **Use MusicBrainz (Local)** instead of MusicBrainz API or iTunes (100x faster)
2. **More RAM** equals faster pandas operations
3. **SSD storage** equals faster database queries
4. **Don't run other heavy apps** during processing

### Does the app support Apple Silicon Macs?

**Yes!** The macOS app is a **universal binary** that runs natively on both:

- Apple Silicon (M1, M2, M3, M4) - Fully optimized
- Intel Macs - Full compatibility

No Rosetta 2 translation needed.

## Data & Privacy Questions

### What data does the app collect?

**None.** The app collects zero telemetry, analytics, or user data. Everything runs locally.

### Can I use this offline?

**Partially**:

- **MusicBrainz (Local)**: Yes, after initial database download (fully offline)
- **MusicBrainz API**: No, requires internet for every search
- **iTunes API**: No, requires internet for every search

### Where does the app store data?

**macOS**:
- Settings: `~/Library/Application Support/AppleMusicConverter/settings.json`
- MusicBrainz DB: `~/.apple_music_converter/musicbrainz_optimized.duckdb`
- Logs: `~/Library/Logs/AppleMusicConverter/`

**Windows**:
- Settings: `%LOCALAPPDATA%\AppleMusicConverter\settings.json`
- MusicBrainz DB: `%USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb`
- Logs: `%LOCALAPPDATA%\AppleMusicConverter\Logs\`

### Is this safe to use?

**Yes!** The app is:

- **Open source** - All code visible on GitHub
- **Code signed** - macOS app signed with Apple Developer ID
- **Notarized** - Approved by Apple's security checks
- **No network tracking** - Zero telemetry or analytics
- **Local processing** - Your data never leaves your computer

## Advanced Questions

### Can I automate this with scripts?

The app is GUI-only, but you can access the underlying Python libraries. See [Development Guide](Development) for:

- Running the app from source
- Using the core conversion libraries
- Batch processing automation

### Can I contribute to the project?

**Yes!** Contributions are welcome:

1. Check [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues) for open tasks
2. Read the [Development Guide](Development)
3. Fork, code, and submit a pull request

### What's the technology stack?

- **UI**: Toga (BeeWare) - Cross-platform native Python UI
- **Data Processing**: Pandas + DuckDB for fast CSV operations
- **MusicBrainz**: DuckDB database with optimized indices
- **iTunes API**: Parallel async requests with rate limiting
- **Build System**: Briefcase for native app packaging

### How do I report a bug?

1. Check [existing issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues) first
2. If it's new, [open an issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues/new) with:
   - Your OS and version
   - App version
   - Steps to reproduce
   - Expected vs actual behavior
   - Log files if available

### Where can I get help?

- **FAQ**: You're reading it!
- **User Guide**: [User-Guide](User-Guide) - Step-by-step instructions
- **Troubleshooting**: [Troubleshooting](Troubleshooting) - Detailed problem solving
- **Issues**: [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues) - Report bugs
- **Discussions**: [GitHub Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions) - Ask questions

## Still Have Questions?

If your question isn't answered here:

1. Check the [User Guide](User-Guide) for detailed instructions
2. Check [Troubleshooting](Troubleshooting) for specific error messages
3. Search [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
4. Open a new [GitHub Discussion](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)

---

**Last Updated**: October 2025 | **Version**: 2.0.2
