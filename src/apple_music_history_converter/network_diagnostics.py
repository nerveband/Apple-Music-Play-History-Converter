#!/usr/bin/env python3
"""
Network diagnostics module for troubleshooting httpx connectivity in packaged apps.
This module can be imported and called early in app startup to verify network configuration.

Can be run directly for testing:
    python -m apple_music_history_converter.network_diagnostics
    or
    python src/apple_music_history_converter/network_diagnostics.py
"""

import sys
import os
from pathlib import Path

try:
    from .app_directories import get_log_path
    from .logging_config import get_logger
except ImportError:
    from app_directories import get_log_path
    from logging_config import get_logger


def run_diagnostics(log_file=None, verbose=True):
    """
    Run comprehensive network diagnostics and log results.

    Args:
        log_file: Optional path to log file. If None, uses platform-appropriate log directory
        verbose: If True, print to terminal in addition to file (default: True)

    Returns:
        bool: True if all diagnostics passed, False otherwise
    """
    # Set up logger with clean print-like output
    logger = get_logger("network_diagnostics")

    # Helper function for compatibility with existing code
    def log(message, force_print=False):
        """Log to both console and file using the new logger"""
        logger.info(message)

    log("\n" + "="*80)
    log("NETWORK DIAGNOSTICS - Apple Music History Converter")
    log("="*80)

    # Python environment
    log(f"\n1. Python Environment:")
    log(f"   Python version: {sys.version}")
    log(f"   Python executable: {sys.executable}")
    log(f"   Platform: {sys.platform}")

    # App directories
    log(f"\n2. App Directory Configuration:")
    try:
        from .app_directories import (
            get_user_data_dir, get_user_log_dir,
            get_user_cache_dir, get_legacy_data_dir
        )
        log(f"   User Data Dir:  {get_user_data_dir()}")
        log(f"   User Log Dir:   {get_user_log_dir()}")
        log(f"   User Cache Dir: {get_user_cache_dir()}")
        log(f"   Legacy Dir:     {get_legacy_data_dir()}")

        # Test write access
        test_file = get_user_log_dir() / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            log(f"   ✅ Log directory is writable")
        except Exception as e:
            log(f"   ❌ Log directory NOT writable: {e}")
    except Exception as e:
        log(f"   ⚠️  Directory check error: {e}")

    # SSL/TLS certificates
    log(f"\n3. SSL/TLS Certificate Configuration:")
    try:
        import ssl
        log(f"   ✅ ssl module imported successfully")
        log(f"   OpenSSL version: {ssl.OPENSSL_VERSION}")
        ctx = ssl.create_default_context()
        log(f"   ✅ Default SSL context created")
    except Exception as e:
        log(f"   ❌ SSL module error: {e}")
        return False

    # Certifi
    log(f"\n4. Certifi Certificate Bundle:")
    try:
        import certifi
        certifi_path = certifi.where()
        log(f"   ✅ certifi imported successfully")
        log(f"   Certificate bundle path: {certifi_path}")

        if os.path.exists(certifi_path):
            size = os.path.getsize(certifi_path)
            log(f"   ✅ Certificate bundle exists ({size:,} bytes)")
        else:
            log(f"   ❌ Certificate bundle NOT FOUND at {certifi_path}")
            return False
    except Exception as e:
        log(f"   ❌ Certifi error: {e}")
        return False

    # httpx
    log(f"\n5. httpx HTTP Client:")
    try:
        import httpx
        log(f"   ✅ httpx imported successfully")
        log(f"   httpx version: {httpx.__version__}")
    except Exception as e:
        log(f"   ❌ httpx import error: {e}")
        log("   CRITICAL: Cannot proceed without httpx")
        return False

    # Test basic connectivity
    log(f"\n6. Network Connectivity Test:")
    try:
        import ssl
        import certifi
        import httpx

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        log(f"   Testing connection to https://www.apple.com...")

        response = httpx.get("https://www.apple.com", timeout=10, verify=ssl_context)
        log(f"   ✅ Connection successful!")
        log(f"   Status code: {response.status_code}")
        log(f"   Response size: {len(response.content):,} bytes")
    except httpx.ConnectError as e:
        log(f"   ❌ Connection error: {e}")
        log(f"   Error type: {type(e).__name__}")
        return False
    except httpx.TimeoutException as e:
        log(f"   ❌ Timeout error: {e}")
        return False
    except Exception as e:
        log(f"   ❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        log(f"   Traceback:\n{traceback.format_exc()}")
        return False

    # Test iTunes API specifically
    log(f"\n7. iTunes API Connectivity Test:")
    try:
        import ssl
        import certifi
        import httpx

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        url = "https://itunes.apple.com/search"
        params = {
            'term': 'test',
            'media': 'music',
            'entity': 'song',
            'limit': 1
        }

        log(f"   Testing iTunes API with SSL context...")
        response = httpx.get(url, params=params, timeout=10, verify=ssl_context)
        log(f"   ✅ iTunes API connection successful!")
        log(f"   Status code: {response.status_code}")

        data = response.json()
        results_count = len(data.get('results', []))
        log(f"   Results returned: {results_count}")

        if results_count > 0:
            artist = data['results'][0].get('artistName', 'Unknown')
            track = data['results'][0].get('trackName', 'Unknown')
            log(f"   Sample result: {artist} - {track}")

    except Exception as e:
        log(f"   ❌ iTunes API error: {type(e).__name__}: {e}")
        import traceback
        log(f"   Traceback:\n{traceback.format_exc()}")
        return False

    log(f"\n" + "="*80)
    log("✅ ALL DIAGNOSTICS PASSED - Network connectivity OK")
    log("="*80 + "\n")
    log(f"📝 Full log saved to: {log_file}", force_print=True)

    return True


if __name__ == "__main__":
    # Use a simple logger for standalone execution
    logger = get_logger(__name__)

    logger.print_always("\n🔬 Running Network Diagnostics...")
    logger.print_always("="*80)
    success = run_diagnostics(verbose=True)
    logger.print_always("="*80)

    if success:
        logger.print_always("\n✅ All diagnostics passed! Network is working correctly.\n")
        sys.exit(0)
    else:
        logger.print_always("\n❌ Diagnostics failed! Check the log file for details.\n")
        sys.exit(1)
