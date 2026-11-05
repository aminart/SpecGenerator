"""Exports take the Markdown the user edited in the app, in the shape the in-place editor writes it."""

import io

from docx import Document

EDITED_SPEC = """# Spécification Connexion

## Vue d’ensemble

L’écran permet de **se connecter**. Paragraphe ajouté à la main.

## Détail de la feature

| ID | Composant Figma | Comportement |
| --- | --- | --- |
| #1 | Input/Email | Champ obligatoire \\| requis |
|  |  |  |

- Premier point
- Second point
  - Sous-point
"""


def test_exports_use_the_edited_markdown(client):
    markdown = client.post("/api/export/spec/md", json={"markdown": EDITED_SPEC})
    assert markdown.content.decode("utf-8") == EDITED_SPEC

    html = client.post("/api/export/spec/html", json={"markdown": EDITED_SPEC}).text
    assert "Paragraphe ajouté à la main." in html
    assert "Champ obligatoire | requis" in html

    docx = client.post("/api/export/spec/docx", json={"markdown": EDITED_SPEC})
    document = Document(io.BytesIO(docx.content))
    assert any("Paragraphe ajouté à la main." in paragraph.text for paragraph in document.paragraphs)
    cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    assert "Champ obligatoire | requis" in cells


def test_exports_never_contain_html_breaks(client):
    markdown = "# Contexte\n\n## Personas\n\n| Persona | Objectifs |\n|---|---|\n| Opératrice | Suivre<br>Agir |\n"
    exported = client.post("/api/export/context/md", json={"markdown": markdown}).content.decode("utf-8")
    assert "<br>" not in exported and "Suivre ; Agir" in exported

    html = client.post("/api/export/context/html", json={"markdown": markdown}).text
    assert "&lt;br&gt;" not in html and "<br>" not in html.split("<body", 1)[-1].split("Opératrice", 1)[-1].split("</table>")[0]

    docx = client.post("/api/export/context/docx", json={"markdown": markdown})
    cells = [cell.text for table in Document(io.BytesIO(docx.content)).tables for row in table.rows for cell in row.cells]
    assert "Suivre ; Agir" in cells
