#!/usr/bin/env python3
"""
Integration tests for the Python sidecar.
Tests real CSV files and IPC message handling.
"""

import json
import subprocess
import sys
import os
import queue
import threading
import time
from pathlib import Path

# Project paths
SIDECAR_PATH = Path(__file__).parent / "sidecar.py"
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_CSVS = Path(__file__).parent / "fixtures"

# Test CSV files
PLAY_ACTIVITY_CSV = TEST_CSVS / "play_activity.csv"
RECENTLY_PLAYED_CSV = TEST_CSVS / "recently_played.csv"
DAILY_TRACKS_CSV = TEST_CSVS / "daily_tracks.csv"

passed = 0
failed = 0
errors = []


def sidecar_test(name):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            global passed, failed
            try:
                func()
                passed += 1
                print(f"  [OK] {name}")
            except AssertionError as e:
                failed += 1
                errors.append(f"{name}: {e}")
                print(f"  [FAIL] {name}: {e}")
            except Exception as e:
                failed += 1
                errors.append(f"{name}: {type(e).__name__}: {e}")
                print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        wrapper._test_name = name
        return wrapper
    return decorator


class SidecarProcess:
    """Helper to manage sidecar process for tests."""

    def __init__(self):
        self.proc = None
        self.messages = queue.Queue()
        self.reader_thread = None

    def start(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SIDECAR_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
            text=True,
            bufsize=1,
        )
        self.reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader_thread.start()
        # Read the "ready" message
        ready = self.read_message(timeout=120.0)
        assert ready.get("type") == "ready", f"Expected ready, got: {ready}"
        return ready

    def _read_stdout(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                self.messages.put(line)

    def send(self, msg: dict):
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def read_message(self, timeout: float = 10.0) -> dict:
        """Read one JSON message from stdout."""
        try:
            return json.loads(self.messages.get(timeout=timeout))
        except queue.Empty:
            if self.proc.poll() is not None:
                stderr = self.proc.stderr.read()
                raise RuntimeError(
                    f"Sidecar exited with {self.proc.returncode}: {stderr}"
                )
            raise TimeoutError(f"No message received within {timeout}s")

    def read_messages_until(self, msg_type: str, timeout: float = 15.0) -> list:
        """Read messages until we get one of the specified type."""
        messages = []
        start = time.time()
        while time.time() - start < timeout:
            try:
                msg = self.read_message(timeout=1.0)
                messages.append(msg)
                if msg.get("type") == msg_type:
                    return messages
            except TimeoutError:
                continue
            except json.JSONDecodeError:
                continue
        return messages

    def stop(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@sidecar_test("Sidecar starts and responds to ping")
def test_ping():
    sidecar = SidecarProcess()
    try:
        ready = sidecar.start()
        assert ready["type"] == "ready"
        assert ready["version"] == "3.0.3", f"Unexpected sidecar version: {ready}"

        sidecar.send({"action": "ping"})
        resp = sidecar.read_message()
        assert resp["type"] == "pong"
    finally:
        sidecar.stop()


@sidecar_test("CSV analysis detects Play Activity format")
def test_analyze_play_activity():
    if not PLAY_ACTIVITY_CSV.exists():
        raise AssertionError(f"Test CSV not found: {PLAY_ACTIVITY_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "analyzeCSV", "path": str(PLAY_ACTIVITY_CSV)})
        msgs = sidecar.read_messages_until("fileAnalysis", timeout=30)
        analyses = [m for m in msgs if m.get("type") == "fileAnalysis"]
        assert len(analyses) == 1, f"Got types: {[m.get('type') for m in msgs]}"
        resp = analyses[0]
        assert resp["type"] == "fileAnalysis", f"Got: {resp}"
        assert resp["fileType"] == "Play Activity", f"Got fileType: {resp.get('fileType')}"
        assert resp["rowCount"] > 0, f"Got rowCount: {resp.get('rowCount')}"
    finally:
        sidecar.stop()


@sidecar_test("CSV analysis detects Recently Played format")
def test_analyze_recently_played():
    if not RECENTLY_PLAYED_CSV.exists():
        raise AssertionError(f"Test CSV not found: {RECENTLY_PLAYED_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "analyzeCSV", "path": str(RECENTLY_PLAYED_CSV)})
        msgs = sidecar.read_messages_until("fileAnalysis", timeout=30)
        analyses = [m for m in msgs if m.get("type") == "fileAnalysis"]
        assert len(analyses) == 1, f"Got types: {[m.get('type') for m in msgs]}"
        resp = analyses[0]
        assert resp["type"] == "fileAnalysis", f"Got: {resp}"
        assert resp["fileType"] == "Recently Played Tracks", f"Got: {resp.get('fileType')}"
    finally:
        sidecar.stop()


@sidecar_test("CSV analysis detects Daily Tracks format")
def test_analyze_daily_tracks():
    if not DAILY_TRACKS_CSV.exists():
        raise AssertionError(f"Test CSV not found: {DAILY_TRACKS_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "analyzeCSV", "path": str(DAILY_TRACKS_CSV)})
        msgs = sidecar.read_messages_until("fileAnalysis", timeout=30)
        analyses = [m for m in msgs if m.get("type") == "fileAnalysis"]
        assert len(analyses) == 1, f"Got types: {[m.get('type') for m in msgs]}"
        resp = analyses[0]
        assert resp["type"] == "fileAnalysis", f"Got: {resp}"
        assert resp["fileType"] == "Play History Daily Tracks", f"Got: {resp.get('fileType')}"
    finally:
        sidecar.stop()


@sidecar_test("CSV preview returns normalized columns for Play Activity")
def test_preview_play_activity():
    if not PLAY_ACTIVITY_CSV.exists():
        raise AssertionError(f"Test CSV not found: {PLAY_ACTIVITY_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "getPreview", "path": str(PLAY_ACTIVITY_CSV)})
        msgs = sidecar.read_messages_until("csvPreview", timeout=30)
        previews = [m for m in msgs if m.get("type") == "csvPreview"]
        assert len(previews) == 1, f"Got types: {[m.get('type') for m in msgs]}"
        resp = previews[0]
        assert resp["type"] == "csvPreview", f"Got: {resp}"
        assert resp["headers"] == ["Artist", "Track", "Album", "Timestamp", "Duration"]
        assert len(resp["rows"]) > 0
        # Check first row has track name
        first_row = resp["rows"][0]
        assert len(first_row) == 5
        # Track column (index 1) should have data from Song Name
        assert first_row[1], f"Empty track name in first row: {first_row}"
    finally:
        sidecar.stop()


@sidecar_test("CSV preview returns normalized columns for Recently Played")
def test_preview_recently_played():
    if not RECENTLY_PLAYED_CSV.exists():
        raise AssertionError(f"Test CSV not found: {RECENTLY_PLAYED_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "getPreview", "path": str(RECENTLY_PLAYED_CSV)})
        msgs = sidecar.read_messages_until("csvPreview", timeout=30)
        previews = [m for m in msgs if m.get("type") == "csvPreview"]
        assert len(previews) == 1, f"Got types: {[m.get('type') for m in msgs]}"
        resp = previews[0]
        assert resp["type"] == "csvPreview", f"Got: {resp}"
        assert len(resp["rows"]) > 0
        first_row = resp["rows"][0]
        # Recently Played has "Artist - Track" in Track Description
        # After normalization, artist (index 0) should be populated
        assert first_row[0], f"Empty artist in Recently Played: {first_row}"
        assert first_row[1], f"Empty track in Recently Played: {first_row}"
    finally:
        sidecar.stop()


@sidecar_test("CSV loading normalizes tracks correctly")
def test_load_csv():
    if not PLAY_ACTIVITY_CSV.exists():
        raise AssertionError(f"Test CSV not found: {PLAY_ACTIVITY_CSV}")

    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "loadCSV", "path": str(PLAY_ACTIVITY_CSV)})
        msgs = sidecar.read_messages_until("csvLoaded", timeout=30)
        csv_loaded = [m for m in msgs if m.get("type") == "csvLoaded"]
        assert len(csv_loaded) == 1, f"Expected csvLoaded, got: {[m.get('type') for m in msgs]}"
        assert csv_loaded[0]["success"] is True
        assert csv_loaded[0]["rowCount"] > 0
        assert csv_loaded[0]["fileType"] == "Play Activity"
    finally:
        sidecar.stop()


@sidecar_test("Settings can be saved and retrieved")
def test_settings():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        # Set settings
        sidecar.send({"action": "setSettings", "settings": {"itunes_country": "gb"}})
        resp = sidecar.read_message()
        assert resp["type"] == "status"

        # Get settings
        sidecar.send({"action": "getSettings"})
        resp = sidecar.read_message()
        assert resp["type"] == "settingsLoaded", f"Got: {resp}"
        assert resp["settings"]["itunes_country"] == "gb"
    finally:
        sidecar.stop()


@sidecar_test("Unknown action returns error")
def test_unknown_action():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "nonexistentAction"})
        resp = sidecar.read_message()
        assert resp["type"] == "error", f"Got: {resp}"
        assert "Unknown action" in resp["error"]
    finally:
        sidecar.stop()


@sidecar_test("Search without loaded CSV returns error")
def test_search_without_csv():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "startSearch", "provider": "musicbrainz_api"})
        resp = sidecar.read_message()
        assert resp["type"] == "error", f"Got: {resp}"
        assert "No tracks loaded" in resp["error"]
    finally:
        sidecar.stop()


@sidecar_test("Export without tracks returns error")
def test_export_without_tracks():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "export", "format": "lastfm", "path": "/tmp/test.csv"})
        resp = sidecar.read_message()
        assert resp["type"] == "error", f"Got: {resp}"
        assert "No tracks" in resp["error"]
    finally:
        sidecar.stop()


@sidecar_test("Service initializes successfully")
def test_initialize():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "initialize"})
        msgs = sidecar.read_messages_until("initialized", timeout=15)
        init_msgs = [m for m in msgs if m.get("type") == "initialized"]
        assert len(init_msgs) == 1, f"No initialized message. Got: {[m.get('type') for m in msgs]}"
        assert init_msgs[0]["success"] is True
    finally:
        sidecar.stop()


@sidecar_test("Database status returns structured data")
def test_database_status():
    sidecar = SidecarProcess()
    try:
        sidecar.start()
        sidecar.send({"action": "initialize"})
        sidecar.read_messages_until("initialized", timeout=15)

        sidecar.send({"action": "getDatabaseStatus"})
        msgs = sidecar.read_messages_until("databaseStatus", timeout=10)
        db_msgs = [m for m in msgs if m.get("type") == "databaseStatus"]
        assert len(db_msgs) == 1, f"No databaseStatus. Got types: {[m.get('type') for m in msgs]}"
        resp = db_msgs[0]
        assert "downloaded" in resp
        assert "trackCount" in resp
        assert "size" in resp
    finally:
        sidecar.stop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global passed, failed, errors

    print(f"\n{'=' * 60}")
    print("Python Sidecar Integration Tests")
    print(f"{'=' * 60}")
    print(f"Sidecar: {SIDECAR_PATH}")
    print(f"Test CSVs: {TEST_CSVS}")
    print(f"Python: {sys.executable}")
    print()

    # Check test CSVs exist
    csv_files = [PLAY_ACTIVITY_CSV, RECENTLY_PLAYED_CSV, DAILY_TRACKS_CSV]
    for csv in csv_files:
        status = "[OK]" if csv.exists() else "[MISSING]"
        print(f"  {status} {csv.name}")
    print()

    # Run tests
    test_funcs = [
        test_ping,
        test_analyze_play_activity,
        test_analyze_recently_played,
        test_analyze_daily_tracks,
        test_preview_play_activity,
        test_preview_recently_played,
        test_load_csv,
        test_settings,
        test_unknown_action,
        test_search_without_csv,
        test_export_without_tracks,
        test_initialize,
        test_database_status,
    ]

    for func in test_funcs:
        func()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"  - {err}")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
