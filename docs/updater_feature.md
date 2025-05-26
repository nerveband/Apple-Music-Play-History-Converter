# AI Coder Instructions: MusicBrainz Database Integration

## Project Overview
Integrate MusicBrainz offline database functionality into existing music app while keeping iTunes API as fallback option.

## Core Requirements

### 1. Database Management System
Create a `MusicBrainzManager` class that handles:
- Download MusicBrainz canonical dataset (.zst files)
- Extract and convert to SQLite database
- Provide search functionality for artist/song matching
- Manage database lifecycle (download/delete)

### 2. User Interface Changes

#### Settings Panel
Add new settings section with these controls:
```
Music Database Settings:
┌─────────────────────────────────────┐
│ Search Provider: [MusicBrainz ▼]    │  // Dropdown: MusicBrainz, iTunes API
│                                     │
│ MusicBrainz Database:               │
│ Status: [Not Downloaded] [Download] │  // Button to download database
│                                     │
│ [Check for Updates]                 │  // Manual update check only
│ [Delete Database]                   │  // Remove local database
│                                     │
│ Database Size: ~200MB               │  // Show current space usage
│ Last Updated: Never                 │  // Show last download date
└─────────────────────────────────────┘
```

#### First-Time User Experience
When user first opens app and tries to search:
```
┌─────────────────────────────────────┐
│ ⚠️  Music Database Required          │
│                                     │
│ To search music metadata, please    │
│ download the MusicBrainz database   │
│ (~200MB).                          │
│                                     │
│ [Download Now] [Use iTunes API]     │
└─────────────────────────────────────┘
```

### 3. Search Logic Implementation

```python
class MusicSearchService:
    def __init__(self):
        self.musicbrainz_manager = MusicBrainzManager()
        self.itunes_api = ITunesAPI()
        self.search_provider = self.get_user_preference()  # "musicbrainz" or "itunes"
    
    def search_song(self, song_name, artist_name=None, album_name=None):
        """Main search method that routes to appropriate provider"""
        
        if self.search_provider == "musicbrainz":
            if not self.musicbrainz_manager.is_database_available():
                # Show download prompt
                return self.prompt_download_or_fallback(song_name, artist_name, album_name)
            
            results = self.musicbrainz_manager.search(song_name, artist_name, album_name)
            if results:
                return results
            else:
                # Optionally fallback to iTunes if no results
                return self.itunes_api.search(song_name, artist_name, album_name)
        
        elif self.search_provider == "itunes":
            return self.itunes_api.search(song_name, artist_name, album_name)
    
    def prompt_download_or_fallback(self, song_name, artist_name, album_name):
        """Show user choice: download database or use iTunes API for this search"""
        # Return special result that triggers UI prompt
        return {"requires_download": True, "search_params": (song_name, artist_name, album_name)}
```

### 4. MusicBrainz Manager Implementation

```python
class MusicBrainzManager:
    def __init__(self, data_dir="app_data/musicbrainz"):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "musicbrainz.db"
        self.metadata_file = self.data_dir / "metadata.json"
        
    # Key methods to implement:
    
    def is_database_available(self) -> bool:
        """Check if local database exists and is usable"""
        
    def download_database(self, progress_callback=None) -> bool:
        """Download and setup database with progress updates"""
        
    def delete_database(self) -> bool:
        """Remove local database and free up space"""
        
    def check_for_updates(self) -> tuple[bool, str]:
        """Manual check for newer database version"""
        
    def get_database_info(self) -> dict:
        """Return size, version, last updated info"""
        
    def search(self, song_name, artist_name=None, album_name=None) -> list:
        """Search local database and return results"""
```

### 5. Download Process with Progress

```python
def download_with_progress(self, progress_callback):
    """
    Download process should:
    1. Show progress dialog with cancel button
    2. Download canonical_musicbrainz_data.csv.zst (~200MB)
    3. Extract to temporary location
    4. Convert to SQLite database
    5. Update metadata file
    6. Clean up temporary files
    7. Call progress_callback(percentage, status_message)
    """
    
    # Example progress updates:
    progress_callback(10, "Downloading database...")
    progress_callback(60, "Extracting files...")
    progress_callback(80, "Building search index...")
    progress_callback(100, "Database ready!")
```

### 6. Settings Persistence

```python
# User preferences to save:
{
    "search_provider": "musicbrainz",  # or "itunes"
    "auto_fallback_to_itunes": True,   # if musicbrainz has no results
    "database_location": "app_data/musicbrainz",
    "last_update_check": "2025-05-23T10:30:00Z"
}
```

### 7. Error Handling

Handle these scenarios gracefully:
- Network connection issues during download
- Corrupted database files
- Insufficient disk space
- Database download interrupted
- Search timeouts

Show user-friendly error messages and offer alternatives.

### 8. Database URLs and Files

```python
# URLs to use:
CANONICAL_BASE_URL = "https://data.metabrainz.org/pub/musicbrainz/canonical_data/"
TARGET_FILE = "canonical_musicbrainz_data.csv.zst"

# File structure after download:
app_data/
└── musicbrainz/
    ├── musicbrainz.db          # SQLite database
    ├── metadata.json           # Version info, download date
    └── temp/                   # Temporary extraction folder
```

### 9. Key User Stories

1. **New User**: "I want to search music but haven't downloaded database yet"
   - Show download prompt with size estimate
   - Allow one-time iTunes API usage
   - Remember user's choice

2. **Existing User**: "I want to update my database"
   - Manual check for updates button
   - Show current vs available version
   - Update only if user confirms

3. **Storage-Conscious User**: "I want to free up space"
   - Clear database deletion with size info
   - Switch to iTunes API automatically
   - Easy re-download when needed

4. **Offline User**: "I want to search without internet"
   - Use local database only
   - Show helpful message if database missing
   - No automatic online fallback

### 10. Implementation Priority

1. **Phase 1**: Basic download/delete functionality
2. **Phase 2**: Search integration with existing code
3. **Phase 3**: Settings UI and provider switching
4. **Phase 4**: Progress dialogs and error handling
5. **Phase 5**: Update checking and optimization

### 11. Dependencies to Add

```
pip install requests zstandard sqlite3
```

### 12. Testing Requirements

Create tests for:
- Database download and extraction
- Search functionality with various inputs
- Settings persistence
- Error conditions (network issues, corrupted files)
- Provider switching behavior

## Notes for Implementation

- Keep existing iTunes API code intact
- Make MusicBrainz the default but not mandatory
- Always give users control over downloads
- Show clear storage impact information
- Handle all operations asynchronously to avoid UI blocking
- Use appropriate progress indicators for long operations

## Success Criteria

- User can choose between MusicBrainz offline and iTunes API online
- Database downloads work reliably with progress indication
- Search results are fast and accurate from local database
- Users can manage database storage easily
- Fallback to iTunes API works seamlessly when needed