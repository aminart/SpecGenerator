import json
from pathlib import Path

import pytest

from conftest import GOOD_SPEC_FR


@pytest.fixture
def log_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("SPECGEN_CONFIG_DIR", str(tmp_path))
    return Path(tmp_path) / "journal"


def test_no_journal_by_default(fake_llm, client, login_screen, log_dir):
    fake_llm.queue(GOOD_SPEC_FR)
    client.post("/api/spec/generate", json={"spec_json": login_screen})
    assert not log_dir.exists()


def test_journal_holds_every_call_and_the_result(fake_llm, client, login_screen, log_dir, monkeypatch):
    monkeypatch.setenv("CUSTOM_GENERATION_LOG", "1")
    bad = GOOD_SPEC_FR.replace("## Questions ouvertes\n", "")
    fake_llm.queue(bad, GOOD_SPEC_FR)
    client.post("/api/spec/generate", json={"spec_json": login_screen})
    (path,) = log_dir.glob("*_spec.json")
    journal = json.loads(path.read_text(encoding="utf-8"))
    assert journal["kind"] == "spec" and journal["request"]["language"] == "fr"
    assert [call["answer"] for call in journal["calls"]] == [bad, GOOD_SPEC_FR]
    assert journal["calls"][0]["options"]["temperature"] == 0.15
    assert journal["calls"][1]["messages"][-1]["content"].startswith("Le document présente les problèmes")
    assert journal["result"]["corrected"] is True and journal["result"]["warnings"] == []


def test_journal_is_written_on_failure(fake_llm, client, login_screen, log_dir, monkeypatch):
    monkeypatch.setenv("CUSTOM_GENERATION_LOG", "1")
    fake_llm.queue(RuntimeError("service down"))
    assert client.post("/api/spec/generate", json={"spec_json": login_screen}).status_code == 500
    (path,) = log_dir.glob("*_spec.json")
    journal = json.loads(path.read_text(encoding="utf-8"))
    assert journal["calls"][0]["error"] == "RuntimeError: service down"
    assert "error" in journal["result"]


def test_journal_setting_is_saved(client, log_dir):
    form = {"api_base": "https://ia.example/v1", "api_key": "secret-key-1234", "model": "mistral-small", "timeout": 300}
    assert client.put("/api/settings", json={**form, "generation_log": True}).json()["generation_log"] is True
    assert client.get("/api/settings").json()["generation_log_dir"] == str(log_dir)
