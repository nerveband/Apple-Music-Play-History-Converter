#!/usr/bin/env python3
"""
Debug script to test MusicBrainz search functionality
Tests the search methods with sample data from the CSV to identify where the hang occurs
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

async def test_search():
    """Test MusicBrainz search with sample data"""
    print("\n" + "="*80)
    print("MUSICBRAINZ SEARCH DEBUG TEST")
    print("="*80 + "\n")

    # Initialize service
    print("1. Initializing MusicSearchServiceV2...")
    service = MusicSearchServiceV2()
    print(f"   Provider: {service.get_search_provider()}")
    print(f"   Auto-fallback: {service.get_auto_fallback()}")

    # Check MusicBrainz status
    print("\n2. Checking MusicBrainz status...")
    mb_manager = service.musicbrainz_manager
    print(f"   CSV available: {mb_manager.is_database_available()}")
    print(f"   DuckDB exists: {mb_manager.duckdb_file.exists()}")
    print(f"   Is ready: {mb_manager.is_ready()}")
    print(f"   Optimization complete: {mb_manager._optimization_complete}")

    # Ensure MusicBrainz is ready
    print("\n3. Ensuring MusicBrainz is ready...")
    try:
        ready = await asyncio.wait_for(
            service.ensure_musicbrainz_ready(),
            timeout=10.0
        )
        print(f"   Ready result: {ready}")
    except asyncio.TimeoutError:
        print("   ❌ TIMEOUT: ensure_musicbrainz_ready() took more than 10 seconds!")
        return
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test searches with sample data from CSV
    test_cases = [
        {"track": "Apple Music 1", "artist": None, "album": ""},  # The problematic one
        {"track": "1/2", "artist": "Brian Eno", "album": ""},
        {"track": "Get Lucky (feat. Nile Rodgers & Pharrell Williams)", "artist": "Daft Punk", "album": ""},
        {"track": "I Can Change", "artist": "LCD Soundsystem", "album": ""},
    ]

    print("\n4. Testing searches...")
    for i, test in enumerate(test_cases, 1):
        print(f"\n   Test {i}: track='{test['track']}', artist='{test['artist']}', album='{test['album']}'")
        try:
            result = await asyncio.wait_for(
                service.search_song(
                    test['track'],
                    test['artist'],
                    test['album']
                ),
                timeout=5.0  # 5 second timeout per search
            )
            print(f"   ✅ Result: {result}")
        except asyncio.TimeoutError:
            print(f"   ❌ TIMEOUT: Search took more than 5 seconds!")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_search())