"""Regenerates fixtures/app_document.json and fixtures/login_screen.json: a small Figma-like export (REST API shape) with
the signals SpecGen reads: variants, hidden layer, prototype interaction, component set,
plus the geometry and styling noise a real export carries. Run: python tests/make_fixture.py"""
import json
from pathlib import Path

GEOMETRY = {
    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 100, "height": 40},
    "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}],
    "strokes": [],
    "effects": [],
    "blendMode": "PASS_THROUGH",
}


def node(identifier, name, kind, children=None, **extra):
    value = {"id": identifier, "name": name, "type": kind, **GEOMETRY, **extra}
    if children is not None:
        value["children"] = children
    return value


def text(identifier, name, characters, **extra):
    return node(identifier, name, "TEXT", characters=characters, **extra)


login = node("1:1", "Login screen", "FRAME", [
    node("2:1", "Header", "FRAME", [text("2:2", "Title", "Connexion"), node("2:3", "Logo", "VECTOR")]),
    node("3:1", "Form", "FRAME", [
        node("3:2", "Input email", "INSTANCE", [text("3:3", "Label", "Email")],
             componentProperties={"State": {"type": "VARIANT", "value": "Default"}, "Show helper#12:3": {"type": "BOOLEAN", "value": False}}),
        node("3:4", "Input password", "INSTANCE", [text("3:5", "Label", "Mot de passe")],
             componentProperties={"State": {"type": "VARIANT", "value": "Focused"}}),
        text("3:6", "Error message", "Identifiants invalides", visible=False),
        node("3:7", "Button/Primary", "INSTANCE", [text("3:8", "Label", "Se connecter")],
             componentProperties={"Type": {"type": "VARIANT", "value": "Primary"}},
             reactions=[{"trigger": {"type": "ON_CLICK"}, "actions": [{"type": "NODE", "destinationId": "9:1", "navigation": "NAVIGATE"}]}]),
    ]),
    node("4:1", "Footer", "FRAME", [text("4:2", "Link", "Mot de passe oublié ?")]),
])
document = {"document": node("0:0", "Document", "DOCUMENT", [node("0:1", "Page 1", "CANVAS", [
    login,
    node("9:1", "Home", "FRAME", [text("9:2", "Title", "Accueil")]),
    node("5:1", "Button", "COMPONENT_SET", [node("5:2", "Type=Primary", "COMPONENT", [])],
         componentPropertyDefinitions={"Type": {"type": "VARIANT", "variantOptions": ["Primary", "Secondary", "Ghost"]},
                                       "State": {"type": "VARIANT", "variantOptions": ["Default", "Hover", "Disabled"]}}),
])])}

out = Path(__file__).parent / "fixtures" / "app_document.json"
out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
(out.parent / "login_screen.json").write_text(json.dumps(login, ensure_ascii=False, indent=2), encoding="utf-8")
