"""Conversion of office / web documents (MarkItDown) draw.io diagrams and .mapline files to Markdown."""
from __future__ import annotations

import io

from markitdown import MarkItDown, StreamInfo

from drawio_converter import DRAWIO_EXTENSIONS, NotADrawioFile, convert_drawio, looks_like_drawio_image
from mapline_converter import MAPLINE_EXTENSIONS, convert_mapline

OFFICE_EXTENSIONS = {".docx", ".pdf", ".pptx", ".xlsx", ".html", ".htm", ".txt", ".md"}
# PNG and SVG are only accepted when they embed a draw.io diagram.
SUPPORTED_EXTENSIONS = OFFICE_EXTENSIONS | DRAWIO_EXTENSIONS | MAPLINE_EXTENSIONS | {".png", ".svg"}

_converter = MarkItDown(enable_plugins=False)


def convert_to_markdown(content: bytes, extension: str, title: str = "Schéma") -> str:
    if extension in MAPLINE_EXTENSIONS:
        return convert_mapline(content, title)
    if extension in DRAWIO_EXTENSIONS or looks_like_drawio_image(content, extension):
        return convert_drawio(content, extension, title)
    if extension in (".png", ".svg"):
        raise NotADrawioFile("Seules les images exportées depuis draw.io avec le schéma inclus sont prises en charge.")
    result = _converter.convert_stream(io.BytesIO(content), stream_info=StreamInfo(extension=extension))
    return result.text_content.strip() + "\n"
