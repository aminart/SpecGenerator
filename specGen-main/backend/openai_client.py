from __future__ import annotations

import httpx
from openai import OpenAI

from settings_store import EffectiveSettings, get_effective_settings


def get_missing_settings() -> list[str]:
    return get_effective_settings().missing


def is_custom_configured() -> bool:
    return get_effective_settings().configured


def get_model_name() -> str:
    return get_effective_settings().model


def build_client(settings: EffectiveSettings, timeout_seconds: float | None = None) -> OpenAI:
    timeout = timeout_seconds if timeout_seconds is not None else settings.timeout
    http_client = httpx.Client(
        verify=settings.ca_bundle or True,
        timeout=httpx.Timeout(timeout, connect=min(30.0, timeout)),
    )
    return OpenAI(base_url=settings.api_base, api_key=settings.api_key, http_client=http_client)


def get_openai_client() -> OpenAI:
    settings = get_effective_settings()
    if not settings.configured:
        raise RuntimeError(f"Paramètres de connexion incomplets : {', '.join(settings.missing)}")
    return build_client(settings)
