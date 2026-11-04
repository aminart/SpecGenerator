"""Document rendering and export helpers (HTML preview, DOCX from Word templates).

Extracted from the former Streamlit app so they can be served by the API.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from datetime import datetime
from typing import Any

import markdown
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph

from app_paths import app_dir, resource_dir


def _template_path(filename: str) -> str:
    """A template placed next to the app (or the .exe) overrides the bundled one."""
    custom = app_dir() / filename
    return str(custom if custom.is_file() else resource_dir() / filename)


SPEC_DOCX_TEMPLATES = {
    "fr": "Template_Documentatio_Specs_fr.docx",
    "en": "Template_Documentatio_Specs_en.docx",
}
CONTEXT_DOCX_TEMPLATES = {
    "fr": "Template_Documentatio_Context_fr.docx",
    "en": "Template_Documentatio_Context_en.docx",
}


def normalize_markdown_title(markdown_text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown_text, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def extract_sections(markdown_text: str) -> list[dict[str, str]]:
    pattern = re.compile(r"^##?\s+(.+)$", flags=re.MULTILINE)
    matches = list(pattern.finditer(markdown_text))
    sections: list[dict[str, str]] = []

    if not matches:
        return [{"title": "Contenu", "body": markdown_text.strip()}] if markdown_text.strip() else []

    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        body = markdown_text[start:end].strip()
        sections.append({"title": title, "body": body})

    return sections


_MERMAID_BLOCK = re.compile(r"^```mermaid[ \t]*\n(.*?)\n```[ \t]*$", re.DOTALL | re.MULTILINE)


def diagrams_by_code(diagrams: list[dict[str, str]] | None) -> dict[str, bytes]:
    """Mermaid code -> PNG bytes, as drawn by the frontend."""
    images: dict[str, bytes] = {}
    for diagram in diagrams or []:
        try:
            images[diagram["code"].strip()] = base64.b64decode(diagram["png_base64"], validate=True)
        except (KeyError, ValueError, TypeError):
            continue
    return images


def embed_diagrams_in_markdown(markdown_text: str, diagrams: dict[str, bytes]) -> str:
    """For the HTML export: each drawn Mermaid block becomes an inline image."""
    if not diagrams:
        return markdown_text

    def replace(match: re.Match[str]) -> str:
        image = diagrams.get(match.group(1).strip())
        if image is None:
            return match.group(0)
        data = base64.b64encode(image).decode("ascii")
        return f"<p class='doc-diagram'><img src='data:image/png;base64,{data}' alt='Diagramme' style='max-width:100%;height:auto;' /></p>"

    return _MERMAID_BLOCK.sub(replace, markdown_text)


def markdown_to_html(md_text: str) -> str:
    rendered = markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])
    rendered = rendered.replace("<h3>", "<h3 class='doc-h3'>")
    rendered = rendered.replace("<table>", "<table class='doc-table'>")
    rendered = rendered.replace("<blockquote>", "<blockquote class='doc-blockquote'>")
    rendered = rendered.replace("<ul>", "<ul class='doc-list'>")
    rendered = rendered.replace("<ol>", "<ol class='doc-list'>")
    rendered = rendered.replace("<code>", "<code class='doc-code'>")
    return rendered


def _is_effectively_empty_section(body: str) -> bool:
    normalized = (body or "").strip()
    if not normalized:
        return True

    cleaned_lines: list[str] = []
    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"[-*+]", stripped):
            continue
        if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", stripped):
            continue
        cleaned_lines.append(stripped)

    return not cleaned_lines


def get_ui_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "content": "Content",
            "no_content": "No generated content yet.",
            "generated_on": "Generated on",
            "detected_features": "Detected features",
            "component": "Component",
            "nodes": "Nodes",
            "fields": "Fields",
            "sections": "Sections",
            "actions": "Actions",
            "spec_help": "Generation may take from 30 seconds to several minutes depending on the JSON size.",
            "spec_spinner": "The specification is being generated...",
            "spec_success": "Specification generated.",
            "spec_error_prefix": "Error while generating the specification:",
        }

    return {
        "content": "Contenu",
        "no_content": "Aucun contenu généré pour le moment.",
        "generated_on": "Généré le",
        "detected_features": "Features détectées",
        "component": "Composant",
        "nodes": "Noeuds",
        "fields": "Champs",
        "sections": "Sections",
        "actions": "Actions",
        "spec_help": "La génération peut prendre de 30 secondes à plusieurs minutes selon la taille du JSON.",
        "spec_spinner": "La spécification est en cours de génération...",
        "spec_success": "Spécification générée.",
        "spec_error_prefix": "Erreur lors de la génération de la spec :",
    }


def build_document_html(
    markdown_text: str,
    title: str,
    subtitle: str,
    analysis: dict[str, Any] | None = None,
    language: str = "fr",
    feature_image_data: str | None = None,
    feature_image_mime: str | None = None,
) -> str:
    labels = get_ui_labels(language)
    sections = [section for section in extract_sections(markdown_text) if not _is_effectively_empty_section(section["body"])]
    rendered_sections = "".join(
        f"""
        <section class='doc-section'>
            <div class='doc-section-title-row'>
                <h2 class='doc-section-title'>{html.escape(section['title'])}</h2>
            </div>
            <div class='doc-section-body'>{markdown_to_html(section['body'])}</div>
        </section>
        """
        for section in sections
    )

    if not rendered_sections:
        rendered_sections = f"""
        <section class='doc-section doc-section-empty'>
            <p style='margin:0;color:#6b7280;'>{html.escape(labels['no_content'])}</p>
        </section>
        """

    if sections and sections[0]["title"].strip() == title.strip():
        sections = sections[1:]
        rendered_sections = "".join(
            f"""
            <section class='doc-section'>
                <div class='doc-section-title-row'>
                    <h2 class='doc-section-title'>{html.escape(section['title'])}</h2>
                </div>
                <div class='doc-section-body'>{markdown_to_html(section['body'])}</div>
            </section>
            """
            for section in sections
        )

    image_markup = ""
    if feature_image_data and feature_image_mime:
        image_markup = (
            f"<div class='doc-feature-image-wrap'><img src='data:{feature_image_mime};base64,{feature_image_data}' alt='{html.escape(title)}' class='doc-feature-image' /></div>"
        )

    rendered_sections_with_image: list[str] = []
    image_inserted = False
    overview_section_titles = {
        "feature overview",
        "vue d’ensemble de la feature",
        "vue d'ensemble de la feature",
        "overview",
    }

    for section in sections:
        section_title = section["title"].strip().lower()
        section_body_html = markdown_to_html(section["body"])
        if image_markup and not image_inserted and section_title in overview_section_titles:
            section_body_html = image_markup + section_body_html
            image_inserted = True

        rendered_sections_with_image.append(
            f"""
            <section class='doc-section'>
                <div class='doc-section-title-row'>
                    <h2 class='doc-section-title'>{html.escape(section['title'])}</h2>
                </div>
                <div class='doc-section-body'>{section_body_html}</div>
            </section>
            """
        )

    rendered_sections = "".join(rendered_sections_with_image)

    if image_markup and not image_inserted:
        rendered_sections = image_markup + rendered_sections

    return f"""
    <style>
        .doc-root {{ background:#f8fafc; padding:24px; border-radius:20px; }}
        .doc-cover {{ background:#eef2ff; color:#1f2937; border:1px solid #c7d2fe; border-radius:18px; padding:24px; margin-bottom:18px; }}
        .doc-cover-subtitle {{ font-size:13px; color:#4b5563; margin-bottom:6px; }}
        .doc-cover-title {{ margin:0; font-size:30px; line-height:1.2; color:#111827; }}
        .doc-cover-meta {{ font-size:13px; color:#6b7280; margin-top:8px; }}
        .doc-section {{ background:#ffffff; border:1px solid #e5e7eb; border-radius:16px; padding:22px; margin-bottom:16px; box-shadow:0 1px 2px rgba(15,23,42,.04); }}
        .doc-section-empty {{ border-style:dashed; }}
        .doc-section-title-row {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }}
        .doc-section-title {{ margin:0; font-size:22px; color:#4b5563; }}
        .doc-section-body {{ color:#374151; line-height:1.65; font-size:15px; }}
        .doc-section-body p {{ margin:0 0 12px 0; }}
        .doc-section-body .doc-h3 {{ margin:18px 0 10px 0; font-size:16px; color:#111827; border-left:4px solid #e5e7eb; padding-left:10px; }}
        .doc-section-body .doc-table {{ width:100%; border-collapse:collapse; margin:14px 0; font-size:14px; overflow:hidden; border-radius:12px; }}
        .doc-section-body .doc-table th {{ background:#111827; color:#ffffff; text-align:left; padding:10px 12px; border:1px solid #1f2937; }}
        .doc-section-body .doc-table td {{ padding:10px 12px; border:1px solid #e5e7eb; vertical-align:top; background:#ffffff; }}
        .doc-section-body .doc-table tr:nth-child(even) td {{ background:#f9fafb; }}
        .doc-section-body .doc-blockquote {{ margin:14px 0; padding:12px 14px; border-left:4px solid #f59e0b; background:#fffbeb; color:#92400e; border-radius:8px; }}
        .doc-section-body .doc-list {{ margin:10px 0 14px 18px; }}
        .doc-section-body .doc-code {{ background:#f3f4f6; padding:2px 6px; border-radius:6px; font-size:13px; }}
        .doc-feature-image-wrap {{ margin:0 0 16px 0; }}
        .doc-feature-image {{ width:100%; max-width:100%; max-height:420px; height:auto; object-fit:contain; border:1px solid #e5e7eb; border-radius:12px; display:block; background:#ffffff; }}
    </style>
    <div class='doc-root'>
        <div class='doc-cover'>
            <div class='doc-cover-subtitle'>{html.escape(subtitle)}</div>
            <h1 class='doc-cover-title'>{html.escape(title)}</h1>
            <div class='doc-cover-meta'>{html.escape(labels['generated_on'])} {html.escape(datetime.now().strftime('%d/%m/%Y %H:%M'))}</div>
        </div>
        {rendered_sections}
    </div>
    """


def build_export_html(
    markdown_text: str,
    title: str,
    subtitle: str,
    analysis: dict[str, Any] | None = None,
    language: str = "fr",
    feature_image_data: str | None = None,
    feature_image_mime: str | None = None,
) -> str:
    body = build_document_html(markdown_text, title, subtitle, analysis, language, feature_image_data, feature_image_mime)
    return f"""
<!DOCTYPE html>
<html lang='fr'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>{html.escape(title)}</title>
</head>
<body style='margin:0;padding:24px;background:#eef2f7;font-family:Roboto,sans-serif;'>
  <div style='max-width:1100px;margin:0 auto;'>
    {body}
  </div>
</body>
</html>
    """


def build_component_library_summary(analysis: dict[str, Any] | None) -> str:
    if not analysis:
        return ""

    feature_groups = analysis.get("feature_groups", [])
    fields = analysis.get("fields", [])
    labels = analysis.get("labels", [])
    placeholders = analysis.get("placeholders", [])

    lines = [
        "# Référence librairie composants projet",
        f"- Nom racine : {analysis.get('root_name', 'Inconnu')}",
        f"- Nombre de noeuds analysés : {analysis.get('node_count', 0)}",
        f"- Types de composants détectés : {', '.join(analysis.get('field_types', [])[:12]) or 'Aucun'}",
        f"- Sections détectées : {', '.join(analysis.get('sections', [])[:12]) or 'Aucune'}",
        f"- Actions détectées : {', '.join(analysis.get('actions', [])[:12]) or 'Aucune'}",
        f"- Labels visibles notables : {' | '.join(labels[:12]) or 'Aucun'}",
        f"- Placeholders notables : {' | '.join(placeholders[:10]) or 'Aucun'}",
        "## Groupes de composants / patterns principaux",
    ]

    if feature_groups:
        for group in feature_groups[:8]:
            lines.append(
                f"- {group.get('label', 'Groupe')} | composants: {group.get('component_count', 0)} | types: {', '.join(group.get('component_types', [])[:6]) or 'Aucun'} | labels: {' | '.join(group.get('labels', [])[:6]) or 'Aucun'}"
            )
    else:
        lines.append("- Aucun groupe notable détecté")

    lines.append("## Composants / champs représentatifs")
    if fields:
        for field in fields[:12]:
            lines.append(
                f"- {field.get('name', 'Champ')} | type: {field.get('type', 'unknown')} | label: {field.get('label', '-')} | placeholder: {field.get('placeholder', '-')}"
            )
    else:
        lines.append("- Aucun composant représentatif détecté")

    lines.extend(
        [
            "## Règle d'utilisation",
            "- Cette librairie doit être utilisée comme référence design system / patterns UI, et non comme preuve qu’un composant est présent dans la feature analysée.",
        ]
    )

    return "\n".join(lines)


def build_context_source_payload(global_json_text: str, global_markdown_text: str) -> tuple[str, Any]:
    json_text = global_json_text.strip()
    markdown_text = global_markdown_text.strip()

    if json_text and markdown_text:
        parsed_json = json.loads(json_text)
        payload = {
            "source_type": "mixed_context",
            "json_context": parsed_json,
            "markdown_context": markdown_text,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2), payload

    if json_text:
        parsed_json = json.loads(json_text)
        return json_text, parsed_json

    if markdown_text:
        payload = {
            "source_type": "markdown_context",
            "markdown_context": markdown_text,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2), payload

    raise ValueError("Aucune source de contexte fournie.")


def _split_markdown_table_row(row: str) -> list[str]:
    normalized = row.strip().strip("|")
    cells: list[str] = []
    current: list[str] = []
    escaped = False

    for char in normalized:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if escaped:
        current.append("\\")

    cells.append("".join(current).strip())
    return cells


def _is_markdown_table_separator(row: str) -> bool:
    cells = _split_markdown_table_row(row)
    if not cells:
        return False
    return all(bool(cell) and re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _escape_markdown_table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _build_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not headers:
        return []
    normalized_rows = []
    column_count = len(headers)
    for row in rows:
        normalized_row = row[:column_count] + [""] * max(0, column_count - len(row))
        normalized_rows.append(normalized_row)
    return [
        "| " + " | ".join(_escape_markdown_table_cell(cell) for cell in headers) + " |",
        "| " + " | ".join(["---"] * column_count) + " |",
        *[
            "| " + " | ".join(_escape_markdown_table_cell(cell) for cell in row) + " |"
            for row in normalized_rows
        ],
    ]


def _repair_structured_section_table(heading: str, section_lines: list[str]) -> list[str]:
    normalized_heading = heading.strip().lower()
    non_empty_lines = [line.strip() for line in section_lines if line.strip()]

    expected_headers_by_heading = {
        "macro layout": ["Zone", "Rôle", "Contenu principal", "Comportement / règles"],
        "structure générale": ["Zone", "Rôle", "Contenu principal", "Comportement / règles"],
        "layout global": ["Zone", "Rôle", "Contenu principal", "Comportement / règles"],
        "présentation des sous-niveaux": ["Niveau", "Point d’entrée", "Contenu affiché", "Interaction / règle"],
        "sub-level presentation": ["Level", "Entry point", "Displayed content", "Interaction / rule"],
        "hypothèses": ["ID", "Hypothèse", "Justification", "Niveau de confiance"],
        "hypotheses": ["ID", "Hypothesis", "Rationale", "Confidence level"],
        "questions ouvertes": ["ID", "Question", "Contexte", "Impact"],
        "liste des écrans": ["Écran", "Rôle", "Accès depuis", "Specs liées"],
        "screen list": ["Screen", "Role", "Accessed from", "Related specs"],
        "glossaire métier": ["Terme", "Définition", "Source"],
        "business glossary": ["Term", "Definition", "Source"],
        "open questions": ["ID", "Question", "Context", "Impact"],
    }
    expected_headers = expected_headers_by_heading.get(normalized_heading)
    if not expected_headers:
        return []

    for index, line in enumerate(non_empty_lines[:-1]):
        if "|" in line and _is_markdown_table_separator(non_empty_lines[index + 1]):
            table_lines = [line, non_empty_lines[index + 1]]
            cursor = index + 2
            while cursor < len(non_empty_lines) and "|" in non_empty_lines[cursor]:
                table_lines.append(non_empty_lines[cursor])
                cursor += 1
            rows = [_split_markdown_table_row(table_line) for table_line in table_lines if table_line.strip()]
            if len(rows) >= 2:
                body_rows = [row for row in rows[2:] if any(cell.strip() for cell in row)]
                return _build_markdown_table(expected_headers, body_rows)

    bullet_rows: list[list[str]] = []
    for item_index, line in enumerate(section_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        normalized = _normalize_docx_bullet_line(stripped)
        if re.match(r"^[+\-*]\s+", stripped):
            if len(expected_headers) == 4 and expected_headers[0] == "ID":
                bullet_rows.append([str(item_index), normalized, "", ""])
            elif len(expected_headers) == 4:
                parts = [part.strip() for part in normalized.split(":", 1)]
                if len(parts) == 2:
                    bullet_rows.append([parts[0], "", parts[1], ""])
                else:
                    bullet_rows.append([normalized, "", "", ""])
        elif ":" in normalized:
            key, value = [part.strip() for part in normalized.split(":", 1)]
            if len(expected_headers) == 4 and expected_headers[0] == "ID":
                bullet_rows.append([str(len(bullet_rows) + 1), key, value, ""])
            else:
                bullet_rows.append([key, "", value, ""])

    if bullet_rows:
        return _build_markdown_table(expected_headers, bullet_rows)

    return []


def _style_docx_document(document: Document) -> None:
    if "Normal" in document.styles:
        normal_style = document.styles["Normal"]
        if not normal_style.font.name:
            normal_style.font.name = "Aptos"
        if not normal_style.font.size:
            normal_style.font.size = Pt(10.5)

    for style_name, size in [("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5), ("Heading 4", 10.5)]:
        if style_name in document.styles:
            style = document.styles[style_name]
            if not style.font.name:
                style.font.name = "Aptos"
            if not style.font.size:
                style.font.size = Pt(size)


def _apply_inline_markdown(paragraph: Any, text: str) -> None:
    parts = re.split(r"(\*\*.*?\*\*|`.*?`|\*.*?\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) >= 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Courier New"
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        else:
            paragraph.add_run(part)


def _style_table_header_cell(cell: Any) -> None:
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True


def _normalize_docx_bullet_line(text: str) -> str:
    return re.sub(r"^[+\-*]\s+", "", text.strip())


def _extract_key_value_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    current_key = ""
    current_value_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = _normalize_docx_bullet_line(line)
        if ":" in normalized:
            if current_key:
                pairs.append((current_key, " ".join(current_value_lines).strip()))
            key, value = normalized.split(":", 1)
            current_key = key.strip()
            current_value_lines = [value.strip()]
        elif current_key:
            current_value_lines.append(normalized)
        else:
            pairs.append((normalized, ""))

    if current_key:
        pairs.append((current_key, " ".join(current_value_lines).strip()))

    return pairs


def _add_key_value_table_to_docx(document: Document, headers: list[str], pairs: list[tuple[str, str]]) -> None:
    if not pairs:
        return

    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for index, header in enumerate(headers):
        paragraph = table.rows[0].cells[index].paragraphs[0]
        _apply_inline_markdown(paragraph, header)
        _style_table_header_cell(table.rows[0].cells[index])

    for key, value in pairs:
        cells = table.add_row().cells
        _apply_inline_markdown(cells[0].paragraphs[0], key)
        if len(headers) > 1:
            _apply_inline_markdown(cells[1].paragraphs[0], value)


def _maybe_add_structured_section_table(document: Document, heading: str, section_lines: list[str]) -> bool:
    normalized_heading = heading.strip().lower()
    inferred_language = "en" if normalized_heading in {"sub-level presentation", "information architecture", "open questions", "assumptions", "hypotheses", "hypotheses / open questions"} else "fr"
    non_empty_lines = [line.strip() for line in section_lines if line.strip()]
    body_text = "\n".join(non_empty_lines)
    pairs = _extract_key_value_pairs(body_text)

    structured_table_sections = {
        "macro layout",
        "structure générale",
        "layout global",
        "sub-level presentation",
        "information architecture",
        "présentation des sous-niveaux",
        "questions ouvertes",
        "open questions",
        "hypothèses",
        "assumptions",
        "hypotheses",
        "hypothèses / questions ouvertes",
        "hypotheses / open questions",
    }

    if normalized_heading in structured_table_sections:
        repaired_table_lines = _repair_structured_section_table(heading, section_lines)
        if repaired_table_lines:
            _add_markdown_table_to_docx(document, repaired_table_lines)
            return True

    if normalized_heading in {"macro layout", "structure générale", "layout global", "sub-level presentation", "information architecture", "présentation des sous-niveaux"}:
        if pairs:
            headers = ["Area / level", "Description"] if inferred_language == "en" else ["Zone / niveau", "Description"]
            _add_key_value_table_to_docx(document, headers, pairs)
            return True

    if normalized_heading in {"questions ouvertes", "open questions", "hypothèses", "assumptions", "hypotheses", "hypothèses / questions ouvertes", "hypotheses / open questions"}:
        if pairs:
            headers = ["Topic", "Detail"] if inferred_language == "en" else ["Sujet", "Détail"]
            _add_key_value_table_to_docx(document, headers, pairs)
            return True
        bullet_items = [
            _normalize_docx_bullet_line(line)
            for line in section_lines
            if re.match(r"^[+\-*]\s+", line.strip())
        ]
        if bullet_items:
            table = document.add_table(rows=1, cols=2)
            table.style = "Table Grid"
            headers = ["ID", "Item"] if inferred_language == "en" else ["ID", "Élément"]
            for index, header in enumerate(headers):
                paragraph = table.rows[0].cells[index].paragraphs[0]
                _apply_inline_markdown(paragraph, header)
                _style_table_header_cell(table.rows[0].cells[index])
            for item_index, item in enumerate(bullet_items, start=1):
                cells = table.add_row().cells
                cells[0].paragraphs[0].add_run(str(item_index))
                _apply_inline_markdown(cells[1].paragraphs[0], item)
            return True

    return False


def _get_docx_style_name(document: Document, preferred: str, fallback: str | None = None) -> str | None:
    if preferred in document.styles:
        return preferred
    if fallback and fallback in document.styles:
        return fallback
    return None


def _add_markdown_table_to_docx(document: Document, table_lines: list[str]) -> None:
    if len(table_lines) < 2:
        return

    rows = [_split_markdown_table_row(line) for line in table_lines if line.strip()]
    if len(rows) < 2:
        return

    header = rows[0]
    body_rows = [row for row in rows[2:] if row]
    if not header:
        return

    column_count = max(
        len(header),
        max((len(row) for row in body_rows), default=0),
    )
    if column_count == 0:
        return

    normalized_header = header + [""] * (column_count - len(header))

    table = document.add_table(rows=1, cols=column_count)
    table_style = _get_docx_style_name(document, "Table Grid")
    if table_style:
        table.style = table_style

    header_cells = table.rows[0].cells
    for index, cell_text in enumerate(normalized_header):
        paragraph = header_cells[index].paragraphs[0]
        _apply_inline_markdown(paragraph, cell_text)
        _style_table_header_cell(header_cells[index])

    for row in body_rows:
        table_row = table.add_row().cells
        normalized_row = row[:column_count] + [""] * max(0, column_count - len(row))
        for index in range(column_count):
            paragraph = table_row[index].paragraphs[0]
            _apply_inline_markdown(paragraph, normalized_row[index])


def _add_code_block_to_docx(document: Document, language: str, code_lines: list[str], diagrams: dict[str, bytes]) -> None:
    image = diagrams.get("\n".join(code_lines).strip()) if language == "mermaid" else None
    if image is not None:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(io.BytesIO(image), width=Inches(6.0))
        return
    for code_line in code_lines:
        run = document.add_paragraph().add_run(code_line)
        run.font.name = "Consolas"
        run.font.size = Pt(9)


def _append_markdown_to_docx_document(document: Document, markdown_text: str, diagrams: dict[str, bytes] | None = None) -> None:
    lines = markdown_text.splitlines()
    index = 0
    current_section_heading = ""
    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            language = stripped[3:].strip().lower()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index].rstrip())
                index += 1
            index += 1  # closing fence
            _add_code_block_to_docx(document, language, code_lines, diagrams or {})
            continue

        if not stripped:
            document.add_paragraph("")
            index += 1
            continue

        if "|" in stripped and index + 1 < len(lines) and _is_markdown_table_separator(lines[index + 1]):
            table_lines = [stripped, lines[index + 1].strip()]
            index += 2
            while index < len(lines) and "|" in lines[index]:
                candidate = lines[index].strip()
                if not candidate:
                    break
                table_lines.append(candidate)
                index += 1
            _add_markdown_table_to_docx(document, table_lines)
            continue

        if stripped.startswith("### "):
            heading_text = stripped[4:].strip()
            heading_style = _get_docx_style_name(document, "Heading 3")
            document.add_paragraph(heading_text, style=heading_style)
            current_section_heading = heading_text

            section_lines: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor].rstrip()
                candidate_stripped = candidate.strip()
                if candidate_stripped.startswith("### ") or candidate_stripped.startswith("## ") or candidate_stripped.startswith("# "):
                    break
                section_lines.append(candidate)
                cursor += 1

            if _maybe_add_structured_section_table(document, current_section_heading, section_lines):
                index = cursor
                continue
        elif stripped.startswith("## "):
            heading_text = stripped[3:].strip()
            heading_style = _get_docx_style_name(document, "Heading 2")
            document.add_paragraph(heading_text, style=heading_style)
            current_section_heading = heading_text

            section_lines = []
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor].rstrip()
                candidate_stripped = candidate.strip()
                if candidate_stripped.startswith("## ") or candidate_stripped.startswith("# "):
                    break
                section_lines.append(candidate)
                cursor += 1

            if _maybe_add_structured_section_table(document, current_section_heading, section_lines):
                index = cursor
                continue
        elif stripped.startswith("# "):
            heading_text = stripped[2:].strip()
            heading_style = _get_docx_style_name(document, "Heading 1")
            document.add_paragraph(heading_text, style=heading_style)
            current_section_heading = heading_text
        elif re.match(r"^[+\-*]\s+", stripped):
            bullet_style = _get_docx_style_name(document, "List Bullet")
            paragraph = document.add_paragraph(style=bullet_style)
            _apply_inline_markdown(paragraph, _normalize_docx_bullet_line(stripped))
        elif re.match(r"^\d+\.\s+", stripped):
            number_style = _get_docx_style_name(document, "List Number")
            paragraph = document.add_paragraph(style=number_style)
            _apply_inline_markdown(paragraph, re.sub(r"^\d+\.\s+", "", stripped))
        elif stripped.startswith(">"):
            paragraph = document.add_paragraph()
            _apply_inline_markdown(paragraph, stripped.lstrip("> "))
        else:
            paragraph = document.add_paragraph()
            _apply_inline_markdown(paragraph, stripped)

        index += 1


def build_docx_bytes(
    markdown_text: str,
    title: str,
    subtitle: str,
    language: str = "fr",
    feature_image_bytes: bytes | None = None,
    diagrams: dict[str, bytes] | None = None,
) -> bytes:
    labels = get_ui_labels(language)
    document = Document()
    _style_docx_document(document)

    title_paragraph = document.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_paragraph.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(22)
    title_run.font.color.rgb = RGBColor(17, 24, 39)

    subtitle_paragraph = document.add_paragraph()
    subtitle_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle_paragraph.add_run(subtitle)
    subtitle_run.italic = True
    subtitle_run.font.size = Pt(10.5)
    subtitle_run.font.color.rgb = RGBColor(75, 85, 99)

    date_paragraph = document.add_paragraph()
    date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_paragraph.add_run(f"{labels['generated_on']} {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    date_run.font.size = Pt(9)
    date_run.font.color.rgb = RGBColor(107, 114, 128)

    document.add_paragraph("")

    if feature_image_bytes:
        image_paragraph = document.add_paragraph()
        image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        image_stream = io.BytesIO(feature_image_bytes)
        image_paragraph.add_run().add_picture(image_stream, width=Inches(6.3))
        document.add_paragraph("")

    _append_markdown_to_docx_document(document, markdown_text, diagrams)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


CONTENT_TAG = "{{CONTENT}}"
_LEFTOVER_TAG = re.compile(r"^\s*\{\{[A-Z0-9_]+\}\}\s*$")
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _iter_all_paragraphs(container: Any) -> list[Paragraph]:
    paragraphs: list[Paragraph] = list(getattr(container, "paragraphs", []))
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(_iter_all_paragraphs(cell))
    return paragraphs


def _iter_document_paragraphs(document: Document) -> list[Paragraph]:
    paragraphs = _iter_all_paragraphs(document)
    for section in document.sections:
        for part in (section.header, section.footer, section.first_page_header, section.first_page_footer):
            paragraphs.extend(_iter_all_paragraphs(part))
    return paragraphs


def _is_in_body(paragraph: Paragraph, body: Any) -> bool:
    element = paragraph._p.getparent()
    while element is not None:
        if element is body:
            return True
        element = element.getparent()
    return False


def _replace_tag_in_paragraph(paragraph: Paragraph, tag: str, value: str) -> None:
    """Replaces a tag even when Word split it across runs, keeping the first run's formatting."""
    runs = paragraph.runs
    if not runs:
        return
    full_text = "".join(run.text for run in runs)
    runs[0].text = full_text.replace(tag, value)
    for run in runs[1:]:
        run.text = ""


def _shift_headings_up(markdown_text: str) -> str:
    """Drops the H1 (already on the cover page) and promotes ## to #, ### to ##…"""
    lines = []
    for line in markdown_text.splitlines():
        if re.match(r"^#\s+", line):
            continue
        lines.append(line[1:] if re.match(r"^#{2,6}\s+", line) else line)
    return "\n".join(lines)


def _append_content(document: Document, markdown_text: str, image_bytes: bytes | None, diagrams: dict[str, bytes] | None = None) -> None:
    """Writes the document; the optional image goes right under the first section heading."""
    if not image_bytes:
        _append_markdown_to_docx_document(document, markdown_text, diagrams)
        return
    match = re.search(r"^##?\s+.+$", markdown_text, flags=re.MULTILINE)
    split_at = match.end() if match else 0
    _append_markdown_to_docx_document(document, markdown_text[:split_at], diagrams)
    image_paragraph = document.add_paragraph()
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.add_run().add_picture(io.BytesIO(image_bytes), width=Inches(6.0))
    _append_markdown_to_docx_document(document, markdown_text[split_at:], diagrams)


def _request_fields_update(document: Document) -> None:
    """Asks Word to refresh the table of contents when the file is opened."""
    if "TOC" not in "".join(document.element.body.itertext()):
        return
    settings = document.settings.element
    if settings.find(f"{{{_W_NS}}}updateFields") is None:
        update = settings.makeelement(f"{{{_W_NS}}}updateFields", {f"{{{_W_NS}}}val": "true"})
        settings.append(update)


def render_docx_template(
    template_path: str,
    markdown_text: str,
    title: str,
    subtitle: str,
    language: str = "fr",
    image_bytes: bytes | None = None,
    diagrams: dict[str, bytes] | None = None,
) -> bytes:
    """Fills a Word template.

    The template keeps its cover page, headers/footers, tables and styles. The
    generated document is written where the {{CONTENT}} paragraph is (at the end
    when there is none). {{DOC_TITLE}}, {{DOC_SUBTITLE}} and {{GENERATED_ON}} are
    replaced anywhere (page headers included); when {{DOC_TITLE}} is in the body
    (cover page), the document's own H1 is not repeated and its sections become
    Heading 1.
    """
    document = Document(template_path)
    body = document.element.body
    tags = {
        "{{DOC_TITLE}}": title,
        "{{DOC_SUBTITLE}}": subtitle,
        "{{GENERATED_ON}}": f"{get_ui_labels(language)['generated_on']} {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    }

    anchor: Paragraph | None = None
    title_placed = False
    for paragraph in _iter_document_paragraphs(document):
        text = paragraph.text
        if CONTENT_TAG in text and anchor is None and paragraph._p.getparent() is body:
            anchor = paragraph
            continue
        for tag, value in tags.items():
            if tag in "".join(run.text for run in paragraph.runs):
                _replace_tag_in_paragraph(paragraph, tag, value)
                # A title in the page header is a running title, not a cover page title.
                title_placed = title_placed or (tag == "{{DOC_TITLE}}" and _is_in_body(paragraph, body))
        if anchor is None and _LEFTOVER_TAG.match(paragraph.text) and paragraph._p.getparent() is body:
            # Older templates: drop unknown placeholders instead of printing them.
            body.remove(paragraph._p)

    content = _shift_headings_up(markdown_text) if title_placed else markdown_text
    def content_elements() -> list[Any]:
        return [element for element in body.iterchildren() if not element.tag.endswith("sectPr")]

    count_before = len(content_elements())
    _append_content(document, content, image_bytes, diagrams)

    if anchor is not None:
        # python-docx appends before the final sectPr: the new elements are the last ones.
        for element in content_elements()[count_before:]:
            anchor._p.addprevious(element)
        body.remove(anchor._p)

    _request_fields_update(document)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def build_docx_from_template(
    markdown_text: str,
    title: str,
    subtitle: str,
    language: str = "fr",
    feature_image_bytes: bytes | None = None,
    diagrams: dict[str, bytes] | None = None,
) -> bytes:
    template_path = _template_path(SPEC_DOCX_TEMPLATES.get(language, SPEC_DOCX_TEMPLATES["fr"]))
    try:
        return render_docx_template(template_path, markdown_text, title, subtitle, language, feature_image_bytes, diagrams)
    except Exception:
        return build_docx_bytes(
            markdown_text=markdown_text, title=title, subtitle=subtitle, language=language,
            feature_image_bytes=feature_image_bytes, diagrams=diagrams,
        )


def build_context_docx_from_template(
    markdown_text: str,
    title: str,
    subtitle: str,
    language: str = "fr",
    diagrams: dict[str, bytes] | None = None,
) -> bytes:
    template_path = _template_path(CONTEXT_DOCX_TEMPLATES.get(language, CONTEXT_DOCX_TEMPLATES["fr"]))
    try:
        return render_docx_template(template_path, markdown_text, title, subtitle, language, diagrams=diagrams)
    except Exception:
        return build_docx_bytes(markdown_text=markdown_text, title=title, subtitle=subtitle, language=language, diagrams=diagrams)


def is_timeout_error(exc: Exception) -> bool:
    error_message = str(exc)
    return (
        "504" in error_message
        or "Gateway Time-out" in error_message
        or "Gateway Timeout" in error_message
        or "timed out" in error_message.lower()
    )


def format_generation_error(exc: Exception) -> str:
    error_message = str(exc)
    if is_timeout_error(exc):
        return (
            "Le service IA a dépassé le temps de réponse autorisé (erreur 504). "
            "Le timeout client a été augmenté, mais la requête reste probablement trop lourde côté serveur. "
            "Essayez de réduire la taille du JSON, de simplifier la description, ou de relancer la génération."
        )
    return error_message


def get_context_document_subtitle(language: str) -> str:
    if language == "en":
        return "Document type: UX Architecture / Global application context"
    return "Type de document : Architecture UX / Contexte global application"


def get_context_default_title(language: str) -> str:
    if language == "en":
        return "UX Architecture / Project overview"
    return "Architecture UX / Project overview"


def get_spec_document_subtitle(language: str) -> str:
    if language == "en":
        return "Document type: Detailed UX / HMI specification"
    return "Type de document : Spécification UX / HMI détaillée"


def get_spec_default_title(language: str) -> str:
    if language == "en":
        return "UX / HMI Specification"
    return "Spécification UX / HMI"

