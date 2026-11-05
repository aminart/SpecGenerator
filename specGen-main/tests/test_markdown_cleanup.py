from markdown_cleanup import remove_html_breaks, replace_json_paths_with_names, unwrap_markdown_fence


def test_unwraps_a_fenced_document():
    assert unwrap_markdown_fence("```markdown\n# Titre\n\nTexte\n```") == "# Titre\n\nTexte\n"


def test_keeps_an_unfenced_document():
    assert unwrap_markdown_fence("# Titre\n") == "# Titre\n"


def test_json_paths_become_layer_names(login_screen):
    markdown = "| #1 | `$.children[1].children[3]` |"
    assert replace_json_paths_with_names(markdown, login_screen) == "| #1 | Button/Primary |"


PERSONAS = """## Personas

| Persona | Objectifs | Frustrations |
|---|---|---|
| Opératrice | - Suivre les alertes<br>- Agir vite<BR/> | Trop d’écrans<br />Lenteur |

Contexte : poste fixe<br>écran large

```mermaid
flowchart LR
  A["Accueil<br/>connecté"] --> B
```
"""


def test_html_breaks_are_removed_outside_code():
    cleaned = remove_html_breaks(PERSONAS)
    assert "| Opératrice | Suivre les alertes ; Agir vite | Trop d’écrans ; Lenteur |" in cleaned
    assert "Contexte : poste fixe\nécran large" in cleaned
    # Mermaid labels legitimately use <br/>.
    assert 'A["Accueil<br/>connecté"]' in cleaned
    assert "<br>" not in cleaned.replace('A["Accueil<br/>connecté"]', "").lower()


def test_html_breaks_use_english_separator():
    assert remove_html_breaks("| a<br>b |", "en") == "| a; b |"
