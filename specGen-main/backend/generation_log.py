"""Optional journal of the generations: every call to the model (prompt, answer, finish
reason, duration) and the final result (warnings, corrections, timings), one JSON file per
generation in the settings folder. Meant for analysing what the model gets wrong.

Enabled from the settings screen, or with CUSTOM_GENERATION_LOG=1 in the .env. The files
hold the project documents and JSON: they stay on this computer."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app_paths import config_dir

logger = logging.getLogger(__name__)

LOG_VARIABLE = "CUSTOM_GENERATION_LOG"
MAX_LOG_FILES = 100

_current: ContextVar["Journal | None"] = ContextVar("generation_journal", default=None)


def log_dir() -> Path:
    return config_dir() / "journal"


def is_enabled() -> bool:
    variable = os.getenv(LOG_VARIABLE, "").strip().lower()
    if variable:
        return variable in ("1", "true", "yes", "oui")
    from settings_store import load_saved  # late import: settings_store imports app_paths only

    return bool(load_saved().get("generation_log"))


@dataclass
class Journal:
    kind: str
    request: dict[str, Any]
    started: float = field(default_factory=time.perf_counter)
    calls: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)


def record_call(
    messages: list[dict[str, str]],
    options: dict[str, Any],
    *,
    answer: str | None = None,
    finish_reason: str | None = None,
    error: str | None = None,
    duration: float,
) -> None:
    journal = _current.get()
    if journal is None:
        return
    journal.calls.append(
        {
            "messages": messages,
            "options": options,
            "answer": answer,
            "finish_reason": finish_reason,
            "error": error,
            "duration_s": round(duration, 2),
        }
    )


def set_result(**result: Any) -> None:
    journal = _current.get()
    if journal is not None:
        journal.result.update(result)


@contextmanager
def generation_journal(kind: str, **request: Any) -> Iterator[None]:
    """Collects the calls made inside the block and writes them when it ends, even on error."""
    if not is_enabled():
        yield
        return
    journal = Journal(kind=kind, request=request)
    token = _current.set(journal)
    try:
        yield
    except Exception as exc:
        journal.result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _current.reset(token)
        _write(journal)


def _write(journal: Journal) -> None:
    try:
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        payload = {
            "kind": journal.kind,
            "date": datetime.now().isoformat(timespec="seconds"),
            "total_duration_s": round(time.perf_counter() - journal.started, 2),
            "request": journal.request,
            "result": journal.result,
            "calls": journal.calls,
        }
        (directory / f"{stamp}_{journal.kind}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for old in sorted(directory.glob("*.json"))[:-MAX_LOG_FILES]:
            old.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not write the generation journal", exc_info=True)
