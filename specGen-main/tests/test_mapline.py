import json
from pathlib import Path

import pytest

from mapline_converter import NotAMaplineFile, convert_mapline

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def project_md():
    return convert_mapline((FIXTURES / "reservation.mapline").read_bytes(), "reservation")


def test_project_title_and_documents(project_md):
    assert project_md.startswith("# Réservation en ligne\n")
    assert "## Carte : Parcours patient" in project_md
    assert "## Flow : Prise de rendez-vous" in project_md
    assert "## Persona : Patient — Réserve depuis son téléphone, souvent pressé" in project_md


def test_mission_map_steps_phases_personas(project_md):
    assert "**Objectif** : Permettre à un patient de réserver une consultation en moins de 3 minutes" in project_md
    assert "### Phase : Avant la visite\n\n#### Étape 1 : Découverte" in project_md
    assert "### Phase : Pendant\n\n#### Étape 4 : Consultation" in project_md
    # Two slots of one step: both activities under the persona, in order.
    assert "- **Patient**\n  - Choisit un créneau\n  - Renseigne ses informations\n- **Secrétaire**" in project_md
    assert "_Storyboard_ : Compare les créneaux affichés sur la page du cabinet" in project_md
    assert "- **Choisit un créneau** → **Renseigne ses informations**" in project_md
    assert "data:image" not in project_md


def test_flow_mermaid_and_transitions(project_md):
    flow = project_md.split("## Flow")[1].split("## Persona :")[0]
    assert "_Détaille l'étape « Prise de rendez-vous »._" in flow
    assert "**Objectifs** : Réserver sans créer de compte" in flow
    assert "```mermaid\nflowchart LR" in flow
    assert '{"Patient connu ?"}' in flow and '(["Début"])' in flow
    assert "-->|Oui|" in flow
    assert "- **Patient connu ?** → **Saisit ses coordonnées** : Non" in flow
    assert "- **Patient connu ?** `irritant`\n  - Commentaire : Vérifier par e-mail ou téléphone" in flow


def test_persona_sheet(project_md):
    sheet = project_md.split("## Persona :")[1]
    assert "- **Âge** : 34 ans" in sheet
    assert "> Je veux réserver en deux minutes, entre deux réunions." in sheet
    assert "### Frustrations\n\n- Les sites qui imposent un compte" in sheet
    assert "- Aisance numérique : 80 %" in sheet
    assert "### Canaux et outils" not in sheet  # empty block left out


def test_version_1_missionmap_file():
    md = convert_mapline((FIXTURES / "projet-v0.9.missionmap").read_bytes())
    assert md.startswith("# Projet 0.9\n")
    assert "- **Client**\n  - Activité héritée `irritant`" in md


def test_alternative_card_and_note():
    data = {
        "version": 2, "title": "", "docs": [{"id": "m", "kind": "mission-map", "name": "", "map": {
            "steps": [{"id": "s", "title": "Paiement", "slots": ["k"]}],
            "personas": [{"id": "p", "name": "Client"}],
            "activities": {"p:k": {"id": "a", "text": "Paie par carte", "note": "3-D Secure"},
                           "p:k:b": {"id": "b", "text": "Paie par virement", "kind": "choice"}},
            "textRows": [{"id": "r", "title": "Canal", "cells": {"s": "Web"}}],
        }}],
    }
    md = convert_mapline(json.dumps(data).encode(), "paiement")
    assert md.startswith("# paiement\n")
    assert "  - Paie par carte\n    - Commentaire : 3-D Secure\n  - _ou_ Décision : Paie par virement" in md
    assert "- _Canal_ : Web" in md


@pytest.mark.parametrize(("content", "message"), [
    (b"pas du json", "JSON illisible"),
    (b"[]", "pas un projet Mapline"),
    (b'{"version": 3, "docs": []}', "plus récente"),
    (b'{"version": 2, "docs": []}', "aucun document"),
])
def test_invalid_files(content, message):
    with pytest.raises(NotAMaplineFile, match=message):
        convert_mapline(content)


def test_api_accepts_mapline(client):
    response = client.post(
        "/api/markdown/convert",
        files={"file": ("reservation.mapline", (FIXTURES / "reservation.mapline").read_bytes(), "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "reservation.md"
    assert "## Carte : Parcours patient" in response.json()["markdown"]


def test_api_invalid_mapline_is_422(client):
    response = client.post("/api/markdown/convert", files={"file": ("vide.mapline", b"", "application/json")})
    assert response.status_code == 422
    assert "vide.mapline" in response.json()["detail"]
