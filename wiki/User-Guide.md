# User Guide

Learn how to use Apple Music Play History Converter to convert your Apple Music data for Last.fm and Universal Scrobbler.

## Getting Your Apple Music Data

### Step 1: Request Your Data from Apple

1. Go to [Apple Privacy Portal](https://privacy.apple.com/)
2. Sign in with your Apple ID
3. Select "Request a copy of your data"
4. Choose "Media & Purchases" → "Apple Music Activity"
5. Submit the request

Apple will email you when your data is ready (usually 1-3 days).

### Step 2: Download and Extract

1. Click the link in Apple's email
2. Download the ZIP file
3. Extract the ZIP - you'll find CSV files inside

**Supported File Types**:
- `Apple Music - Play Activity.csv`
- `Apple Music - Recently Played Tracks.csv`
- `Apple Music - Play History Daily Tracks.csv`

## Using the Application

### Basic Workflow

1. **Select CSV File**
   - Click "Select CSV" button
   - Choose your Apple Music export file
   - The app auto-detects the file type

2. **Preview Data**
   - First 100-200 rows are shown automatically
   - Check that columns are mapped correctly
   - Review missing artist information

3. **Choose Search Provider**
   - **MusicBrainz** (recommended for large files):
     - Requires ~2GB database download (one-time)
     - Searches 10,000+ tracks/second
     - No rate limiting
   - **iTunes API** (works immediately):
     - No download required
     - Slower (10 parallel requests)
     - Rate limited to ~600 requests/minute

4. **Search for Missing Artists**
   - Click "Search with MusicBrainz" or "Search with iTunes"
   - Live progress updates show results as they arrive
   - Auto-saves every 50 tracks
   - Can be stopped and resumed

5. **Save Converted File**
   - Click "Save CSV" button
   - Choose output location
   - File is ready for Last.fm/Universal Scrobbler

## Understanding the Interface

### Main Window

- **File Selection**: Browse and select your CSV file
- **Preview Table**: Shows converted data (first 200 rows)
- **Progress Bar**: Live updates during search operations
- **Results Log**: Real-time search results and errors
- **Control Buttons**: Process, pause/resume, stop operations

### Search Provider Panel

- **Radio Buttons**: Select MusicBrainz or iTunes
- **Database Status**: Shows MusicBrainz database info
- **Download Button**: Get MusicBrainz database
- **Settings**: Configure search behavior

### Status Information

- **File Info**: Size, row count, file type
- **Search Stats**: Tracks processed, artists found, time elapsed
- **Missing Count**: Live count of tracks still needing artists

## MusicBrainz Database

### First-Time Setup

1. Select "MusicBrainz" as search provider
2. Click "Download DB" button
3. Wait for ~2GB download to complete
4. Database optimizes automatically (one-time process)

### Database Management

- **Check for Updates**: Manually check for newer database versions
- **Re-download**: Replace database with latest version
- **Delete Database**: Remove database to free disk space
- **Location**: Click "Reveal Location" to see where database is stored

**Database Path**: `~/.apple_music_converter/musicbrainz/`

### When to Optimize

The database auto-optimizes on first use. Re-optimization is needed if:
- Database becomes corrupted
- You manually import a new database file
- Searches are significantly slower than expected

## iTunes API Mode

### How It Works

- Sends queries to Apple's iTunes Search API
- Processes 10 tracks in parallel
- Adaptive rate limiting discovers actual API limits
- Starts at 120 req/min, adjusts based on 403 responses

### Rate Limiting

When rate limit is hit:
- Progress bar shows wait time remaining
- Search automatically resumes after wait
- No user intervention needed

**Typical Speed**: 300-600 tracks per hour (depends on API limits)

### Managing Rate-Limited Tracks

iTunes API occasionally returns 403 Forbidden errors when rate limits are exceeded. The app provides dedicated controls to manage these tracks:

**Manage Rate Limit Row** (visible only when iTunes API is selected):

1. **Skip Rate Limit Wait**
   - Click to skip current wait timer
   - Useful if you want to stop and resume later

2. **Retry Rate-Limited Tracks**
   - Shows count of tracks that hit 403 errors (e.g., "Retry Rate-Limited (15)")
   - Click to retry all rate-limited tracks
   - **Important**: Wait 60+ seconds after last rate limit before retrying
   - Button disabled when no rate-limited tracks exist

3. **Export Rate-Limited List**
   - Export all rate-limited tracks to CSV for manual review
   - Includes Track, Artist, Album, Reason, and Timestamp
   - Useful for researching tracks outside the app

**Rate Limit Strategy**:
- Rate-limited tracks (403 errors) are **temporary failures** - they may succeed on retry
- Failed tracks (404 errors) are **permanent failures** - track not found in iTunes database
- The app automatically separates these two categories

**Why 403 Errors Occur**:
- iTunes API has undocumented rate limits
- Limits can vary by region and time of day
- Multiple failed requests can trigger temporary blocks
- Conservative rate limiting (120 req/min) minimizes 403 errors

## Tips for Large Files

### For 100,000+ Track Files

1. **Use MusicBrainz** - Much faster for large datasets
2. **Monitor Progress** - Auto-saves protect against interruptions
3. **Check Disk Space** - Ensure 3GB+ free for MusicBrainz database
4. **RAM Requirements** - 8GB+ recommended for large files

### Handling Errors

- **Network Errors**: iTunes API may fail intermittently - search will retry
- **Missing Artists**: Some tracks may not be found in either database
- **Corrupted Files**: Verify CSV file is not corrupted (open in Excel/Numbers)

## Export Options

### Save CSV

Creates Last.fm compatible CSV with columns:
- Artist
- Track
- Album
- Timestamp (reverse-chronological)
- Album Artist
- Duration

### Export Missing Artists

Creates a separate CSV containing only tracks with missing artists:
- Useful for manual research
- Can be imported back after manual completion

## Troubleshooting

### Common Issues

**"No artists found"**
- Verify internet connection (for iTunes API)
- Check MusicBrainz database is downloaded
- Try switching search providers

**"Application won't start"**
- Check system requirements (8GB RAM for MusicBrainz)
- Verify all dependencies installed (if running from source)
- See [Troubleshooting](Troubleshooting) page

**"Progress seems stuck"**
- iTunes API may be rate limited - wait time shows in progress bar
- For MusicBrainz: database may need optimization

## Advanced Features

### Settings

Access via Settings button:
- **Parallel Requests**: Enable/disable iTunes parallel processing
- **Adaptive Rate Limit**: Auto-discover iTunes API limits
- **Workers**: Number of parallel iTunes requests (default: 10)

### Keyboard Shortcuts

- **Cmd/Ctrl+O**: Open CSV file
- **Cmd/Ctrl+S**: Save converted file
- **Cmd/Ctrl+Q**: Quit application

## Next Steps

- [MusicBrainz Database](MusicBrainz-Database) - Detailed database information
- [Building from Source](Building-from-Source) - Developer instructions
- [Troubleshooting](Troubleshooting) - Solve common problems
