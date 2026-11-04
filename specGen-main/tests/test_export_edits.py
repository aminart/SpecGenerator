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
