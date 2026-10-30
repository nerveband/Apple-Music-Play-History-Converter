import importlib.util
import json
import pathlib
import tempfile


def _load_export_formats():
    sidecar_path = pathlib.Path(__file__).parent / "sidecar.py"
    spec = importlib.util.spec_from_file_location("sidecar_module", sidecar_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.export_formats


def test_listenbrainz_export_skips_rows_without_valid_timestamp():
    export_formats = _load_export_formats()
    tracks = [
        {"artist": "A", "track": "Valid", "album": "X", "timestamp": "2025-01-01T00:00:00Z"},
        {"artist": "B", "track": "Bad", "album": "", "timestamp": "not a date"},
        {"artist": "C", "track": "Empty", "album": "", "timestamp": ""},
        {"artist": "D", "track": "Too old", "album": "", "timestamp": "1999-01-01T00:00:00Z"},
    ]
    output_path = pathlib.Path(tempfile.mkdtemp()) / "listens.json"

    assert export_formats.export_listenbrainz_json(tracks, str(output_path)) is True

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert [d["track_metadata"]["track_name"] for d in data] == ["Valid"]
    assert data[0]["listened_at"] == 1735689600
