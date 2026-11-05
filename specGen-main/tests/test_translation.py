"""Translation of a generated document after the generation."""
from __future__ import annotations

from translation import split_markdown, structure_differences, structure_of

DOCUMENT = """# Spécification

## Écran de connexion

Texte d'introduction.

| Élément | Comportement |
| --- | --- |
| Bouton « Valider » | Envoie le formulaire |

## Parcours

```mermaid
flowchart TD
    A[Connexion] --> B[Accueil]
```

## Erreurs

- Mot de passe incorrect
"""

TRANSLATED = """# Specification

## Login screen

Introduction text.

| Element | Behavior |
| --- | --- |
| « Valider » button | Submits the form |

## Flow

```mermaid
flowchart TD
    A[Login] --> B[Home]
```

## Errors

- Wrong password
"""


def test_split_keeps_everything_and_never_cuts_code_or_tables():
    long_section = "## Tableau\n\n| A | B |\n| --- | --- |\n" + "\n".join(f"| ligne {i} | valeur |" for i in range(200))
    document = DOCUMENT + "\n" + long_section + "\n\n```json\n# pas un titre\n```\n"
    chunks = split_markdown(document, max_chars=300)
    assert len(chunks) > 1
    assert "\n".join(chunks).replace("\n", "") == document.rstrip("\n").replace("\n", "")
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0
    # The heading-like line inside the code block is not a cut point.
    assert not any(chunk.startswith("# pas un titre") for chunk in chunks)


def test_structure_counts_ignore_code_blocks():
    assert structure_of(DOCUMENT) == {"headings": 4, "table_rows": 3, "code_blocks": 1}
    assert structure_differences(DOCUMENT, TRANSLATED) == []
    assert structure_differences(DOCUMENT, "# Spec\n") != []


def test_translate_endpoint(client, fake_llm):
    fake_llm.queue(TRANSLATED)
    response = client.post("/api/translate/spec", json={"markdown": DOCUMENT, "target_language": "en"})
    assert response.status_code == 200
    body = response.json()
    assert body["markdown"] == TRANSLATED
    assert body["language"] == "en"
    assert body["warnings"] == []
    assert "into English" in fake_llm.system_prompt()
    assert "Bouton « Valider »" in fake_llm.user_prompt()


def test_translate_retries_once_when_the_structure_changes(client, fake_llm):
    fake_llm.queue("# Specification\n\nShortened.\n", "```markdown\n" + TRANSLATED + "```")
    body = client.post("/api/translate/context", json={"markdown": DOCUMENT, "target_language": "en"}).json()
    assert body["markdown"] == TRANSLATED
    assert body["warnings"] == []
    assert len(fake_llm.calls) == 2
    assert "does not keep the structure" in fake_llm.calls[1]["messages"][-1]["content"]


def test_translate_warns_when_the_structure_is_still_wrong(client, fake_llm):
    fake_llm.queue("# Spécification\n", "# Spécification\n")
    body = client.post("/api/translate/spec", json={"markdown": DOCUMENT, "target_language": "fr"}).json()
    assert len(body["warnings"]) == 1
    assert "Traduction à relire" in body["warnings"][0]
    assert "into French" in fake_llm.system_prompt()


def test_translate_rejects_empty_document(client, fake_llm):
    assert client.post("/api/translate/spec", json={"markdown": "  ", "target_language": "en"}).status_code == 400
