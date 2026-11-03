"""Deterministic conversion of draw.io diagrams to Markdown.

Arrow direction comes from the file itself (each edge's source, target and
arrowheads), never from an AI. Each page becomes a Mermaid flowchart plus a
readable list of relations; arrows that are not attached to shapes, whose
direction cannot be guaranteed, are reported instead of guessed.
"""
from __future__ import annotations

import base64
import html
import io
import re
import zlib
from dataclasses import dataclass, field
from urllib.parse import unquote
from xml.etree import ElementTree

DRAWIO_EXTENSIONS = {".drawio", ".dio", ".xml"}


class NotADrawioFile(ValueError):
    pass


@dataclass
class Node:
    id: str
    label: str
    style: dict[str, str]
    parent: str
    is_container: bool = False


@dataclass
class Edge:
    id: str
    label: str
    style: dict[str, str]
    source: str | None
    target: str | None


@dataclass
class Page:
    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)


# --- Reading the XML out of the file --------------------------------------------


def _xml_from_png(content: bytes) -> str:
    from PIL import Image

    with Image.open(io.BytesIO(content)) as image:
        text_chunks = getattr(image, "text", {}) or {}
    value = text_chunks.get("mxfile")
    if not value:
        raise NotADrawioFile("Cette image ne contient pas de schéma draw.io (exportez-la depuis draw.io en cochant « Inclure une copie du schéma »).")
    return unquote(value) if value.lstrip().startswith("%3C") else value


def _xml_from_svg(content: bytes) -> str:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise NotADrawioFile(f"SVG illisible ({exc}).") from exc
    # The XML parser already decodes the attribute: no second unescaping.
    embedded = root.get("content")
    if not embedded or "mxfile" not in embedded and "mxGraphModel" not in embedded:
        raise NotADrawioFile("Ce SVG ne contient pas de schéma draw.io (exportez-le depuis draw.io en cochant « Inclure une copie du schéma »).")
    return embedded


def _decompress(text: str) -> str:
    """draw.io's compressed pages: URI-encoded, raw-deflated, then base64."""
    data = zlib.decompress(base64.b64decode(text), -15).decode("utf-8")
    return unquote(data)


def _graph_models(xml_text: str) -> list[tuple[str, ElementTree.Element]]:
    root = ElementTree.fromstring(xml_text)
    if root.tag == "mxGraphModel":
        return [("Page-1", root)]
    if root.tag != "mxfile":
        raise NotADrawioFile("Ce fichier XML n’est pas un schéma draw.io.")
    models = []
    for index, diagram in enumerate(root.findall("diagram"), start=1):
        name = diagram.get("name") or f"Page-{index}"
        model = diagram.find("mxGraphModel")
        if model is None and (diagram.text or "").strip():
            model = ElementTree.fromstring(_decompress(diagram.text.strip()))
        if model is not None:
            models.append((name, model))
    return models


# --- Model ------------------------------------------------------------------------


def _parse_style(style: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        key, _, value = part.partition("=")
        parsed[key.strip()] = value.strip() if _ else ""
    return parsed


def _clean_label(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"<br\s*/?>|</div>|</p>|</li>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _cells(model: ElementTree.Element) -> list[tuple[str, str, ElementTree.Element]]:
    """(id, label, mxCell) for every cell, including those wrapped in <object>/<UserObject>."""
    root = model.find("root")
    if root is None:
        return []
    cells = []
    for element in root:
        if element.tag == "mxCell":
            cells.append((element.get("id", ""), element.get("value", ""), element))
        elif element.tag in ("object", "UserObject"):
            cell = element.find("mxCell")
            if cell is not None:
                cells.append((element.get("id", ""), element.get("label", ""), cell))
    return cells


def _build_page(name: str, model: ElementTree.Element) -> Page:
    page = Page(name=name)
    edge_cells: dict[str, Edge] = {}
    pending_labels: list[tuple[str, str]] = []

    for cell_id, raw_label, cell in _cells(model):
        style = _parse_style(cell.get("style"))
        label = _clean_label(raw_label)
        parent = cell.get("parent", "")
        if cell.get("edge") == "1":
            edge_cells[cell_id] = Edge(cell_id, label, style, cell.get("source"), cell.get("target"))
        elif cell.get("vertex") == "1":
            if "edgeLabel" in style:
                pending_labels.append((parent, label))
            else:
                page.nodes[cell_id] = Node(cell_id, label, style, parent)

    # Labels drawn as separate cells on an edge.
    for parent, label in pending_labels:
        edge = edge_cells.get(parent)
        if edge and label:
            edge.label = f"{edge.label} {label}".strip()

    parents = {node.parent for node in page.nodes.values()}
    for node in page.nodes.values():
        style_keys = node.style.keys()
        node.is_container = node.id in parents or "swimlane" in style_keys or node.style.get("container") == "1" or "group" in style_keys

    page.edges = list(edge_cells.values())
    return page


# --- Markdown output ----------------------------------------------------------------


def _direction(edge: Edge) -> str:
    """'forward', 'backward', 'both' or 'none', from the arrowheads in the style."""
    end = edge.style.get("endArrow", "classic") != "none"
    start = edge.style.get("startArrow", "none") not in ("none", "")
    if end and start:
        return "both"
    if end:
        return "forward"
    if start:
        return "backward"
    return "none"


def _node_label(node: Node | None) -> str:
    if node is None:
        return "?"
    return node.label or f"[forme sans texte {node.id}]"


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;").replace("|", "#124;")


def _mermaid_node(mermaid_id: str, node: Node) -> str:
    label = _mermaid_text(node.label or " ")
    shape = node.style.get("shape", "")
    if "rhombus" in node.style or shape == "rhombus":
        return f'{mermaid_id}{{"{label}"}}'
    if "ellipse" in node.style or shape in ("ellipse", "doubleEllipse"):
        return f'{mermaid_id}(["{label}"])'
    if node.style.get("rounded") == "1":
        return f'{mermaid_id}("{label}")'
    return f'{mermaid_id}["{label}"]'


def _layout_direction(model: ElementTree.Element, page: Page) -> str:
    """LR when the connected shapes are laid out mostly left to right, else TD."""
    positions: dict[str, tuple[float, float]] = {}
    for cell_id, _label, cell in _cells(model):
        geometry = cell.find("mxGeometry")
        if geometry is not None and cell_id in page.nodes:
            positions[cell_id] = (float(geometry.get("x", 0)), float(geometry.get("y", 0)))
    horizontal = vertical = 0.0
    for edge in page.edges:
        if edge.source in positions and edge.target in positions:
            (x1, y1), (x2, y2) = positions[edge.source], positions[edge.target]
            horizontal += abs(x2 - x1)
            vertical += abs(y2 - y1)
    return "LR" if horizontal > vertical else "TD"


def _page_markdown(page: Page, model: ElementTree.Element, with_heading: bool) -> list[str]:
    connected = [edge for edge in page.edges if edge.source in page.nodes and edge.target in page.nodes]
    floating = [edge for edge in page.edges if edge not in connected]
    linked_ids = {edge.source for edge in connected} | {edge.target for edge in connected}

    lines: list[str] = [f"## {page.name}", ""] if with_heading else []
    mermaid_ids = {node_id: f"n{index}" for index, node_id in enumerate(page.nodes, start=1)}

    # Shapes shown in the diagram: everything connected, plus standalone shapes that are not plain text.
    shown = {
        node_id
        for node_id, node in page.nodes.items()
        if node_id in linked_ids or (not node.is_container and "text" not in node.style and node.label)
    }
    containers = {node_id: node for node_id, node in page.nodes.items() if node.is_container}

    if shown:
        lines += ["```mermaid", f"flowchart {_layout_direction(model, page)}"]

        def has_content(container_id: str) -> bool:
            return any(child.id in shown or (child.id in containers and has_content(child.id)) for child in page.nodes.values() if child.parent == container_id)

        def emit(parent_id: str, indent: str) -> None:
            for node_id, node in page.nodes.items():
                if node.parent != parent_id:
                    continue
                if node_id in containers and has_content(node_id):
                    # Mermaid links can target a subgraph, so a linked container stays a group.
                    lines.append(f'{indent}subgraph {mermaid_ids[node_id]}["{_mermaid_text(node.label or " ")}"]')
                    emit(node_id, indent + "  ")
                    lines.append(f"{indent}end")
                elif node_id in shown:
                    lines.append(indent + _mermaid_node(mermaid_ids[node_id], node))

        root_parents = {node.parent for node in page.nodes.values() if node.parent not in page.nodes}
        for root_parent in root_parents:
            emit(root_parent, "  ")

        arrows = {"forward": "-->", "backward": "-->", "both": "<-->", "none": "---"}
        dashed_arrows = {"forward": "-.->", "backward": "-.->", "both": "<-.->", "none": "-.-"}
        for edge in connected:
            direction = _direction(edge)
            source, target = (edge.target, edge.source) if direction == "backward" else (edge.source, edge.target)
            arrow = (dashed_arrows if edge.style.get("dashed") == "1" else arrows)[direction]
            label = f"|{_mermaid_text(edge.label)}|" if edge.label else ""
            lines.append(f"  {mermaid_ids[source]} {arrow}{label} {mermaid_ids[target]}")
        lines += ["```", ""]

    if connected:
        lines += ["### Relations", ""]
        symbols = {"forward": "→", "backward": "→", "both": "↔", "none": "—"}
        for edge in connected:
            direction = _direction(edge)
            source, target = (edge.target, edge.source) if direction == "backward" else (edge.source, edge.target)
            relation = f"- **{_node_label(page.nodes[source])}** {symbols[direction]} **{_node_label(page.nodes[target])}**"
            if edge.label:
                relation += f" : {edge.label}"
            if edge.style.get("dashed") == "1":
                relation += " _(trait pointillé)_"
            lines.append(relation)
        lines.append("")

    groups = [
        (node, [page.nodes[child_id] for child_id in page.nodes if page.nodes[child_id].parent == node.id])
        for node in containers.values()
        if node.label
    ]
    groups = [(node, children) for node, children in groups if children]
    if groups:
        lines += ["### Regroupements", ""]
        for node, children in groups:
            lines.append(f"- **{node.label}** : {', '.join(_node_label(child) for child in children)}")
        lines.append("")

    annotations = [node.label for node_id, node in page.nodes.items() if node_id not in shown and not node.is_container and node.label]
    if annotations:
        lines += ["### Textes du schéma", ""]
        lines += [f"- {text}" for text in annotations]
        lines.append("")

    if floating:
        lines += ["### Points d’attention", ""]
        for edge in floating:
            description = f"« {edge.label} »" if edge.label else "sans libellé"
            ends = [page.nodes[end] for end in (edge.source, edge.target) if end in page.nodes]
            attached = f", reliée seulement à **{_node_label(ends[0])}**" if ends else ""
            lines.append(
                f"- Flèche {description} non accrochée à deux formes{attached} : son sens ne peut pas être garanti. "
                "Dans draw.io, accrochez ses deux extrémités aux formes puis reconvertissez."
            )
        lines.append("")

    if not page.nodes and not page.edges:
        lines += ["_Page vide._", ""]
    return lines


def convert_drawio(content: bytes, extension: str, title: str) -> str:
    if extension == ".png":
        xml_text = _xml_from_png(content)
    elif extension == ".svg":
        xml_text = _xml_from_svg(content)
    else:
        xml_text = content.decode("utf-8-sig")

    try:
        models = _graph_models(xml_text)
    except (ElementTree.ParseError, zlib.error, ValueError) as exc:
        if isinstance(exc, NotADrawioFile):
            raise
        raise NotADrawioFile(f"Schéma draw.io illisible ({exc}).") from exc
    if not models:
        raise NotADrawioFile("Aucune page trouvée dans ce schéma draw.io.")

    lines = [f"# {title}", ""]
    for name, model in models:
        lines += _page_markdown(_build_page(name, model), model, with_heading=len(models) > 1 or not name.startswith("Page-"))
    return "\n".join(lines).rstrip() + "\n"


def looks_like_drawio_image(content: bytes, extension: str) -> bool:
    if extension == ".svg":
        return b"content=" in content[:20000] and b"mxfile" in content[:200000]
    if extension == ".png":
        return b"mxfile" in content[:500000] or b"mxGraphModel" in content[:500000]
    return False
