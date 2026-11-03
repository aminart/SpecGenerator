import json

from conftest import GOOD_SPEC_FR

CONTEXT = "# Projet\nApplication de connexion CONTEXTE_UNIQUE"


def test_spec_prompt_holds_each_source_once(fake_llm, client, login_screen):
    fake_llm.queue(GOOD_SPEC_FR)
    response = client.post("/api/spec/generate", json={"spec_json": login_screen, "business_context": CONTEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == [] and body["corrected"] is False
    prompt = fake_llm.user_prompt()
    assert prompt.count("CONTEXTE_UNIQUE") == 1
    assert "<screen_json>" in prompt and "Identifiants invalides" in prompt
    assert "Niveau détaillé" in prompt  # detailed by default
    assert fake_llm.system_prompt().startswith("Vous êtes")  # French instructions for a French output


def test_spec_correction_pass(fake_llm, client, login_screen):
    bad = GOOD_SPEC_FR.replace("## Questions ouvertes\n", "").replace("| #2 | Button/Primary |", "| #2 | Bouton Annuler |")
    fake_llm.queue(bad, GOOD_SPEC_FR)
    body = client.post("/api/spec/generate", json={"spec_json": login_screen}).json()
    assert body["corrected"] is True and body["warnings"] == []
    feedback = fake_llm.calls[1]["messages"][-1]["content"]
    assert "Titre manquant : ## Questions ouvertes" in feedback and "Bouton Annuler" in feedback
    assert fake_llm.calls[1]["temperature"] == 0


def test_spec_warnings_when_the_correction_fails(fake_llm, client, login_screen):
    bad = GOOD_SPEC_FR.replace("| Identifiants invalides |", "| Mot de passe incorrect |")
    fake_llm.queue(bad, bad)
    body = client.post("/api/spec/generate", json={"spec_json": login_screen}).json()
    assert body["warnings"] == ["Texte absent du JSON : « Mot de passe incorrect » (peut-être reformulé ou inventé)"]


def _feature_zone(app_document):
    """The app document with enough content in its zones to be classified as a feature zone."""
    frame = app_document["document"]["children"][0]["children"][0]
    form = frame["children"][1]
    form["children"] += [{"name": f"Field {i}", "type": "TEXT", "characters": f"Champ {i}"} for i in range(10)]
    frame["children"].append(
        {"name": "Panel", "type": "FRAME", "children": [{"name": n, "type": "TEXT", "characters": n} for n in "ABC"]}
    )
    return app_document


def test_feature_zone_gets_an_inventory_pass(fake_llm, client, app_document):
    app_document = _feature_zone(app_document)
    inventory = {"zones": [{"name": "Form", "components": [{"figma_name": "Input email"}, {"figma_name": "Invented"}]}]}
    fake_llm.queue("```json\n" + json.dumps(inventory) + "\n```", GOOD_SPEC_FR)
    body = client.post("/api/spec/generate", json={"spec_json": app_document}).json()
    assert body["scope"]["scope"] == "feature_zone" and body["inventory"] is True
    assert fake_llm.calls[0]["response_format"] == {"type": "json_object"}
    writing_prompt = fake_llm.user_prompt(1)
    assert "<component_inventory>" in writing_prompt and "Invented" not in writing_prompt


def test_context_prompt_and_correction(fake_llm, client, app_document):
    fake_llm.queue("# Vue d’ensemble du projet\n", "# Vue d’ensemble du projet\n")
    response = client.post(
        "/api/context/generate",
        json={
            "json_sources": [{"name": "app.json", "content": app_document}],
            "markdown_sources": [{"name": "brief.md", "content": CONTEXT}],
            "designer_description": "NOTE_DESIGNER",
        },
    )
    assert response.status_code == 200
    prompt = fake_llm.user_prompt()
    assert prompt.count("CONTEXTE_UNIQUE") == 1 and prompt.count("NOTE_DESIGNER") == 1
    assert "<application_json>" in prompt and "ON_CLICK: NAVIGATE → Home" in prompt
    assert len(fake_llm.calls) == 2  # incomplete document: one correction pass
    assert any(warning.startswith("Titre manquant") for warning in response.json()["warnings"])


def test_mermaid_fix_from_the_frontend_error(fake_llm, client):
    fake_llm.queue("flowchart TD\n  A --> B")
    body = client.post(
        "/api/context/mermaid",
        json={"markdown": "# x", "previous_code": "flowchart TD\n  A -->", "error": "Parse error on line 2"},
    ).json()
    assert body["mermaid"] == "flowchart TD\n  A --> B"
    assert "Parse error on line 2" in fake_llm.calls[0]["messages"][-1]["content"]


def test_invalid_mermaid_is_fixed_once(fake_llm, client):
    fake_llm.queue("```mermaid\nflowchart TD\n  A[Start --> B\n```", "flowchart TD\n  A[Start] --> B")
    assert client.post("/api/context/mermaid", json={"markdown": "# x"}).json()["mermaid"] == "flowchart TD\n  A[Start] --> B"


def test_exports(client):
    for kind in ("spec", "context"):
        for fmt in ("md", "html", "docx"):
            response = client.post(f"/api/export/{kind}/{fmt}", json={"markdown": GOOD_SPEC_FR})
            assert response.status_code == 200, (kind, fmt)
            assert response.content
