# MusicBrainz Database Setup

Learn how to download, install, and optimize the MusicBrainz offline database for ultra-fast music searches.

## Overview

MusicBrainz is a community-maintained open music encyclopedia. The offline database enables searches **100x faster** than the iTunes API:

| Feature | MusicBrainz (Local) | iTunes API (Online) |
|---------|---------------------|---------------------|
| **Search Speed** | 10,000+ tracks/sec (1-5ms each) | ~10 tracks/sec (100-200ms each) |
| **Setup Time** | 5-10 minutes (one-time download) | Instant (no setup) |
| **Download Size** | ~2GB compressed | None |
| **Disk Space Required** | ~3GB total | Minimal |
| **Internet Required** | Only for initial download | For every search |
| **Rate Limits** | None | 20 requests/minute |
| **Best For** | Large files (10k+ tracks) | Small files, quick tests |

**Recommendation**: If you're processing more than 1,000 tracks, the MusicBrainz database is essential.

## Prerequisites

Before downloading the MusicBrainz database:

- **Disk Space**: 3GB free space
  - 2GB for compressed download
  - 1GB for decompression and optimization
- **RAM**: 8GB+ recommended (4GB minimum)
- **Internet**: Broadband connection (download takes 5-30 minutes)
- **Storage Type**: SSD strongly recommended for best performance

## Installation Methods

### Method 1: In-App Download (Recommended)

The app includes a built-in downloader that handles everything automatically:

1. **Launch** the Apple Music History Converter app
2. **Click** "Database Management" or "Settings"
3. **Select** "MusicBrainz" as your search provider
4. **Click** "Download MusicBrainz Database"
5. **Wait** for download and optimization (5-10 minutes)
6. **Done!** The database is ready to use

**Progress indicators**:
- Download progress: Shows percentage and speed
- Extraction: Decompressing the archive
- Optimization: Building search indices (takes longest)
- Ready: Database indexed and ready for searches

**What happens during download**:
1. **Download**: Fetches latest MusicBrainz canonical data (~2GB)
2. **Verify**: Checks file integrity
3. **Extract**: Decompresses the archive
4. **Load**: Imports data into DuckDB database
5. **Index**: Creates optimized search indices for fast lookups
6. **Clean up**: Removes temporary files

### Method 2: Manual Download (Advanced)

For users who want to manage the download themselves:

**Step 1: Download the data file**

Visit MusicBrainz's canonical data export page:
```
https://musicbrainz.org/doc/MusicBrainz_Database/Download
```

Download the latest **recordings** dump file:
- File format: `.tar.zst` (Zstandard compressed tar)
- Size: ~2GB compressed
- Updated: Monthly (usually around the 1st)

**Step 2: Extract the archive**

```bash
# macOS/Linux
tar --use-compress-program=unzstd -xvf mbdump-recordings-latest.tar.zst

# Windows (requires zstd.exe)
zstd -d mbdump-recordings-latest.tar.zst
tar -xf mbdump-recordings-latest.tar
```

**Step 3: Import into app**

1. Open the app
2. Go to Database Management
3. Click "Import Database"
4. Select the extracted files
5. Wait for optimization to complete

### Method 3: Pre-Built Database (Coming Soon)

We plan to offer pre-built, optimized database files for direct download. This will skip the optimization step and reduce setup time to 1-2 minutes.

## Database Location

The MusicBrainz database is stored in your user directory:

**macOS**:
```
~/.apple_music_converter/musicbrainz_optimized.duckdb
~/.apple_music_converter/musicbrainz_optimized.duckdb.wal (write-ahead log)
```

**Windows**:
```
%USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb
%USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb.wal
```

**Linux**:
```
~/.apple_music_converter/musicbrainz_optimized.duckdb
~/.apple_music_converter/musicbrainz_optimized.duckdb.wal
```

## Database Optimization

The optimization process creates search indices for fast lookups. This is the most time-consuming part of setup.

### Optimization Process

**What happens during optimization**:

1. **Create artist index**: Indexes artist names for fuzzy matching
2. **Create track index**: Indexes track titles for fuzzy matching
3. **Create combined index**: Indexes artist+track combinations
4. **Build FTS index**: Full-text search index for fuzzy matching
5. **Analyze statistics**: Optimizes query planner

**Expected duration**:
- **SSD**: 2-3 minutes
- **HDD**: 10-15 minutes
- **Slow HDD**: 30+ minutes (not recommended)

### Manual Re-Optimization

If searches become slow or you suspect database corruption:

1. Open the app
2. Go to Database Management
3. Click "Re-Optimize Database"
4. Wait for process to complete

**When to re-optimize**:
- After major app updates
- If search performance degrades
- If database was interrupted during creation
- After disk errors or crashes

### Optimization Settings

Advanced users can tune optimization parameters in `settings.json`:

```json
{
  "musicbrainz": {
    "optimization": {
      "enable_fts": true,          // Full-text search (slower but better matching)
      "enable_ngrams": true,        // N-gram indexing (fuzzy matching)
      "index_threshold": 1000000,   // Only index if >1M records
      "chunk_size": 100000          // Records per optimization batch
    }
  }
}
```

## Performance Tuning

### Hardware Recommendations

**For best performance**:
- **SSD**: Essential for good query performance
- **RAM**: 8GB+ for database operations
- **CPU**: Modern multi-core processor

**Performance comparison**:

| Hardware | Search Time (per track) | Throughput (tracks/sec) |
|----------|------------------------|-------------------------|
| **SSD + 16GB RAM** | 1-2ms | 50,000+ |
| **SSD + 8GB RAM** | 2-5ms | 10,000+ |
| **HDD + 16GB RAM** | 10-50ms | 1,000-2,000 |
| **HDD + 8GB RAM** | 50-200ms | 100-500 |

### Moving Database to SSD

If you initially installed on HDD, move the database to SSD:

**macOS**:
```bash
# 1. Close the app
# 2. Move database to SSD location
mkdir -p /Volumes/SSD/.apple_music_converter
mv ~/.apple_music_converter/musicbrainz_optimized.duckdb* /Volumes/SSD/.apple_music_converter/

# 3. Create symlink
rm -rf ~/.apple_music_converter
ln -s /Volumes/SSD/.apple_music_converter ~/.apple_music_converter

# 4. Restart app
```

**Windows**:
```cmd
REM 1. Close the app
REM 2. Move database to SSD
move %USERPROFILE%\.apple_music_converter D:\FastDrive\.apple_music_converter

REM 3. Create junction
rmdir %USERPROFILE%\.apple_music_converter
mklink /J %USERPROFILE%\.apple_music_converter D:\FastDrive\.apple_music_converter

REM 4. Restart app
```

### Query Performance Tuning

For advanced users who want to tune query performance:

```python
# Edit settings.json
{
  "musicbrainz": {
    "query": {
      "fuzzy_threshold": 0.8,    // Lower = more lenient matching (0.6-0.9)
      "max_results": 10,          // Maximum results per query
      "timeout_ms": 5000,         // Query timeout (5 seconds)
      "cache_size": 10000,        // Number of queries to cache in RAM
      "use_prepared_statements": true  // Faster repeated queries
    }
  }
}
```

## Updating the Database

MusicBrainz releases new data dumps monthly. To update:

### Automatic Update (Recommended)

1. Open the app
2. Go to Database Management
3. Click "Check for Updates"
4. If update available, click "Download Update"
5. Wait for download and re-optimization

### Manual Update

1. Download latest dump from MusicBrainz
2. Delete old database:
   ```bash
   # macOS/Linux
   rm ~/.apple_music_converter/musicbrainz_optimized.duckdb*

   # Windows
   del %USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb*
   ```
3. Import new dump using the app

**Update frequency**: Monthly updates are recommended but not required. The database doesn't change dramatically month-to-month.

## Database Management

### Checking Database Status

View database information:

1. Open the app
2. Go to Database Management
3. View status panel:
   - Database version
   - Total recordings
   - Total artists
   - Index status
   - Last optimized date
   - Disk space used

### Database Health Check

Run a health check to verify integrity:

1. Open the app
2. Go to Database Management
3. Click "Run Health Check"

**Health check verifies**:
- Database file exists and is readable
- All required tables present
- Indices are complete
- No corruption detected
- Query performance meets benchmarks

### Backup and Restore

**Backing up the database**:

```bash
# macOS/Linux
tar -czf musicbrainz_backup_$(date +%Y%m%d).tar.gz ~/.apple_music_converter/

# Windows
tar -czf musicbrainz_backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%.tar.gz %USERPROFILE%\.apple_music_converter\
```

**Restoring from backup**:

```bash
# macOS/Linux
tar -xzf musicbrainz_backup_20251008.tar.gz -C ~/

# Windows
tar -xzf musicbrainz_backup_20251008.tar.gz -C %USERPROFILE%\
```

### Deleting the Database

To remove the MusicBrainz database and free up space:

1. Open the app
2. Go to Database Management
3. Click "Delete Database"
4. Confirm deletion

**Or manually**:

```bash
# macOS/Linux
rm -rf ~/.apple_music_converter/musicbrainz_optimized.duckdb*

# Windows
del /s /q %USERPROFILE%\.apple_music_converter\musicbrainz_optimized.duckdb*
```

**Space freed**: ~2-3GB

## Troubleshooting

### Download fails or times out

**Cause**: Slow connection, network timeout, or server busy.

**Solutions**:
1. **Retry**: Click "Retry Download"
2. **Check connection**: Test internet speed
3. **Off-peak hours**: Try downloading late night/early morning
4. **Manual download**: Use Method 2 above

### Optimization takes forever (>30 minutes)

**Cause**: HDD instead of SSD, low RAM, or CPU-intensive background tasks.

**Solutions**:
1. **Close other apps**: Free up RAM and CPU
2. **Move to SSD**: See [Moving Database to SSD](#moving-database-to-ssd)
3. **Be patient**: HDDs are very slow for database operations
4. **Upgrade hardware**: Consider SSD upgrade

### Database corrupted

**Symptoms**: Crashes, slow queries, "database malformed" errors.

**Solutions**:
1. **Re-optimize**: Database Management → Re-Optimize
2. **Delete and re-download**: Removes corruption
3. **Check disk errors**: Run disk utility/CHKDSK

### Searches returning no results

**Symptoms**: MusicBrainz finds nothing, but tracks definitely exist.

**Diagnosis**:
```python
# Check database has data
import duckdb
conn = duckdb.connect('~/.apple_music_converter/musicbrainz_optimized.duckdb')
print(conn.execute("SELECT COUNT(*) FROM recordings").fetchone())
# Should show millions of records
```

**Solutions**:
1. **Check database loaded**: Status should show "Ready"
2. **Re-optimize**: Indices may be corrupted
3. **Update database**: Might be too old
4. **Try iTunes API**: Compare results

## Advanced Topics

### Database Schema

The DuckDB database schema:

```sql
-- Recordings table (main table)
CREATE TABLE recordings (
  id VARCHAR PRIMARY KEY,
  name VARCHAR,
  artist_name VARCHAR,
  artist_credit VARCHAR,
  length INTEGER,
  comment VARCHAR
);

-- Indices for fast lookups
CREATE INDEX idx_artist_name ON recordings(artist_name);
CREATE INDEX idx_recording_name ON recordings(name);
CREATE INDEX idx_combined ON recordings(artist_name, name);

-- Full-text search index
CREATE INDEX idx_fts ON recordings USING FTS(artist_name, name);
```

### Custom Queries

Advanced users can query the database directly:

```python
import duckdb

# Connect to database
conn = duckdb.connect('~/.apple_music_converter/musicbrainz_optimized.duckdb')

# Find all tracks by an artist
results = conn.execute("""
    SELECT name, artist_name, length
    FROM recordings
    WHERE LOWER(artist_name) LIKE LOWER('%Beatles%')
    LIMIT 100
""").fetchall()

# Count tracks per artist
results = conn.execute("""
    SELECT artist_name, COUNT(*) as track_count
    FROM recordings
    GROUP BY artist_name
    ORDER BY track_count DESC
    LIMIT 20
""").fetchall()

conn.close()
```

### Exporting Database Statistics

Generate statistics about your database:

```python
import duckdb
conn = duckdb.connect('~/.apple_music_converter/musicbrainz_optimized.duckdb')

# Total records
print(f"Total recordings: {conn.execute('SELECT COUNT(*) FROM recordings').fetchone()[0]:,}")

# Total artists
print(f"Total artists: {conn.execute('SELECT COUNT(DISTINCT artist_name) FROM recordings').fetchone()[0]:,}")

# Database size
import os
db_size = os.path.getsize('~/.apple_music_converter/musicbrainz_optimized.duckdb')
print(f"Database size: {db_size / 1024**3:.2f} GB")

# Index status
print(conn.execute("PRAGMA show_tables").fetchall())
```

## FAQ

**Q: Do I need the database if I only have a few hundred tracks?**
A: No. For small files (<1,000 tracks), the iTunes API is sufficient and requires no setup.

**Q: Can I use both MusicBrainz and iTunes API?**
A: Yes! The app can try MusicBrainz first, then fall back to iTunes API for tracks not found.

**Q: How often should I update the database?**
A: Every 3-6 months is sufficient. New music is added constantly, but older music doesn't change.

**Q: Can I share the database with friends?**
A: Yes, but it's ~2-3GB. It's easier for them to download it themselves using the app.

**Q: Does the database work offline?**
A: Yes! After the initial download, no internet connection is needed for MusicBrainz searches.

**Q: What if my search provider is set to iTunes but I want to switch?**
A: Go to Settings → Search Provider → Select "MusicBrainz". Download the database if you haven't already.

---

**Last Updated**: October 2025 | **Version**: 2.0.2

**Need help?** → [Troubleshooting](Troubleshooting) | [FAQ](FAQ) | [User Guide](User-Guide)
