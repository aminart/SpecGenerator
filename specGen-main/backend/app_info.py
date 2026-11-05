"""Identity of the app, shared by the /health route, the launcher (portal contract) and the exports.

The version number lives in ONE place: the VERSION file at the root of specGen-main (bundled into the
.exe). To publish a new version: python scripts/bump_version.py X.Y.Z (see README, « Versions »).
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_ID = "specgen"
APP_NAME = "SpecGen"
DEFAULT_PORT = 8010


def _version_file() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "VERSION"
    return Path(__file__).resolve().parent.parent / "VERSION"


def _read_version() -> str:
    try:
        return _version_file().read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


VERSION = _read_version()
