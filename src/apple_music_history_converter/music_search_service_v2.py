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
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    # Use optimized manager by default
    from .musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized as MusicBrainzManagerV2
    from .optimization_modal import run_with_optimization_modal
    from .trace_utils import TRACE_ENABLED, trace_call, trace_log
    from .app_directories import get_settings_path, get_database_dir
    from .logging_config import get_logger
except ImportError:
    # Fall back to optimized manager
    from musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized as MusicBrainzManagerV2
    from optimization_modal import run_with_optimization_modal
    from trace_utils import TRACE_ENABLED, trace_call, trace_log
    from app_directories import get_settings_path, get_database_dir
    from logging_config import get_logger

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

        # UI integration
        self._parent_window = None
        self._optimization_modal_shown = False

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
        return {
            "search_provider": "musicbrainz",
            "auto_fallback": True,
            "itunes_rate_limit": 20,  # requests per minute (user-configurable)
            "discovered_rate_limit": None,  # Actual limit discovered from rate limit errors
            "use_adaptive_rate_limit": True,  # Use discovered limit if available
            "rate_limit_safety_margin": 0.8,  # Use 80% of discovered limit for safety
            "use_parallel_requests": False,  # Use parallel requests (default: sequential for safety)
            "parallel_workers": 10  # Number of parallel workers when parallel mode enabled
        }

    def _save_settings(self):
        """Save settings to JSON file."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.debug(f"Settings saved to: {self.settings_file}")
            # Extra logging for Windows debugging of rate limiting settings
            if sys.platform == "win32":
                logger.info(f"Windows settings update: parallel={self.settings.get('use_parallel_requests')}, adaptive={self.settings.get('use_adaptive_rate_limit')}")
        except Exception as e:
            logger.error(f"Error saving settings to {self.settings_file}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def get_search_provider(self) -> str:
        """Get current search provider."""
        return self.settings.get("search_provider", "musicbrainz")

    def set_search_provider(self, provider: str):
        """Set search provider (musicbrainz or itunes)."""
        if provider in ["musicbrainz", "itunes"]:
            self.settings["search_provider"] = provider
            self._save_settings()
            logger.info(f"Search provider set to: {provider}")

    def get_auto_fallback(self) -> bool:
        """Get auto-fallback setting."""
        return self.settings.get("auto_fallback", True)

    def set_auto_fallback(self, enabled: bool):
        """Set auto-fallback to iTunes when MusicBrainz fails."""
        self.settings["auto_fallback"] = enabled
        self._save_settings()
        logger.info(f"Auto-fallback set to: {enabled}")

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
            logger.error("⚠️ MusicBrainz ensure failed: CSV not available")
            return False

        if self.musicbrainz_manager.is_ready():
            logger.info("✅ MusicBrainz already marked ready")
            if TRACE_ENABLED:
                trace_log.debug("ensure_musicbrainz_ready -> already ready")
            return True

        # Show optimization modal if we have a parent window and we're on the UI thread
        use_modal = (
            self._parent_window is not None
            and not self._optimization_modal_shown
            and threading.current_thread() is threading.main_thread()
        )

        if use_modal:
            # Use modal to start and wait for optimization
            self._optimization_modal_shown = True
            try:
                logger.print_always("🔧 Starting optimization with modal...")
                await run_with_optimization_modal(
                    self._parent_window,
                    self.musicbrainz_manager.run_optimization_synchronously,
                    cancellation_callback=self.musicbrainz_manager.cancel_optimization
                )
                logger.print_always("✅ MusicBrainz optimization completed via modal")
                if TRACE_ENABLED:
                    trace_log.debug("Optimization modal completed successfully")
            except Exception as e:
                # Check if it was a user cancellation
                if "cancelled by user" in str(e).lower():
                    logger.warning("⚠️ Optimization cancelled by user")
                    return False
                # Fall back to iTunes for this session on other errors
                self.set_search_provider("itunes")
                logger.error(f"⚠️ MusicBrainz optimization modal failed: {e}")
                if TRACE_ENABLED:
                    trace_log.exception("Optimization modal failed: %s", e)
                return False
        else:
            # No UI available or running off the main thread; start optimization and wait silently
            logger.print_always("🔧 Starting optimization without modal (background thread)...")
            optimization_started = self.musicbrainz_manager.start_optimization_if_needed()

            if not optimization_started:
                logger.error("❌ Failed to start optimization - CSV not available")
                return False

            logger.print_always("⏳ Waiting for MusicBrainz optimization to complete...")
            success = self.musicbrainz_manager.wait_until_ready(timeout=600.0)
            if not success:
                self.set_search_provider("itunes")
                logger.warning("⚠️ MusicBrainz optimization timed out; switching to iTunes")
                if TRACE_ENABLED:
                    trace_log.warning("Optimization wait timed out; switching provider to iTunes")
                return False

        ready = self.musicbrainz_manager.is_ready()
        logger.print_always(f"✅ MusicBrainz readiness check complete: {ready}")
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
            - source: str ("musicbrainz", "itunes", or "none")
            - error: str (if error occurred)
        """
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
                return result

            # If no match and auto-fallback enabled, try iTunes
            if auto_fallback:
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz miss for %s – falling back to iTunes", song_name)
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

        logger.debug(f"🎵 === MUSICBRAINZ SERVICE SEARCH START ===")
        logger.debug(f"   📊 Inputs: song='{song_name}', artist='{artist_name}', album='{album_name}'")

        try:
            # Check if manager is ready
            if not self.musicbrainz_manager.is_ready():
                elapsed = (time.time() - search_start) * 1000
                logger.debug(f"   ❌ MusicBrainz manager not ready after {elapsed:.1f}ms")
                logger.debug(f"🎵 === MUSICBRAINZ SERVICE SEARCH END (NOT READY) ===\n")
                return {
                    "success": False,
                    "source": "musicbrainz",
                    "error": "MusicBrainz not ready - optimization required"
                }

            logger.debug(f"   ✅ MusicBrainz manager is ready - calling search...")

            # Use the comprehensive search with bidirectional cascade
            artist_result = self.musicbrainz_manager.search(
                track_name=song_name,
                artist_hint=artist_name,
                album_hint=album_name
            )

            elapsed = (time.time() - search_start) * 1000

            if artist_result:
                logger.debug(f"   ✅ MusicBrainz SUCCESS: Found '{artist_result}' for '{song_name}' in {elapsed:.1f}ms")
                logger.debug(f"🎵 === MUSICBRAINZ SERVICE SEARCH END (SUCCESS) ===\n")
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz artist_result=%s elapsed=%.2fms", artist_result, elapsed)
                return {
                    "success": True,
                    "artist": artist_result,
                    "source": "musicbrainz"
                }
            else:
                logger.debug(f"   ❌ MusicBrainz NO MATCH for '{song_name}' after {elapsed:.1f}ms")
                logger.debug(f"🎵 === MUSICBRAINZ SERVICE SEARCH END (NO MATCH) ===\n")
                if TRACE_ENABLED:
                    trace_log.debug("MusicBrainz no match for %s elapsed=%.2fms", song_name, elapsed)
                return {
                    "success": False,
                    "source": "musicbrainz",
                    "error": "No match found"
                }

        except Exception as e:
            elapsed = (time.time() - search_start) * 1000
            logger.error(f"   💥 MusicBrainz ERROR after {elapsed:.1f}ms: {e}")
            logger.debug(f"🎵 === MUSICBRAINZ SERVICE SEARCH END (ERROR) ===\n")
            import traceback
            logger.debug(f"   📚 Stack trace: {traceback.format_exc()}")
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
            self._debug_log(f"   ❌ httpx import error: {e}")
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
                self._debug_log(f"   ❌ certifi bundle NOT FOUND at {certifi.where()}")
        except Exception as e:
            diagnostics["error"] = f"certifi check failed: {e}"
            self._debug_log(f"   ❌ certifi error: {e}")

        # Test simple HTTP connection with explicit SSL context
        try:
            import ssl
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._debug_log("   Testing HTTP connection to apple.com...")
            response = httpx.get("https://www.apple.com", timeout=5, verify=ssl_context)
            diagnostics["network_reachable"] = True
            diagnostics["ssl_working"] = True
            self._debug_log(f"   ✅ Network test successful (status: {response.status_code})")
        except httpx.ConnectError as e:
            diagnostics["error"] = f"Connection error: {e}"
            self._debug_log(f"   ❌ Connection error: {e}")
        except httpx.TimeoutException as e:
            diagnostics["error"] = f"Timeout: {e}"
            self._debug_log(f"   ❌ Timeout: {e}")
        except Exception as e:
            diagnostics["error"] = f"Network test failed: {e}"
            self._debug_log(f"   ❌ Network test error: {e}")
            import traceback
            self._debug_log(f"   Traceback: {traceback.format_exc()}")

        self._debug_log("=== NETWORK DIAGNOSTICS END ===")
        return diagnostics

    @trace_call("MusicSearch._search_itunes")
    def _search_itunes(self, song_name: str, artist_name: Optional[str] = None, album_name: Optional[str] = None) -> Dict:
        """Search iTunes API with rate limiting."""
        import threading
        thread_id = threading.current_thread().ident
        self._debug_log(f"\n🎵 DEBUG: _search_itunes START (Thread {thread_id})")
        self._debug_log(f"   Song: '{song_name}'")
        self._debug_log(f"   Artist: '{artist_name}'")
        self._debug_log(f"   Album: '{album_name}'")

        if TRACE_ENABLED:
            trace_log.debug("_search_itunes start song=%s artist=%s album=%s", song_name, artist_name, album_name)
        try:
            # Rate limiting
            self._debug_log(f"   🔒 DEBUG: Thread {thread_id} acquiring iTunes lock in _search_itunes...")
            with self.itunes_lock:
                self._debug_log(f"   ✅ DEBUG: Thread {thread_id} acquired iTunes lock in _search_itunes")
                self._debug_log(f"   📝 Enforcing rate limit...")
                self._enforce_rate_limit()
                self._debug_log(f"   ✅ Rate limit enforced, proceeding with API call...")

                # Build search term
                if artist_name:
                    search_term = f"{artist_name} {song_name}"
                else:
                    search_term = song_name
                self._debug_log(f"   🔍 Search term: '{search_term}'")

                # iTunes API call
                url = "https://itunes.apple.com/search"
                params = {
                    'term': search_term,
                    'media': 'music',
                    'entity': 'song',
                    'limit': 5
                }
                self._debug_log(f"   📝 Making iTunes API request...")
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

                    self._debug_log(f"   🔐 SSL context created with certifi bundle: {certifi.where()}")
                    self._debug_log(f"   🌐 Executing httpx.get()...")
                    response = httpx.get(url, params=params, timeout=10, verify=ssl_context)
                    request_time = time.time() - request_start
                    self._debug_log(f"   ✅ iTunes API responded in {request_time:.2f}s")
                    self._debug_log(f"   📊 Status code: {response.status_code}")

                    # Raise exception for bad status codes (this triggers HTTPStatusError below)
                    response.raise_for_status()
                except httpx.ConnectError as conn_err:
                    self._debug_log(f"   ❌ httpx.ConnectError caught: {conn_err}")
                    self._debug_log(f"   Error type: {type(conn_err).__name__}")
                    self._debug_log(f"   Error details: {str(conn_err)}")
                    raise  # Re-raise to be caught by outer exception handler
                except httpx.TimeoutException as timeout_err:
                    self._debug_log(f"   ❌ httpx.TimeoutException caught: {timeout_err}")
                    raise
                except httpx.HTTPStatusError as status_err:
                    self._debug_log(f"   ❌ httpx.HTTPStatusError caught: {status_err}")
                    self._debug_log(f"   Status code: {status_err.response.status_code}")

                    # Check if this is a 403 Forbidden (iTunes rate limit in disguise)
                    if status_err.response.status_code == 403:
                        self._debug_log(f"   ⚠️  403 Forbidden - iTunes API is blocking due to rate limit")

                        # Calculate discovered rate limit based on requests in last 60 seconds
                        current_time = time.time()
                        recent_requests = [t for t in self.itunes_requests if current_time - t <= 60]
                        discovered_count = len(recent_requests)

                        self._debug_log(f"   📊 Current request rate: {discovered_count} requests/minute")

                        # Only update discovered rate limit if we have a meaningful sample
                        if discovered_count > 5:
                            # Use 80% of current rate as the safe limit
                            safe_limit = int(discovered_count * 0.8)
                            self._debug_log(f"   📊 Setting discovered rate limit to {safe_limit} req/min (80% of {discovered_count})")
                            self.settings["discovered_rate_limit"] = safe_limit
                            self._save_settings()

                            # Notify UI about discovery
                            if hasattr(self, 'rate_limit_discovered_callback') and self.rate_limit_discovered_callback:
                                try:
                                    self.rate_limit_discovered_callback(safe_limit)
                                except Exception as cb_error:
                                    self._debug_log(f"⚠️  Rate limit discovered callback failed: {cb_error}")

                        # Reset rate limit queue to force full 60-second wait
                        self._debug_log(f"   🔄 Resetting rate limit queue - forcing 60s cooldown")
                        self.itunes_requests.clear()

                        # Notify the UI if callback is available
                        if hasattr(self, 'rate_limit_hit_callback') and self.rate_limit_hit_callback:
                            try:
                                self.rate_limit_hit_callback()
                            except Exception as cb_error:
                                self._debug_log(f"⚠️  Rate limit hit callback failed: {cb_error}")

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
                    self._debug_log(f"   ❌ Unexpected error during httpx.get(): {req_err}")
                    self._debug_log(f"   Error type: {type(req_err).__name__}")
                    import traceback
                    self._debug_log(f"   Traceback: {traceback.format_exc()}")
                    raise

                # If we get here, response was successful (200 status)
                self._debug_log(f"   📝 Parsing JSON response...")
                data = response.json()
                self._debug_log(f"   ✅ JSON parsed successfully")

                results = data.get('results', [])
                self._debug_log(f"   📊 Found {len(results)} results")

                if results:
                    # Return first result's artist
                    artist = results[0].get('artistName', '')
                    self._debug_log(f"   ✅ iTunes found artist: '{artist}'")
                    logger.info(f"iTunes found: '{artist}' for '{song_name}'")
                    if TRACE_ENABLED:
                        trace_log.debug("iTunes success for %s -> %s", song_name, artist)
                    return {
                        "success": True,
                        "artist": artist,
                        "source": "itunes"
                    }
                else:
                    self._debug_log(f"   ❌ No iTunes match found")
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
            self._debug_log(f"   ⚠️  Broken pipe error during iTunes API call: {e}")
            logger.warning(f"⚠️  iTunes API connection broken - will retry on next search")
            return {
                "success": False,
                "source": "itunes",
                "error": "Connection closed (broken pipe)"
            }
        except httpx.ConnectError as e:
            # Handle connection errors
            self._debug_log(f"   ⚠️  Connection error during iTunes API call: {e}")
            self._debug_log(f"   Error type: {type(e).__name__}")
            self._debug_log(f"   Error str: {str(e)}")
            import traceback
            self._debug_log(f"   Full traceback: {traceback.format_exc()}")
            logger.warning(f"⚠️  iTunes API connection error: {e}")
            return {
                "success": False,
                "source": "itunes",
                "error": f"Connection error: {e}"
            }
        except httpx.TimeoutException as e:
            self._debug_log(f"   ⚠️  Timeout during iTunes API call: {e}")
            logger.warning(f"⚠️  iTunes API timeout")
            return {
                "success": False,
                "source": "itunes",
                "error": f"Timeout: {e}"
            }
        except Exception as e:
            # Check if this is a rate limit error (429)
            error_str = str(e)
            self._debug_log(f"   ❌ Exception caught in _search_itunes: {type(e).__name__}")
            self._debug_log(f"   Error message: {error_str}")

            # Check for broken pipe in string representation
            if "broken pipe" in error_str.lower() or "errno 32" in error_str.lower():
                self._debug_log(f"   ⚠️  Broken pipe error (in exception): {e}")
                logger.warning(f"⚠️  iTunes API broken pipe error")
                return {
                    "success": False,
                    "source": "itunes",
                    "error": "Connection broken"
                }

            if "429" in error_str or "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                self._debug_log(f"   ⚠️  Rate limit detected from iTunes API: {e}")
                logger.warning(f"⚠️  iTunes API rate limit hit - discovering actual limit")

                # Calculate discovered rate limit based on requests in last 60 seconds
                current_time = time.time()
                recent_requests = [t for t in self.itunes_requests if current_time - t <= 60]
                discovered_count = len(recent_requests)

                # Only update if we have a meaningful sample
                if discovered_count > 5:
                    self._debug_log(f"   📊 Discovered actual rate limit: {discovered_count} requests/minute")
                    self.settings["discovered_rate_limit"] = discovered_count
                    self._save_settings()

                    # Notify UI about discovery
                    if hasattr(self, 'rate_limit_discovered_callback') and self.rate_limit_discovered_callback:
                        try:
                            self.rate_limit_discovered_callback(discovered_count)
                        except Exception as cb_error:
                            self._debug_log(f"⚠️  Rate limit discovered callback failed: {cb_error}")

                # Reset rate limit queue to force full 60-second wait
                # This prevents immediately hitting the limit again
                self._debug_log(f"   🔄 Resetting rate limit queue - forcing full 60s wait before next request")
                self.itunes_requests.clear()

                # Notify the UI if callback is available
                if hasattr(self, 'rate_limit_hit_callback') and self.rate_limit_hit_callback:
                    try:
                        self.rate_limit_hit_callback()
                    except Exception as cb_error:
                        self._debug_log(f"⚠️  Rate limit hit callback failed: {cb_error}")
            else:
                self._debug_log(f"   ❌ iTunes search error: {e}")
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
        logger.debug(f"      🕐 _enforce_rate_limit START (Thread {thread_id}, lock already held by caller)")

        # Use discovered limit if available and adaptive mode is enabled
        use_adaptive = self.settings.get("use_adaptive_rate_limit", True)
        discovered_limit = self.settings.get("discovered_rate_limit", None)
        user_limit = self.settings.get("itunes_rate_limit", 20)

        logger.debug(f"      📊 use_adaptive={use_adaptive}, discovered={discovered_limit}, user={user_limit}")

        if use_adaptive:
            if discovered_limit:
                # Use discovered limit with safety margin
                safety_margin = self.settings.get("rate_limit_safety_margin", 0.8)
                rate_limit = int(discovered_limit * safety_margin)
                logger.debug(f"      🎯 Using adaptive rate limit: {rate_limit} req/min (discovered: {discovered_limit}, margin: {safety_margin})")
            else:
                # No discovered limit yet - start conservatively to avoid 403 blocking
                # Use 120 req/min (2 req/sec) which is safe and won't trigger 403
                # iTunes API has been observed to block at 600 req/min with 403 Forbidden
                rate_limit = 120
                logger.debug(f"      🔍 Discovery mode: Using conservative {rate_limit} req/min to avoid 403 blocking (will adapt if we hit rate limit)")
        else:
            rate_limit = user_limit
            logger.debug(f"      📊 Using manual rate limit: {rate_limit} requests/min")

        min_interval = 60.0 / rate_limit
        logger.debug(f"      📊 Min interval: {min_interval:.2f}s")

        current_time = time.time()
        logger.debug(f"      📊 Current requests in queue: {len(self.itunes_requests)}")

        # Remove old requests (older than 1 minute)
        logger.debug(f"      📝 Removing old requests...")
        old_count = len(self.itunes_requests)
        while self.itunes_requests and current_time - self.itunes_requests[0] > 60:
            self.itunes_requests.popleft()
        removed = old_count - len(self.itunes_requests)
        logger.debug(f"      ✅ Removed {removed} old requests, {len(self.itunes_requests)} remaining")

        # Check if we need to wait
        if len(self.itunes_requests) >= rate_limit:
            sleep_time = 60 - (current_time - self.itunes_requests[0])
            if sleep_time > 0:
                logger.debug(f"      ⏸️  Rate limit reached - sleeping {sleep_time:.1f}s")
                logger.print_always(f"⏸️  iTunes rate limit reached - waiting {sleep_time:.0f}s before continuing...")

                # Call rate limit callback if provided
                logger.debug(f"      📞 Checking for rate_limit_callback...")
                if hasattr(self, 'rate_limit_callback') and self.rate_limit_callback:
                    try:
                        logger.debug(f"      📞 Calling rate_limit_callback({sleep_time})...")
                        self.rate_limit_callback(sleep_time)
                        logger.debug(f"      ✅ rate_limit_callback completed")
                    except Exception as e:
                        logger.error(f"⚠️  Rate limit callback failed: {e}")

                # Interruptible sleep with countdown
                logger.debug(f"      ⏸️  Checking for rate_limit_wait_callback...")
                if hasattr(self, 'rate_limit_wait_callback') and self.rate_limit_wait_callback:
                    # Use callback-based interruptible wait with countdown
                    logger.debug(f"      ⏸️  Calling rate_limit_wait_callback({sleep_time})... THIS MAY BLOCK")
                    self.rate_limit_wait_callback(sleep_time)
                    logger.debug(f"      ✅ rate_limit_wait_callback completed")
                else:
                    # Fallback to blocking sleep
                    logger.debug(f"      💤 No callback, using time.sleep({sleep_time})...")
                    time.sleep(sleep_time)
                    logger.debug(f"      ✅ time.sleep completed")
                logger.debug(f"      ✅ Sleep complete")
        else:
            logger.debug(f"      ✅ No rate limit wait needed ({len(self.itunes_requests)}/{rate_limit})")

        # Add current request
        self.itunes_requests.append(current_time)
        logger.debug(f"      ✅ Added request to queue, total: {len(self.itunes_requests)}")
        logger.debug(f"      🕐 _enforce_rate_limit END")

    def search_itunes_batch_parallel(self, song_names: List[str], progress_callback=None, interrupt_check=None) -> List[Dict]:
        """
        Search iTunes API for multiple songs in parallel using thread pool.
        Returns results in same order as input song_names.

        Args:
            song_names: List of track names to search
            progress_callback: Optional callback(track_idx, track_name, result, completed_count, total_count)
            interrupt_check: Optional callable that returns True if search should be interrupted
        """
        # Run network diagnostics BEFORE starting parallel search
        self._debug_log("\n" + "="*80)
        self._debug_log("STARTING ITUNES PARALLEL SEARCH - RUNNING DIAGNOSTICS FIRST")
        self._debug_log("="*80)
        diagnostics = self._test_network_connectivity()
        self._debug_log(f"Network diagnostics results: {diagnostics}")

        # If network test failed, log details and potentially abort
        if not diagnostics.get("network_reachable"):
            error_msg = f"Network connectivity test failed: {diagnostics.get('error', 'Unknown error')}"
            self._debug_log(f"❌ CRITICAL: {error_msg}")
            self._debug_log(f"   httpx version: {diagnostics.get('httpx_version', 'unknown')}")
            self._debug_log(f"   certifi available: {diagnostics.get('certifi_available', False)}")
            self._debug_log(f"   certifi path: {diagnostics.get('certifi_path', 'N/A')}")
            # Continue anyway to see what happens with actual iTunes API
        else:
            self._debug_log(f"✅ Network diagnostics passed - proceeding with iTunes search")

        use_parallel = self.settings.get("use_parallel_requests", False)
        max_workers = self.settings.get("parallel_workers", 10)

        if not use_parallel:
            # Fall back to sequential processing with progress updates
            self._debug_log(f"Using sequential mode (parallel disabled)")
            results = []
            for idx, song in enumerate(song_names):
                # Check for interrupt
                if interrupt_check and interrupt_check():
                    self._debug_log(f"⏹️ Search interrupted by user at track {idx}/{len(song_names)}")
                    logger.print_always(f"⏹️ iTunes search stopped by user at {idx}/{len(song_names)} tracks")
                    break

                result = self._search_itunes(song)
                results.append(result)
                if progress_callback:
                    progress_callback(idx, song, result, idx + 1, len(song_names))
            return results

        self._debug_log(f"🚀 Starting parallel iTunes search for {len(song_names)} tracks with {max_workers} workers")

        results = [None] * len(song_names)  # Pre-allocate results array
        completed_count = 0
        interrupted = False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._search_itunes, song_name): (idx, song_name)
                for idx, song_name in enumerate(song_names)
            }

            # Collect results as they complete
            for future in as_completed(future_to_index):
                # Check for interrupt before processing next result
                if interrupt_check and interrupt_check():
                    self._debug_log(f"⏹️ Search interrupted by user at {completed_count}/{len(song_names)} tracks")
                    logger.print_always(f"⏹️ iTunes search stopped by user at {completed_count}/{len(song_names)} tracks")
                    interrupted = True
                    # Cancel remaining futures
                    for f in future_to_index:
                        if not f.done():
                            f.cancel()
                    break

                idx, song_name = future_to_index[future]
                try:
                    result = future.result()
                    results[idx] = result
                    completed_count += 1

                    # Call progress callback with live update
                    if progress_callback:
                        progress_callback(idx, song_name, result, completed_count, len(song_names))

                except Exception as e:
                    logger.error(f"   ❌ Parallel search failed for track {idx}: {e}")
                    result = {
                        "success": False,
                        "source": "itunes",
                        "error": str(e)
                    }
                    results[idx] = result
                    completed_count += 1

                    # Call progress callback even on error
                    if progress_callback:
                        progress_callback(idx, song_name, result, completed_count, len(song_names))

        if interrupted:
            logger.print_always(f"⏹️ Parallel search interrupted: {completed_count}/{len(song_names)} tracks completed")
        else:
            logger.print_always(f"✅ Parallel search complete: {len(results)} results")
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
