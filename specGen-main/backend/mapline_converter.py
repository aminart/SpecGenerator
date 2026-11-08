"""Best-effort conversion of .mapline files to Markdown.

The .mapline format is not publicly documented, so the content is sniffed:
a zip archive is opened and its first JSON / XML entry is read, JSON and XML
are rendered as nested Markdown lists (node labels first, children indented),
anything else is kept as plain text.
"""
from __future__ import annotations

import io
import json
import zipfile
from xml.etree import ElementTree

from drawio_converter import convert_drawio

MAPLINE_EXTENSIONS = {".mapline"}

# Keys that usually hold a node's visible text, by priority.
_LABEL_KEYS = ("title", "name", "label", "text", "topic", "content", "value", "caption")
# Keys that usually hold a node's children.
_CHILD_KEYS = ("children", "nodes", "items", "topics", "subtopics", "steps", "elements", "lines")
_MAX_DEPTH = 30


class NotAMaplineFile(ValueError):
    pass


def convert_mapline(content: bytes, title: str = "Carte") -> str:
    if zipfile.is_zipfile(io.BytesIO(content)):
        content = _payload_from_zip(content)
    text = _decode(content)
    stripped = text.lstrip()
    if not stripped:
        raise NotAMaplineFile("Le fichier .mapline est vide.")
    if stripped[0] in "{[":
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            return _render(title, _json_lines(data, 0))
    if stripped.startswith("<"):
        if "<mxfile" in stripped or "<mxGraphModel" in stripped:
            return convert_drawio(content, ".drawio", title)
        try:
            root = ElementTree.fromstring(stripped)
        except ElementTree.ParseError:
            root = None
        if root is not None:
            return _render(title, _xml_lines(root, 0))
    return f"# {title}\n\n{text.strip()}\n"


def _payload_from_zip(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        for suffixes in ((".json",), (".xml",), (".txt", ".md")):
            for name in names:
                if name.lower().endswith(suffixes):
                    return archive.read(name)
    raise NotAMaplineFile("L'archive .mapline ne contient aucun fichier JSON, XML ou texte lisible.")


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _render(title: str, lines: list[str]) -> str:
    if not lines:
        raise NotAMaplineFile("Aucun contenu exploitable n'a été trouvé dans le fichier .mapline.")
    return f"# {title}\n\n" + "\n".join(lines) + "\n"


def _scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) and value != ""


def _json_lines(data: object, depth: int) -> list[str]:
    if depth > _MAX_DEPTH:
        return []
    indent = "  " * depth
    if isinstance(data, list):
        lines: list[str] = []
        for item in data:
            if _scalar(item):
                lines.append(f"{indent}- {item}")
            else:
                lines.extend(_json_lines(item, depth))
        return lines
    if not isinstance(data, dict):
        return [f"{indent}- {data}"] if _scalar(data) else []

    label_key = next((k for k in _LABEL_KEYS if _scalar(data.get(k))), None)
    child_keys = [k for k in _CHILD_KEYS if isinstance(data.get(k), (list, dict))]
    if label_key is None and not child_keys:
        # Plain object without a recognisable node shape: list its fields.
        lines = []
        for key, value in data.items():
            if _scalar(value):
                lines.append(f"{indent}- **{key}** : {value}")
            elif value:
                sub = _json_lines(value, depth + 1)
                if sub:
                    lines.append(f"{indent}- **{key}**")
                    lines.extend(sub)
        return lines

    lines = []
    child_depth = depth
    if label_key is not None:
        lines.append(f"{indent}- {str(data[label_key]).strip()}")
        child_depth = depth + 1
        # Other short text fields (notes, descriptions) as sub-items.
        for key in ("description", "note", "notes", "comment"):
            if key != label_key and _scalar(data.get(key)):
                lines.append(f"{'  ' * child_depth}- _{key}_ : {data[key]}")
    for key in child_keys:
        lines.extend(_json_lines(data[key], child_depth))
    return lines


def _xml_lines(element: ElementTree.Element, depth: int) -> list[str]:
    if depth > _MAX_DEPTH:
        return []
    attrs = {k.split("}")[-1].lower(): v for k, v in element.attrib.items()}
    label = next((attrs[k] for k in _LABEL_KEYS if attrs.get(k)), None)
    text = (element.text or "").strip()
    if label is None and text:
        label = text
    lines: list[str] = []
    child_depth = depth
    if label:
        lines.append(f"{'  ' * depth}- {label.strip()}")
        child_depth = depth + 1
    for child in element:
        lines.extend(_xml_lines(child, child_depth))
    return lines
