#!/usr/bin/env python3
"""
MusicBrainz Manager with DuckDB CSV Direct Query
Fast searching without database building - uses CSV files directly.
"""

import os
import requests
import gzip
import tarfile
import zstandard as zstd
import json
import sqlite3
import logging
import tarfile
from pathlib import Path
from typing import List, Dict, Optional, Callable
import duckdb
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MusicBrainzManager:
    """
    MusicBrainz database manager with CSV direct querying.
    No database building required - queries CSV files directly using DuckDB.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize MusicBrainz manager."""
        if data_dir is None:
            # Use simple home directory path to avoid read-only issues
            data_dir = Path.home() / ".apple_music_converter" / "musicbrainz"
        
        self.data_dir = Path(data_dir)
        self.csv_file = None
        self.parquet_file = None
        self.metadata_file = self.data_dir / 'metadata.json'
        self._view_created = False  # Track if we've already created the table
        
        # Progressive loading attributes
        self._progressive_loader = None
        self._loading_complete = False
        self._search_cache = {}
        self._fuzzy_cache = {}
        
        # Download cancellation flag
        self._download_cancelled = False
        
        # Initialize DuckDB connection with optimized settings for large CSV files
        self.conn = duckdb.connect()
        self.conn.execute("SET memory_limit='4GB'")  # Increase memory limit
        self.conn.execute("SET threads=2")  # Reduce threads to save memory
        # Enable optimizations for better performance
        self.conn.execute("SET enable_progress_bar=false")  # Disable progress bars for faster execution
        self.conn.execute("SET enable_object_cache=true")   # Enable object caching
        self.conn.execute("SET preserve_insertion_order=false")  # Save memory during operations
        
        # Find existing CSV file
        self._find_csv_file()
    
    def _find_csv_file(self):
        """Find existing CSV file in data directory."""
        if self.data_dir.exists():
            csv_files = list(self.data_dir.rglob("*.csv"))
            if csv_files:
                # Use the largest CSV file
                self.csv_file = max(csv_files, key=lambda f: f.stat().st_size)
                logger.info(f"Found CSV file: {self.csv_file}")
    
    def download_database(self, progress_callback: Optional[Callable] = None) -> bool:
        """Download and extract latest MusicBrainz canonical database."""
        try:
            # Reset cancellation flag
            self._download_cancelled = False
            
            # Create data directory
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            if progress_callback:
                progress_callback("Finding latest MusicBrainz canonical export...", 0, None)
            
            # Get list of canonical data directories
            canonical_base_url = "https://data.metabrainz.org/pub/musicbrainz/canonical_data/"
            
            # Get directory listing to find latest canonical directory
            response = requests.get(canonical_base_url)
            response.raise_for_status()
            
            # Parse HTML to find canonical dump directories
            import re
            canonical_dirs = re.findall(r'href="(musicbrainz-canonical-dump-[^"/]*/)?"', response.text)
            # Filter out None values and remove trailing "?"
            canonical_dirs = [d.rstrip('?') for d in canonical_dirs if d and 'musicbrainz-canonical-dump-' in d]
            
            if not canonical_dirs:
                logger.error("No canonical dump directories found")
                return False
            
            # Sort directories to get the latest (they have date in name)
            canonical_dirs.sort(reverse=True)
            latest_dir = canonical_dirs[0]
            
            if progress_callback:
                progress_callback(f"Found latest canonical dump: {latest_dir}", 3, None)
            
            # Now get the .tar.zst file from the latest directory
            latest_dir_url = canonical_base_url + latest_dir
            dir_response = requests.get(latest_dir_url)
            dir_response.raise_for_status()
            
            # Find .tar.zst files in the directory
            tar_files = re.findall(r'href="([^"]*\.tar\.zst)"', dir_response.text)
            
            if not tar_files:
                logger.error(f"No .tar.zst files found in {latest_dir}")
                return False
            
            # Use the first (and likely only) .tar.zst file
            latest_filename = tar_files[0]
            url = latest_dir_url + latest_filename
            
            if progress_callback:
                progress_callback(f"Starting download of {latest_filename}...", 5, {"url": url})
            
            download_path = self.data_dir / latest_filename
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_progress_update = 0
            progress_update_threshold = 1024 * 1024  # Update progress every 1MB
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # Check for cancellation
                    if self._download_cancelled:
                        f.close()
                        if download_path.exists():
                            download_path.unlink()  # Delete partial file
                        return False
                    
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Only update progress every 1MB or at completion
                        if (total_size > 0 and progress_callback and 
                            (downloaded_size - last_progress_update >= progress_update_threshold or 
                             downloaded_size >= total_size)):
                            progress = 5 + (downloaded_size / total_size) * 70  # 5-75% for download
                            mb_downloaded = downloaded_size / (1024 * 1024)
                            progress_callback(f"Downloading: {mb_downloaded:.1f} MB downloaded", progress, None)
                            last_progress_update = downloaded_size
            
            if progress_callback:
                progress_callback("Extracting canonical database files...", 80, None)
            
            # Extract and convert to CSV
            return self._extract_and_convert_canonical_csv(download_path, progress_callback)
            
        except Exception as e:
            logger.error(f"Error downloading canonical database: {e}")
            return False
    
    def cancel_download(self):
        """Cancel the current download operation."""
        self._download_cancelled = True
        logger.info("Download cancellation requested")
    
    def _extract_and_convert_canonical_csv(self, tar_file: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Extract canonical database files from .tar.zst archive."""
        try:
            # Extract the tar.zst file
            extract_dir = self.data_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback("Decompressing zstd archive...", 85)
            
            with open(tar_file, 'rb') as compressed_file:
                dctx = zstd.ZstdDecompressor()
                
                with tarfile.open(fileobj=dctx.stream_reader(compressed_file), mode='r|') as tar:
                    tar.extractall(extract_dir)
            
            if progress_callback:
                progress_callback("Finding canonical CSV file...", 90)
            
            # Look specifically for canonical_musicbrainz_data.csv
            canonical_csv_path = None
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == "canonical_musicbrainz_data.csv":
                        canonical_csv_path = Path(root) / file
                        break
                if canonical_csv_path:
                    break
            
            if not canonical_csv_path or not canonical_csv_path.exists():
                logger.error("canonical_musicbrainz_data.csv not found in extracted archive")
                return False
            
            # Copy to data directory
            self.csv_file = self.data_dir / "canonical_musicbrainz_data.csv"
            import shutil
            shutil.copy2(canonical_csv_path, self.csv_file)
            
            if progress_callback:
                progress_callback("Saving metadata...", 95)
            
            # Save metadata
            self._save_metadata()
            
            if progress_callback:
                progress_callback("Setup complete!", 100)
            
            # Clean up extracted files
            shutil.rmtree(extract_dir)
            
            logger.info(f"Canonical CSV file imported: {self.csv_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error extracting canonical CSV: {e}")
            return False
    
    def _extract_and_convert_to_csv(self, tar_file: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Legacy method for backward compatibility with non-canonical files."""
        try:
            # Extract the tar.bz2 file
            extract_dir = self.data_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            with tarfile.open(tar_file, 'r:bz2') as tar:
                tar.extractall(extract_dir)
            
            if progress_callback:
                progress_callback("Converting to CSV...", 90)
            
            # Find the CSV file in extracted content
            csv_files = list(extract_dir.rglob("*.csv"))
            if not csv_files:
                logger.error("No CSV file found in extracted archive")
                return False
            
            # Use the largest CSV file (main data file)
            source_csv = max(csv_files, key=lambda f: f.stat().st_size)
            
            # Copy to data directory
            self.csv_file = self.data_dir / "canonical_musicbrainz_data.csv"
            import shutil
            shutil.copy2(source_csv, self.csv_file)
            
            if progress_callback:
                progress_callback("Saving metadata...", 95)
            
            # Save metadata
            self._save_metadata()
            
            if progress_callback:
                progress_callback("Setup complete!", 100)
            
            # Clean up extracted files
            shutil.rmtree(extract_dir)
            
            logger.info(f"CSV file imported: {self.csv_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error extracting and converting to CSV: {e}")
            return False
    
    def import_database_file(self, file_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """Import MusicBrainz data from a tar.bz2 or tar.zst file."""
        try:
            tar_path = Path(file_path)
            if not tar_path.exists():
                logger.error(f"File not found: {tar_path}")
                return False
            
            # Create data directory
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            if progress_callback:
                progress_callback("Starting import...", 0)
            
            # Extract the archive
            extract_dir = self.data_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback("Extracting archive... This may take several minutes for large files.", 10)
            
            # Handle different archive types
            try:
                if tar_path.suffix == '.zst':
                    # Handle .tar.zst files
                    if progress_callback:
                        progress_callback("Decompressing zstd archive...", 20)
                    
                    with open(tar_path, 'rb') as compressed_file:
                        dctx = zstd.ZstdDecompressor()
                        
                        if progress_callback:
                            progress_callback("Opening compressed stream...", 30)
                        
                        # Create a progress-tracking reader
                        file_size = tar_path.stat().st_size
                        bytes_read = 0
                        
                        def track_progress(data):
                            nonlocal bytes_read
                            bytes_read += len(data)
                            if progress_callback and bytes_read % (50 * 1024 * 1024) == 0:  # Every 50MB
                                percentage = min(40 + (bytes_read / file_size) * 30, 70)
                                progress_callback(f"Processing: {bytes_read / (1024*1024):.0f}MB...", percentage)
                            return data
                        
                        if progress_callback:
                            progress_callback("Extracting files from archive...", 40)
                        
                        with tarfile.open(fileobj=dctx.stream_reader(compressed_file), mode='r|') as tar:
                            extracted_members = 0
                            
                            for member in tar:
                                tar.extract(member, extract_dir)
                                extracted_members += 1
                                if extracted_members % 200 == 0 and progress_callback:
                                    # Update progress every 200 files
                                    current_progress = min(40 + (extracted_members / 2000) * 30, 70)
                                    progress_callback(f"Extracted {extracted_members} files...", current_progress)
                
                elif tar_path.suffix == '.bz2':
                    # Handle .tar.bz2 files
                    if progress_callback:
                        progress_callback("Extracting bz2 archive...", 20)
                    
                    with tarfile.open(tar_path, 'r:bz2') as tar:
                        members = tar.getmembers()
                        total_members = len(members)
                        
                        for i, member in enumerate(members):
                            tar.extract(member, extract_dir)
                            if progress_callback and i % 50 == 0:
                                progress = 20 + (i / total_members) * 50  # 20-70% for extraction
                                progress_callback(f"Extracting: {i+1}/{total_members} files", progress)
                else:
                    # Handle regular tar files
                    if progress_callback:
                        progress_callback("Extracting tar archive...", 20)
                    
                    with tarfile.open(tar_path, 'r') as tar:
                        members = tar.getmembers()
                        total_members = len(members)
                        
                        for i, member in enumerate(members):
                            tar.extract(member, extract_dir)
                            if progress_callback and i % 50 == 0:
                                progress = 20 + (i / total_members) * 50  # 20-70% for extraction
                                progress_callback(f"Extracting: {i+1}/{total_members} files", progress)
                
            except Exception as e:
                logger.error(f"Error during extraction: {e}")
                if progress_callback:
                    progress_callback(f"Extraction error: {e}", 0)
                return False
            
            if progress_callback:
                progress_callback("Finding CSV file...", 75)
            
            # Look specifically for canonical_musicbrainz_data.csv first
            canonical_csv_path = None
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == "canonical_musicbrainz_data.csv":
                        canonical_csv_path = Path(root) / file
                        break
                if canonical_csv_path:
                    break
            
            if canonical_csv_path and canonical_csv_path.exists():
                source_csv = canonical_csv_path
                logger.info(f"Found canonical CSV file: {source_csv} ({source_csv.stat().st_size / (1024*1024):.1f} MB)")
            else:
                # Fall back to largest CSV file for legacy imports
                csv_files = list(extract_dir.rglob("*.csv"))
                if not csv_files:
                    logger.error("No CSV file found in extracted archive")
                    if progress_callback:
                        progress_callback("Error: No CSV files found", 0)
                    return False
                
                # Use the largest CSV file (main data file)
                source_csv = max(csv_files, key=lambda f: f.stat().st_size)
                logger.info(f"Found CSV file: {source_csv} ({source_csv.stat().st_size / (1024*1024):.1f} MB)")
            
            if progress_callback:
                progress_callback("Copying CSV file...", 85)
            
            # Copy to data directory
            self.csv_file = self.data_dir / "canonical_musicbrainz_data.csv"
            import shutil
            shutil.copy2(source_csv, self.csv_file)
            
            if progress_callback:
                progress_callback("Saving metadata...", 95)
            
            # Save metadata
            self._save_metadata()
            
            if progress_callback:
                progress_callback("Import complete!", 100)
            
            # Clean up extracted files
            shutil.rmtree(extract_dir, ignore_errors=True)
            
            logger.info(f"CSV file imported: {self.csv_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing file: {e}")
            if progress_callback:
                progress_callback(f"Import failed: {e}", 0)
            return False
    
    def _save_metadata(self):
        """Save metadata."""
        metadata = {
            "created": datetime.now().isoformat(),
            "source_file": str(self.csv_file),
            "last_updated": datetime.now().isoformat(),
            "data_type": "canonical",
            "format_version": "2.0"
        }
        
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata saved: {self.metadata_file}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def start_progressive_loading(self, progress_callback: Optional[Callable] = None):
        """Start progressive loading of MusicBrainz data for instant searches."""
        import threading
        import time
        
        if not self.csv_file or not self.csv_file.exists():
            logger.error("CSV file not available. Please download or import data first.")
            return False
        
        if self._loading_complete:
            logger.info("Progressive loading already complete")
            return True
        
        def load_in_background():
            try:
                logger.info("Starting progressive loading for enhanced searches...")
                overall_start = time.time()
                
                if progress_callback:
                    progress_callback("Setting up basic search capabilities...", 10, overall_start)
                
                # Ensure basic view is ready first (should be fast)
                view_start = time.time()
                self._ensure_csv_view()
                view_time = time.time() - view_start
                logger.info(f"Basic search view created in {view_time:.2f}s")
                
                if progress_callback:
                    progress_callback("Creating enhanced search structures...", 30, overall_start)
                
                # Create a lightweight fuzzy search enhancement
                # Only create if it doesn't exist and is manageable size
                try:
                    # Check if fuzzy table already exists
                    existing_tables = self.conn.execute("SHOW TABLES").fetchall()
                    table_names = [table[0] for table in existing_tables]
                    
                    if 'musicbrainz_fuzzy' not in table_names:
                        if progress_callback:
                            progress_callback("Building fuzzy search optimization (this may take a few minutes)...", 40, overall_start)
                        
                        # Create a sample-based fuzzy table for large datasets
                        logger.info("Creating fuzzy search enhancement...")
                        fuzzy_start = time.time()
                        
                        self.conn.execute("""
                            CREATE TABLE musicbrainz_fuzzy AS 
                            SELECT 
                                artist_credit_name,
                                recording_name,
                                release_name,
                                LOWER(REPLACE(REPLACE(REPLACE(artist_credit_name, 'the ', ''), ' & ', ' '), ' and ', ' ')) as artist_clean,
                                LOWER(REPLACE(REPLACE(recording_name, '(', ''), ')', '')) as recording_clean,
                                LOWER(artist_credit_name) as artist_lower,
                                LOWER(recording_name) as recording_lower,
                                LOWER(release_name) as release_lower
                            FROM musicbrainz_fast
                            WHERE recording_name IS NOT NULL 
                              AND artist_credit_name IS NOT NULL
                              AND length(recording_name) > 2
                              AND length(artist_credit_name) > 2
                            LIMIT 2000000
                        """)
                        
                        fuzzy_time = time.time() - fuzzy_start
                        logger.info(f"Fuzzy search table created in {fuzzy_time:.2f}s")
                        
                        if progress_callback:
                            progress_callback("Creating search indexes...", 80, overall_start)
                        
                        # Create indexes for fuzzy matching
                        index_start = time.time()
                        self.conn.execute("CREATE INDEX idx_artist_clean ON musicbrainz_fuzzy(artist_clean)")
                        self.conn.execute("CREATE INDEX idx_recording_clean ON musicbrainz_fuzzy(recording_clean)")
                        index_time = time.time() - index_start
                        logger.info(f"Search indexes created in {index_time:.2f}s")
                    else:
                        logger.info("Fuzzy search table already exists, skipping creation")
                    
                except Exception as e:
                    logger.warning(f"Fuzzy search enhancement failed (continuing with basic search): {e}")
                
                load_time = time.time() - overall_start
                if progress_callback:
                    progress_callback(f"Progressive loading complete! (Total time: {load_time:.1f}s)", 100, overall_start)
                
                self._loading_complete = True
                logger.info(f"Progressive loading completed in {load_time:.2f}s - Enhanced search ready")
                
            except Exception as e:
                logger.error(f"Error in progressive loading: {e}")
                # Don't fail completely - basic search should still work
                self._loading_complete = False
                if progress_callback:
                    progress_callback(f"Enhanced loading failed, basic search available", 0, time.time())
        
        # Start loading in background thread
        self._progressive_loader = threading.Thread(target=load_in_background, daemon=True)
        self._progressive_loader.start()
        return True
    
    def search(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> List[Dict]:
        """Ultra-fast search with progressive loading and fuzzy matching."""
        import time
        search_start = time.time()
        
        if not self.csv_file or not self.csv_file.exists():
            logger.error("CSV file not available. Please download or import data first.")
            return []
        
        # Create cache key
        cache_key = f"{song_name}:{artist_name}:{album_name}"
        if cache_key in self._search_cache:
            cached_result = self._search_cache[cache_key]
            logger.info(f"Cache hit for '{song_name}': <1ms")
            return cached_result
        
        try:
            # Ensure basic view is ready
            self._ensure_csv_view()
            
            # Try progressive fuzzy search if available
            if self._loading_complete:
                results = self._fuzzy_search(song_name, artist_name, album_name)
            else:
                # Fall back to regular search
                results = self._regular_search(song_name, artist_name, album_name)
            
            # Cache the result
            if len(self._search_cache) > 10000:  # Limit cache size
                self._search_cache.clear()
            self._search_cache[cache_key] = results
            
            total_time = time.time() - search_start
            logger.info(f"Search for '{song_name}': {total_time*1000:.2f}ms -> {len(results)} results")
            
            return results
            
        except Exception as e:
            total_time = time.time() - search_start
            logger.error(f"Error searching MusicBrainz database after {total_time*1000:.2f}ms: {e}")
            return []
    
    def _fuzzy_search(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> List[Dict]:
        """Ultra-fast fuzzy search using optimized structures."""
        import re
        
        # Clean search terms
        clean_song = re.sub(r'[^a-zA-Z0-9]', '', song_name.lower()) if song_name else ''
        clean_artist = re.sub(r'[^a-zA-Z0-9]', '', artist_name.lower()) if artist_name else ''
        
        if not clean_song:
            return []
        
        # Build search strategy: exact > fuzzy > partial
        searches = []
        
        # 1. Exact match (highest priority)
        if clean_artist:
            searches.append((f"artist_clean = '{clean_artist}' AND recording_clean = '{clean_song}'", 100))
        searches.append((f"recording_clean = '{clean_song}'", 90))
        
        # 2. Fuzzy variations
        if clean_artist:
            # Handle "The Band" vs "Band" variations
            artist_variants = [clean_artist]
            if clean_artist.startswith('the'):
                artist_variants.append(clean_artist[3:])
            else:
                artist_variants.append('the' + clean_artist)
            
            for variant in artist_variants:
                searches.append((f"artist_clean LIKE '%{variant}%' AND recording_clean LIKE '%{clean_song}%'", 80))
        
        # 3. Partial matches
        searches.append((f"recording_clean LIKE '%{clean_song}%'", 70))
        
        # Execute searches in priority order
        all_results = []
        for search_condition, priority in searches:
            try:
                query = f"""
                    SELECT DISTINCT
                        artist_credit_name as artist_name,
                        recording_name as track_name,
                        COALESCE(release_name, '') as album_name,
                        0 as track_length,
                        {priority} as match_score
                    FROM musicbrainz_fuzzy
                    WHERE {search_condition}
                    LIMIT 10
                """
                
                results = self.conn.execute(query).fetchall()
                all_results.extend(results)
                
                if len(all_results) >= 5:  # Stop when we have enough results
                    break
                    
            except Exception as e:
                logger.warning(f"Fuzzy search error: {e}")
                continue
        
        # Format and deduplicate results
        formatted_results = []
        seen = set()
        
        for row in all_results:
            key = (row[0], row[1])
            if key not in seen:
                seen.add(key)
                result = {
                    'artistName': row[0],
                    'trackName': row[1],
                    'collectionName': row[2],
                    'trackTimeMillis': row[3],
                    'matchScore': row[4]
                }
                formatted_results.append(result)
        
        # Sort by match score (highest first)
        formatted_results.sort(key=lambda x: x['matchScore'], reverse=True)
        return formatted_results[:5]  # Return top 5 matches
    
    def _regular_search(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> List[Dict]:
        """Regular search for when progressive loading isn't complete."""
        search_terms = []
        if song_name:
            search_terms.append(f"recording_lower ILIKE '%{song_name.lower()}%'")
        if artist_name:
            search_terms.append(f"artist_lower ILIKE '%{artist_name.lower()}%'")
        if album_name:
            search_terms.append(f"release_lower ILIKE '%{album_name.lower()}%'")
        
        if not search_terms:
            return []
        
        where_clause = " AND ".join(search_terms)
        
        query = f"""
            SELECT 
                COALESCE(artist_credit_name, 'Unknown Artist') as artist_name,
                COALESCE(recording_name, 'Unknown Track') as track_name,
                COALESCE(release_name, 'Unknown Album') as album_name,
                0 as track_length
            FROM musicbrainz_fast
            WHERE ({where_clause})
            ORDER BY artist_credit_name, recording_name
            LIMIT 20
        """
        
        results = self.conn.execute(query).fetchall()
        
        formatted_results = []
        for row in results:
            result = {
                'artistName': row[0],
                'trackName': row[1],
                'collectionName': row[2],
                'trackTimeMillis': row[3]
            }
            formatted_results.append(result)
        
        return formatted_results
    
    def _ensure_csv_view(self):
        """Create optimized view for fast searches without heavy upfront loading."""
        import time
        try:
            # Check if we already have the basic view set up
            if hasattr(self, '_view_created') and self._view_created:
                return
            
            logger.info("Setting up fast CSV query view...")
            setup_start = time.time()
            
            # Create a lightweight view directly on the CSV for instant searches
            # This avoids loading everything into memory upfront
            try:
                self.conn.execute("DROP VIEW IF EXISTS musicbrainz_fast")
            except:
                pass
            
            # Create an optimized view with selective indexing
            self.conn.execute(f"""
                CREATE VIEW musicbrainz_fast AS 
                SELECT 
                    artist_credit_name,
                    recording_name,
                    release_name,
                    LOWER(artist_credit_name) as artist_lower,
                    LOWER(recording_name) as recording_lower,
                    LOWER(release_name) as release_lower
                FROM read_csv_auto('{self.csv_file}')
                WHERE recording_name IS NOT NULL 
                  AND recording_name != ''
                  AND artist_credit_name IS NOT NULL
                  AND artist_credit_name != ''
                  AND length(recording_name) > 1
                  AND length(artist_credit_name) > 1
            """)
            
            setup_time = time.time() - setup_start
            logger.info(f"Fast CSV view created in {setup_time:.3f}s - Ready for searches")
            
            self._view_created = True
            
        except Exception as e:
            logger.error(f"Error setting up CSV view: {e}")
            self._view_created = False
    
    def is_database_available(self) -> bool:
        """Check if CSV data is available for searching."""
        return self.csv_file is not None and self.csv_file.exists()
    
    def get_database_info(self) -> Dict:
        """Return information about the CSV data."""
        info = {
            "exists": False,
            "size_mb": 0,
            "last_updated": "Never",
            "version": "Unknown",
            "track_count": 0,
            "type": "CSV Direct Query"
        }
        
        if self.is_database_available():
            info["exists"] = True
            info["size_mb"] = round(self.csv_file.stat().st_size / (1024 * 1024), 1)
            
            # Load metadata if available
            if self.metadata_file.exists():
                try:
                    with open(self.metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        info.update(metadata)
                except Exception:
                    pass
            
            # Get quick count estimate
            try:
                count_result = self.conn.execute(
                    f"SELECT COUNT(*) FROM read_csv_auto('{self.csv_file}')"
                ).fetchone()
                if count_result:
                    info["track_count"] = count_result[0]
            except Exception:
                pass
        
        return info
    
    def delete_database(self) -> bool:
        """Remove CSV data and free up space."""
        try:
            if self.csv_file and self.csv_file.exists():
                self.csv_file.unlink()
                self.csv_file = None
            
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            
            # Clean up extracted directory if it exists
            extract_dir = self.data_dir / "extracted"
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
            
            # Clean up parquet file if it exists
            parquet_file = self.data_dir / "musicbrainz_optimized.parquet"
            if parquet_file.exists():
                parquet_file.unlink()
            
            # Clean up memory table if it exists
            try:
                self.conn.execute("DROP TABLE IF EXISTS musicbrainz_fast")
                self._memory_table_loaded = False
            except:
                pass
            
            return True
        except Exception as e:
            logger.error(f"Error deleting database: {e}")
            return False
    
    def check_for_updates(self) -> tuple:
        """Check for updates by comparing with latest canonical data."""
        try:
            if not self.is_database_available():
                return True, "No local data found"
            
            metadata = self.get_database_info()
            last_updated = metadata.get("last_updated", "Never")
            
            if last_updated == "Never":
                return True, "Data needs to be downloaded"
            
            # Check what's available online
            try:
                canonical_base_url = "https://data.metabrainz.org/pub/musicbrainz/canonical_data/"
                
                # Get directory listing to find latest canonical directory
                response = requests.get(canonical_base_url, timeout=10)
                response.raise_for_status()
                
                # Parse HTML to find canonical dump directories
                import re
                canonical_dirs = re.findall(r'href="(musicbrainz-canonical-dump-[^"/]*/)?"', response.text)
                # Filter out None values and remove trailing "?"
                canonical_dirs = [d.rstrip('?') for d in canonical_dirs if d and 'musicbrainz-canonical-dump-' in d]
                
                if canonical_dirs:
                    # Sort directories to get the latest (they have date in name)
                    canonical_dirs.sort(reverse=True)
                    latest_dir = canonical_dirs[0]
                    
                    # Extract date from directory name (format: musicbrainz-canonical-dump-YYYYMMDD-HHMMSS)
                    date_match = re.search(r'(\d{8})-(\d{6})', latest_dir)
                    if date_match:
                        date_str = date_match.group(1)  # YYYYMMDD
                        time_str = date_match.group(2)  # HHMMSS
                        
                        # Parse the online version date
                        from datetime import datetime
                        online_date = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                        
                        # Parse our local date
                        local_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                        if local_date.tzinfo:
                            local_date = local_date.replace(tzinfo=None)
                        
                        # Compare dates
                        if online_date > local_date:
                            days_newer = (online_date - local_date).days
                            return True, f"Newer version available ({days_newer} days newer)"
                        else:
                            return False, "Data is up to date"
                    else:
                        logger.warning(f"Could not parse date from directory: {latest_dir}")
                        # Fall back to simple age check
                        pass
                else:
                    logger.warning("No canonical directories found online")
                    # Fall back to simple age check
                    pass
                    
            except Exception as e:
                logger.warning(f"Could not check online version: {e}")
                # Fall back to simple age check
                pass
            
            # Fallback: Simple check if data is older than 30 days
            try:
                from datetime import datetime
                last_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                if last_date.tzinfo:
                    last_date = last_date.replace(tzinfo=None)
                days_old = (datetime.now() - last_date).days
                if days_old > 30:
                    return True, f"Data is {days_old} days old, check recommended"
            except Exception:
                pass
            
            return False, "Data appears current"
            
        except Exception as e:
            return False, f"Error checking for updates: {str(e)}"
    
    def is_loading_complete(self) -> bool:
        """Check if progressive loading is complete."""
        return self._loading_complete
    
    def get_loading_status(self) -> str:
        """Get current loading status."""
        if self._loading_complete:
            return "Ready for instant searches"
        elif self._progressive_loader and self._progressive_loader.is_alive():
            return "Progressive loading in progress..."
        else:
            return "Ready for standard searches"
    
    def cleanup(self):
        """Clean up DuckDB connection."""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def __del__(self):
        """Ensure cleanup on destruction."""
        self.cleanup()
