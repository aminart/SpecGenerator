import io
import json
import zipfile

import pytest

from mapline_converter import NotAMaplineFile, convert_mapline


def test_json_tree_becomes_nested_list():
    data = {"title": "Parcours", "children": [
        {"title": "Connexion", "note": "SSO", "children": [{"title": "Mot de passe oublié"}]},
        {"name": "Tableau de bord"},
    ]}
    md = convert_mapline(json.dumps(data).encode(), "carte")
    assert md.startswith("# carte\n")
    assert "- Parcours\n  - Connexion\n    - _note_ : SSO\n    - Mot de passe oublié\n  - Tableau de bord" in md


def test_json_without_node_shape_lists_fields():
    md = convert_mapline(json.dumps({"version": 2, "author": "A"}).encode())
    assert "- **version** : 2" in md and "- **author** : A" in md


def test_xml_outline():
    xml = b'<map><node text="Racine"><node text="Enfant"/></node></map>'
    assert "- Racine\n  - Enfant" in convert_mapline(xml)


def test_zip_with_json_entry():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content.json", json.dumps({"label": "Dans le zip"}))
    assert "- Dans le zip" in convert_mapline(buffer.getvalue())


def test_plain_text_kept():
    assert "ligne 1\nligne 2" in convert_mapline("ligne 1\nligne 2".encode())


def test_empty_file_rejected():
    with pytest.raises(NotAMaplineFile):
        convert_mapline(b"   ")


def test_api_accepts_mapline(client):
    response = client.post(
        "/api/markdown/convert",
        files={"file": ("plan.mapline", json.dumps({"title": "Étape"}).encode(), "application/octet-stream")},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "plan.md"
    assert "- Étape" in response.json()["markdown"]


def test_api_empty_mapline_is_422(client):
    response = client.post("/api/markdown/convert", files={"file": ("vide.mapline", b"", "application/octet-stream")})
    assert response.status_code == 422
