from pathlib import Path

KNOWN_HEADERS = [
    "Play Duration Milliseconds",
    "Date Played",
    "Play Count",
]


def validate_csv_headers(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"File not found: {path}"
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline().strip()
        if any(header in first_line for header in KNOWN_HEADERS):
            return True, ""
        return False, "Unknown CSV format"
    except Exception as e:
        return False, f"Failed to read CSV header: {e}"
