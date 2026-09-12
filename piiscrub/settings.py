"""Tiny persisted user preferences (sensitivity, always-redact list).

No UI code here, same reasoning as core.py: stays testable on its own.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import core

DEFAULTS: dict = {
    "threshold": core.DEFAULT_THRESHOLD,
    "extra_terms": "",
    "enabled_entities": {entity: True for entity in core.supported_entities()},
    "theme_mode": "system",
    "auto_scan": True,
}


def default_path() -> Path:
    return Path.home() / ".piiscrub" / "settings.json"


def load(path: Path) -> dict:
    """Read saved settings, falling back to DEFAULTS if missing or corrupt.

    An entity type absent from the saved file - because it didn't exist yet
    when the file was written - defaults to enabled rather than disabled, so
    a newly added detector isn't silently turned off for existing users.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {**DEFAULTS, "enabled_entities": dict(DEFAULTS["enabled_entities"])}
    merged = {**DEFAULTS, **data}
    merged["enabled_entities"] = {
        **DEFAULTS["enabled_entities"], **data.get("enabled_entities", {})
    }
    return merged


def save(path: Path, values: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")
