from pathlib import Path
import sys

SIDE_CAR_DIR = Path(__file__).resolve().parents[1] / "tauri-app" / "python-sidecar"
sys.path.insert(0, str(SIDE_CAR_DIR))

from tauri_app_python_sidecar_stub import apply_settings


def test_sidecar_sets_itunes_country():
    state = {}
    apply_settings(state, {"itunes_country": "IT"})
    assert state["itunes_country"] == "IT"
