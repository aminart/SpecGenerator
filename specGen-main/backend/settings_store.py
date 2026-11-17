"""Connection settings: saved from the app, overridable by a .env file next to the app.

Studio Dock (Réglages › Modèles d'IA) can provide the connection and model for SpecGen, shared by all the apps of
the suite: read with studiodock_ia.py. Order: .env (deployment) > Studio Dock > settings saved in this app.

The API key is encrypted with the Windows user account (DPAPI) before being
written to disk; it is never sent back to the frontend in clear.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from dotenv import load_dotenv

import studiodock_ia
from app_paths import config_dir, env_file

DEFAULT_MODEL = "mistral"
DEFAULT_TIMEOUT_SECONDS = 300.0
CERTIFICATE_FILENAME = "ca.crt"

# Field name -> environment variable that overrides it.
ENV_VARIABLES = {
    "api_base": "CUSTOM_API_BASE",
    "api_key": "CUSTOM_API_KEY",
    "ca_bundle": "CUSTOM_CA_BUNDLE",
    "model": "CUSTOM_MODEL",
    "timeout": "CUSTOM_TIMEOUT_SECONDS",
}
REQUIRED_FIELDS = {"api_base": "URL du service", "api_key": "Clé API", "ca_bundle": "Certificat de l’entreprise"}
STUDIODOCK_APP_ID = "specgen"  # SpecGen's id in the Studio Dock catalogue
# Variables that, when set, make the .env the source of the connection (Studio Dock is then ignored)
CONNECTION_VARIABLES = ("CUSTOM_API_BASE", "CUSTOM_API_KEY", "CUSTOM_MODEL")

load_dotenv(env_file())


@dataclass
class EffectiveSettings:
    api_base: str
    api_key: str
    ca_bundle: str
    model: str
    timeout: float
    env_fields: list[str]
    source: str = "app"  # "app" (this screen and .env) or "studiodock"
    studiodock_name: str = ""  # Studio Dock: name of the connection

    @property
    def missing(self) -> list[str]:
        if self.source == "studiodock":
            # Studio Dock already tested its connection: key and certificate depend on the service (none for Ollama)
            return [] if self.api_base else [REQUIRED_FIELDS["api_base"]]
        return [label for field, label in REQUIRED_FIELDS.items() if not getattr(self, field)]

    @property
    def configured(self) -> bool:
        return not self.missing


# --- API key encryption -------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data: bytes) -> tuple[_DataBlob, Any]:
        buffer = ctypes.create_string_buffer(data, len(data))
        return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    def _dpapi(data: bytes, protect: bool) -> bytes:
        blob_in, _buffer = _blob(data)
        blob_out = _DataBlob()
        if protect:
            ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), "SpecGenerator", None, None, None, 0, ctypes.byref(blob_out))
        else:
            ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

    def _encrypt(value: str) -> dict[str, str]:
        return {"scheme": "dpapi", "data": base64.b64encode(_dpapi(value.encode("utf-8"), True)).decode("ascii")}

else:
    # Development on Linux/macOS only: no OS keystore wired, the key is merely encoded.
    def _encrypt(value: str) -> dict[str, str]:
        return {"scheme": "plain", "data": base64.b64encode(value.encode("utf-8")).decode("ascii")}


def _decrypt(stored: dict[str, str] | None) -> str:
    if not stored:
        return ""
    raw = base64.b64decode(stored["data"])
    if stored.get("scheme") == "dpapi":
        if sys.platform != "win32":
            return ""
        return _dpapi(raw, False).decode("utf-8")
    return raw.decode("utf-8")


# --- Saved settings -----------------------------------------------------------


def _config_file() -> Path:
    return config_dir() / "config.json"


def certificate_path() -> Path:
    return config_dir() / CERTIFICATE_FILENAME


def load_saved() -> dict[str, Any]:
    try:
        return json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_saved(data: dict[str, Any]) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    _config_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def saved_api_key() -> str:
    try:
        return _decrypt(load_saved().get("api_key"))
    except OSError:
        # Encrypted by another Windows account: treat as missing.
        return ""


def save_settings(api_base: str, api_key: str | None, model: str, timeout: float, generation_log: bool = False) -> None:
    data = load_saved()
    if studiodock_choice() is not None:
        # Connection provided by Studio Dock: only the options of this screen are saved
        data.update({"timeout": timeout, "generation_log": generation_log})
        _write_saved(data)
        return
    data.update(
        {
            "api_base": api_base.strip(),
            "model": model.strip() or DEFAULT_MODEL,
            "timeout": timeout,
            "generation_log": generation_log,
        }
    )
    if api_key is not None:
        data["api_key"] = _encrypt(api_key.strip()) if api_key.strip() else None
    _write_saved(data)


def _studiodock_key(effective: EffectiveSettings) -> str:
    return f"{effective.api_base}|{effective.model}"


def _studiodock_test(saved: dict[str, Any], effective: EffectiveSettings) -> dict[str, Any] | None:
    test = saved.get("studiodock_test")
    return test.get("result") if isinstance(test, dict) and test.get("key") == _studiodock_key(effective) else None


def save_test_result(result: dict[str, Any]) -> None:
    data = load_saved()
    effective = get_effective_settings()
    if effective.source == "studiodock":
        # Kept apart: the test of this screen's own connection stays valid for later
        data["studiodock_test"] = {"key": _studiodock_key(effective), "result": result}
    else:
        data["last_test"] = result
    _write_saved(data)


def clear_settings() -> None:
    for path in (_config_file(), certificate_path()):
        path.unlink(missing_ok=True)


def store_certificate(filename: str, content: bytes) -> dict[str, Any]:
    """Validates a .crt (PEM or DER, possibly a chain) and stores it as PEM."""
    try:
        certificates = x509.load_pem_x509_certificates(content)
    except ValueError:
        try:
            certificates = [x509.load_der_x509_certificate(content)]
        except ValueError as exc:
            raise ValueError("Ce fichier n’est pas un certificat valide (.crt au format PEM ou DER attendu).") from exc

    config_dir().mkdir(parents=True, exist_ok=True)
    certificate_path().write_bytes(b"".join(certificate.public_bytes(Encoding.PEM) for certificate in certificates))
    info = {
        "name": filename,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": min(certificate.not_valid_after_utc for certificate in certificates).isoformat(),
    }
    data = load_saved()
    data["certificate"] = info
    data.pop("last_test", None)
    _write_saved(data)
    return info


# --- Effective settings (.env first, then saved) -------------------------------


# Model picked for one generation ("<connection id>|<model>"), set from the X-StudioDock-Model header (main.py)
_requested_model: ContextVar[str | None] = ContextVar("requested_model", default=None)


@contextmanager
def use_model(key: str | None):
    """Generations inside this block use this Studio Dock model (if it still exists)."""
    token = _requested_model.set(key or None)
    try:
        yield
    finally:
        _requested_model.reset(token)


def model_key(choice: studiodock_ia.Choix) -> str:
    return f"{choice.connexion.id}|{choice.model}"


def studiodock_options() -> list[studiodock_ia.Choix]:
    """Every model set in Studio Dock, unless the .env provides the connection or Studio Dock leaves SpecGen its own
    configuration."""
    if any(os.getenv(variable) for variable in CONNECTION_VARIABLES) or studiodock_ia.garde_sa_configuration(STUDIODOCK_APP_ID):
        return []
    return [studiodock_ia.Choix(c, model) for c in studiodock_ia.connexions() for model in c.models]


def _find(options: list[studiodock_ia.Choix], key: Any) -> studiodock_ia.Choix | None:
    return next((o for o in options if model_key(o) == key), None) if key else None


def studiodock_default(options: list[studiodock_ia.Choix] | None = None) -> studiodock_ia.Choix | None:
    """Default model: the one chosen in this app's settings, else the one Studio Dock gives SpecGen."""
    options = studiodock_options() if options is None else options
    if not options:
        return None
    return _find(options, load_saved().get("studiodock_model")) or studiodock_ia.pour_app(STUDIODOCK_APP_ID) or options[0]


def studiodock_choice() -> studiodock_ia.Choix | None:
    """Model used now: the one picked for this generation, else the default one (None: no Studio Dock model)."""
    options = studiodock_options()
    return _find(options, _requested_model.get()) or studiodock_default(options)


def save_default_model(key: str | None) -> None:
    """Default model among those of Studio Dock (None: the one Studio Dock gives SpecGen)."""
    if key and not _find(studiodock_options(), key):
        raise ValueError("Ce modèle n’est plus proposé par Studio Dock.")
    data = load_saved()
    data["studiodock_model"] = key or None
    _write_saved(data)


def model_options() -> dict[str, Any]:
    """Models offered when launching a generation, with the default one."""
    options = studiodock_options()
    default = studiodock_default(options)
    given = studiodock_ia.pour_app(STUDIODOCK_APP_ID)
    return {
        "available": bool(options),
        "default": model_key(default) if default else None,
        "saved_default": load_saved().get("studiodock_model") if _find(options, load_saved().get("studiodock_model")) else None,
        "studiodock_default": model_key(given) if given else None,
        "options": [{"id": model_key(o), "model": o.model, "connection": o.connexion.name, "local": o.connexion.local}
                    for o in options],
    }


def _timeout(saved: dict[str, Any]) -> float:
    value = os.getenv(ENV_VARIABLES["timeout"]) or saved.get("timeout")
    try:
        return float(value) if value else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def get_effective_settings() -> EffectiveSettings:
    saved = load_saved()
    choice = studiodock_choice()
    if choice is not None:
        connection = choice.connexion
        return EffectiveSettings(
            api_base=connection.api_base, api_key=connection.api_key, ca_bundle=connection.ca_bundle, model=choice.model,
            timeout=_timeout(saved), env_fields=["timeout"] if os.getenv(ENV_VARIABLES["timeout"]) else [],
            source="studiodock", studiodock_name=connection.name,
        )
    env_fields = [field for field, variable in ENV_VARIABLES.items() if os.getenv(variable)]

    def pick(field: str, saved_value: Any) -> Any:
        return os.getenv(ENV_VARIABLES[field]) or saved_value

    saved_certificate = str(certificate_path()) if saved.get("certificate") and certificate_path().is_file() else ""
    timeout = pick("timeout", saved.get("timeout"))
    try:
        timeout_seconds = float(timeout) if timeout else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    return EffectiveSettings(
        api_base=pick("api_base", saved.get("api_base") or ""),
        api_key=pick("api_key", "") or saved_api_key(),
        ca_bundle=pick("ca_bundle", saved_certificate),
        model=pick("model", saved.get("model") or DEFAULT_MODEL),
        timeout=timeout_seconds,
        env_fields=env_fields,
    )


def public_settings() -> dict[str, Any]:
    """What the settings screen may show: never the API key itself."""
    saved = load_saved()
    effective = get_effective_settings()
    from_dock = effective.source == "studiodock"
    return {
        # Connection provided by Studio Dock: shown read-only, the fields of this screen are kept for later
        "source": effective.source,
        "studiodock": {"name": effective.studiodock_name, "local": effective.api_base.startswith(("http://localhost", "http://127.0.0.1"))}
        if from_dock else None,
        "studiodock_own": studiodock_ia.garde_sa_configuration(STUDIODOCK_APP_ID),
        "configured": effective.configured,
        "missing": effective.missing,
        "env_fields": effective.env_fields,
        "env_file": str(env_file()) if env_file().is_file() else None,
        "storage_dir": str(config_dir()),
        "api_base": effective.api_base,
        "has_api_key": bool(effective.api_key),
        "api_key_hint": effective.api_key[-4:] if len(effective.api_key) >= 8 else "",
        "certificate": {"name": Path(effective.ca_bundle).name} if from_dock and effective.ca_bundle
        else None if from_dock
        else saved.get("certificate") if "ca_bundle" not in effective.env_fields else {"name": Path(effective.ca_bundle).name},
        "model": effective.model,
        "timeout": effective.timeout,
        "last_test": _studiodock_test(saved, effective) if from_dock else saved.get("last_test"),
        # Journal of the generations (see generation_log.py); CUSTOM_GENERATION_LOG overrides it.
        "generation_log": (
            os.getenv("CUSTOM_GENERATION_LOG", "").strip().lower() in ("1", "true", "yes", "oui")
            if os.getenv("CUSTOM_GENERATION_LOG", "").strip()
            else bool(saved.get("generation_log"))
        ),
        "generation_log_from_env": bool(os.getenv("CUSTOM_GENERATION_LOG", "").strip()),
        "generation_log_dir": str(config_dir() / "journal"),
    }
