"""Translation of a generated document (context or spec) between French and English.

The document is cut at its headings into chunks of moderate size so that a small model
(Mistral Small) translates each one completely and keeps its Markdown structure. Every
chunk is checked: same headings, table rows and code blocks as the source; a chunk that
comes back with a different structure is asked again once, then kept with a warning."""
from __future__ import annotations

import re

from markdown_cleanup import unwrap_markdown_fence
from openai_client import complete, get_openai_client

MAX_CHUNK_CHARS = 6000

LANGUAGE_NAMES = {"fr": "French", "en": "English"}

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^#{1,6}\s")
_SPLIT_HEADING = re.compile(r"^#{1,3}\s")
_TABLE_ROW = re.compile(r"^\s*\|")


def _system_prompt(target: str) -> str:
    source = LANGUAGE_NAMES["en" if target == "fr" else "fr"]
    name = LANGUAGE_NAMES[target]
    return (
        f"You are a professional technical translator for UX design and software documentation. "
        f"Translate the Markdown excerpt you receive from {source} into {name}.\n"
        "Rules:\n"
        "- Answer with the translated Markdown only: no introduction, no comment, no ``` wrapping.\n"
        "- Translate everything, down to the last line: do not summarise, shorten, merge or add anything.\n"
        "- Keep the exact Markdown structure: same headings and levels, same lists, same tables "
        "(same number of rows and columns, separator rows untouched), same bold and italics, same line breaks.\n"
        "- Do not translate: content of inline `code` and of code blocks, JSON paths ($.…), identifiers, "
        "Figma layer names in parentheses such as (Frame 01010), URLs, file names, numbers and units.\n"
        "- Texts displayed in the interface and quoted between « » or \" \" are the real labels of the "
        "product: keep them as they are.\n"
        "- In ```mermaid blocks, translate only the visible labels (text between brackets, quotes or "
        "after |), never the node ids, keywords, arrows or syntax.\n"
        "- Use the usual UX and software vocabulary of the target language."
    )


def _outside_fences(markdown: str) -> list[tuple[str, bool]]:
    """Lines with a flag telling whether they sit outside a code block."""
    lines: list[tuple[str, bool]] = []
    in_fence = False
    for line in markdown.split("\n"):
        if _FENCE.match(line):
            lines.append((line, False))
            in_fence = not in_fence
            continue
        lines.append((line, not in_fence))
    return lines


def split_markdown(markdown: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Chunks cut before a heading (levels 1 to 3), never inside a code block; a section
    longer than max_chars is cut before a blank line, never inside a table."""
    sections: list[list[str]] = [[]]
    for line, outside in _outside_fences(markdown):
        if outside and _SPLIT_HEADING.match(line) and any(l.strip() for l in sections[-1]):
            sections.append([])
        sections[-1].append(line)

    pieces: list[str] = []
    for section in sections:
        text = "\n".join(section)
        if len(text) <= max_chars:
            pieces.append(text)
            continue
        current: list[str] = []
        size = 0
        flags = _outside_fences(text)
        for index, (line, outside) in enumerate(flags):
            next_is_table = index + 1 < len(flags) and _TABLE_ROW.match(flags[index + 1][0])
            if size >= max_chars and outside and not line.strip() and not next_is_table:
                pieces.append("\n".join(current))
                current, size = [], 0
            current.append(line)
            size += len(line) + 1
        pieces.append("\n".join(current))

    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + len(piece) + 1 <= max_chars:
            chunks[-1] += "\n" + piece
        else:
            chunks.append(piece)
    return [chunk for chunk in chunks if chunk.strip()]


def structure_of(markdown: str) -> dict[str, int]:
    counts = {"headings": 0, "table_rows": 0, "code_blocks": 0}
    for line, outside in _outside_fences(markdown):
        if _FENCE.match(line):
            counts["code_blocks"] += 1
        elif outside and _HEADING.match(line):
            counts["headings"] += 1
        elif outside and _TABLE_ROW.match(line):
            counts["table_rows"] += 1
    counts["code_blocks"] //= 2
    return counts


def structure_differences(source: str, translated: str) -> list[str]:
    labels = {"headings": "titres", "table_rows": "lignes de tableau", "code_blocks": "blocs de code"}
    expected, found = structure_of(source), structure_of(translated)
    return [f"{labels[key]} : {found[key]} au lieu de {expected[key]}" for key in labels if expected[key] != found[key]]


def _first_heading(chunk: str) -> str:
    for line, outside in _outside_fences(chunk):
        if outside and _HEADING.match(line):
            return line.lstrip("#").strip()
    return chunk.strip().split("\n", 1)[0][:60]


def translate_markdown(markdown: str, target: str) -> dict[str, object]:
    """Translated document and the warnings for the chunks whose structure changed."""
    if target not in LANGUAGE_NAMES:
        raise ValueError(f"Langue cible inconnue : {target}")
    client = get_openai_client()
    system = _system_prompt(target)
    translated_chunks: list[str] = []
    warnings: list[str] = []
    for chunk in split_markdown(unwrap_markdown_fence(markdown).rstrip("\n")):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": chunk}]
        translated = unwrap_markdown_fence(complete(client, messages, temperature=0)).rstrip("\n")
        differences = structure_differences(chunk, translated)
        if differences:
            retry = [
                *messages,
                {"role": "assistant", "content": translated},
                {
                    "role": "user",
                    "content": "Your translation does not keep the structure of the source ("
                    + "; ".join(differences)
                    + "). Translate the whole excerpt again, keeping exactly the same headings, table rows and code blocks.",
                },
            ]
            second = unwrap_markdown_fence(complete(client, retry, temperature=0)).rstrip("\n")
            second_differences = structure_differences(chunk, second)
            if len(second_differences) <= len(differences):
                translated, differences = second, second_differences
        if differences:
            warnings.append(f"Traduction à relire dans la section « {_first_heading(chunk)} » ({', '.join(differences)}).")
        translated_chunks.append(translated)
    return {"markdown": "\n\n".join(translated_chunks).strip() + "\n", "warnings": warnings}
