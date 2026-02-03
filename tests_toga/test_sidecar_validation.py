from pathlib import Path
import sys

SIDE_CAR_DIR = Path(__file__).resolve().parents[1] / "tauri-app" / "python-sidecar"
sys.path.insert(0, str(SIDE_CAR_DIR))

from tauri_app_python_sidecar_stub import validate_csv_headers


def test_invalid_csv_headers(tmp_path: Path):
    csv = tmp_path / "bad.csv"
    csv.write_text("NotAHeader\n1,2\n", encoding="utf-8")
    ok, err = validate_csv_headers(csv)
    assert ok is False
    assert "Unknown CSV format" in err
