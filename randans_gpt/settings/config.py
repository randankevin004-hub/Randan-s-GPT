"""
settings/config.py
------------------
Persistent user settings (a small JSON file in %APPDATA%\\RandansGPT) plus path
helpers that keep working when the app is frozen into an .exe by PyInstaller.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

APP_NAME = "Randan's GPT"
APP_VERSION = "1.0"


def app_data_dir() -> Path:
    """Folder where the database, settings and log file live."""
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "RandansGPT"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> str:
    """Absolute path to a bundled resource (works in dev and in PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / relative)


# Every setting the app knows about, with its default value.
DEFAULTS: dict = {
    "default_model": "llama3.2:1b",
    "known_models": [],          # extra models seen in Ollama (so the list works offline)
    "auto_mode": False,          # start the app in Auto routing mode
    "theme": "Dark",             # "Dark" or "Light"
    "font_size": 14,             # chat font size in points
    "memory_enabled": True,
    "user_name": "Kevin",        # shown in the greeting and profile
    "avatar_path": "",           # profile picture (copied into the data folder)
    "member_since": "",          # set on first launch
    "onboarded": False,          # first-run setup wizard finished?
    "route_map": {},             # category -> model tag chosen in the wizard
    "use_cases": [],
    "perf_pref": "balanced",     # speed | balanced | quality
    "auto_preview": True,        # open the live preview when the AI writes a web page
    "reduce_effects": False,     # HTML UI: turn off blur / animations (older GPUs)
    "mcp_confirm": True,         # ask before every MCP tool call
    "show_history": True,        # right-hand history panel
    # Low-resource tuning knobs (not shown in the UI):
    "num_ctx": 2048,             # context window; smaller = less RAM
    "history_messages": 10,      # how many past messages are sent to the model
    "temperature": 0.7,
}


class Settings:
    """Dictionary-like settings store that saves itself on every change."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else app_data_dir() / "settings.json"
        self._data: dict = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                for key in DEFAULTS:
                    if key in stored:
                        self._data[key] = stored[key]
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError):
            logging.warning("Could not read settings file; using defaults.")
        self._sanitize()

    def _sanitize(self) -> None:
        """Repair hand-edited or corrupted values."""
        if self._data["theme"] not in ("Dark", "Light"):
            self._data["theme"] = "Dark"
        try:
            self._data["font_size"] = min(24, max(10, int(self._data["font_size"])))
        except (TypeError, ValueError):
            self._data["font_size"] = DEFAULTS["font_size"]

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._sanitize()
        self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            tmp.replace(self.path)
        except OSError:
            logging.exception("Could not save settings")
