#!/usr/bin/env python3
"""Regression tests for the mutable user-track mapping cache."""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apple_music_history_converter.app_directories import (  # noqa: E402
    STORAGE_ROOT_ENV,
    get_database_dir,
    get_user_cache_dir,
    get_user_data_dir,
    get_user_log_dir,
)
from apple_music_history_converter.track_mapping import TrackMappingCache  # noqa: E402


class TrackMappingSQLiteTests(unittest.TestCase):
    def test_repeated_duplicate_upserts_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = TrackMappingCache(str(Path(tmp) / "mappings.sqlite3"))
            for _ in range(10_000):
                self.assertTrue(cache.store(
                    "Duplicate Song", "Duplicate Album", "Duplicate Artist",
                    "Resolved Artist", "Resolved Album", "recording-id", "high",
                ))
            stats = cache.get_stats()
            self.assertEqual(stats["total_mappings"], 1)
            self.assertEqual(stats["engine"], "sqlite")
            result = cache.lookup("duplicate song", "duplicate album", "duplicate artist")
            self.assertEqual(result["mb_artist_credit_name"], "Resolved Artist")
            self.assertEqual(result["use_count"], 10_000)
            cache.close()

    def test_concurrent_duplicate_upserts_keep_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = TrackMappingCache(str(Path(tmp) / "mappings.sqlite3"))
            failures = []

            def writer():
                for _ in range(1_000):
                    if not cache.store("Song", "Album", "Artist", "Match"):
                        failures.append(True)

            threads = [threading.Thread(target=writer) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertFalse(failures)
            self.assertEqual(cache.get_stats()["total_mappings"], 1)
            cache.close()

    def test_manual_mapping_is_not_overwritten_by_automatic_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = TrackMappingCache(str(Path(tmp) / "mappings.sqlite3"))
            self.assertTrue(cache.store_user_verified(
                "Song", "Album", "Artist", "User Choice", "User Release",
            ))
            self.assertTrue(cache.store(
                "Song", "Album", "Artist", "Automatic Choice", confidence="high",
            ))
            result = cache.lookup("Song", "Album", "Artist")
            self.assertEqual(result["verified_by"], "user")
            self.assertEqual(result["mb_artist_credit_name"], "User Choice")
            cache.close()

    def test_external_storage_root_routes_large_and_mutable_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(STORAGE_ROOT_ENV)
            os.environ[STORAGE_ROOT_ENV] = tmp
            try:
                root = Path(tmp)
                self.assertEqual(get_user_data_dir(), root / "data")
                self.assertEqual(get_database_dir(), root / "data")
                self.assertEqual(get_user_cache_dir(), root / "cache")
                self.assertEqual(get_user_log_dir(), root / "logs")
            finally:
                if previous is None:
                    os.environ.pop(STORAGE_ROOT_ENV, None)
                else:
                    os.environ[STORAGE_ROOT_ENV] = previous

    def test_legacy_duckdb_cache_is_imported_once(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("DuckDB is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(STORAGE_ROOT_ENV)
            os.environ[STORAGE_ROOT_ENV] = tmp
            legacy_path = Path(tmp) / "data" / "track_mappings.duckdb"
            legacy_path.parent.mkdir(parents=True)
            legacy = duckdb.connect(str(legacy_path))
            legacy.execute("""
                CREATE TABLE user_track_mappings (
                    track_hash VARCHAR PRIMARY KEY,
                    apple_song_name VARCHAR NOT NULL,
                    apple_album_name VARCHAR,
                    apple_artist_name VARCHAR,
                    mb_recording_mbid VARCHAR,
                    mb_artist_credit_name VARCHAR,
                    mb_release_name VARCHAR,
                    confidence VARCHAR,
                    verified_by VARCHAR,
                    created_at TIMESTAMP,
                    last_used_at TIMESTAMP,
                    use_count INTEGER
                )
            """)
            legacy.execute("""
                INSERT INTO user_track_mappings VALUES (
                    'legacy-hash', 'Song', 'Album', 'Artist', NULL,
                    'Resolved Artist', 'Release', 'high', 'auto',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 3
                )
            """)
            legacy.close()
            try:
                cache = TrackMappingCache()
                self.assertEqual(cache.get_stats()["total_mappings"], 1)
                cache.close()
                self.assertTrue(
                    (Path(tmp) / "data" / "track_mappings.sqlite3.legacy-imported").exists()
                )

                reopened = TrackMappingCache()
                self.assertEqual(reopened.get_stats()["total_mappings"], 1)
                reopened.close()
            finally:
                if previous is None:
                    os.environ.pop(STORAGE_ROOT_ENV, None)
                else:
                    os.environ[STORAGE_ROOT_ENV] = previous

    def test_corrupt_sqlite_cache_is_quarantined_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "mappings.sqlite3"
            db_path.write_bytes(b"not a sqlite database")
            cache = TrackMappingCache(str(db_path))
            self.assertTrue(cache.is_enabled)
            self.assertTrue(cache.store("Song", "Album", "Artist", "Match"))
            self.assertEqual(cache.get_stats()["total_mappings"], 1)
            cache.close()
            self.assertEqual(len(list(Path(tmp).glob("mappings.sqlite3.corrupt-*"))), 1)


if __name__ == "__main__":
    unittest.main()
