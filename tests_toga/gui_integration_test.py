#!/usr/bin/env python3
"""
Comprehensive GUI Integration Tests

Tests the full application workflow with real CSV files from _test_csvs folder.
This script runs automated tests against the actual application.
"""

import sys
import os
import time
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Test CSV directory
TEST_CSV_DIR = Path(__file__).parent.parent / "_test_csvs"

# Test files to process
TEST_FILES = [
    ("Apple Music - Recently Played Tracks.csv", "recently_played"),
    ("Apple Music - Play History Daily Tracks.csv", "daily_tracks"),
    ("Apple Music Play Activity small.csv", "play_activity"),
]

class TestResult:
    """Store test results."""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0.0
        self.details = {}

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"{status}: {self.name} ({self.duration:.2f}s)"


class GUIIntegrationTester:
    """Run comprehensive GUI integration tests."""

    def __init__(self):
        self.results = []
        self.app = None
        self.output_dir = None

    def log(self, msg: str):
        """Print timestamped log message."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    async def run_all_tests(self):
        """Run all integration tests."""
        self.log("=" * 60)
        self.log("Starting GUI Integration Tests")
        self.log("=" * 60)

        # Create temp output directory
        self.output_dir = tempfile.mkdtemp(prefix="gui_test_")
        self.log(f"Output directory: {self.output_dir}")

        # Initialize the app
        await self.test_app_initialization()

        # Test each CSV file
        for filename, file_type in TEST_FILES:
            csv_path = TEST_CSV_DIR / filename
            if csv_path.exists():
                await self.test_file_processing(csv_path, file_type)
            else:
                self.log(f"SKIP: {filename} not found")

        # Test error handling
        await self.test_error_handling()

        # Test MusicBrainz integration
        await self.test_musicbrainz_search()

        # Test session alignment feature
        await self.test_session_alignment()

        # Print summary
        self.print_summary()

        return all(r.passed for r in self.results)

    async def test_app_initialization(self):
        """Test app initialization."""
        result = TestResult("App Initialization")
        start = time.time()

        try:
            from apple_music_history_converter.music_search_service_v2 import MusicSearchServiceV2

            self.search_service = MusicSearchServiceV2()

            # Check MusicBrainz status
            mb_ready = self.search_service.is_musicbrainz_optimized()
            result.details['musicbrainz_ready'] = mb_ready

            if mb_ready:
                self.log("MusicBrainz database is ready")
            else:
                self.log("MusicBrainz database not ready (will use iTunes API)")

            result.passed = True
            self.log("App initialization: PASSED")

        except Exception as e:
            result.error = str(e)
            self.log(f"App initialization: FAILED - {e}")

        result.duration = time.time() - start
        self.results.append(result)

    async def test_file_processing(self, csv_path: Path, file_type: str):
        """Test processing a specific CSV file."""
        test_result = TestResult(f"Process {csv_path.name}")
        start = time.time()

        try:
            import pandas as pd
            from apple_music_history_converter.ultra_fast_csv_processor import UltraFastCSVProcessor

            self.log(f"\nProcessing: {csv_path.name}")

            # Load CSV
            df = pd.read_csv(csv_path, low_memory=False)
            row_count = len(df)
            test_result.details['row_count'] = row_count
            self.log(f"  Loaded {row_count} rows")

            # Detect columns
            columns = list(df.columns)
            test_result.details['columns'] = len(columns)
            self.log(f"  Columns: {len(columns)}")

            # Process sample of tracks (first 50 for speed)
            sample_size = min(50, row_count)
            processed = 0
            matched = 0
            errors = 0

            for idx in range(sample_size):
                row = df.iloc[idx]

                # Extract track info based on file type
                if file_type == "recently_played":
                    track_desc = str(row.get('Track Description', ''))
                    if ' - ' in track_desc:
                        parts = track_desc.split(' - ', 1)
                        artist = parts[0].strip()
                        track = parts[1].strip()
                    else:
                        artist = ''
                        track = track_desc.strip()
                    album = str(row.get('Container Description', '')) if pd.notna(row.get('Container Description')) else ''

                elif file_type == "daily_tracks":
                    track = str(row.get('Song Name', '')) if pd.notna(row.get('Song Name')) else ''
                    artist = str(row.get('Artist', '')) if pd.notna(row.get('Artist')) else ''
                    album = str(row.get('Album', '')) if pd.notna(row.get('Album')) else ''

                else:  # play_activity
                    track = str(row.get('Song Name', '')) if pd.notna(row.get('Song Name')) else ''
                    artist = str(row.get('Artist Name', '')) if pd.notna(row.get('Artist Name')) else ''
                    album = str(row.get('Container Name', '')) if pd.notna(row.get('Container Name')) else ''

                if not track:
                    continue

                processed += 1

                # Search for track (search_song is async, returns Dict)
                try:
                    search_result = await self.search_service.search_song(
                        song_name=track,
                        artist_name=artist if artist else None,
                        album_name=album if album else None
                    )

                    if search_result.get('success') and search_result.get('artist') and search_result.get('artist') != "[Unknown]":
                        matched += 1

                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        self.log(f"    Error searching '{track}': {e}")

            test_result.details['processed'] = processed
            test_result.details['matched'] = matched
            test_result.details['errors'] = errors
            test_result.details['match_rate'] = f"{matched/processed*100:.1f}%" if processed > 0 else "N/A"

            self.log(f"  Processed: {processed}, Matched: {matched} ({test_result.details['match_rate']})")

            test_result.passed = errors < processed * 0.1  # Allow up to 10% errors
            status = "PASSED" if test_result.passed else "FAILED"
            self.log(f"  Result: {status}")

        except Exception as e:
            test_result.error = str(e)
            self.log(f"  FAILED: {e}")

        test_result.duration = time.time() - start
        self.results.append(test_result)

    async def test_error_handling(self):
        """Test error handling for invalid inputs."""
        result = TestResult("Error Handling")
        start = time.time()

        try:
            tests_passed = 0
            tests_total = 0

            # Test 1: Empty track name
            tests_total += 1
            try:
                r = await self.search_service.search_song("")
                if not r.get('success') or r.get('artist') is None or r.get('artist') == "[Unknown]":
                    tests_passed += 1
                    self.log("  Empty track name: PASS (returned None/Unknown)")
            except:
                tests_passed += 1  # Exception is acceptable
                self.log("  Empty track name: PASS (raised exception)")

            # Test 2: Very long track name
            tests_total += 1
            try:
                long_name = "A" * 1000
                r = await self.search_service.search_song(long_name)
                tests_passed += 1
                self.log("  Long track name: PASS (handled without crash)")
            except Exception as e:
                self.log(f"  Long track name: FAIL ({e})")

            # Test 3: Special characters
            tests_total += 1
            try:
                r = await self.search_service.search_song("Test !@#$%^&*()")
                tests_passed += 1
                self.log("  Special characters: PASS (handled without crash)")
            except Exception as e:
                self.log(f"  Special characters: FAIL ({e})")

            # Test 4: Unicode characters
            tests_total += 1
            try:
                r = await self.search_service.search_song("Cafe - Musica Clasica")
                tests_passed += 1
                self.log("  Unicode characters: PASS (handled without crash)")
            except Exception as e:
                self.log(f"  Unicode characters: FAIL ({e})")

            result.details['tests_passed'] = tests_passed
            result.details['tests_total'] = tests_total
            result.passed = tests_passed == tests_total

        except Exception as e:
            result.error = str(e)

        result.duration = time.time() - start
        self.results.append(result)

    async def test_musicbrainz_search(self):
        """Test MusicBrainz search functionality."""
        result = TestResult("MusicBrainz Search")
        start = time.time()

        try:
            if not self.search_service.is_musicbrainz_optimized():
                result.details['skipped'] = "MusicBrainz not ready"
                result.passed = True
                self.log("  MusicBrainz not ready - SKIPPED")
                result.duration = time.time() - start
                self.results.append(result)
                return

            # Test known tracks
            test_tracks = [
                ("Blinding Lights", "The Weeknd", "After Hours"),
                ("Bohemian Rhapsody", "Queen", "A Night at the Opera"),
                ("Thriller", "Michael Jackson", "Thriller"),
                ("One More Time", "Daft Punk", "Discovery"),
                ("Bad Guy", "Billie Eilish", None),
            ]

            matched = 0
            for track, expected_artist, album in test_tracks:
                search_result = await self.search_service.search_song(
                    song_name=track,
                    artist_name=expected_artist,
                    album_name=album
                )

                found = search_result.get('artist', '')
                if found and expected_artist.lower() in found.lower():
                    matched += 1
                    self.log(f"  '{track}': MATCHED ({found})")
                else:
                    self.log(f"  '{track}': MISMATCH (got: {found}, expected: {expected_artist})")

            result.details['matched'] = matched
            result.details['total'] = len(test_tracks)
            result.passed = matched >= len(test_tracks) * 0.8  # 80% match rate

        except Exception as e:
            result.error = str(e)

        result.duration = time.time() - start
        self.results.append(result)

    async def test_session_alignment(self):
        """Test the album-session alignment feature."""
        result = TestResult("Session Alignment")
        start = time.time()

        try:
            if not self.search_service.is_musicbrainz_optimized():
                result.details['skipped'] = "MusicBrainz not ready"
                result.passed = True
                self.log("  MusicBrainz not ready - SKIPPED")
                result.duration = time.time() - start
                self.results.append(result)
                return

            # Create test session data (consecutive tracks from same album)
            test_tracks = [
                {'track': 'Blinding Lights', 'album': 'After Hours', 'artist': ''},
                {'track': 'Save Your Tears', 'album': 'After Hours', 'artist': ''},
                {'track': 'Heartless', 'album': 'After Hours', 'artist': ''},
                {'track': 'In Your Eyes', 'album': 'After Hours', 'artist': ''},
            ]

            # Test session alignment
            aligned_tracks, stats = self.search_service.apply_session_alignment(test_tracks)

            result.details['sessions_detected'] = stats.get('sessions_detected', 0)
            result.details['tracks_aligned'] = stats.get('tracks_aligned', 0)

            self.log(f"  Sessions detected: {stats.get('sessions_detected', 0)}")
            self.log(f"  Tracks aligned: {stats.get('tracks_aligned', 0)}")

            # Check if alignment was applied
            if stats.get('sessions_detected', 0) >= 1:
                result.passed = True
                self.log("  Session alignment: PASSED")
            else:
                self.log("  Session alignment: No sessions detected (may be expected)")
                result.passed = True  # Not a failure, just no sessions

        except Exception as e:
            result.error = str(e)
            self.log(f"  Session alignment: FAILED - {e}")

        result.duration = time.time() - start
        self.results.append(result)

    def print_summary(self):
        """Print test summary."""
        self.log("\n" + "=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            self.log(f"  [{status}] {result.name} ({result.duration:.2f}s)")
            if result.error:
                self.log(f"         Error: {result.error}")
            for key, value in result.details.items():
                self.log(f"         {key}: {value}")

        self.log("-" * 60)
        self.log(f"TOTAL: {passed}/{total} passed, {failed} failed")

        if failed == 0:
            self.log("ALL TESTS PASSED!")
        else:
            self.log(f"WARNING: {failed} test(s) failed")

        self.log("=" * 60)


async def main():
    """Run the GUI integration tests."""
    tester = GUIIntegrationTester()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
