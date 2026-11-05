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


_HTML_BREAK = re.compile(r"(?:\s*<\s*br\s*/?\s*>\s*)+", re.IGNORECASE)
_CELL_BULLET = re.compile(r"^(?:[-*•–]\s+)")
_FENCE_LINE = re.compile(r"^\s*(```|~~~)")


def _clean_table_row(line: str, separator: str) -> str:
    cells = line.split("|")
    cleaned = []
    for cell in cells:
        if not _HTML_BREAK.search(cell):
            cleaned.append(cell)
            continue
        parts = [_CELL_BULLET.sub("", part.strip()) for part in _HTML_BREAK.split(cell)]
        parts = [part for part in parts if part]
        cleaned.append(f" {separator.join(parts)} " if parts else " ")
    return "|".join(cleaned)


def remove_html_breaks(markdown_text: str, language: str = "fr") -> str:
    """Models put `<br>` in table cells (personas…) and paragraphs; Markdown shows them as text.

    In a table cell the items are joined with a semicolon (a cell must stay on one line);
    elsewhere the tag becomes a real line break. Code blocks (Mermaid labels use `<br/>`) are kept.
    """
    if not markdown_text or "<" not in markdown_text:
        return markdown_text
    separator = " ; " if language == "fr" else "; "
    out: list[str] = []
    fence: str | None = None
    for line in markdown_text.split("\n"):
        marker = _FENCE_LINE.match(line)
        if fence:
            out.append(line)
            if marker and marker.group(1) == fence:
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            out.append(line)
            continue
        if not _HTML_BREAK.search(line):
            out.append(line)
        elif line.lstrip().startswith("|"):
            out.append(_clean_table_row(line, separator))
        else:
            indent = re.match(r"\s*", line).group(0)
            parts = [part.strip() for part in _HTML_BREAK.split(line.strip())]
            out.extend(f"{indent}{part}" for part in parts if part)
    return "\n".join(out)
