"""Translation of a generated document (context or spec) between French and English, after generation.

The document is translated section by section so that a long document fits the output limit of a
small model. Code blocks never go through the general prompt: Mermaid diagrams get their own call
(labels only), other code is kept as is. The fixed vocabulary (headings, table columns, confidence
levels) comes from the generation structures, so that a translated document passes the same checks
as a document generated directly in the target language.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from context_generator import _get_expected_context_structure
from markdown_cleanup import remove_html_breaks, unwrap_markdown_fence
from openai_client import complete, get_openai_client
from spec_validation import (
    CONFIDENCE_LEVELS,
    EXPECTED_HEADINGS,
    EXPECTED_TABLES,
    check_against_structure,
    check_structure,
    format_warnings,
)

DocKind = Literal["context", "spec"]
LANGUAGE_NAMES = {"fr": "French", "en": "English"}
MAX_CHUNK_CHARS = 6000

_FENCE = re.compile(r"^(?P<fence>```|~~~)(?P<lang>[^\n]*)\n.*?^(?P=fence)[ \t]*$", re.DOTALL | re.MULTILINE)
_PLACEHOLDER = "@@BLOCK_{}@@"
_PLACEHOLDER_RE = re.compile(r"@@BLOCK_(\d+)@@")
_HEADING_LINE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def _structure_pairs(structure_fr: str, structure_en: str) -> list[tuple[str, str]]:
    """Heading and column names that sit on the same line of both structures."""
    pairs: list[tuple[str, str]] = []
    for line_fr, line_en in zip(structure_fr.splitlines(), structure_en.splitlines()):
        heading_fr, heading_en = _HEADING_LINE.match(line_fr), _HEADING_LINE.match(line_en)
        if heading_fr and heading_en:
            pairs.append((heading_fr.group(1), heading_en.group(1)))
        elif line_fr.startswith("|") and line_en.startswith("|") and "---" not in line_fr:
            cells_fr = [cell.strip() for cell in line_fr.strip("|").split("|")]
            cells_en = [cell.strip() for cell in line_en.strip("|").split("|")]
            if len(cells_fr) == len(cells_en):
                pairs.extend(zip(cells_fr, cells_en))
    return pairs


def glossary(kind: DocKind) -> list[tuple[str, str]]:
    """(French, English) pairs that must be translated exactly."""
    if kind == "context":
        pairs = _structure_pairs(
            _get_expected_context_structure("fr", "standard"), _get_expected_context_structure("en", "standard")
        )
    else:
        pairs = [(fr, en) for (_, fr), (_, en) in zip(EXPECTED_HEADINGS["fr"], EXPECTED_HEADINGS["en"])]
        for table_fr, table_en in zip(EXPECTED_TABLES["fr"].values(), EXPECTED_TABLES["en"].values()):
            pairs.extend(zip(table_fr, table_en))
    pairs.extend(zip(CONFIDENCE_LEVELS["fr"], CONFIDENCE_LEVELS["en"]))
    seen: set[tuple[str, str]] = set()
    return [pair for pair in pairs if pair[0] != pair[1] and not (pair in seen or seen.add(pair))]


def _system_prompt(kind: DocKind, source: str, target: str) -> str:
    pairs = glossary(kind)
    if source == "en":
        pairs = [(en, fr) for fr, en in pairs]
    terms = "\n".join(f"- {a} → {b}" for a, b in pairs)
    separator = "« ; »" if target == "fr" else '"; "'
    document = "project context document" if kind == "context" else "UX / HMI specification"
    return (
        f"You are a professional translator of UX documentation. Translate a part of a {document} from "
        f"{LANGUAGE_NAMES[source]} to {LANGUAGE_NAMES[target]}.\n\n"
        "Rules:\n"
        "- Keep the Markdown exactly: same heading levels, same tables with the same number of columns and "
        "rows, same lists, bold and links. Translate the content of every cell.\n"
        "- Keep every placeholder such as @@BLOCK_0@@ unchanged, on its own line.\n"
        "- Do not translate: Figma layer and component names (often in backticks or in parentheses, e.g. "
        "(Frame 01010)), texts quoted from the interface between « » or quotation marks, IDs (#1, H1, Q2…), "
        "product names, file names.\n"
        f"- {'Use French typography (non-breaking space before : ; ! ?, quotes « »).' if target == 'fr' else 'Use English typography (no space before : ; ! ?).'}\n"
        f"- No HTML tags (<br>…): in a table cell, separate several items with {separator}.\n"
        "- Translate fully and faithfully: add nothing, remove nothing, no comment.\n\n"
        f"Fixed vocabulary, to use exactly:\n{terms}\n\n"
        f"Answer with the translated Markdown only, entirely in {LANGUAGE_NAMES[target]}."
    )


def _mermaid_prompt(source: str, target: str) -> str:
    return (
        f"Translate the labels of this Mermaid diagram from {LANGUAGE_NAMES[source]} to {LANGUAGE_NAMES[target]}. "
        "Translate only the visible texts (node labels, edge labels, subgraph titles). Keep everything else "
        "exactly: diagram type, node ids, arrows, quotes, brackets, <br/> inside labels, line order. "
        "Answer with the Mermaid code only, without a ``` fence."
    )


def _split_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Cuts before level 1 or 2 headings, joining small sections up to max_chars."""
    sections = re.split(r"(?m)^(?=#{1,2}\s)", text)
    chunks: list[str] = []
    for section in sections:
        if chunks and len(chunks[-1]) + len(section) <= max_chars:
            chunks[-1] += section
        elif section:
            chunks.append(section)
    return chunks


def _strip_fence(code: str) -> str:
    text = code.strip()
    match = re.match(r"^```[a-z]*\s*\n(.*?)\n```$", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def _translate_block(client: Any, block: str, lang: str, source: str, target: str) -> str:
    if lang != "mermaid":
        return block
    lines = block.split("\n")
    code = "\n".join(lines[1:-1])
    try:
        translated = _strip_fence(complete(
            client,
            [{"role": "system", "content": _mermaid_prompt(source, target)}, {"role": "user", "content": code}],
            temperature=0,
        ))
    except Exception:
        return block
    if not translated or translated.splitlines()[0].split()[:1] != code.strip().splitlines()[0].split()[:1]:
        # The diagram type changed or vanished: keep the original diagram rather than a broken one.
        return block
    return f"{lines[0]}\n{translated}\n{lines[-1]}"


def translate_markdown(markdown: str, kind: DocKind, source: str, target: str) -> dict[str, Any]:
    """Returns {"markdown", "warnings"}."""
    client = get_openai_client()
    blocks: list[tuple[str, str]] = []

    def stash(match: re.Match[str]) -> str:
        blocks.append((match.group(0), match.group("lang").strip().lower()))
        return _PLACEHOLDER.format(len(blocks) - 1)

    text = _FENCE.sub(stash, unwrap_markdown_fence(markdown))
    system = _system_prompt(kind, source, target)
    translated_chunks: list[str] = []
    for chunk in _split_chunks(text):
        if not chunk.strip() or _PLACEHOLDER_RE.fullmatch(chunk.strip()):
            translated_chunks.append(chunk)
            continue
        answer = unwrap_markdown_fence(
            complete(client, [{"role": "system", "content": system}, {"role": "user", "content": chunk}], temperature=0)
        )
        if not answer.strip():
            raise ValueError("Le modèle n’a renvoyé aucune traduction.")
        # A placeholder the model dropped is put back at the end of its part, so no diagram is lost.
        missing = [p for p in _PLACEHOLDER_RE.findall(chunk) if _PLACEHOLDER.format(p) not in answer]
        if missing:
            answer = answer.rstrip() + "\n\n" + "\n\n".join(_PLACEHOLDER.format(p) for p in missing) + "\n"
        translated_chunks.append(answer.rstrip() + "\n\n")

    result = "".join(translated_chunks).strip() + "\n"
    translated_blocks = [_translate_block(client, block, lang, source, target) for block, lang in blocks]
    result = _PLACEHOLDER_RE.sub(
        lambda match: translated_blocks[int(match.group(1))] if int(match.group(1)) < len(translated_blocks) else "",
        result,
    )
    result = remove_html_breaks(result, target)

    if kind == "context":
        issues = check_against_structure(result, _get_expected_context_structure(target, "standard"), target)
    else:
        issues = check_structure(result, target)
    return {"markdown": result, "warnings": format_warnings({"structure": issues, "unknown_components": []})}
