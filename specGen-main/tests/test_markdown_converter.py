"""Conversion des documents en Markdown, sans la détection de type de MarkItDown (Magika)."""
import io

import docx
import openpyxl

from markdown_converter import convert_to_markdown


def _xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Écrans"
    ws.append(["Nom", "Statut", "Nb"])
    ws.append(["Accueil", "OK", 3])
    ws.append(["Profil", None, 4.5])
    wb.create_sheet("Vide")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_une_table_par_feuille_sans_nan():
    md = convert_to_markdown(_xlsx(), ".xlsx")
    assert "## Écrans" in md and "| Nom | Statut | Nb |" in md
    assert "| Accueil | OK | 3 |" in md and "| Profil |  | 4.5 |" in md
    assert "NaN" not in md and "Unnamed" not in md
    assert "## Vide" in md


def test_texte_utf8_et_windows():
    assert convert_to_markdown("Écran d'accueil".encode("utf-8"), ".txt") == "Écran d'accueil\n"
    assert convert_to_markdown("Écran d'accueil".encode("cp1252"), ".txt") == "Écran d'accueil\n"


def test_docx_titres_et_tableaux():
    d = docx.Document()
    d.add_heading("Titre principal", 1)
    t = d.add_table(rows=2, cols=1)
    t.cell(0, 0).text, t.cell(1, 0).text = "A", "1"
    buf = io.BytesIO()
    d.save(buf)
    md = convert_to_markdown(buf.getvalue(), ".docx")
    assert md.startswith("# Titre principal") and "| A |" in md


def test_html():
    assert convert_to_markdown(b"<h1>Titre</h1><p>Texte <b>gras</b></p>", ".html") == "# Titre\n\nTexte **gras**\n"
