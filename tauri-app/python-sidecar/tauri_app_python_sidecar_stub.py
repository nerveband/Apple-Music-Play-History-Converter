from csv_validation import validate_csv_headers


def apply_settings(state: dict, settings: dict) -> dict:
    state.update(settings)
    return state


__all__ = ["validate_csv_headers", "apply_settings"]
