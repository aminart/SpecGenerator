"""Normalisation of the Markdown returned by the LLM."""
from __future__ import annotations

import re
from typing import Any

_OUTER_FENCE = re.compile(r"^\s*```(?:markdown|md)?[ \t]*\n(?P<body>.*?)\n```\s*$", re.DOTALL | re.IGNORECASE)
_INNER_FENCE = re.compile(r"```(?:markdown|md)[ \t]*\n(?P<body>.*?)\n```", re.DOTALL | re.IGNORECASE)
_JSON_PATH = re.compile(r"(?:\bJSON\s*[:\-–]\s*)?`?(\$(?:\.[A-Za-z_][\w-]*|\[\d+\])+)`?")


def unwrap_markdown_fence(text: str) -> str:
    """Models often wrap the whole document in ```markdown … ```: keep only the document."""
    stripped = (text or "").strip()
    match = _OUTER_FENCE.match(stripped)
    if match:
        return match.group("body").strip() + "\n"
    inner = _INNER_FENCE.search(stripped)
    if inner and "#" in inner.group("body"):
        outside = (stripped[: inner.start()] + stripped[inner.end() :]).strip()
        # Only a short preamble or closing sentence around the fenced document.
        if len(outside) < 300:
            return inner.group("body").strip() + "\n"
    return stripped + "\n" if stripped else ""


def _node_label(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    for key in ("name", "label", "title", "id"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_json_path(data: Any, path: str) -> Any:
    node = data
    for key, index in re.findall(r"\.([A-Za-z_][\w-]*)|\[(\d+)\]", path[1:]):
        try:
            node = node[key] if key else node[int(index)]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return node


def replace_json_paths_with_names(markdown_text: str, data: Any) -> str:
    """Turns technical locators like `JSON: $.children[0].children[2]` into the Figma layer name."""

    def substitute(match: re.Match[str]) -> str:
        label = _node_label(_resolve_json_path(data, match.group(1)))
        return label if label else match.group(0)

    return _JSON_PATH.sub(substitute, markdown_text)
