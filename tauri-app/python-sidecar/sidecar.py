#!/usr/bin/env python3
"""
Apple Music History Converter - Python Sidecar for Tauri
JSON-based IPC wrapper for the existing Python backend.

This sidecar communicates with the Tauri frontend via stdin/stdout JSON messages.
"""

import json
import sys
import os
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
import queue

# Add the source directory to the path
# Prefer bundled resources when available
resource_dir = os.getenv("APP_RESOURCE_DIR")
if resource_dir:
    resource_path = Path(resource_dir)
    bundled_src = resource_path / "src" / "apple_music_history_converter"
    if bundled_src.exists():
        sys.path.insert(0, str(bundled_src))
    else:
        alt_src = resource_path / "apple_music_history_converter"
        if alt_src.exists():
            sys.path.insert(0, str(alt_src))

# Dev fallback (repo layout)
src_dir = Path(__file__).parent.parent.parent / "src" / "apple_music_history_converter"
sys.path.insert(0, str(src_dir))

# Import the existing modules
try:
    from music_search_service_v2 import MusicSearchServiceV2
    from ultra_fast_csv_processor import UltraFastCSVProcessor
    import export_formats
    from logging_config import get_logger
except ImportError as e:
    print(json.dumps({
        "type": "error",
        "error": f"Failed to import modules: {e}",
        "traceback": traceback.format_exc()
    }), file=sys.stderr, flush=True)
    sys.exit(1)

logger = get_logger(__name__)


class SidecarHandler:
    """Handles IPC messages from Tauri frontend."""
    
    def __init__(self):
        self.music_service: Optional[MusicSearchServiceV2] = None
        self.csv_processor: Optional[UltraFastCSVProcessor] = None
        self.current_df = None
        self.current_tracks = []
        self.search_thread: Optional[threading.Thread] = None
        self.stop_search = False
        self.pause_search = False
        self.result_queue = queue.Queue()
        
    def send_message(self, msg: Dict[str, Any]):
        """Send JSON message to stdout for Tauri to receive."""
        print(json.dumps(msg), flush=True)
        
    def send_error(self, error: str, context: str = ""):
        """Send error message."""
        self.send_message({
            "type": "error",
            "error": error,
            "context": context
        })
        
    def send_progress(self, current: int, total: int, found: int, missing: int, 
                      provider: str, status: str, current_track: str = ""):
        """Send search progress update."""
        self.send_message({
            "type": "progress",
            "current": current,
            "total": total,
            "found": found,
            "missing": missing,
            "provider": provider,
            "status": status,
            "currentTrack": current_track
        })
        
    def initialize_service(self):
        """Initialize the music search service."""
        try:
            if self.music_service is None:
                self.music_service = MusicSearchServiceV2()
                self.csv_processor = UltraFastCSVProcessor()
            self.send_message({
                "type": "initialized",
                "success": True
            })
        except Exception as e:
            self.send_error(str(e), "initialize_service")
            
    def get_database_status(self) -> Dict[str, Any]:
        """Get status of available databases/APIs."""
        status = {
            "musicbrainz": {
                "available": False,
                "trackCount": 0
            },
            "musicbrainzApi": {
                "available": True
            },
            "itunes": {
                "available": True
            },
            "appleMusic": {
                "available": False,
                "configured": False
            }
        }
        
        # Check if MusicBrainz local database exists
        if self.music_service:
            try:
                # Check for local MusicBrainz database
                mb_manager = self.music_service.get_musicbrainz_manager()
                if mb_manager and hasattr(mb_manager, 'is_database_available'):
                    status["musicbrainz"]["available"] = mb_manager.is_database_available()
                    if hasattr(mb_manager, 'get_track_count'):
                        status["musicbrainz"]["trackCount"] = mb_manager.get_track_count()
            except Exception:
                pass
                
        self.send_message({
            "type": "databaseStatus",
            **status
        })
        return status
        
    def analyze_csv(self, file_path: str) -> Dict[str, Any]:
        """Analyze a CSV file and return info."""
        try:
            path = Path(file_path)
            if not path.exists():
                self.send_error(f"File not found: {file_path}", "analyze_csv")
                return {}
                
            # Use the ultra fast processor for analysis
            import pandas as pd
            
            # Quick analysis - read first few lines to detect format
            with open(path, 'r', encoding='utf-8-sig') as f:
                first_line = f.readline().strip()
                
            # Count total lines
            with open(path, 'r', encoding='utf-8-sig') as f:
                row_count = sum(1 for _ in f) - 1  # Subtract header
                
            # Detect file type
            if "Play Duration Milliseconds" in first_line:
                file_type = "Play Activity"
            elif "Date Played" in first_line:
                file_type = "Recently Played Tracks"
            elif "Play Count" in first_line:
                file_type = "Play History Daily Tracks"
            else:
                file_type = "Unknown"
                
            result = {
                "type": "fileAnalysis",
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "rowCount": row_count,
                "fileType": file_type
            }
            
            self.send_message(result)
            return result
            
        except Exception as e:
            self.send_error(str(e), "analyze_csv")
            return {}

    def get_preview(self, file_path: str) -> bool:
        """Get first 5 rows of CSV for preview."""
        try:
            import pandas as pd
            import io
            
            # Read just the first few lines to avoid loading huge files
            df = pd.read_csv(file_path, nrows=5, encoding='utf-8-sig')
            
            # fill na
            df = df.fillna('')
            
            # Convert to list of lists (header + rows)
            header = df.columns.tolist()
            rows = df.values.tolist()
            
            # We just want the data rows for the frontend, usually
            # But let's send rows, frontend can format
            # Actually frontend Table expects string[][]
            
            # Format all as strings
            formatted_rows = [[str(x) for x in row] for row in rows]
            
            self.send_message({
                "type": "csvPreview",
                "path": file_path,
                "rows": formatted_rows
            })
            return True
            
        except Exception as e:
            self.send_error(str(e), "get_preview")
            return False

            
    def load_csv(self, file_path: str) -> bool:
        """Load and process a CSV file."""
        try:
            import pandas as pd
            
            self.send_message({
                "type": "status",
                "status": "Loading CSV file..."
            })
            
            # Use pandas to load
            self.current_df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Convert to list of dicts for processing
            self.current_tracks = self.current_df.to_dict('records')
            
            self.send_message({
                "type": "csvLoaded",
                "success": True,
                "rowCount": len(self.current_tracks)
            })
            
            return True
            
        except Exception as e:
            self.send_error(str(e), "load_csv")
            return False
            
    def start_search(self, provider: str):
        """Start searching tracks with specified provider."""
        if not self.current_tracks:
            self.send_error("No tracks loaded", "start_search")
            return
            
        self.stop_search = False
        self.pause_search = False
        
        def search_worker():
            found = 0
            missing = 0
            total = len(self.current_tracks)
            
            for i, track in enumerate(self.current_tracks):
                if self.stop_search:
                    self.send_message({
                        "type": "searchStopped",
                        "current": i,
                        "total": total,
                        "found": found,
                        "missing": missing
                    })
                    return
                    
                while self.pause_search and not self.stop_search:
                    import time
                    time.sleep(0.1)
                    
                if self.stop_search:
                    return
                    
                # Get track info
                artist = track.get('Artist', track.get('artist', ''))
                title = track.get('Title', track.get('title', 
                         track.get('Track Description', track.get('Song Name', ''))))
                album = track.get('Album', track.get('album', ''))
                
                track_name = f"{artist} - {title}"
                
                # Send progress
                self.send_progress(
                    current=i + 1,
                    total=total,
                    found=found,
                    missing=missing,
                    provider=provider,
                    status=f"Searching...",
                    current_track=track_name
                )
                
                # Perform actual search using music service
                try:
                    if self.music_service:
                        result = self.music_service.search_track(
                            artist=artist,
                            title=title,
                            album=album,
                            provider=provider
                        )
                        
                        if result and result.get('found'):
                            found += 1
                            # Update track with found info
                            track['_found'] = True
                            track['_mbid'] = result.get('mbid', '')
                            track['_album_found'] = result.get('album', album)
                            track['_artist_found'] = result.get('artist', artist)
                        else:
                            missing += 1
                            track['_found'] = False
                    else:
                        # Mock search for testing
                        import random
                        if random.random() > 0.2:  # 80% success rate
                            found += 1
                            track['_found'] = True
                        else:
                            missing += 1
                            track['_found'] = False
                            
                except Exception as e:
                    missing += 1
                    track['_found'] = False
                    track['_error'] = str(e)
                    
            # Search complete
            self.send_message({
                "type": "searchComplete",
                "total": total,
                "found": found,
                "missing": missing,
                "provider": provider
            })
            
        self.search_thread = threading.Thread(target=search_worker, daemon=True)
        self.search_thread.start()
        
    def pause_search_toggle(self) -> bool:
        """Toggle pause state of search."""
        self.pause_search = not self.pause_search
        self.send_message({
            "type": "searchPaused",
            "paused": self.pause_search
        })
        return self.pause_search
        
    def stop_search_now(self):
        """Stop the current search."""
        self.stop_search = True
        self.pause_search = False
        
    def export_results(self, format_key: str, output_path: str) -> bool:
        """Export results to specified format."""
        try:
            if not self.current_tracks:
                self.send_error("No tracks to export", "export_results")
                return False
                
            self.send_message({
                "type": "status",
                "status": f"Exporting to {format_key} format..."
            })
            
            # Use the export_formats module
            success = export_formats.export_tracks(
                format_key=format_key,
                tracks=self.current_tracks,
                output_path=output_path,
                original_df=self.current_df
            )
            
            self.send_message({
                "type": "exportComplete",
                "success": success,
                "format": format_key,
                "path": output_path
            })
            
            return success
            
        except Exception as e:
            self.send_error(str(e), "export_results")
            return False
            
    def handle_message(self, msg: Dict[str, Any]):
        """Handle incoming IPC message."""
        action = msg.get("action", "")
        
        try:
            if action == "initialize":
                self.initialize_service()
                
            elif action == "getDatabaseStatus":
                self.get_database_status()
                
            elif action == "analyzeCSV":
                self.analyze_csv(msg.get("path", ""))
                
            elif action == "loadCSV":
                self.load_csv(msg.get("path", ""))

            elif action == "getPreview":
                self.get_preview(msg.get("path", ""))
                
            elif action == "startSearch":
                self.start_search(msg.get("provider", "musicbrainz"))
                
            elif action == "pauseSearch":
                self.pause_search_toggle()
                
            elif action == "stopSearch":
                self.stop_search_now()
                
            elif action == "export":
                self.export_results(
                    msg.get("format", "lastfm"),
                    msg.get("path", "")
                )
                
            elif action == "setProvider":
                if self.music_service:
                    self.music_service.set_search_provider(msg.get("provider", "musicbrainz"))
                self.send_message({
                    "type": "providerSet",
                    "provider": msg.get("provider", "musicbrainz")
                })
                
            elif action == "ping":
                self.send_message({"type": "pong"})
                
            else:
                self.send_error(f"Unknown action: {action}", "handle_message")
                
        except Exception as e:
            self.send_error(str(e), f"handle_message:{action}")
            

def main():
    """Main entry point for sidecar."""
    handler = SidecarHandler()
    
    # Send ready message
    handler.send_message({
        "type": "ready",
        "version": "3.0.0"
    })
    
    # Read messages from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        try:
            msg = json.loads(line)
            handler.handle_message(msg)
        except json.JSONDecodeError as e:
            handler.send_error(f"Invalid JSON: {e}", "main")
        except Exception as e:
            handler.send_error(f"Error: {e}", "main")
            

if __name__ == "__main__":
    main()
