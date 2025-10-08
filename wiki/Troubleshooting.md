# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Apple Music Play History Converter.

## Quick Diagnostic Checklist

Before diving into specific issues, try these quick fixes:

- [ ] **Update to latest version** - Many issues are fixed in newer releases
- [ ] **Restart the app** - Clears temporary state issues
- [ ] **Check disk space** - Need 3GB free for MusicBrainz
- [ ] **Check internet connection** - Required for iTunes API and database downloads
- [ ] **Review log files** - See [Viewing Logs](#viewing-logs) below

## Installation Issues

### macOS: "App is damaged and can't be opened"

**Symptoms**: Error message when trying to open the app for the first time.

**Causes**:
1. Downloaded file was corrupted
2. App bundle extracted with `zip` instead of proper macOS tool
3. Quarantine attribute not removed

**Solutions**:

```bash
# Solution 1: Remove quarantine attribute (most common fix)
xattr -cr "/Applications/Apple Music History Converter.app"

# Solution 2: If the above fails, re-download
# 1. Delete the current app
# 2. Download fresh DMG from GitHub Releases
# 3. Open DMG with Archive Utility (not third-party tools)
# 4. Drag app to Applications folder
```

**Why this happens**: macOS adds a quarantine attribute to downloaded files. If the app bundle is corrupted during extraction, macOS refuses to open it.

**Prevention**: Always download from official [GitHub Releases](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest) and use macOS's built-in Archive Utility.

### macOS: Gatekeeper blocks the app

**Symptoms**: "macOS cannot verify the developer" or similar security warning.

**Solution**:
1. Right-click (Control-click) the app
2. Select "Open" from the context menu
3. Click "Open" in the security dialog
4. The app will now start and be remembered for future launches

**Why this happens**: Apple's Gatekeeper requires manual approval for apps from identified developers.

### Windows: Microsoft Defender blocks installation

**Symptoms**: "Windows protected your PC" warning when running the MSI installer.

**Solution**:
1. Click "More info"
2. Click "Run anyway"
3. Proceed with installation

**Why this happens**: New MSI installers without widespread usage trigger SmartScreen warnings.

**Safety**: The app is safe - it's open source and signed. The warning will disappear as more users install it.

### Linux: Dependencies missing

**Symptoms**: Error about missing GTK3, Python, or other libraries.

**Solution** (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install python3.12 python3-pip python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-webkit2-4.0 libgirepository1.0-dev
```

**Solution** (Fedora):
```bash
sudo dnf install python3 python3-pip gtk3 webkit2gtk3 gobject-introspection-devel
```

See [Building from Source](Building-from-Source) for complete Linux installation instructions.

## Startup Issues

### App crashes immediately on launch

**Symptoms**: App opens briefly then closes, or never appears.

**Diagnosis**:
```bash
# macOS: Check crash logs
cat ~/Library/Logs/AppleMusicConverter/apple_music_converter.log

# Windows: Check event viewer
eventvwr.msc
# Look under Windows Logs → Application
```

**Common causes**:

1. **Corrupted settings file**
   ```bash
   # macOS
   rm ~/Library/Application\ Support/AppleMusicConverter/settings.json

   # Windows
   del %LOCALAPPDATA%\AppleMusicConverter\settings.json
   ```

2. **Corrupted database file**
   ```bash
   # macOS
   rm ~/.apple_music_converter/musicbrainz_optimized.duckdb*

   # Windows
   del %USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb*
   ```

3. **Incompatible Python version** (source installs only)
   - Requires Python 3.8+
   - Check: `python --version`

### App freezes on startup

**Symptoms**: App window appears but is unresponsive, beachball (macOS) or "Not Responding" (Windows).

**Cause**: Large MusicBrainz database loading on slow drive.

**Solution**:
- **Wait 30-60 seconds** - Database initialization takes time
- **Move database to SSD** if on HDD
- **Disable MusicBrainz** in settings and use iTunes API instead

### "Permission denied" errors

**Symptoms**: Can't save files, can't create database, or can't write logs.

**macOS Solution**:
```bash
# Grant full disk access to the app
# System Settings → Privacy & Security → Full Disk Access → Add app
```

**Windows Solution**:
- Run as Administrator (right-click app → Run as administrator)
- Check antivirus isn't blocking file creation

## CSV File Issues

### "File not found" or "Cannot open file"

**Diagnosis**:
1. **Check file path** - No spaces or special characters in folder names
2. **Check file permissions** - You must have read access
3. **Check file isn't open elsewhere** - Close Excel, Numbers, etc.

**Solution**:
```bash
# macOS: Check file permissions
ls -la /path/to/your/file.csv

# Should show readable permissions like: -rw-r--r--
```

### "Invalid CSV format" or "Unable to detect format"

**Symptoms**: App can't read your CSV file or shows format errors.

**Supported formats**:
- Play Activity (standard Apple Music export)
- Recently Played Tracks
- Play History Daily Tracks

**Diagnosis**:
1. Open CSV in text editor (not Excel)
2. Check first line has column headers
3. Verify it's comma-separated (not tab or semicolon)

**Common causes**:
- Excel modified the file and changed encoding
- File was concatenated from multiple exports
- File is from a different music service (not Apple Music)

**Fix**:
```bash
# Check file encoding
file -I yourfile.csv

# Should show: text/csv; charset=utf-8 or similar

# If wrong encoding, convert:
iconv -f WINDOWS-1252 -t UTF-8 yourfile.csv > yourfile_utf8.csv
```

### CSV file too large to open

**Symptoms**: Out of memory errors, app becomes unresponsive.

**RAM requirements**:
- 10k rows: ~500MB RAM
- 100k rows: ~2-3GB RAM
- 250k rows: ~5-6GB RAM

**Solutions**:
1. **Split the file**: Use a text editor to split into smaller chunks
2. **Process in batches**: Import each chunk separately
3. **Add more RAM**: Consider upgrading to 16GB if processing huge files

## MusicBrainz Database Issues

### Database download fails

**Symptoms**: "Download failed", "Connection timeout", or stuck at X%.

**Diagnosis**:
```bash
# Test connection to MusicBrainz
curl -I https://musicbrainz.org/
# Should return: HTTP/2 200
```

**Solutions**:

1. **Slow connection**: Download takes time (~30-60 minutes for 2GB)
   - Leave it running and don't close the app
   - Try during off-peak hours
   - Use wired ethernet instead of WiFi if possible

2. **Timeout**: Adjust timeout in settings
   - Increase from 300s to 600s or higher

3. **Network blocked**: Check firewall/proxy
   - Temporarily disable VPN
   - Check corporate firewall isn't blocking MusicBrainz

4. **Disk space**: Need 3GB free
   ```bash
   # Check free space (macOS)
   df -h ~

   # Check free space (Windows)
   wmic logicaldisk get size,freespace,caption
   ```

### Database optimization fails

**Symptoms**: "Optimization failed" or takes extremely long (>30 minutes).

**Cause**: Insufficient RAM or slow disk I/O.

**Solution**:
1. **Close other applications** - Free up RAM
2. **Use SSD** - HDD optimization is very slow
3. **Manual re-download**:
   ```bash
   # macOS
   rm -rf ~/.apple_music_converter/musicbrainz_optimized.duckdb*
   # Restart app and re-download

   # Windows
   del %USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb*
   # Restart app and re-download
   ```

### Database queries are slow

**Symptoms**: MusicBrainz searches taking >100ms per track.

**Expected performance**: 1-5ms per track (10,000+ tracks/sec throughput).

**Diagnosis**:
```python
# Enable debug logging in settings.json:
{
  "logging": {
    "enabled": true,
    "level": "DEBUG"
  }
}
# Restart app and check logs for query times
```

**Solutions**:
1. **Database not optimized**: Re-run optimization
2. **HDD instead of SSD**: Move database to SSD
3. **Low RAM**: Close other applications
4. **Database corrupted**: Delete and re-download

## iTunes API Issues

### Rate limiting (403 errors)

**Symptoms**: "iTunes API rate limited" messages, searches pause frequently.

**Explanation**: iTunes API limits requests to ~20 per minute. This is normal.

**Solutions**:
1. **Let it run**: App automatically waits 60s and resumes
2. **Use "Retry Rate-Limited"**: After search completes, retry failed tracks
3. **Switch to MusicBrainz**: No rate limits, 100x faster

**What NOT to do**:
- Don't restart the app during rate limit wait
- Don't spam retry - wait at least 60 seconds
- Don't run multiple searches simultaneously

### iTunes API returning no results

**Symptoms**: Most tracks show "Not found" but you know they exist.

**Causes**:
1. **Network connectivity issues**
2. **iTunes API temporarily down**
3. **Special characters in track names confusing search**

**Diagnosis**:
```bash
# Test iTunes API directly
curl "https://itunes.apple.com/search?term=beatles+hey+jude&limit=1"
# Should return JSON with results
```

**Solutions**:
1. **Check internet**: Visit apple.com to verify connectivity
2. **Wait and retry**: iTunes API may be temporarily down
3. **Use MusicBrainz**: More comprehensive music database

### iTunes API search stuck

**Symptoms**: Progress bar frozen, no updates for several minutes.

**Cause**: Network timeout or app thread deadlock.

**Solution**:
1. **Wait 5 minutes**: May be a long timeout
2. **Click "Pause"**: Then "Resume" to restart thread
3. **Restart app**: Progress is auto-saved every 50 tracks

## Search & Processing Issues

### "Search already in progress" error

**Status**: **Fixed in v2.0.1+**

**Solution**: Update to latest version from [GitHub Releases](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest).

**Workaround** (if can't update):
1. Close app completely
2. Re-open and reload CSV
3. If persists, restart computer

### Progress stuck at X%

**Symptoms**: Progress bar stops updating for >5 minutes.

**Diagnosis**:
1. Check CPU usage - should be >0% if working
2. Check network activity - should see requests if using iTunes API
3. Check logs - may show error messages

**Solutions**:

1. **Rate limiting**: Wait 60 seconds for iTunes API
2. **Large file processing**: Be patient, may appear stuck but still working
3. **Thread deadlock**: Close and restart app (progress auto-saved)

### Wrong artist/track matches

**Symptoms**: Search finds tracks, but artist names are incorrect.

**Cause**: Fuzzy matching sometimes finds similar-but-wrong tracks.

**Solutions**:
1. **Manual correction**: Edit output CSV file before importing to Last.fm
2. **Try different provider**: Switch between MusicBrainz and iTunes API
3. **Report issue**: If consistently wrong, [open an issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)

### Auto-save not working

**Symptoms**: Closing and reopening loses all progress.

**Diagnosis**: Check auto-save is enabled and working:
```bash
# macOS: Check for checkpoint files
ls ~/Library/Application\ Support/AppleMusicConverter/checkpoints/

# Windows
dir %LOCALAPPDATA%\AppleMusicConverter\checkpoints\
```

**Solution**:
1. Ensure you have write permissions to app data directory
2. Check disk isn't full
3. Try saving manually before closing app

## Export Issues

### Can't save output file

**Symptoms**: "Permission denied" or "Unable to write file" errors.

**Solutions**:
1. **Choose different location**: Desktop or Documents folder
2. **Check permissions**: Need write access to target folder
3. **Close file if open**: Can't overwrite file open in Excel/Numbers
4. **Check disk space**: Need space for output file

### Output CSV is empty

**Symptoms**: File created but 0 bytes or only headers.

**Cause**: Search didn't complete or no results found.

**Solution**:
1. Verify search completed successfully (saw "Search complete" message)
2. Check if any tracks were found (look at progress summary)
3. Re-run search if no results
4. Try different search provider

### Last.fm rejects my import

**Symptoms**: Last.fm won't import the CSV or skips many scrobbles.

**Last.fm limitations**:
- Rejects scrobbles older than ~2 years for free accounts
- Rejects duplicate scrobbles (same artist/track/timestamp)
- Requires valid timestamps
- May rate-limit large imports (import in batches)

**Solutions**:
1. **Check timestamp format**: Should be Unix timestamp (10 digits)
2. **Import in batches**: Split file into smaller chunks (10k rows each)
3. **Check for duplicates**: Remove duplicate rows
4. **Verify format**: Last.fm expects: Artist, Track, Album, Timestamp

## Performance Issues

### App using excessive RAM

**Expected RAM usage**:
- Idle: ~200MB
- Small file (1k rows): ~500MB
- Medium file (10k rows): ~1GB
- Large file (100k rows): ~3GB
- Very large file (250k rows): ~6GB

**If usage is higher**:
1. Close and restart app
2. Process file in smaller batches
3. Add more RAM to computer

### App using excessive CPU

**Expected CPU usage**:
- Idle: <1%
- CSV processing: 20-50%
- MusicBrainz search: 10-30%
- iTunes API search: 5-15%

**If usage is higher**:
1. **Check for runaway threads**: Restart app
2. **Multiple searches running**: Only one search at a time
3. **Background indexing**: Wait for MusicBrainz optimization to complete

### Slow performance on HDD

**Symptoms**: Everything takes 5-10x longer than expected.

**Cause**: MusicBrainz database requires fast I/O (SSD recommended).

**Solutions**:
1. **Move database to SSD**: Copy `musicbrainz_optimized.duckdb` to SSD location
2. **Use iTunes API instead**: Doesn't require local database
3. **Upgrade to SSD**: Recommended for best performance

## Crash Issues

### macOS: App crashes on exit

**Status**: **Fixed in v2.0.2+**

**Symptoms**: "Abort trap: 6" or app crashes when clicking Quit.

**Solution**: Update to v2.0.2 or later from [GitHub Releases](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/latest).

**Technical details**: Was a Toga/Rubicon framework GIL crash. Fixed with proper cleanup sequence and os._exit() workaround. See `docs/TOGA_EXIT_CRASH_WORKAROUND.md` for implementation details.

### Random crashes during processing

**Symptoms**: App closes unexpectedly mid-search.

**Diagnosis**:
```bash
# macOS: Check crash logs
ls -lt ~/Library/Logs/DiagnosticReports/ | head -5

# Windows: Check Event Viewer
eventvwr.msc → Application logs
```

**Common causes**:
1. **Out of memory**: File too large for available RAM
2. **Corrupted database**: Delete and re-download MusicBrainz
3. **Thread deadlock**: Restart app

**Prevention**:
1. Process files in smaller batches
2. Close other applications
3. Ensure adequate RAM (8GB+ recommended)

## Viewing Logs

### Enable debug logging

Edit settings file to enable detailed logging:

**macOS**: `~/Library/Application Support/AppleMusicConverter/settings.json`
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

**Windows**: `%LOCALAPPDATA%\AppleMusicConverter\settings.json`
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

### View log files

**macOS**:
```bash
# View current log
tail -f ~/Library/Logs/AppleMusicConverter/apple_music_converter.log

# View all logs
ls -lt ~/Library/Logs/AppleMusicConverter/
```

**Windows**:
```cmd
# View current log
notepad %LOCALAPPDATA%\AppleMusicConverter\Logs\apple_music_converter.log

# List all logs
dir %LOCALAPPDATA%\AppleMusicConverter\Logs\
```

### Understanding log levels

- **DEBUG**: Detailed technical information (very verbose)
- **INFO**: General informational messages
- **WARNING**: Potential issues that don't stop processing
- **ERROR**: Errors that may affect functionality
- **CRITICAL**: Fatal errors that stop the app

## Getting Help

If you're still experiencing issues:

1. **Check FAQ**: [FAQ](FAQ) - Quick answers to common questions
2. **Search existing issues**: [GitHub Issues](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues)
3. **Collect diagnostic information**:
   - App version (Help → About)
   - Operating system and version
   - Log files with DEBUG level enabled
   - Steps to reproduce the issue
   - Expected vs actual behavior
4. **Open a new issue**: [New Issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues/new)

## Advanced Troubleshooting

### Network diagnostics

Test connectivity to required services:

```bash
# MusicBrainz (database download)
curl -I https://musicbrainz.org/
# Expected: HTTP/2 200

# iTunes API (search)
curl "https://itunes.apple.com/search?term=test&limit=1"
# Expected: JSON response with results

# Check DNS resolution
nslookup musicbrainz.org
nslookup itunes.apple.com
```

### Database diagnostics

Check MusicBrainz database integrity:

```python
import duckdb
conn = duckdb.connect('~/.apple_music_converter/musicbrainz_optimized.duckdb')
print(conn.execute("SELECT COUNT(*) FROM recordings").fetchone())
# Should show: (large number like 50000000+,)

print(conn.execute("PRAGMA table_info(recordings)").fetchall())
# Should show table schema with columns
```

### Clean reinstall

If nothing else works, try a clean reinstall:

**macOS**:
```bash
# 1. Backup your data
cp -r ~/.apple_music_converter ~/apple_music_converter_backup
cp -r ~/Library/Application\ Support/AppleMusicConverter ~/AppleMusicConverter_settings_backup

# 2. Uninstall app
rm -rf "/Applications/Apple Music History Converter.app"
rm -rf ~/.apple_music_converter
rm -rf ~/Library/Application\ Support/AppleMusicConverter
rm -rf ~/Library/Logs/AppleMusicConverter

# 3. Download and install fresh copy from GitHub
# 4. Restore database if needed
cp -r ~/apple_music_converter_backup ~/.apple_music_converter
```

**Windows**:
```cmd
REM 1. Uninstall via Settings → Apps
REM 2. Delete remaining files
del /s /q %USERPROFILE%\.apple_music_converter
del /s /q %LOCALAPPDATA%\AppleMusicConverter

REM 3. Download and install fresh MSI from GitHub
```

---

**Last Updated**: October 2025 | **Version**: 2.0.2

**Still need help?** → [Open an Issue](https://github.com/nerveband/Apple-Music-Play-History-Converter/issues/new) | [Ask in Discussions](https://github.com/nerveband/Apple-Music-Play-History-Converter/discussions)
