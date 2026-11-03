"""Endpoints of the connection settings screen."""
from __future__ import annotations

import ssl
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import httpx
import openai
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from openai_client import build_client
from settings_store import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    clear_settings,
    get_effective_settings,
    public_settings,
    save_settings,
    save_test_result,
    store_certificate,
)

router = APIRouter(prefix="/api/settings")

TEST_TIMEOUT_SECONDS = 30.0


class SettingsPayload(BaseModel):
    api_base: str = ""
    # None keeps the stored key.
    api_key: str | None = None
    model: str = DEFAULT_MODEL
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=1800)


@router.get("")
def read_settings() -> dict[str, Any]:
    return public_settings()


@router.put("")
def update_settings(payload: SettingsPayload) -> dict[str, Any]:
    save_settings(payload.api_base, payload.api_key, payload.model, payload.timeout)
    return public_settings()


@router.delete("")
def delete_settings() -> dict[str, Any]:
    clear_settings()
    return public_settings()


@router.post("/certificate")
def upload_certificate(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        store_certificate(file.filename or "certificat.crt", file.file.read())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return public_settings()


def _is_certificate_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(current):
            return True
        current = current.__cause__ or current.__context__
    return False


def _failure(field: str | None, title: str, message: str) -> dict[str, Any]:
    return {"ok": False, "field": field, "title": title, "message": message}


def _diagnose(exc: Exception) -> dict[str, Any]:
    if _is_certificate_error(exc):
        return _failure(
            "certificate",
            "Échec de la connexion : certificat non reconnu",
            "Le serveur a été joint, mais la connexion sécurisée a été refusée. Vérifiez que le fichier .crt est bien celui fourni par votre service informatique.",
        )
    if isinstance(exc, openai.APITimeoutError):
        return _failure("api_base", "Échec de la connexion : délai dépassé", "Le service n’a pas répondu à temps. Vérifiez l’URL et votre accès au réseau de l’entreprise.")
    if isinstance(exc, openai.APIConnectionError):
        return _failure("api_base", "Échec de la connexion : serveur injoignable", "Impossible de joindre le service. Vérifiez l’URL et votre accès au réseau de l’entreprise (VPN).")
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return _failure("api_key", "Échec de la connexion : clé API refusée", "Le service a refusé la clé API. Vérifiez qu’elle a été copiée en entier et qu’elle est toujours valide.")
    if isinstance(exc, openai.NotFoundError):
        return _failure("api_base", "Échec de la connexion : adresse ou modèle introuvable", "Le service répond, mais l’URL ou le modèle demandé n’existe pas. Vérifiez l’URL (elle se termine souvent par /v1) et le modèle.")
    if isinstance(exc, openai.APIStatusError):
        return _failure(None, f"Échec de la connexion : erreur {exc.status_code}", str(exc.message))
    return _failure(None, "Échec de la connexion", str(exc))


@router.post("/test")
def test_connection(payload: SettingsPayload) -> dict[str, Any]:
    """Tests the values typed in the form (not yet saved) with the stored certificate."""
    settings = get_effective_settings()
    candidate = replace(
        settings,
        api_base=settings.api_base if "api_base" in settings.env_fields else payload.api_base.strip(),
        api_key=settings.api_key if payload.api_key is None or "api_key" in settings.env_fields else payload.api_key.strip(),
        model=settings.model if "model" in settings.env_fields else (payload.model.strip() or DEFAULT_MODEL),
    )
    tested_at = datetime.now(timezone.utc).isoformat()

    if not candidate.configured:
        return {**_failure(None, "Paramètres incomplets", f"À renseigner : {', '.join(candidate.missing)}."), "at": tested_at}

    try:
        client = build_client(candidate, timeout_seconds=TEST_TIMEOUT_SECONDS)
        client.chat.completions.create(model=candidate.model, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
        result: dict[str, Any] = {"ok": True, "field": None, "title": "Connexion opérationnelle", "message": f"modèle {candidate.model}"}
    except (openai.OpenAIError, httpx.HTTPError, ssl.SSLError, OSError) as exc:
        result = _diagnose(exc)

    result.update({"at": tested_at, "model": candidate.model})
    save_test_result(result)
    return result
