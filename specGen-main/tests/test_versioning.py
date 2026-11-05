"""Versionnement : un seul numéro (VERSION), repris partout, et un script de montée de version fiable."""
import datetime as dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

import app_info

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _bump_module():
    spec = importlib.util.spec_from_file_location("bump_version", ROOT / "scripts" / "bump_version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_file_is_semver():
    assert SEMVER.match((ROOT / "VERSION").read_text(encoding="utf-8").strip())


def test_backend_reads_the_version_file():
    assert app_info.VERSION == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_frontend_package_has_the_same_version():
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == app_info.VERSION


def test_changelog_lists_the_current_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Non publié]" in changelog
    assert f"## [{app_info.VERSION}]" in changelog


@pytest.mark.parametrize(
    ("wanted", "expected"),
    [("patch", "1.4.3"), ("minor", "1.5.0"), ("major", "2.0.0"), ("1.10.0", "1.10.0")],
)
def test_next_version(wanted, expected):
    assert _bump_module().next_version("1.4.2", wanted) == expected


@pytest.mark.parametrize("wanted", ["1.4.2", "1.3.9", "v1.5.0", "1.5"])
def test_next_version_refuses_bad_numbers(wanted):
    with pytest.raises(SystemExit):
        _bump_module().next_version("1.4.2", wanted)


def test_bump_dates_the_unreleased_section(tmp_path, monkeypatch):
    bump = _bump_module()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Historique\n\n## [Non publié]\n\n### Corrigé\n\n- Un bug\n\n## [1.0.0] — référence\n", encoding="utf-8")
    monkeypatch.setattr(bump, "CHANGELOG", changelog)
    bump.update_changelog("1.0.1", dt.date(2026, 11, 5))
    text = changelog.read_text(encoding="utf-8")
    assert "## [Non publié]\n\n## [1.0.1] — 2026-11-05\n\n### Corrigé\n\n- Un bug" in text
    assert "## [1.0.0] — référence" in text


def test_bump_refuses_an_empty_unreleased_section(tmp_path, monkeypatch):
    bump = _bump_module()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Historique\n\n## [Non publié]\n\n## [1.0.0] — référence\n", encoding="utf-8")
    monkeypatch.setattr(bump, "CHANGELOG", changelog)
    with pytest.raises(SystemExit):
        bump.update_changelog("1.0.1", dt.date(2026, 11, 5))
