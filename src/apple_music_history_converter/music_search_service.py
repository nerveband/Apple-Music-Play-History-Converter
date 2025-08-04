import os
import json
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from musicbrainz_manager import MusicBrainzManager


class MusicSearchService:
    """Service to route music searches between MusicBrainz and iTunes API."""
    
    def __init__(self, settings_file: str = None):
        # Completely avoid the problematic mkdir by ensuring the path is always writable
        if settings_file is None:
            # Always use home directory with a simple subdirectory name
            settings_file = Path.home() / ".apple_music_converter" / "settings.json"
        
        self.settings_file = Path(settings_file)
        
        # Create parent directory only when actually needed (in _save_settings)
        # This avoids the read-only filesystem issue entirely
        
        self.musicbrainz_manager = MusicBrainzManager()
        self.settings = self._load_settings()
        self._progressive_loading_started = False
        
    def _load_settings(self) -> Dict:
        """Load user settings from file."""
        default_settings = {
            "search_provider": "musicbrainz",  # or "itunes"
            "auto_fallback_to_itunes": True,
            "database_location": str(Path.home() / ".apple_music_converter" / "musicbrainz"),
            "last_update_check": None
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
                print(f"Warning: Could not load settings file: {e}")
            except Exception as e:
                print(f"Unexpected error loading settings: {e}")
        
        return default_settings
    
    def _save_settings(self):
        """Save current settings to file."""
        try:
            # Create parent directory only when actually saving
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except (OSError, json.JSONEncodeError) as e:
            print(f"Warning: Could not save settings file: {e}")
        except Exception as e:
            print(f"Unexpected error saving settings: {e}")
    
    def get_search_provider(self) -> str:
        """Get current search provider preference."""
        return self.settings.get("search_provider", "musicbrainz")
    
    def set_search_provider(self, provider: str):
        """Set search provider preference."""
        if provider in ["musicbrainz", "itunes"]:
            self.settings["search_provider"] = provider
            self._save_settings()
    
    def get_auto_fallback(self) -> bool:
        """Get auto fallback to iTunes setting."""
        return self.settings.get("auto_fallback_to_itunes", True)
    
    def set_auto_fallback(self, enabled: bool):
        """Set auto fallback to iTunes setting."""
        self.settings["auto_fallback_to_itunes"] = enabled
        self._save_settings()
    
    def get_database_path(self) -> Optional[str]:
        """Get the path to the MusicBrainz CSV file."""
        if self.musicbrainz_manager and self.musicbrainz_manager.csv_file:
            return str(self.musicbrainz_manager.csv_file)
        return None
    
    def start_progressive_loading(self, progress_callback=None):
        """Start progressive loading for instant searches."""
        if not self._progressive_loading_started and self.musicbrainz_manager.is_database_available():
            self._progressive_loading_started = True
            return self.musicbrainz_manager.start_progressive_loading(progress_callback)
        return True
    
    def search_song(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """
        Main search method that routes to appropriate provider.
        
        Returns:
            Dict with keys:
            - success: bool
            - artist: str (if found)
            - source: str ("musicbrainz", "itunes", or "none")
            - requires_download: bool (if MusicBrainz DB needed)
            - search_params: tuple (for retrying after download)
            - error: str (if error occurred)
        """
        
        provider = self.get_search_provider()
        
        if provider == "musicbrainz":
            # Auto-start progressive loading if not started
            if not self._progressive_loading_started and self.musicbrainz_manager.is_database_available():
                self.start_progressive_loading()
            
            return self._search_musicbrainz(song_name, artist_name, album_name)
        elif provider == "itunes":
            return {
                "success": False,
                "source": "itunes",
                "use_itunes": True,  # Signal to use existing iTunes implementation
                "search_params": (song_name, artist_name, album_name)
            }
        else:
            return {
                "success": False,
                "source": "none",
                "error": "Invalid search provider"
            }
    
    def _search_musicbrainz(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search using MusicBrainz database."""
        
        # Check if database is available
        if not self.musicbrainz_manager.is_database_available():
            return {
                "success": False,
                "source": "musicbrainz",
                "requires_download": True,
                "search_params": (song_name, artist_name, album_name)
            }
        
        try:
            # Search MusicBrainz database
            results = self.musicbrainz_manager.search(song_name, artist_name, album_name)
            
            if results:
                # Return the best match
                best_match = results[0]
                return {
                    "success": True,
                    "artist": best_match["artistName"],
                    "source": "musicbrainz",
                    "track_name": best_match["trackName"],
                    "album_name": best_match.get("collectionName", ""),
                    "all_results": results
                }
            else:
                # No results found in MusicBrainz
                if self.get_auto_fallback():
                    # Try iTunes API as fallback
                    return {
                        "success": False,
                        "source": "musicbrainz",
                        "use_itunes_fallback": True,
                        "search_params": (song_name, artist_name, album_name)
                    }
                else:
                    return {
                        "success": False,
                        "source": "musicbrainz",
                        "error": "No results found in MusicBrainz database"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "source": "musicbrainz",
                "error": f"MusicBrainz search error: {str(e)}"
            }
    
    def get_database_info(self) -> Dict:
        """Get information about the MusicBrainz database."""
        return self.musicbrainz_manager.get_database_info()
    
    def download_database(self, progress_callback=None) -> bool:
        """Download MusicBrainz database."""
        return self.musicbrainz_manager.download_database(progress_callback)
    
    def import_database_file(self, file_path: str, progress_callback=None) -> bool:
        """Import MusicBrainz database from a manually downloaded file."""
        return self.musicbrainz_manager.import_database_file(file_path, progress_callback)
    
    def delete_database(self) -> bool:
        """Delete MusicBrainz database."""
        return self.musicbrainz_manager.delete_database()
    
    def check_for_updates(self) -> Tuple[bool, str]:
        """Check for database updates."""
        return self.musicbrainz_manager.check_for_updates()
    
    def cancel_download(self):
        """Cancel ongoing database download."""
        self.musicbrainz_manager.cancel_download()
    
    def get_database_status(self) -> Dict:
        """Get comprehensive database status information."""
        db_info = self.musicbrainz_manager.get_database_info()
        
        return {
            "downloaded": db_info["exists"],
            "size": db_info["size_mb"] * 1024 * 1024,  # Convert to bytes
            "updated": db_info["last_updated"],
            "track_count": db_info["track_count"],
            "version": db_info["version"]
        }
    
    def is_loading_complete(self) -> bool:
        """Check if progressive loading is complete."""
        return self.musicbrainz_manager.is_loading_complete()
    
    def get_loading_status(self) -> str:
        """Get current loading status."""
        return self.musicbrainz_manager.get_loading_status()
