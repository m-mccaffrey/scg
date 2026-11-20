"""Per-installation user settings, saved as JSON next to the application.

settings.json is not part of the distributed package, so updates leave it alone.
"""

import json
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
DEFAULT_DATABASE = os.path.join(APP_DIR, "SciGlass.db")


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def get_database_path() -> str:
    """The saved database if it still exists, otherwise SciGlass.db in the app folder."""
    path = load_settings().get("database_path")
    if path and os.path.isfile(path):
        return path
    return DEFAULT_DATABASE


def set_database_path(path: str) -> None:
    data = load_settings()
    data["database_path"] = os.path.abspath(path)
    save_settings(data)
