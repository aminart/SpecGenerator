from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from openai import BadRequestError, OpenAI

from generation_log import record_call
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


# --- Completions ---------------------------------------------------------------

# Writing temperature recommended by Mistral for Mistral Small; structured passes use 0.
WRITING_TEMPERATURE = 0.15
DEFAULT_MAX_OUTPUT_TOKENS = 16000
MAX_OUTPUT_TOKENS_VARIABLE = "CUSTOM_MAX_OUTPUT_TOKENS"
MAX_CONTINUATIONS = 3
CONTINUE_PROMPT = (
    "Your answer was cut because it reached the length limit. Continue exactly where you stopped, "
    "without repeating anything and without any introduction."
)

logger = logging.getLogger(__name__)


def get_max_output_tokens() -> int:
    try:
        value = int(os.getenv(MAX_OUTPUT_TOKENS_VARIABLE, ""))
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS
    return value if value > 0 else DEFAULT_MAX_OUTPUT_TOKENS


def _create(client: OpenAI, messages: list[dict[str, str]], temperature: float, json_mode: bool) -> Any:
    """One call; drops the optional parameters a server rejects instead of failing."""
    options: dict[str, Any] = {"max_tokens": get_max_output_tokens()}
    if json_mode:
        options["response_format"] = {"type": "json_object"}
    while True:
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=get_model_name(), temperature=temperature, messages=messages, **options
            )
        except Exception as exc:
            record_call(messages, {"temperature": temperature, **options}, error=f"{type(exc).__name__}: {exc}", duration=time.perf_counter() - started)
            if not isinstance(exc, BadRequestError) or not options:
                raise
            # Unsupported response_format first, then a max_tokens above the server limit.
            dropped = "response_format" if "response_format" in options else "max_tokens"
            logger.warning("Model service rejected %s, retrying without it: %s", dropped, exc)
            options.pop(dropped)
            continue
        choice = response.choices[0]
        record_call(
            messages,
            {"temperature": temperature, **options},
            answer=choice.message.content,
            finish_reason=getattr(choice, "finish_reason", None),
            duration=time.perf_counter() - started,
        )
        return response


def complete(
    client: OpenAI, messages: list[dict[str, str]], *, temperature: float = WRITING_TEMPERATURE, json_mode: bool = False
) -> str:
    """Text of the answer. When the answer is cut by the length limit (finish_reason
    "length"), asks the model to continue and joins the parts."""
    response = _create(client, messages, temperature, json_mode)
    choice = response.choices[0]
    text = choice.message.content or ""
    continuations = 0
    while getattr(choice, "finish_reason", None) == "length" and continuations < MAX_CONTINUATIONS and not json_mode:
        continuations += 1
        follow_up = [*messages, {"role": "assistant", "content": text}, {"role": "user", "content": CONTINUE_PROMPT}]
        response = _create(client, follow_up, temperature, json_mode)
        choice = response.choices[0]
        text += choice.message.content or ""
    if getattr(choice, "finish_reason", None) == "length":
        logger.warning("Model answer still cut after %s continuations", continuations)
    return text
