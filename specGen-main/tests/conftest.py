"""Shared fixtures. The model is never called: `fake_llm` replaces the client and returns
queued answers, recording every request so tests can check the prompts."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Isolate the tests from the settings and .env of the machine, before importing the app.
os.environ["SPECGEN_CONFIG_DIR"] = tempfile.mkdtemp(prefix="specgen-tests-")
for variable in list(os.environ):
    if variable.startswith("CUSTOM_"):
        del os.environ[variable]
sys.path.insert(0, str(BACKEND))


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def login_screen() -> dict[str, Any]:
    return load_fixture("login_screen.json")


@pytest.fixture
def app_document() -> dict[str, Any]:
    return load_fixture("app_document.json")


class FakeLLM:
    """Stands for the OpenAI client: `answers` are returned in order (a str, or a
    (text, finish_reason) tuple, or an exception to raise); `calls` keeps every request."""

    def __init__(self) -> None:
        self.answers: list[Any] = []
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def queue(self, *answers: Any) -> "FakeLLM":
        self.answers.extend(answers)
        return self

    def _create(self, **request: Any) -> Any:
        self.calls.append(request)
        answer = self.answers.pop(0) if self.answers else "# Réponse par défaut\n"
        if isinstance(answer, Exception):
            raise answer
        text, finish_reason = answer if isinstance(answer, tuple) else (answer, "stop")
        message = SimpleNamespace(content=text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])

    def user_prompt(self, index: int = 0) -> str:
        return self.calls[index]["messages"][1]["content"]

    def system_prompt(self, index: int = 0) -> str:
        return self.calls[index]["messages"][0]["content"]


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    import context_generator
    import main
    import mermaid_generator
    import spec_generator

    llm = FakeLLM()
    for module in (spec_generator, context_generator, mermaid_generator):
        monkeypatch.setattr(module, "get_openai_client", lambda: llm)
    monkeypatch.setattr(main, "_require_llm", lambda: None)
    return llm


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


# A complete French UX/HMI specification matching the login screen fixture.
GOOD_SPEC_FR = """# Connexion

## Vue d’ensemble de la feature
### Vue globale
Écran de connexion.
- Image de la feature à fournir : [à compléter / capture attendue]

### Objectif
Permettre de se connecter.

### Moyens d’accès
Lancement de l’application (hypothèse).

## Variantes de la feature
| ID | Variante | Contexte d’affichage | Différences visuelles / comportementales | Conditions / règles |
|---|---|---|---|---|
| V1 | Erreur | Après refus | Message visible | Calque masqué par défaut |

## Détail de la feature
| ID | Composant Figma | Type de composant | État par défaut | Comportement | Niveau de confiance |
|---|---|---|---|---|---|
| #1 | Input email, Input password | Champ | Default | Saisie | Élevé |
| #2 | Button/Primary | Bouton | Actif | Ouvre Home | Élevé |
| #3 | - | Case à cocher | - | - | Faible |

## Messages et textes conditionnels
| Composant Figma | Texte | Type de texte | Condition d’affichage |
|---|---|---|---|
| Error message | Identifiants invalides | Message d’erreur | Après validation avec des identifiants refusés |

## Données affichées
| Donnée | Composant Figma | Format | Cas vide / long |
|---|---|---|---|
| Email saisi | Input email | Email (hypothèse) | Vide : libellé seul |

## Erreurs possibles
- **Identifiants refusés**

## Hypothèses
- Une case « Se souvenir de moi » pourrait exister.

## Questions ouvertes
- Le bouton est-il désactivé quand les champs sont vides ?
"""


@pytest.fixture
def good_spec_fr() -> str:
    return GOOD_SPEC_FR
