from types import SimpleNamespace

import httpx
from openai import BadRequestError

import settings_api


def bad_request(message="rejected"):
    return BadRequestError(message, response=httpx.Response(400, request=httpx.Request("POST", "http://test")), body=None)


class Service:
    """A model service with limits: max output tokens, JSON mode support, max prompt size."""

    def __init__(self, max_tokens=100_000, json_mode=True, max_prompt=10**9):
        self.max_tokens, self.json_mode, self.max_prompt = max_tokens, json_mode, max_prompt
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        if request.get("max_tokens", 0) > self.max_tokens:
            raise bad_request("max_tokens too large")
        if "response_format" in request and not self.json_mode:
            raise bad_request("response_format unsupported")
        if len(request["messages"][-1]["content"]) > self.max_prompt:
            raise bad_request("context length exceeded")
        content = '{"ok": true}' if "response_format" in request else "OK"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")])


def run(monkeypatch, service):
    monkeypatch.setattr(settings_api, "build_client", lambda *args, **kwargs: service)
    return {check["name"]: check for check in settings_api.run_capability_checks(SimpleNamespace(model="mistral-small"))}


def test_everything_supported(monkeypatch):
    checks = run(monkeypatch, Service())
    assert all(check["ok"] for check in checks.values())
    assert checks["Taille de prompt"]["message"].startswith("180\u202f000 caractères acceptés")


def test_limits_are_reported_with_advice(monkeypatch):
    checks = run(monkeypatch, Service(max_tokens=8000, json_mode=False, max_prompt=100_000))
    assert not checks["Longueur de réponse"]["ok"] and "CUSTOM_MAX_OUTPUT_TOKENS" in checks["Longueur de réponse"]["message"]
    assert not checks["Mode JSON"]["ok"]
    size = checks["Taille de prompt"]
    assert not size["ok"] and "180\u202f000 caractères refusés, 90\u202f000 acceptés" in size["message"]
