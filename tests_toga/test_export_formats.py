import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import apple_music_history_converter.export_formats as export_formats


def test_export_itunes_xml(tmp_path):
    tracks = [{"artist": "A", "track": "T", "album": "AL", "timestamp": "2024-01-01 10:00:00"}]
    out = tmp_path / "out.xml"
    assert export_formats.export_tracks("itunes_xml", tracks, str(out)) is True
    xml = out.read_text(encoding="utf-8")
    assert "plist" in xml
