"""Conversion of office / web documents (MarkItDown) draw.io diagrams and .mapline files to Markdown.

The file type is always known from its extension, so each document goes straight to the matching MarkItDown
converter. This skips MarkItDown's content sniffing (Magika, an AI model running on onnxruntime + numpy), which
weighed tens of MB in the exe for nothing. Excel workbooks are read with openpyxl directly (MarkItDown's own
converter needs pandas + numpy, and wrote "NaN" / "Unnamed: 0" in empty cells).
"""
from __future__ import annotations

import io
import sys
import types

try:  # Magika is left out of the exe (SpecGenerator.spec): MarkItDown imports it but it is never called here
    import magika  # noqa: F401
except ImportError:
    sys.modules["magika"] = types.ModuleType("magika")

from markitdown import StreamInfo
from markitdown.converters import DocxConverter, HtmlConverter, PdfConverter, PptxConverter

from drawio_converter import DRAWIO_EXTENSIONS, NotADrawioFile, convert_drawio, looks_like_drawio_image
from mapline_converter import MAPLINE_EXTENSIONS, convert_mapline

OFFICE_EXTENSIONS = {".docx", ".pdf", ".pptx", ".xlsx", ".html", ".htm", ".txt", ".md"}
# PNG and SVG are only accepted when they embed a draw.io diagram.
SUPPORTED_EXTENSIONS = OFFICE_EXTENSIONS | DRAWIO_EXTENSIONS | MAPLINE_EXTENSIONS | {".png", ".svg"}

_CONVERTERS = {
    ".docx": DocxConverter(),
    ".pdf": PdfConverter(),
    ".pptx": PptxConverter(),
    ".html": HtmlConverter(),
    ".htm": HtmlConverter(),
}


def convert_to_markdown(content: bytes, extension: str, title: str = "Schéma") -> str:
    if extension in MAPLINE_EXTENSIONS:
        return convert_mapline(content, title)
    if extension in DRAWIO_EXTENSIONS or looks_like_drawio_image(content, extension):
        return convert_drawio(content, extension, title)
    if extension in (".png", ".svg"):
        raise NotADrawioFile("Seules les images exportées depuis draw.io avec le schéma inclus sont prises en charge.")
    if extension in (".txt", ".md"):
        return _decode_text(content).strip() + "\n"
    if extension == ".xlsx":
        return _xlsx_to_markdown(content)
    converter = _CONVERTERS[extension]
    result = converter.convert(io.BytesIO(content), StreamInfo(extension=extension))
    return result.text_content.strip() + "\n"


def _decode_text(content: bytes) -> str:
    """UTF-8 (with or without BOM), else Windows-1252: the encodings of plain text files met on Windows."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _xlsx_to_markdown(content: bytes) -> str:
    """One Markdown table per sheet: first non-empty row as header, empty rows and columns dropped."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    parts = []
    try:
        for sheet in workbook.worksheets:
            rows = [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
            rows = [r for r in rows if any(r)]
            parts.append(f"## {sheet.title}")
            if not rows:
                parts.append("_(feuille vide)_")
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            used = [i for i in range(width) if any(r[i] for r in rows)]
            rows = [[r[i] for i in used] for r in rows]
            lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in used) + " |"]
            lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
            parts.append("\n".join(lines))
    finally:
        workbook.close()
    return "\n\n".join(parts).strip() + "\n"
