"""Translation of a generated document after generation (the model is faked)."""

import translator

CONTEXT_FR = """# Vue d’ensemble du projet

## Personas

| Persona | Objectifs |
|---|---|
| Opératrice | Suivre les alertes |

# Parcours utilisateur

```mermaid
flowchart LR
  A["Accueil"] --> B["Détail"]
```

1. L’utilisateur ouvre l’accueil → le système affiche les alertes.
"""


def test_translation_keeps_diagrams_and_uses_the_fixed_vocabulary(fake_llm, client):
    fake_llm.queue(
        "# Project overview\n\n## Personas\n\n| Persona | Goals |\n|---|---|\n| Operator | Track alerts<br>Act fast |\n\n"
        "# User flow\n\n@@BLOCK_0@@\n\n1. The user opens the home page → the system shows the alerts.\n",
        'flowchart LR\n  A["Home"] --> B["Detail"]',
    )
    response = client.post(
        "/api/translate", json={"markdown": CONTEXT_FR, "kind": "context", "source_language": "fr", "target_language": "en"}
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert '```mermaid\nflowchart LR\n  A["Home"] --> B["Detail"]\n```' in markdown
    assert "| Operator | Track alerts; Act fast |" in markdown and "<br>" not in markdown
    # The diagram code never goes through the general prompt.
    assert "flowchart" not in fake_llm.user_prompt(0) and "@@BLOCK_0@@" in fake_llm.user_prompt(0)
    assert "Parcours utilisateur → User flow" in fake_llm.system_prompt(0)
    assert "Élevé → High" in fake_llm.system_prompt(0)


def test_a_dropped_placeholder_keeps_the_original_diagram(fake_llm, client):
    fake_llm.queue("# Project overview\n\n# User flow\n\nNo diagram here.\n", "not mermaid at all")
    markdown = client.post(
        "/api/translate", json={"markdown": CONTEXT_FR, "kind": "context", "target_language": "en"}
    ).json()["markdown"]
    assert '```mermaid\nflowchart LR\n  A["Accueil"] --> B["Détail"]\n```' in markdown


def test_spec_glossary_and_same_language_refused(fake_llm, client):
    assert ("Assumptions", "Hypothèses") in [(en, fr) for fr, en in translator.glossary("spec")]
    response = client.post("/api/translate", json={"markdown": "# X", "kind": "spec", "source_language": "en", "target_language": "en"})
    assert response.status_code == 400


def test_long_documents_are_translated_in_several_parts(fake_llm, client):
    sections = "".join(f"## Section {i}\n\n{'Texte. ' * 400}\n\n" for i in range(4))
    client.post("/api/translate", json={"markdown": f"# Titre\n\n{sections}", "kind": "spec", "target_language": "en"})
    assert len(fake_llm.calls) > 1
    assert all(len(call["messages"][1]["content"]) <= translator.MAX_CHUNK_CHARS for call in fake_llm.calls)
