"""Connection and model set in Studio Dock (Réglages › Modèles d'IA), shared by all the apps of the suite."""
from __future__ import annotations

import base64
import json
import shutil

import pytest

import settings_store
import studiodock_ia


def write(choice=None, apps=None):
    folder = studiodock_ia.dossier()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "connexions.json").write_text(json.dumps({
        "format": 1,
        "connections": [
            {"id": "sd1", "name": "Passerelle", "provider": "openai", "api_base": "https://llm.interne/v1",
             "api_key": {"scheme": "plain", "data": base64.b64encode(b"sk-dock-ABCD1234").decode()},
             "models": ["mistral-large", "mistral-small"]},
            {"id": "sd2", "name": "Ollama (ce poste)", "provider": "ollama", "api_base": "http://localhost:11434/v1",
             "models": ["qwen3:8b"], "context_tokens": 4096},
        ],
        "default": choice, "apps": apps or {},
    }), encoding="utf-8")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    shutil.rmtree(studiodock_ia.dossier(), ignore_errors=True)
    settings_store.clear_settings()
    yield
    shutil.rmtree(studiodock_ia.dossier(), ignore_errors=True)
    settings_store.clear_settings()


def test_studio_dock_provides_the_connection():
    settings_store.save_settings("https://own.example/v1", "sk-own", "own-model", 300)
    write({"connection": "sd1", "model": "mistral-small"}, {"specgen": {"connection": "sd2", "model": "qwen3:8b"}})
    effective = settings_store.get_effective_settings()
    assert (effective.source, effective.api_base, effective.model) == ("studiodock", "http://localhost:11434/v1", "qwen3:8b")
    assert effective.configured  # no key nor certificate needed for Ollama
    public = settings_store.public_settings()
    assert public["source"] == "studiodock" and public["studiodock"] == {"name": "Ollama (ce poste)", "local": True}
    assert public["model"] == "qwen3:8b" and public["configured"]

    # Saving from this screen keeps the own connection, only the options change
    settings_store.save_settings("https://ignored/v1", "ignored", "ignored", 450, True)
    saved = settings_store.load_saved()
    assert (saved["api_base"], saved["model"], saved["timeout"]) == ("https://own.example/v1", "own-model", 450)
    assert settings_store.saved_api_key() == "sk-own"


def test_default_model_with_key():
    write({"connection": "sd1", "model": "mistral-small"})
    effective = settings_store.get_effective_settings()
    assert (effective.api_key, effective.model, effective.ca_bundle) == ("sk-dock-ABCD1234", "mistral-small", "")
    assert "sk-dock" not in json.dumps(settings_store.public_settings())


def test_own_configuration_and_env_win(monkeypatch):
    settings_store.save_settings("https://own.example/v1", "sk-own", "own-model", 300)
    write({"connection": "sd1", "model": "mistral-small"}, {"specgen": {"own": True}})
    assert settings_store.get_effective_settings().source == "app"
    assert settings_store.public_settings()["studiodock_own"]

    write({"connection": "sd1", "model": "mistral-small"})
    monkeypatch.setenv("CUSTOM_API_BASE", "https://env.example/v1")
    effective = settings_store.get_effective_settings()
    assert (effective.source, effective.api_base) == ("app", "https://env.example/v1")


def test_connection_test_uses_studio_dock(client, monkeypatch):
    write({"connection": "sd1", "model": "mistral-small"})
    seen = {}

    class Fake:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            seen.update(kwargs)
            return None

    import settings_api

    monkeypatch.setattr(settings_api, "build_client", lambda candidate, timeout_seconds=None: seen.setdefault("base", candidate.api_base) and Fake())
    monkeypatch.setattr(settings_api, "run_capability_checks", lambda candidate: [])
    result = client.post("/api/settings/test", json={"api_base": "", "model": "x"}).json()
    assert result["ok"] and seen["model"] == "mistral-small" and seen["base"] == "https://llm.interne/v1"
    assert client.get("/api/settings").json()["last_test"]["ok"]
    assert settings_store.load_saved().get("last_test") is None  # the own test is left untouched


def test_model_picked_at_launch_and_default_in_settings(client, fake_llm, login_screen):
    write({"connection": "sd1", "model": "mistral-small"})
    options = client.get("/api/settings/models").json()
    assert options["available"] and options["default"] == "sd1|mistral-small"
    assert [o["id"] for o in options["options"]] == ["sd1|mistral-large", "sd1|mistral-small", "sd2|qwen3:8b"]

    # Default chosen in SpecGen's settings, then back to the one of Studio Dock
    assert client.put("/api/settings/models", json={"model": "sd2|qwen3:8b"}).json()["default"] == "sd2|qwen3:8b"
    assert settings_store.get_effective_settings().api_base == "http://localhost:11434/v1"
    assert client.put("/api/settings/models", json={"model": "sd9|absent"}).status_code == 422
    client.put("/api/settings/models", json={"model": "sd2|qwen3:8b"})

    # One generation with another model: the header reaches every call to the AI
    from conftest import GOOD_SPEC_FR

    fake_llm.queue(GOOD_SPEC_FR)
    r = client.post("/api/spec/generate", json={"spec_json": login_screen, "business_context": ""},
                    headers={"X-StudioDock-Model": "sd1|mistral-large"})
    assert r.status_code == 200, r.text
    assert {call["model"] for call in fake_llm.calls} == {"mistral-large"}
    # Without the header: the default model again
    assert settings_store.get_effective_settings().model == "qwen3:8b"
    client.put("/api/settings/models", json={"model": None})
    assert settings_store.get_effective_settings().model == "mistral-small"


def test_no_choice_without_studio_dock(client):
    assert client.get("/api/settings/models").json() == {
        "available": False, "default": None, "saved_default": None, "studiodock_default": None, "options": []}
