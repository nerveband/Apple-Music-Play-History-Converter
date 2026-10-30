#!/usr/bin/env python3
"""Deterministic retry-rate-limited tests for SidecarHandler."""

import asyncio
import tempfile
import threading
import time
from pathlib import Path

from sidecar import SidecarHandler, normalize_tracks


passed = 0
failed = 0
errors = []


def sidecar_test(name):
    """Decorator for simple script-style tests."""
    def decorator(func):
        def wrapper():
            global passed, failed
            try:
                func()
                passed += 1
                print(f"  [OK] {name}")
            except AssertionError as exc:
                failed += 1
                errors.append(f"{name}: {exc}")
                print(f"  [FAIL] {name}: {exc}")
            except Exception as exc:  # noqa: BLE001 - script-style reporting
                failed += 1
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
        return wrapper
    return decorator


def make_handler() -> SidecarHandler:
    """Create handler with temp progress path to avoid user file pollution."""
    handler = SidecarHandler()
    tmp_dir = Path(tempfile.mkdtemp(prefix="sidecar-retry-tests-"))
    handler.progress_file = tmp_dir / "progress.json"
    return handler


class FakeMusicService:
    """Minimal async service stub for _run_search tests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def search_song(self, song_name, artist_name=None, album_name=None, isrc=None):
        self.calls.append({
            "song_name": song_name,
            "artist_name": artist_name,
            "album_name": album_name,
            "isrc": isrc,
        })
        if not self.responses:
            return {"success": False, "error": "No more fake responses"}
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@sidecar_test("retry_rate_limited passes retry subset + original index mapping to start_search")
def test_retry_passes_subset_and_index_mapping():
    handler = make_handler()
    a = {"artist": "A", "track": "One", "_found": True, "_rate_limited": False, "_error": ""}
    b = {"artist": "B", "track": "Two", "_found": False, "_rate_limited": True, "_error": "403"}
    c = {"artist": "C", "track": "Three", "_found": True, "_rate_limited": False, "_error": ""}
    d = {"artist": "D", "track": "Four", "_found": False, "_rate_limited": True, "_error": "rate"}
    handler.current_tracks = [a, b, c, d]

    captured = {}

    def fake_start_search(provider, **kwargs):
        captured["provider"] = provider
        captured["kwargs"] = kwargs

    handler.start_search = fake_start_search  # type: ignore[assignment]
    handler.retry_rate_limited("itunes")

    assert captured.get("provider") == "itunes", f"Wrong provider: {captured}"
    kwargs = captured.get("kwargs", {})
    assert "run_tracks" in kwargs, f"Expected run_tracks in kwargs, got: {kwargs}"
    assert "run_indices" in kwargs, f"Expected run_indices in kwargs, got: {kwargs}"

    run_tracks = kwargs["run_tracks"]
    run_indices = kwargs["run_indices"]
    assert run_tracks == [b, d], f"Unexpected run tracks: {run_tracks}"
    assert run_indices == [1, 3], f"Unexpected run indices: {run_indices}"

    # Non-rate-limited rows must remain untouched
    assert a["_found"] is True and a["_rate_limited"] is False, f"Track A mutated: {a}"
    assert c["_found"] is True and c["_rate_limited"] is False, f"Track C mutated: {c}"

    # Retried rows should be reset before retry
    assert b["_found"] is False and b["_rate_limited"] is False and b["_error"] == "", f"Track B not reset: {b}"
    assert d["_found"] is False and d["_rate_limited"] is False and d["_error"] == "", f"Track D not reset: {d}"


@sidecar_test("retry _run_search emits original indexes and keeps counters scoped to retry subset")
def test_run_search_retry_indices_and_counters():
    handler = make_handler()

    track0 = {"artist": "A", "track": "One", "album": "", "_found": True, "_rate_limited": False, "_source": "mb", "_error": ""}
    track1 = {"artist": "B", "track": "Two", "album": "", "_found": False, "_rate_limited": True, "_source": "", "_error": "403"}
    track2 = {"artist": "C", "track": "Three", "album": "", "_found": True, "_rate_limited": False, "_source": "mb", "_error": ""}
    track3 = {"artist": "D", "track": "Four", "album": "", "_found": False, "_rate_limited": True, "_source": "", "_error": "403"}
    handler.current_tracks = [track0, track1, track2, track3]
    handler.rate_limited_tracks = []

    messages = []
    handler.send_message = lambda msg: messages.append(msg)  # type: ignore[assignment]
    handler.send_log = lambda message, level="info": None  # type: ignore[assignment]

    handler.music_service = FakeMusicService([
        {"success": True, "source": "itunes", "artist": "B2", "album": "AB"},
        {"success": False, "error": "403 rate limit"},
    ])

    retry_tracks = [track1, track3]
    retry_indices = [1, 3]
    asyncio.run(
        handler._run_search(  # type: ignore[call-arg]
            provider="itunes",
            start_index=0,
            found=0,
            missing=0,
            rate_limited=0,
            resumed_elapsed=0.0,
            run_tracks=retry_tracks,
            run_indices=retry_indices,
        )
    )

    track_results = [m for m in messages if m.get("type") == "trackResult"]
    assert [m["index"] for m in track_results] == [1, 3], f"Unexpected trackResult indexes: {track_results}"

    complete = [m for m in messages if m.get("type") == "searchComplete"]
    assert len(complete) == 1, f"Expected one searchComplete, got: {complete}"
    summary = complete[0]
    assert summary["total"] == 2, f"Retry total should be subset size, got: {summary}"
    assert summary["found"] == 1, f"Retry found should be 1, got: {summary}"
    assert summary["missing"] == 0, f"Retry missing should be 0, got: {summary}"
    assert summary["rateLimited"] == 1, f"Retry rateLimited should be 1, got: {summary}"

    # Non-subset tracks must not change.
    assert track0["_found"] is True and track0["_rate_limited"] is False, f"Track 0 mutated: {track0}"
    assert track2["_found"] is True and track2["_rate_limited"] is False, f"Track 2 mutated: {track2}"


@sidecar_test("skip_rate_limit_wait interrupts active wait callback quickly")
def test_skip_rate_limit_wait_interrupts_wait_callback():
    handler = make_handler()
    messages = []
    handler.send_message = lambda msg: messages.append(msg)  # type: ignore[assignment]
    handler.send_log = lambda message, level="info": None  # type: ignore[assignment]

    start = time.time()

    waiter = threading.Thread(target=lambda: handler._on_rate_limit_wait(5), daemon=True)  # type: ignore[attr-defined]
    waiter.start()
    time.sleep(0.2)
    handler.skip_rate_limit_wait()  # type: ignore[attr-defined]
    waiter.join(timeout=1.5)
    elapsed = time.time() - start

    assert not waiter.is_alive(), "Rate-limit wait callback should have exited after skip signal"
    assert elapsed < 2.0, f"Skip should interrupt quickly, elapsed={elapsed:.2f}s"

    wait_events = [m for m in messages if m.get("type") == "rateLimitWait"]
    assert wait_events, f"Expected rateLimitWait messages, got: {messages}"
    assert any(m.get("active") is True for m in wait_events), f"Missing active=true event: {wait_events}"
    assert any(m.get("active") is False for m in wait_events), f"Missing active=false event: {wait_events}"


@sidecar_test("retry_missing passes missing-only subset + original indexes")
def test_retry_missing_passes_subset_and_indices():
    handler = make_handler()
    a = {"artist": "A", "track": "One", "_found": True, "_rate_limited": False, "_error": ""}
    b = {"artist": "B", "track": "Two", "_found": False, "_rate_limited": False, "_error": "No match"}
    c = {"artist": "C", "track": "Three", "_found": False, "_rate_limited": True, "_error": "403"}
    d = {"artist": "D", "track": "Four", "_found": False, "_rate_limited": False, "_error": "No match"}
    handler.current_tracks = [a, b, c, d]

    captured = {}

    def fake_start_search(provider, **kwargs):
        captured["provider"] = provider
        captured["kwargs"] = kwargs

    handler.start_search = fake_start_search  # type: ignore[assignment]
    handler.retry_missing("musicbrainz_api")  # type: ignore[attr-defined]

    assert captured.get("provider") == "musicbrainz_api", f"Wrong provider: {captured}"
    kwargs = captured.get("kwargs", {})
    assert kwargs.get("run_tracks") == [b, d], f"Expected only missing non-rate-limited tracks: {kwargs}"
    assert kwargs.get("run_indices") == [1, 3], f"Expected original indexes [1, 3], got: {kwargs}"
    assert b["_error"] == "" and d["_error"] == "", f"Missing errors should be reset: {b}, {d}"
    assert a["_found"] is True and c["_rate_limited"] is True, f"Non-missing tracks mutated: {a}, {c}"


@sidecar_test("unknown CSV mapping infers artist/track/album/timestamp/duration/isrc")
def test_unknown_csv_mapping_inference():
    raw_rows = [{
        "Performer Name": "Test Artist",
        "Song Title": "Test Track",
        "Record Name": "Test Album",
        "Played At": "2026-02-14T12:00:00Z",
        "ms_played": "183000",
        "Recording ISRC Code": "usrc17607839",
    }]

    normalized = normalize_tracks(raw_rows, "Unknown")
    assert len(normalized) == 1, f"Unexpected row count: {normalized}"
    row = normalized[0]
    assert row["artist"] == "Test Artist", f"Artist not inferred: {row}"
    assert row["track"] == "Test Track", f"Track not inferred: {row}"
    assert row["album"] == "Test Album", f"Album not inferred: {row}"
    assert row["timestamp"] == "2026-02-14T12:00:00Z", f"Timestamp not inferred: {row}"
    assert row["duration"] == 183.0, f"Duration not inferred as seconds: {row}"
    assert row["isrc"] == "USRC17607839", f"ISRC not normalized: {row}"


@sidecar_test("preview edits are applied during load_csv for matching file path")
def test_preview_edits_applied_on_load_csv():
    handler = make_handler()
    tmp_dir = Path(tempfile.mkdtemp(prefix="sidecar-preview-edits-"))
    csv_path = tmp_dir / "generic.csv"
    csv_path.write_text(
        "Performer Name,Song Title,Record Name,Played At,ms_played\n"
        "A,Song A,Album A,2026-02-14T00:00:00Z,120000\n",
        encoding="utf-8",
    )

    handler.set_preview_edits(  # type: ignore[attr-defined]
        str(csv_path),
        [{
            "index": 0,
            "artist": "Edited Artist",
            "track": "Edited Track",
            "album": "Edited Album",
        }]
    )
    loaded = handler.load_csv(str(csv_path))
    assert loaded is True, "CSV should load successfully"
    assert handler.current_tracks[0]["artist"] == "Edited Artist", f"Artist edit not applied: {handler.current_tracks[0]}"
    assert handler.current_tracks[0]["track"] == "Edited Track", f"Track edit not applied: {handler.current_tracks[0]}"
    assert handler.current_tracks[0]["album"] == "Edited Album", f"Album edit not applied: {handler.current_tracks[0]}"


@sidecar_test("transient search failures use backoff retries before succeeding")
def test_search_with_backoff_retries_transient_errors():
    handler = make_handler()
    handler.music_service = FakeMusicService([
        {"success": False, "error": "Network error: timeout"},
        {"success": True, "source": "musicbrainz_api", "artist": "Recovered Artist", "album": "Recovered Album"},
    ])

    sleep_calls = []

    async def fake_interruptible_sleep(seconds: float, allow_skip: bool = False):
        sleep_calls.append(seconds)
        return True, False

    handler._interruptible_sleep = fake_interruptible_sleep  # type: ignore[assignment]
    result = asyncio.run(  # type: ignore[attr-defined]
        handler._search_with_backoff(  # type: ignore[attr-defined]
            song_name="Test Song",
            artist_name="Test Artist",
            album_name=None,
            isrc=None,
            timeout_seconds=15.0,
        )
    )
    assert result.get("success") is True, f"Expected retry success: {result}"
    assert sleep_calls == [2.0], f"Expected one backoff sleep of 2s: {sleep_calls}"


def run_search_with_responses(tracks, responses):
    """Run _run_search over tracks with fake responses. Return (service, messages)."""
    handler = make_handler()
    handler.current_tracks = tracks
    messages = []
    handler.send_message = lambda msg: messages.append(msg)  # type: ignore[assignment]
    handler.send_log = lambda message, level="info": None  # type: ignore[assignment]
    handler.music_service = FakeMusicService(responses)
    asyncio.run(handler._run_search(provider="itunes"))  # type: ignore[call-arg]
    return handler.music_service, messages


@sidecar_test("duplicate tracks are searched once and the result is reused")
def test_run_search_reuses_result_for_duplicate_tracks():
    tracks = [
        {"artist": "A", "track": "One", "album": "X"},
        {"artist": "B", "track": "Two", "album": ""},
        {"artist": "A", "track": "One", "album": "X"},
        {"artist": "B", "track": "Two", "album": ""},
    ]
    service, messages = run_search_with_responses(tracks, [
        {"success": True, "source": "itunes", "artist": "A2", "album": "X2"},
        {"success": False, "error": "No match found"},
    ])

    assert len(service.calls) == 2, f"Expected 2 searches, got: {service.calls}"
    track_results = [m for m in messages if m.get("type") == "trackResult"]
    assert [m["index"] for m in track_results] == [0, 1, 2, 3], f"Unexpected trackResults: {track_results}"
    assert tracks[2]["_found"] is True and tracks[2]["artist"] == "A2", f"Duplicate not filled: {tracks[2]}"
    assert tracks[3]["_found"] is False, f"Duplicate miss not filled: {tracks[3]}"
    summary = [m for m in messages if m.get("type") == "searchComplete"][0]
    assert summary["found"] == 2 and summary["missing"] == 2, f"Unexpected summary: {summary}"


@sidecar_test("rate-limited results are not reused for duplicate tracks")
def test_run_search_does_not_reuse_rate_limited_result():
    tracks = [
        {"artist": "A", "track": "One", "album": ""},
        {"artist": "A", "track": "One", "album": ""},
    ]
    service, messages = run_search_with_responses(tracks, [
        {"success": False, "error": "403 rate limit"},
        {"success": True, "source": "itunes", "artist": "A2", "album": ""},
    ])

    assert len(service.calls) == 2, f"Expected 2 searches, got: {service.calls}"
    summary = [m for m in messages if m.get("type") == "searchComplete"][0]
    assert summary["found"] == 1 and summary["rateLimited"] == 1, f"Unexpected summary: {summary}"


def main():
    """Run retry tests."""
    global passed, failed, errors
    print("=" * 60)
    print("Python Sidecar Retry Tests")
    print("=" * 60)
    print()

    tests = [
        test_retry_passes_subset_and_index_mapping,
        test_run_search_retry_indices_and_counters,
        test_skip_rate_limit_wait_interrupts_wait_callback,
        test_retry_missing_passes_subset_and_indices,
        test_unknown_csv_mapping_inference,
        test_preview_edits_applied_on_load_csv,
        test_search_with_backoff_retries_transient_errors,
        test_run_search_reuses_result_for_duplicate_tracks,
        test_run_search_does_not_reuse_rate_limited_result,
    ]

    for test in tests:
        test()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if errors:
        print("Failures:")
        for err in errors:
            print(f"  - {err}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
