#!/usr/bin/env python3
"""
Music Search Service V2 - Comprehensive Implementation
Integrates with persistent DuckDB MusicBrainz manager and optimization modal.
"""

import os
import sys
import json
import time
import httpx
import urllib.parse
from collections import deque
from threading import RLock
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import logging
import asyncio
import threading

try:
    # Use optimized manager by default
    from .musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized as MusicBrainzManagerV2
    from .optimization_modal import run_with_optimization_modal
    from .trace_utils import TRACE_ENABLED, trace_call, trace_log
    from .app_directories import get_settings_path, get_database_dir
    from .logging_config import get_logger
    from .track_mapping import TrackMappingCache
    from .session_aligner import SessionAligner, AlbumSession
except ImportError:
    # Fall back to optimized manager
    from musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized as MusicBrainzManagerV2
    from optimization_modal import run_with_optimization_modal
    from trace_utils import TRACE_ENABLED, trace_call, trace_log
    from app_directories import get_settings_path, get_database_dir
    from logging_config import get_logger
    from track_mapping import TrackMappingCache
    from session_aligner import SessionAligner, AlbumSession

logger = get_logger(__name__)


class MusicSearchServiceV2:
    """
    Enhanced music search service with comprehensive MusicBrainz integration.
    Features one-time optimization blocking and bidirectional search cascade.
    """

    def __init__(self, settings_file: str = None):
        """Initialize with persistent MusicBrainz manager."""
        logger.info("Initializing MusicSearchServiceV2")

        # Settings management
        if settings_file is None:
            settings_file = get_settings_path()

        self.settings_file = Path(settings_file)
        self.settings = self._load_settings()

        # Initialize new MusicBrainz manager with data directory
        data_dir = str(get_database_dir())
        self.musicbrainz_manager = MusicBrainzManagerV2(data_dir)

        # iTunes API rate limiting (use RLock for reentrant locking)
        self.itunes_lock = RLock()
        self.itunes_requests = deque()

        # MusicBrainz API rate limiting (separate lock to avoid blocking by iTunes)
        self.musicbrainz_api_lock = RLock()

        # Search result cache to avoid duplicate API calls for same track
        # Format: {(song_name, artist_name, album_name): result_dict}
        self._search_cache = {}
        # Cache lock to protect dictionary from concurrent access (CRITICAL for parallel mode)
        self._cache_lock = RLock()

        # Per-user track mapping cache (Phase 3: persistent across sessions)
        self._mapping_cache = TrackMappingCache()

        # Session aligner for album-session alignment (Phase 2: group consecutive album tracks)
        self._session_aligner = SessionAligner(self.musicbrainz_manager)

        # Settings lock to protect dictionary from concurrent access
        # (background threads read settings, main thread writes settings)
        self._settings_lock = RLock()

        # UI integration
        self._parent_window = None
        self._optimization_modal_shown = False

        # Exit flag for graceful shutdown
        self.app_exiting = False

        # Exit event for interruptible sleep (prevents GIL crash on exit)
        # When app_exiting is set to True, this event is set to wake up sleeping threads
        self._exit_event = threading.Event()

        logger.info("MusicSearchServiceV2 initialized")

    def set_parent_window(self, window):
        """Set parent window for modal dialogs."""
        self._parent_window = window

    def _load_settings(self) -> Dict:
        """Load settings from JSON file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading settings: {e}")

        # Default settings
        # NOTE: Adaptive rate limiting was removed - it produced unreliable results.
        # iTunes API uses a fixed rate of itunes_rate_limit (default 20 req/min).
        return {
            "search_provider": "musicbrainz",  # Default to local MusicBrainz database
            "auto_fallback": True,
            "itunes_rate_limit": 20,  # Fixed requests per minute for iTunes API
            "cache_search_results": True  # Cache duplicate track lookups (saves API calls)
        }

    def _save_settings(self):
        """Save settings to JSON file."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.debug(f"Settings saved to: {self.settings_file}")
        except Exception as e:
            logger.error(f"Error saving settings to {self.settings_file}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def get_search_provider(self) -> str:
        """Get current search provider."""
        return self.settings.get("search_provider", "musicbrainz")

    def set_search_provider(self, provider: str):
        """Set search provider (musicbrainz, musicbrainz_api, or itunes)."""
        if provider in ["musicbrainz", "musicbrainz_api", "itunes"]:
            with self._settings_lock:
                self.settings["search_provider"] = provider
                self._save_settings()
            logger.info(f"Search provider set to: {provider}")

    def get_auto_fallback(self) -> bool:
        """Get auto-fallback setting."""
        return self.settings.get("auto_fallback", True)

    def set_auto_fallback(self, enabled: bool):
        """Set auto-fallback to iTunes when MusicBrainz fails."""
        with self._settings_lock:
            self.settings["auto_fallback"] = enabled
            self._save_settings()
        logger.info(f"Auto-fallback set to: {enabled}")

    def clear_search_cache(self):
        """Clear the search result cache.

        This cache prevents duplicate API calls for the same track within a session.
        Normally you don't need to clear it - caching duplicate tracks is beneficial.
        Only clear if you want to force fresh lookups (e.g., after database update).
        """
        # CRITICAL: Protect cache clear with lock (could be called while search is running)
        with self._cache_lock:
            cache_size = len(self._search_cache)
            self._search_cache.clear()
            logger.info(f"Cleared search cache ({cache_size} cached results removed)")

    @trace_call("MusicSearch.ensure_musicbrainz_ready")
    async def ensure_musicbrainz_ready(self) -> bool:
        """
        Ensure MusicBrainz is ready, showing optimization modal if needed.

        Returns:
            True if MusicBrainz is ready, False if not available
        """
        csv_available = self.musicbrainz_manager.is_database_available()
        logger.debug("ensure_musicbrainz_ready: csv_available=%s ready=%s", csv_available, self.musicbrainz_manager.is_ready())
        if TRACE_ENABLED:
            trace_log.debug(
                "ensure_musicbrainz_ready: csv_available=%s ready=%s modal_shown=%s thread=%s",
                csv_available,
                self.musicbrainz_manager.is_ready(),
                self._optimization_modal_shown,
                threading.current_thread().name,
            )

        if not csv_available:
            logger.error("[!] MusicBrainz ensure failed: CSV not available")
            return False

        if self.musicbrainz_manager.is_ready():
            logger.info("[OK] MusicBrainz already marked ready")
            if TRACE_ENABLED:
                trace_log.debug("ensure_musicbrainz_ready -> already ready")
            return True

        # Show optimization modal if we have a parent window
        # NOTE: Removed thread check - Toga's async runs on event loop, not necessarily main thread
        # The modal is safe to use as long as we have a parent window reference
        use_modal = (
            self._parent_window is not None
            and not self._optimization_modal_shown
        )

        if use_modal:
            # Use modal to start and wait for optimization
            self._optimization_modal_shown = True
            try:
                logger.print_always("[T] Starting optimization with modal...")
                await run_with_optimization_modal(
                    self._parent_window,
                    self.musicbrainz_manager.run_optimization_synchronously,
                    cancellation_callback=self.musicbrainz_manager.cancel_optimization
                )
                logger.print_always("[OK] MusicBrainz optimization completed via modal")
                if TRACE_ENABLED:
                    trace_log.debug("Optimization modal completed successfully")
            except Exception as e:
                # Check if it was a user cancellation
                if "cancelled by user" in str(e).lower():
                    logger.warning("[!] Optimization cancelled by user")
                    return False
                # Fall back to iTunes for this session on other errors
                self.set_search_provider("itunes")
                logger.error(f"[!] MusicBrainz optimization modal failed: {e}")
                if TRACE_ENABLED:
                    trace_log.exception("Optimization modal failed: %s", e)
                return False
        else:
            # No UI available or running off the main thread; start optimization and wait silently
            logger.print_always("[T] Starting optimization without modal (background thread)...")
            optimization_started = self.musicbrainz_manager.start_optimization_if_needed()

            if not optimization_started:
                logger.error("[X] Failed to start optimization - CSV not available")
                return False

            # Use ASYNC wait to avoid blocking the UI
            # NOTE: Do NOT call wait_until_ready() here - it uses blocking time.sleep()
            # Timeout increased to 1 hour - optimization of 29M row database takes 30-60 minutes
            logger.print_always("[~] Waiting for MusicBrainz optimization to complete (async)...")
            logger.print_always("    NOTE: This may take 30-60 minutes for large databases")
            start_time = time.time()
            timeout = 3600.0  # 1 hour timeout for large databases
            while not self.musicbrainz_manager.is_ready() and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.5)  # Use async sleep to keep UI responsive

            if not self.musicbrainz_manager.is_ready():
                self.set_search_provider("itunes")
                logger.warning("[!] MusicBrainz optimization timed out; switching to iTunes")
                if TRACE_ENABLED:
                    trace_log.warning("Optimization wait timed out; switching provider to iTunes")
                return False

        ready = self.musicbrainz_manager.is_ready()
        logger.print_always(f"[OK] MusicBrainz readiness check complete: {ready}")
        if TRACE_ENABLED:
            trace_log.debug("ensure_musicbrainz_ready completed with ready=%s", ready)
        return ready

    @trace_call("MusicSearch.search_song")
    async def search_song(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """
        Main search method with comprehensive MusicBrainz integration.

        Returns:
            Dict with keys:
            - success: bool
            - artist: str (if found)
            - source: str ("musicbrainz", "itunes", "cached", or "none")
            - error: str (if error occurred)
        """
        # Phase 3: Check persistent mapping cache first (instant lookup)
        if self._mapping_cache.is_enabled:
            cached = self._mapping_cache.lookup(song_name, album_name, artist_name)
            if cached and cached.get('mb_artist_credit_name'):
                logger.debug(f"Cache hit for '{song_name}' -> '{cached['mb_artist_credit_name']}'")
                return {
                    "success": True,
                    "artist": cached['mb_artist_credit_name'],
                    "source": "cached",
                    "confidence": cached.get('confidence', 'high')
                }

        provider = self.get_search_provider()
        auto_fallback = self.get_auto_fallback()

        logger.debug(f"Searching: song='{song_name}', artist='{artist_name}', album='{album_name}'")
        if TRACE_ENABLED:
            trace_log.debug(
                "search_song: provider=%s song=%s artist=%s album=%s auto_fallback=%s",
                provider,
                song_name,
                artist_name,
                album_name,
                auto_fallback,
            )

        if provider == "musicbrainz":
            # Ensure MusicBrainz is ready (may show modal)
            if not await self.ensure_musicbrainz_ready():
                if auto_fallback:
                    # Fall back to iTunes
                    return await self._search_itunes_async(song_name, artist_name, album_name)
                else:
                    return {
                        "success": False,
                        "source": "none",
                        "error": "MusicBrainz not available and fallback disabled"
                    }

            # Search MusicBrainz
            result = self._search_musicbrainz(song_name, artist_name, album_name)
            if result["success"]:
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz success for %s -> %s", song_name, result.get("artist"))
                # Phase 3: Store in persistent cache for future lookups
                if self._mapping_cache.is_enabled:
                    self._mapping_cache.store(
                        apple_song=song_name,
                        apple_album=album_name,
                        apple_artist=artist_name,
                        mb_artist_credit=result.get("artist", ""),
                        confidence="high"
                    )
                return result

            # If no match and auto-fallback enabled, try iTunes
            if auto_fallback:
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz miss for %s - falling back to iTunes", song_name)
                return await self._search_itunes_async(song_name, artist_name, album_name)
            else:
                return result

        elif provider == "musicbrainz_api":
            # MusicBrainz API search (online, no database needed)
            result = await self._search_musicbrainz_api_async(song_name, artist_name, album_name)
            if result["success"]:
                return result

            # If no match and auto-fallback enabled, try iTunes
            if auto_fallback:
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz API miss for %s - falling back to iTunes", song_name)
                return await self._search_itunes_async(song_name, artist_name, album_name)
            else:
                return result

        elif provider == "itunes":
            # Direct iTunes search
            return await self._search_itunes_async(song_name, artist_name, album_name)

        else:
            return {
                "success": False,
                "source": "none",
                "error": f"Unknown provider: {provider}"
            }

    @trace_call("MusicSearch._search_musicbrainz")
    def _search_musicbrainz(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search using comprehensive MusicBrainz strategy."""
        import time
        search_start = time.time()

        if TRACE_ENABLED:
            trace_log.debug(
                "_search_musicbrainz start song=%s artist=%s album=%s",
                song_name,
                artist_name,
                album_name,
            )

        logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH START ===")
        logger.debug(f"   [=] Inputs: song='{song_name}', artist='{artist_name}', album='{album_name}'")

        try:
            # Check if manager is ready
            if not self.musicbrainz_manager.is_ready():
                elapsed = (time.time() - search_start) * 1000
                logger.debug(f"   [X] MusicBrainz manager not ready after {elapsed:.1f}ms")
                logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH END (NOT READY) ===\n")
                return {
                    "success": False,
                    "source": "musicbrainz",
                    "error": "MusicBrainz not ready - optimization required"
                }

            logger.debug(f"   [OK] MusicBrainz manager is ready - calling search...")

            # Use the comprehensive search with bidirectional cascade
            artist_result = self.musicbrainz_manager.search(
                track_name=song_name,
                artist_hint=artist_name,
                album_hint=album_name
            )

            elapsed = (time.time() - search_start) * 1000

            if artist_result:
                # Check if result is a "bad" placeholder that should trigger fallback
                is_bad = self.musicbrainz_manager._is_bad_result(artist_result)

                # Check if artist hint was provided but result doesn't match
                hint_mismatch = False
                if artist_name and not is_bad:
                    hint_mismatch = not self.musicbrainz_manager._result_matches_hint(artist_result, artist_name)

                if is_bad or hint_mismatch:
                    # Result is bad or doesn't match hint - trigger fallback
                    reason = "bad placeholder result" if is_bad else "doesn't match artist hint"
                    logger.debug(f"   [!] MusicBrainz result '{artist_result}' {reason} - will try fallback")
                    logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH END (BAD MATCH) ===\n")
                    if TRACE_ENABLED:
                        trace_log.debug("MusicBrainz bad match for %s: %s (%s)", song_name, artist_result, reason)
                    return {
                        "success": False,
                        "source": "musicbrainz",
                        "error": f"Result '{artist_result}' {reason}",
                        "partial_result": artist_result  # Keep for debugging
                    }

                logger.debug(f"   [OK] MusicBrainz SUCCESS: Found '{artist_result}' for '{song_name}' in {elapsed:.1f}ms")
                logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH END (SUCCESS) ===\n")
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz artist_result=%s elapsed=%.2fms", artist_result, elapsed)
                return {
                    "success": True,
                    "artist": artist_result,
                    "source": "musicbrainz"
                }
            else:
                logger.debug(f"   [X] MusicBrainz NO MATCH for '{song_name}' after {elapsed:.1f}ms")
                logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH END (NO MATCH) ===\n")
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz no match for %s elapsed=%.2fms", song_name, elapsed)
                return {
                    "success": False,
                    "source": "musicbrainz",
                    "error": "No match found"
                }

        except Exception as e:
            elapsed = (time.time() - search_start) * 1000
            logger.error(f"   [!] MusicBrainz ERROR after {elapsed:.1f}ms: {e}")
            logger.debug(f"[#] === MUSICBRAINZ SERVICE SEARCH END (ERROR) ===\n")
            import traceback
            logger.debug(f"   [BOOKS] Stack trace: {traceback.format_exc()}")
            return {
                "success": False,
                "source": "musicbrainz",
                "error": str(e)
            }

    @trace_call("MusicSearch._search_itunes_async")
    async def _search_itunes_async(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search iTunes API with rate limiting (async wrapper)."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._search_itunes, song_name, artist_name, album_name
        )

    def _safe_print(self, *args, **kwargs):
        """Print with error handling to prevent broken pipe errors."""
        try:
            # Convert to string and use logger
            message = " ".join(str(arg) for arg in args)
            logger.debug(message)
        except BrokenPipeError:
            pass  # Ignore broken pipe errors
        except Exception:
            pass  # Ignore all print errors

    def _debug_log(self, message: str):
        """Write debug message to both console and file for packaged app debugging."""
        # Use logger which handles both console and file automatically
        logger.debug(message)

    def _test_network_connectivity(self) -> Dict:
        """Test basic network connectivity and SSL certificate validation."""
        self._debug_log("=== NETWORK DIAGNOSTICS START ===")

        diagnostics = {
            "network_reachable": False,
            "ssl_working": False,
            "httpx_version": None,
            "certifi_available": False,
            "certifi_path": None,
            "error": None
        }

        try:
            # Check httpx version
            import httpx as httpx_module
            diagnostics["httpx_version"] = httpx_module.__version__
            self._debug_log(f"   httpx version: {httpx_module.__version__}")
        except Exception as e:
            diagnostics["error"] = f"httpx import failed: {e}"
            self._debug_log(f"   [X] httpx import error: {e}")
            return diagnostics

        try:
            # Check certifi
            import certifi
            diagnostics["certifi_available"] = True
            diagnostics["certifi_path"] = certifi.where()
            self._debug_log(f"   certifi available: {certifi.where()}")

            # Verify certificate file exists
            import os
            if os.path.exists(certifi.where()):
                cert_size = os.path.getsize(certifi.where())
                self._debug_log(f"   certifi bundle exists: {cert_size} bytes")
            else:
                self._debug_log(f"   [X] certifi bundle NOT FOUND at {certifi.where()}")
        except Exception as e:
            diagnostics["error"] = f"certifi check failed: {e}"
            self._debug_log(f"   [X] certifi error: {e}")

        # Test simple HTTP connection with explicit SSL context
        try:
            import ssl
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._debug_log("   Testing HTTP connection to apple.com...")
            response = httpx.get("https://www.apple.com", timeout=5, verify=ssl_context)
            diagnostics["network_reachable"] = True
            diagnostics["ssl_working"] = True
            self._debug_log(f"   [OK] Network test successful (status: {response.status_code})")
        except httpx.ConnectError as e:
            diagnostics["error"] = f"Connection error: {e}"
            self._debug_log(f"   [X] Connection error: {e}")
        except httpx.TimeoutException as e:
            diagnostics["error"] = f"Timeout: {e}"
            self._debug_log(f"   [X] Timeout: {e}")
        except Exception as e:
            diagnostics["error"] = f"Network test failed: {e}"
            self._debug_log(f"   [X] Network test error: {e}")
            import traceback
            self._debug_log(f"   Traceback: {traceback.format_exc()}")

        self._debug_log("=== NETWORK DIAGNOSTICS END ===")
        return diagnostics

    @trace_call("MusicSearch._search_itunes")
    def _search_itunes(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search iTunes API with rate limiting."""
        import threading
        thread_id = threading.current_thread().ident

        # Check cache first to avoid duplicate API calls (if caching is enabled)
        if self.settings.get("cache_search_results", True):
            cache_key = (song_name, artist_name, album_name)
            # CRITICAL: Protect cache read with lock (for parallel request safety)
            with self._cache_lock:
                if cache_key in self._search_cache:
                    cached_result = self._search_cache[cache_key]
                    logger.debug(f"   [D] Cache hit for '{song_name}' - returning cached result")
                    return cached_result

        self._debug_log(f"\n[#] DEBUG: _search_itunes START (Thread {thread_id})")
        self._debug_log(f"   Song: '{song_name}'")
        self._debug_log(f"   Artist: '{artist_name}'")
        self._debug_log(f"   Album: '{album_name}'")

        if TRACE_ENABLED:
            trace_log.debug("_search_itunes start song=%s artist=%s album=%s", song_name, artist_name, album_name)
        try:
            # Rate limiting
            self._debug_log(f"   [L] DEBUG: Thread {thread_id} acquiring iTunes lock in _search_itunes...")
            with self.itunes_lock:
                self._debug_log(f"   [OK] DEBUG: Thread {thread_id} acquired iTunes lock in _search_itunes")
                self._debug_log(f"   [N] Enforcing rate limit...")
                self._enforce_rate_limit()
                self._debug_log(f"   [OK] Rate limit enforced, proceeding with API call...")

                # Build search term
                if artist_name:
                    search_term = f"{artist_name} {song_name}"
                else:
                    search_term = song_name
                self._debug_log(f"   [?] Search term: '{search_term}'")

                # iTunes API call
                url = "https://itunes.apple.com/search"
                params = {
                    'term': search_term,
                    'media': 'music',
                    'entity': 'song',
                    'limit': 5
                }
                self._debug_log(f"   [N] Making iTunes API request...")
                self._debug_log(f"   URL: {url}")
                self._debug_log(f"   Params: {params}")

                import time
                request_start = time.time()

                # Add detailed httpx diagnostics with explicit SSL verification
                try:
                    # Use explicit certifi bundle for packaged app compatibility
                    import ssl
                    import certifi
                    ssl_context = ssl.create_default_context(cafile=certifi.where())

                    # Add proper User-Agent header (best practice for API requests)
                    headers = {
                        "User-Agent": "AppleMusicHistoryConverter/2.0 ( hello@ashrafali.net )"
                    }

                    self._debug_log(f"   [LOCK] SSL context created with certifi bundle: {certifi.where()}")
                    self._debug_log(f"   [W] Executing httpx.get()...")
                    response = httpx.get(url, params=params, headers=headers, timeout=10, verify=ssl_context)
                    request_time = time.time() - request_start
                    self._debug_log(f"   [OK] iTunes API responded in {request_time:.2f}s")
                    self._debug_log(f"   [=] Status code: {response.status_code}")

                    # Raise exception for bad status codes (this triggers HTTPStatusError below)
                    response.raise_for_status()
                except httpx.ConnectError as conn_err:
                    self._debug_log(f"   [X] httpx.ConnectError caught: {conn_err}")
                    self._debug_log(f"   Error type: {type(conn_err).__name__}")
                    self._debug_log(f"   Error details: {str(conn_err)}")
                    raise  # Re-raise to be caught by outer exception handler
                except httpx.TimeoutException as timeout_err:
                    self._debug_log(f"   [X] httpx.TimeoutException caught: {timeout_err}")
                    raise
                except httpx.HTTPStatusError as status_err:
                    self._debug_log(f"   [X] httpx.HTTPStatusError caught: {status_err}")
                    self._debug_log(f"   Status code: {status_err.response.status_code}")

                    # Check if this is a 403 Forbidden (iTunes rate limit in disguise)
                    if status_err.response.status_code == 403:
                        self._debug_log(f"   [!]  403 Forbidden - iTunes API is blocking due to rate limit")

                        # NOTE: We intentionally do NOT try to "learn" the rate limit from 403 errors.
                        # Apple's rate limiting is unpredictable and our request counting doesn't match
                        # their internal counting. Just wait 60 seconds and continue at fixed rate.

                        # Wait 60 seconds before returning (allow cooldown)
                        # This is simpler and clearer than filling the queue with fake timestamps
                        self._debug_log(f"   [||]  Sleeping 60 seconds to allow rate limit to reset...")
                        logger.print_always(f"[||]  iTunes rate limit hit (403) - waiting 60 seconds before continuing...")

                        # Notify the UI if callback is available
                        if hasattr(self, 'rate_limit_hit_callback') and self.rate_limit_hit_callback:
                            try:
                                self.rate_limit_hit_callback()
                            except Exception as cb_error:
                                self._debug_log(f"[!]  Rate limit hit callback failed: {cb_error}")

                        # Use interruptible sleep to prevent GIL crash on exit
                        if hasattr(self, 'rate_limit_wait_callback') and self.rate_limit_wait_callback:
                            # Use callback-based interruptible wait (can be interrupted by app exit)
                            self._debug_log(f"      [||]  Using interruptible wait for 60 seconds...")
                            self.rate_limit_wait_callback(60)
                        else:
                            # Fallback to Event.wait() for interruptible sleep (prevents GIL crash)
                            self._debug_log(f"      [ZZZ] No callback, using Event.wait(60) for interruptible sleep...")
                            # Returns False if timeout, True if event set (app exiting)
                            if self._exit_event.wait(timeout=60):
                                self._debug_log(f"      [STOP] Exit event triggered during sleep - aborting")
                                return None

                        # Clear the request queue after the wait
                        self.itunes_requests.clear()
                        self._debug_log(f"   [OK] 60 second cooldown complete, queue cleared")

                        return {
                            "success": False,
                            "source": "itunes",
                            "error": "Rate limit (403 Forbidden)",
                            "rate_limited": True,  # Mark as rate-limited for retry list
                            "http_status": 403
                        }

                    # For other HTTP errors, raise normally
                    raise
                except Exception as req_err:
                    self._debug_log(f"   [X] Unexpected error during httpx.get(): {req_err}")
                    self._debug_log(f"   Error type: {type(req_err).__name__}")
                    import traceback
                    self._debug_log(f"   Traceback: {traceback.format_exc()}")
                    raise

                # If we get here, response was successful (200 status)
                self._debug_log(f"   [N] Parsing JSON response...")
                data = response.json()
                self._debug_log(f"   [OK] JSON parsed successfully")

                results = data.get('results', [])
                self._debug_log(f"   [=] Found {len(results)} results")

                if results:
                    # Return first result's artist
                    artist = results[0].get('artistName', '')
                    self._debug_log(f"   [OK] iTunes found artist: '{artist}'")
                    logger.info(f"iTunes found: '{artist}' for '{song_name}'")
                    if TRACE_ENABLED:
                        trace_log.debug("iTunes success for %s -> %s", song_name, artist)

                    result = {
                        "success": True,
                        "artist": artist,
                        "source": "itunes"
                    }

                    # Cache the result to avoid duplicate API calls (if caching is enabled)
                    if self.settings.get("cache_search_results", True):
                        # CRITICAL: Protect cache write with lock (for parallel request safety)
                        with self._cache_lock:
                            self._search_cache[cache_key] = result

                    return result
                else:
                    self._debug_log(f"   [X] No iTunes match found")
                    logger.debug(f"iTunes no match for: '{song_name}'")
                    if TRACE_ENABLED:
                        trace_log.debug("iTunes no match for %s", song_name)
                    return {
                        "success": False,
                        "source": "itunes",
                        "error": "No match found"
                    }

        except BrokenPipeError as e:
            # Handle broken pipe errors (connection closed unexpectedly)
            self._debug_log(f"   [!]  Broken pipe error during iTunes API call: {e}")
            logger.warning(f"[!]  iTunes API connection broken - will retry on next search")
            return {
                "success": False,
                "source": "itunes",
                "error": "Connection closed (broken pipe)"
            }
        except httpx.ConnectError as e:
            # Handle connection errors
            self._debug_log(f"   [!]  Connection error during iTunes API call: {e}")
            self._debug_log(f"   Error type: {type(e).__name__}")
            self._debug_log(f"   Error str: {str(e)}")
            import traceback
            self._debug_log(f"   Full traceback: {traceback.format_exc()}")
            logger.warning(f"[!]  iTunes API connection error: {e}")
            return {
                "success": False,
                "source": "itunes",
                "error": f"Connection error: {e}"
            }
        except httpx.TimeoutException as e:
            self._debug_log(f"   [!]  Timeout during iTunes API call: {e}")
            logger.warning(f"[!]  iTunes API timeout")
            return {
                "success": False,
                "source": "itunes",
                "error": f"Timeout: {e}"
            }
        except Exception as e:
            # Check if this is a rate limit error (429)
            error_str = str(e)
            self._debug_log(f"   [X] Exception caught in _search_itunes: {type(e).__name__}")
            self._debug_log(f"   Error message: {error_str}")

            # Check for broken pipe in string representation
            if "broken pipe" in error_str.lower() or "errno 32" in error_str.lower():
                self._debug_log(f"   [!]  Broken pipe error (in exception): {e}")
                logger.warning(f"[!]  iTunes API broken pipe error")
                return {
                    "success": False,
                    "source": "itunes",
                    "error": "Connection broken"
                }

            if "429" in error_str or "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                self._debug_log(f"   [!]  Rate limit detected from iTunes API: {e}")
                logger.warning(f"[!]  iTunes API rate limit hit (429)")

                # NOTE: We intentionally do NOT try to "learn" the rate limit from 429 errors.
                # Apple's rate limiting is unpredictable and our request counting doesn't match
                # their internal counting. Just wait 60 seconds and continue at fixed rate.

                # Reset rate limit queue to force full 60-second wait
                # This prevents immediately hitting the limit again
                self._debug_log(f"   [R] Resetting rate limit queue - forcing full 60s wait before next request")
                self.itunes_requests.clear()

                # Notify the UI if callback is available
                if hasattr(self, 'rate_limit_hit_callback') and self.rate_limit_hit_callback:
                    try:
                        self.rate_limit_hit_callback()
                    except Exception as cb_error:
                        self._debug_log(f"[!]  Rate limit hit callback failed: {cb_error}")
            else:
                self._debug_log(f"   [X] iTunes search error: {e}")
                logger.error(f"iTunes search error: {e}")

            if TRACE_ENABLED:
                trace_log.exception("iTunes search error for %s: %s", song_name, e)
            import traceback
            self._debug_log(f"   Full exception traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "source": "itunes",
                "error": str(e)
            }

    @trace_call("MusicSearch._enforce_rate_limit")
    def _enforce_rate_limit(self):
        """
        Enforce iTunes API rate limit with adaptive learning.
        NOTE: This method assumes self.itunes_lock is already held by the caller (_search_itunes).
        """
        import threading
        thread_id = threading.current_thread().ident
        logger.debug(f"      [CLOCK] _enforce_rate_limit START (Thread {thread_id}, lock already held by caller)")

        # Check if rate limiting is paused
        rate_limit_paused = self.settings.get("rate_limit_paused", False)
        if rate_limit_paused:
            logger.debug(f"      [||]  Rate limiting is PAUSED - skipping rate limit enforcement")
            # Still add request to queue for tracking, but don't enforce limits
            current_time = time.time()
            self.itunes_requests.append(current_time)
            return

        # Use a fixed rate limit - adaptive learning was unreliable
        # iTunes API works well at ~20 req/min. When 403/429 hit, we wait 60s and continue.
        rate_limit = self.settings.get("itunes_rate_limit", 20)
        logger.debug(f"      [=] Using fixed rate limit: {rate_limit} requests/min")

        min_interval = 60.0 / rate_limit
        logger.debug(f"      [=] Min interval: {min_interval:.2f}s")

        current_time = time.time()
        logger.debug(f"      [=] Current requests in queue: {len(self.itunes_requests)}")

        # Remove old requests (older than 1 minute)
        logger.debug(f"      [N] Removing old requests...")
        old_count = len(self.itunes_requests)
        while self.itunes_requests and current_time - self.itunes_requests[0] > 60:
            self.itunes_requests.popleft()
        removed = old_count - len(self.itunes_requests)
        logger.debug(f"      [OK] Removed {removed} old requests, {len(self.itunes_requests)} remaining")

        # Check if we need to wait
        if len(self.itunes_requests) >= rate_limit:
            sleep_time = 60 - (current_time - self.itunes_requests[0])
            if sleep_time > 0:
                logger.debug(f"      [||]  Rate limit reached - sleeping {sleep_time:.1f}s")
                logger.print_always(f"[||]  iTunes rate limit reached - waiting {sleep_time:.0f}s before continuing...")

                # Call rate limit callback if provided
                logger.debug(f"      [PHONE] Checking for rate_limit_callback...")
                if hasattr(self, 'rate_limit_callback') and self.rate_limit_callback:
                    try:
                        logger.debug(f"      [PHONE] Calling rate_limit_callback({sleep_time})...")
                        self.rate_limit_callback(sleep_time)
                        logger.debug(f"      [OK] rate_limit_callback completed")
                    except Exception as e:
                        logger.error(f"[!]  Rate limit callback failed: {e}")

                # Interruptible sleep with countdown
                logger.debug(f"      [||]  Checking for rate_limit_wait_callback...")
                if hasattr(self, 'rate_limit_wait_callback') and self.rate_limit_wait_callback:
                    # Use callback-based interruptible wait with countdown
                    logger.debug(f"      [||]  Calling rate_limit_wait_callback({sleep_time})... THIS MAY BLOCK")
                    self.rate_limit_wait_callback(sleep_time)
                    logger.debug(f"      [OK] rate_limit_wait_callback completed")
                else:
                    # Fallback to Event.wait() for interruptible sleep (prevents GIL crash)
                    logger.debug(f"      [ZZZ] No callback, using Event.wait({sleep_time}) for interruptible sleep...")
                    # Returns False if timeout, True if event set (app exiting)
                    if self._exit_event.wait(timeout=sleep_time):
                        logger.debug(f"      [STOP] Exit event triggered during sleep - aborting rate limit wait")
                        return  # Exit the rate limit enforcement early
                    logger.debug(f"      [OK] Event.wait completed")
                logger.debug(f"      [OK] Sleep complete")
        else:
            logger.debug(f"      [OK] No rate limit wait needed ({len(self.itunes_requests)}/{rate_limit})")

        # Add current request
        self.itunes_requests.append(current_time)
        logger.debug(f"      [OK] Added request to queue, total: {len(self.itunes_requests)}")
        logger.debug(f"      [CLOCK] _enforce_rate_limit END")

    def search_batch_api(self, song_names: List[str], progress_callback=None, interrupt_check=None) -> List[Dict]:
        """
        Search API (iTunes or MusicBrainz) for multiple songs sequentially.
        Both APIs require sequential requests to avoid rate limiting.

        Args:
            song_names: List of track names to search
            progress_callback: Optional callback(track_idx, track_name, result, completed_count, total_count)
            interrupt_check: Optional callable that returns True if search should be interrupted
        """
        # Log batch search entry
        logger.debug(f"search_batch_api: {len(song_names)} songs, provider={self.get_search_provider()}")

        # Run network diagnostics BEFORE starting search
        self._debug_log("\n" + "="*80)
        self._debug_log("STARTING API BATCH SEARCH - RUNNING DIAGNOSTICS FIRST")
        self._debug_log("="*80)
        diagnostics = self._test_network_connectivity()
        self._debug_log(f"Network diagnostics results: {diagnostics}")

        # If network test failed, log details and potentially abort
        if not diagnostics.get("network_reachable"):
            error_msg = f"Network connectivity test failed: {diagnostics.get('error', 'Unknown error')}"
            self._debug_log(f"[X] CRITICAL: {error_msg}")
            self._debug_log(f"   httpx version: {diagnostics.get('httpx_version', 'unknown')}")
            self._debug_log(f"   certifi available: {diagnostics.get('certifi_available', False)}")
            self._debug_log(f"   certifi path: {diagnostics.get('certifi_path', 'N/A')}")
            # Continue anyway to see what happens with actual API

        # ALWAYS use sequential mode - parallel requests don't work with iTunes/MusicBrainz APIs
        self._debug_log(f"Using sequential mode (iTunes and MusicBrainz APIs don't support parallel)")
        results = []
        for idx, song in enumerate(song_names):
            # Check for interrupt
            if interrupt_check and interrupt_check():
                self._debug_log(f"[.] Search interrupted by user at track {idx}/{len(song_names)}")
                provider_name = self.get_search_provider()
                logger.print_always(f"[.] {provider_name} search stopped by user at {idx}/{len(song_names)} tracks")
                break

            # Route to correct API based on provider
            current_search_provider = self.get_search_provider()

            if current_search_provider == "musicbrainz_api":
                logger.debug(f"[?] Request {idx+1}: Routing to MusicBrainz API for '{song}'")
                result = self._search_musicbrainz_api(song)
            else:  # itunes
                logger.debug(f"[?] Request {idx+1}: Routing to iTunes for '{song}' (provider={current_search_provider})")
                result = self._search_itunes(song)
            results.append(result)
            if progress_callback:
                progress_callback(idx, song, result, idx + 1, len(song_names))
        return results

    @trace_call("MusicSearch.get_status")
    def get_status(self) -> Dict:
        """Get comprehensive status information."""
        mb_status = self.musicbrainz_manager.get_optimization_status()

        return {
            "provider": self.get_search_provider(),
            "auto_fallback": self.get_auto_fallback(),
            "musicbrainz": {
                "ready": mb_status["ready"],
                "in_progress": mb_status["in_progress"],
                "csv_available": mb_status["csv_available"],
                "duckdb_exists": mb_status["duckdb_exists"]
            },
            "itunes": {
                "requests_this_minute": len(self.itunes_requests)
            }
        }

    @trace_call("MusicSearch.get_database_info")
    def get_database_info(self) -> Dict:
        """Get information about the MusicBrainz database (legacy compatibility)."""
        # Delegate to MusicBrainz manager if it has the method
        if hasattr(self.musicbrainz_manager, 'get_database_info'):
            return self.musicbrainz_manager.get_database_info()

        # Fallback implementation based on current V2 status
        status = self.musicbrainz_manager.get_optimization_status()
        return {
            "exists": status["csv_available"],
            "size_mb": 0,  # V2 doesn't track size
            "last_updated": "Unknown",
            "version": "V2",
            "track_count": 0,  # V2 doesn't track count
            "type": "DuckDB Optimized"
        }

    def is_musicbrainz_optimized(self) -> bool:
        """Check if MusicBrainz database is optimized and ready."""
        return self.musicbrainz_manager.is_ready()

    # Phase 2: Session Alignment Methods
    @property
    def session_aligner(self) -> SessionAligner:
        """Get the session aligner instance."""
        return self._session_aligner

    def apply_session_alignment(self, tracks: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Apply album-session alignment to a list of tracks.

        Detects consecutive tracks from the same album and aligns them to a
        single MusicBrainz release, providing consistent artist credits.

        Args:
            tracks: List of track dictionaries with 'track', 'album', 'artist' keys

        Returns:
            Tuple of (updated_tracks, stats_dict)
        """
        if not self.is_musicbrainz_optimized():
            logger.debug("Session alignment skipped: MusicBrainz not ready")
            return tracks, {'sessions_detected': 0, 'tracks_aligned': 0}

        # Detect album sessions
        sessions = self._session_aligner.detect_sessions(tracks)

        if not sessions:
            logger.debug("No album sessions detected")
            return tracks, self._session_aligner.get_stats()

        logger.info(f"Detected {len(sessions)} album sessions")

        # Align sessions and apply to tracks
        aligned_tracks = self._session_aligner.align_all_sessions(sessions, tracks)

        stats = self._session_aligner.get_stats()
        logger.info(f"Session alignment complete: {stats['tracks_aligned']} tracks aligned from {stats['sessions_aligned']} sessions")

        return aligned_tracks, stats

    def get_session_alignment_stats(self) -> Dict:
        """Get statistics from the last session alignment."""
        return self._session_aligner.get_stats()

    def reset_session_alignment_stats(self):
        """Reset session alignment statistics."""
        self._session_aligner.reset_stats()

    @trace_call("MusicSearch.force_itunes_fallback")
    def force_itunes_fallback(self):
        """Force fallback to iTunes for this session (when optimization fails)."""
        logger.warning("Forcing iTunes fallback due to MusicBrainz optimization failure")
        self.set_search_provider("itunes")

    # Legacy compatibility methods for existing code
    def start_progressive_loading(self, progress_callback=None):
        """Legacy method - now triggers comprehensive optimization."""
        logger.info("Legacy progressive loading called - triggering comprehensive optimization")
        return self.musicbrainz_manager.start_optimization_if_needed(progress_callback)

    def is_loading_complete(self) -> bool:
        """Legacy method - check if optimization is complete."""
        return self.musicbrainz_manager.is_ready()

    def get_loading_status(self) -> str:
        """Legacy method - get loading status."""
        if self.musicbrainz_manager.is_ready():
            return "complete"
        elif self.musicbrainz_manager._optimization_in_progress:
            return "in_progress"
        else:
            return "not_started"

    def download_database(self, progress_callback=None) -> bool:
        """Download MusicBrainz database (legacy compatibility)."""
        if hasattr(self.musicbrainz_manager, 'download_database'):
            return self.musicbrainz_manager.download_database(progress_callback)
        logger.warning("V2 manager doesn't support direct database download")
        return False

    def check_for_updates(self) -> Tuple[bool, str]:
        """Check for database updates (legacy compatibility)."""
        if hasattr(self.musicbrainz_manager, 'check_for_updates'):
            return self.musicbrainz_manager.check_for_updates()
        return False, "Updates not supported in V2"

    def delete_database(self) -> bool:
        """Delete MusicBrainz database (legacy compatibility)."""
        if hasattr(self.musicbrainz_manager, 'delete_database'):
            return self.musicbrainz_manager.delete_database()
        logger.warning("V2 manager doesn't support database deletion")
        return False

    def get_database_path(self) -> str:
        """Get database path (legacy compatibility)."""
        if hasattr(self.musicbrainz_manager, 'data_dir'):
            return str(self.musicbrainz_manager.data_dir)
        return ""

    def save_settings(self):
        """Save settings (legacy compatibility)."""
        self._save_settings()

    def import_database_file(self, file_path: str, progress_callback=None) -> bool:
        """Import MusicBrainz database from a file (.tar.zst, .csv, .tsv)."""
        if hasattr(self.musicbrainz_manager, 'manual_import_database'):
            return self.musicbrainz_manager.manual_import_database(file_path, progress_callback)
        return False

    def close(self):
        """Close all database connections to prevent GIL issues during shutdown.

        This should be called before application exit to ensure clean shutdown.
        The crash on quit (abort trap: 6) is caused by DuckDB trying to release
        the GIL during cleanup when Python is already shutting down.
        """
        try:
            logger.print_always("[L] Closing MusicSearchService connections...")

            # Set exit event to wake up any sleeping threads
            if hasattr(self, '_exit_event'):
                self._exit_event.set()
                logger.print_always("   [OK] Exit event set to wake sleeping threads")

            if hasattr(self, 'musicbrainz_manager') and self.musicbrainz_manager:
                if hasattr(self.musicbrainz_manager, 'close'):
                    self.musicbrainz_manager.close()
            logger.print_always("[OK] MusicSearchService closed successfully")
        except Exception as e:
            logger.print_always(f"[!]  Error closing MusicSearchService: {e}")

    @trace_call("MusicSearch._search_musicbrainz_api_async")
    async def _search_musicbrainz_api_async(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search MusicBrainz Web Service API with rate limiting (async wrapper)."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._search_musicbrainz_api, song_name, artist_name, album_name
        )

    def _search_musicbrainz_api(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """
        Search MusicBrainz Web Service API.

        Rate limit: 1 request per second (MusicBrainz policy)
        API Docs: https://musicbrainz.org/doc/MusicBrainz_API
        """
        import time
        import threading
        search_start = time.time()
        thread_id = threading.current_thread().ident

        # Check cache first to avoid duplicate API calls (if caching is enabled)
        if self.settings.get("cache_search_results", True):
            cache_key = (song_name, artist_name, album_name)
            # CRITICAL: Protect cache read with lock (for parallel request safety)
            with self._cache_lock:
                if cache_key in self._search_cache:
                    cached_result = self._search_cache[cache_key]
                    logger.debug(f"   [D] Cache hit for '{song_name}' - returning cached result")
                    return cached_result

        logger.debug(f"[#] === MUSICBRAINZ API SEARCH START ===")
        logger.debug(f"   [=] Inputs: song='{song_name}', artist='{artist_name}', album='{album_name}'")

        try:
            # Build query string
            query_parts = []
            if song_name:
                # Clean and escape song name for Lucene query
                clean_song = song_name.replace('"', '\\"')
                query_parts.append(f'recording:"{clean_song}"')
            
            if artist_name:
                clean_artist = artist_name.replace('"', '\\"')
                query_parts.append(f'artist:"{clean_artist}"')
            
            if album_name:
                clean_album = album_name.replace('"', '\\"')
                query_parts.append(f'release:"{clean_album}"')

            if not query_parts:
                return {
                    "success": False,
                    "source": "musicbrainz_api",
                    "error": "No search terms provided"
                }

            query = " AND ".join(query_parts)
            
            # MusicBrainz API endpoint
            base_url = "https://musicbrainz.org/ws/2/recording/"
            params = {
                "query": query,
                "fmt": "json",
                "limit": 10  # Get top 10 results
            }

            # Rate limiting: 1 request per second
            with self.musicbrainz_api_lock:  # Dedicated lock for MusicBrainz API (independent from iTunes)
                current_time = time.time()

                # Check if we need to wait (1 second between requests)
                if hasattr(self, '_mb_api_last_request'):
                    time_since_last = current_time - self._mb_api_last_request
                    if time_since_last < 1.0:
                        wait_time = 1.0 - time_since_last
                        logger.debug(f"[||]  MusicBrainz API rate limit: waiting {wait_time:.2f}s")

                        # Use Event.wait() for interruptible sleep (prevents GIL crash)
                        # Returns False if timeout, True if event set (app exiting)
                        if self._exit_event.wait(timeout=wait_time):
                            logger.debug("[!]  App exiting - aborting MusicBrainz rate limit wait")
                            return None
                
                # Make request with proper User-Agent (MusicBrainz requires contact info)
                # Format: Application/Version ( contact-url-or-email )
                headers = {
                    "User-Agent": "AppleMusicHistoryConverter/2.0 ( hello@ashrafali.net )"
                }
                
                try:
                    with httpx.Client(http2=False, timeout=30.0) as client:
                        response = client.get(base_url, params=params, headers=headers)
                        self._mb_api_last_request = time.time()
                        
                        if response.status_code == 503:
                            # Service unavailable (rate limited or down)
                            elapsed = (time.time() - search_start) * 1000
                            logger.warning(f"   [||]  MusicBrainz API rate limited (503) after {elapsed:.1f}ms")
                            return {
                                "success": False,
                                "source": "musicbrainz_api",
                                "error": "Rate limited (503)",
                                "rate_limited": True
                            }
                        
                        if response.status_code != 200:
                            elapsed = (time.time() - search_start) * 1000
                            logger.error(f"   [X] MusicBrainz API error {response.status_code} after {elapsed:.1f}ms")
                            return {
                                "success": False,
                                "source": "musicbrainz_api",
                                "error": f"HTTP {response.status_code}"
                            }
                        
                        data = response.json()
                        recordings = data.get("recordings", [])
                        
                        if not recordings:
                            elapsed = (time.time() - search_start) * 1000
                            logger.debug(f"   [X] MusicBrainz API NO MATCH for '{song_name}' after {elapsed:.1f}ms")
                            return {
                                "success": False,
                                "source": "musicbrainz_api",
                                "error": "No match found"
                            }
                        
                        # Get artist from first result
                        first_recording = recordings[0]
                        artist_credits = first_recording.get("artist-credit", [])
                        
                        if artist_credits:
                            artist_name = artist_credits[0].get("name", "Unknown Artist")
                            elapsed = (time.time() - search_start) * 1000
                            logger.debug(f"   [OK] MusicBrainz API SUCCESS: Found '{artist_name}' for '{song_name}' in {elapsed:.1f}ms")

                            result = {
                                "success": True,
                                "artist": artist_name,
                                "source": "musicbrainz_api"
                            }

                            # Cache the result to avoid duplicate API calls (if caching is enabled)
                            if self.settings.get("cache_search_results", True):
                                # CRITICAL: Protect cache write with lock (for parallel request safety)
                                with self._cache_lock:
                                    self._search_cache[cache_key] = result

                            return result
                        else:
                            elapsed = (time.time() - search_start) * 1000
                            logger.debug(f"   [X] MusicBrainz API NO ARTIST for '{song_name}' after {elapsed:.1f}ms")
                            return {
                                "success": False,
                                "source": "musicbrainz_api",
                                "error": "No artist in result"
                            }
                
                except httpx.RequestError as e:
                    elapsed = (time.time() - search_start) * 1000
                    logger.error(f"   [!] MusicBrainz API network error after {elapsed:.1f}ms: {e}")
                    return {
                        "success": False,
                        "source": "musicbrainz_api",
                        "error": f"Network error: {str(e)}"
                    }

        except Exception as e:
            elapsed = (time.time() - search_start) * 1000
            logger.error(f"   [!] MusicBrainz API ERROR after {elapsed:.1f}ms: {e}")
            import traceback
            logger.debug(f"   [BOOKS] Stack trace: {traceback.format_exc()}")
            return {
                "success": False,
                "source": "musicbrainz_api",
                "error": str(e)
            }
