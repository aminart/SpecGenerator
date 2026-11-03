from __future__ import annotations

import json
import logging
import os
from typing import Any

from json_analysis import format_analysis_for_prompt_compact
from markdown_cleanup import unwrap_markdown_fence
from openai_client import get_model_name, get_openai_client
from spec_generator import get_max_json_chars, prune_json_for_prompt
from spec_validation import CONFIDENCE_LEVELS, check_against_structure, format_warnings

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT_CHARS = 40000
MAX_CONTEXT_CHARS_VARIABLE = "CUSTOM_MAX_CONTEXT_CHARS"

# "light" is the fallback after a timeout: smaller sources, shorter structure.
CONTEXT_PROMPT_PROFILES = {
    "standard": {
        "max_feature_groups": 12,
        "max_components_per_group": 3,
        "max_fields": 15,
        "max_labels": 20,
        "max_placeholders": 10,
        "context_share": 1.0,
        "json_share": 0.5,
        "include_component_library": True,
    },
    "light": {
        "max_feature_groups": 4,
        "max_components_per_group": 1,
        "max_fields": 5,
        "max_labels": 8,
        "max_placeholders": 4,
        "context_share": 0.3,
        "json_share": 0.0,
        "include_component_library": False,
    },
}


def get_max_context_chars() -> int:
    try:
        value = int(os.getenv(MAX_CONTEXT_CHARS_VARIABLE, ""))
    except ValueError:
        return DEFAULT_MAX_CONTEXT_CHARS
    return value if value > 0 else DEFAULT_MAX_CONTEXT_CHARS


def _get_expected_context_structure(language: str, context_mode: str) -> str:
    if language == "fr":
        if context_mode == "light":
            return "# Vue d’ensemble du projet\n## Description globale\n## Parcours principaux\n# Architecture & Navigation\n## Macro layout\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Zone | Rôle | Contenu principal | Comportement / règles |\n|---|---|---|---|\n## Navigation\n# Patterns UX\n## Chargement et feedback\n# Hypothèses et questions ouvertes\n## Hypothèses\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Hypothèse | Justification | Niveau de confiance |\n|---|---|---|---|\n## Questions ouvertes\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Question | Contexte | Impact |\n|---|---|---|---|"
        return "# Vue d’ensemble du projet\n## Vue globale de l’application\n## Description globale\n## Personas\n# Parcours utilisateur\n# Architecture & Navigation\n## Macro layout\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Zone | Rôle | Contenu principal | Comportement / règles |\n|---|---|---|---|\n## Navigation\n## Architecture de l’information\n## Présentation des sous-niveaux\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Niveau | Point d’entrée | Contenu affiché | Interaction / règle |\n|---|---|---|---|\n# Patterns UX\n## Stratégie de chargement\n## Notifications & alertes\n# Spécifications système et accessibilité\n## Grille d’espacement\n## Navigation clavier\n# Hypothèses et questions ouvertes\n## Hypothèses\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Hypothèse | Justification | Niveau de confiance |\n|---|---|---|---|\n## Questions ouvertes\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Question | Contexte | Impact |\n|---|---|---|---|"

    if context_mode == "light":
        return "# Project overview\n## Global description\n## Main user flows\n# Architecture & Navigation\n## Macro layout\nUse a Markdown table with exactly these columns:\n| Zone | Role | Main content | Behavior / rules |\n|---|---|---|---|\n## Navigation pattern\n# UX patterns\n## Loading and feedback\n# Hypotheses and open questions\n## Hypotheses\nUse a Markdown table with exactly these columns:\n| ID | Hypothesis | Rationale | Confidence level |\n|---|---|---|---|\n## Open questions\nUse a Markdown table with exactly these columns:\n| ID | Question | Context | Impact |\n|---|---|---|---|"
    return "# Project overview\n## Global view of the application\n## Global description\n## Personas\n# User flow\n# Architecture & Navigation\n## Macro layout\nUse a Markdown table with exactly these columns:\n| Zone | Role | Main content | Behavior / rules |\n|---|---|---|---|\n## Navigation pattern\n## Information architecture\n## Sub-level presentation\nUse a Markdown table with exactly these columns:\n| Level | Entry point | Displayed content | Interaction / rule |\n|---|---|---|---|\n# UX patterns\n## Loading strategy\n## Notifications & alerts\n# System specifications and accessibility\n## Spacing grid\n## Keyboard navigation\n# Hypotheses and open questions\n## Hypotheses\nUse a Markdown table with exactly these columns:\n| ID | Hypothesis | Rationale | Confidence level |\n|---|---|---|---|\n## Open questions\nUse a Markdown table with exactly these columns:\n| ID | Question | Context | Impact |\n|---|---|---|---|"


DETAIL_LEVEL_RULES = {
    "fr": {
        "compact": (
            "Niveau synthétique : document court, pour une présentation rapide du projet.\n"
            "- Deux à quatre phrases par section.\n"
            "- Parcours : les deux ou trois parcours principaux, en trois à cinq étapes chacun.\n"
            "- Macro layout : seulement les zones principales.\n"
            "- Hypothèses et questions ouvertes : les cinq plus importantes au plus."
        ),
        "standard": (
            "Niveau standard : document de référence pour écrire les specs.\n"
            "- Parcours : tous les parcours appuyés par les sources, chaque étape avec l’action de l’utilisateur et la réponse du système.\n"
            "- Macro layout et navigation : toutes les zones et tous les points d’entrée identifiés.\n"
            "- Patterns UX : ceux que les sources montrent, les autres en hypothèses."
        ),
        "detailed": (
            "Niveau détaillé : document exhaustif.\n"
            "- Parcours : principaux, secondaires et chemins d’erreur, chaque étape avec l’action, la réponse du système et l’écran concerné.\n"
            "- Architecture de l’information complète, sous-niveaux compris.\n"
            "- Accessibilité et règles système détaillées (clavier, focus, espacements) lorsque les sources les appuient.\n"
            "- Toutes les hypothèses et questions ouvertes identifiées."
        ),
    },
    "en": {
        "compact": (
            "Compact level: short document, for a quick presentation of the project.\n"
            "- Two to four sentences per section.\n"
            "- User flows: the two or three main flows, in three to five steps each.\n"
            "- Macro layout: main zones only.\n"
            "- Hypotheses and open questions: the five most important at most."
        ),
        "standard": (
            "Standard level: reference document for writing specifications.\n"
            "- User flows: every flow supported by the sources, each step with the user action and the system response.\n"
            "- Macro layout and navigation: every zone and entry point identified.\n"
            "- UX patterns: those the sources show, the others as hypotheses."
        ),
        "detailed": (
            "Detailed level: exhaustive document.\n"
            "- User flows: main, secondary and error paths, each step with the action, the system response and the screen involved.\n"
            "- Complete information architecture, including sub-levels.\n"
            "- Detailed accessibility and system rules (keyboard, focus, spacing) when the sources support them.\n"
            "- Every hypothesis and open question identified."
        ),
    },
}

_EXAMPLES = {
    "fr": """Ces exemples montrent la forme et le niveau de précision attendus, pas le contenu : ne les recopiez pas.

Bonne ligne du tableau « Macro layout » :
| Header | Identification et accès global | Logo, titre de l’écran, menu utilisateur | Fixe en haut sur tous les écrans ; le menu utilisateur ouvre un panneau contextuel |

Bon parcours :
### Parcours 1 : Se connecter
1. L’utilisateur saisit son email et son mot de passe → les champs passent à l’état rempli.
2. Il clique sur « Se connecter » → le système ouvre l’écran Accueil (interaction de prototype).
3. Identifiants refusés → message « Identifiants invalides » sous le formulaire (calque masqué par défaut).

Bonne ligne du tableau « Hypothèses » :
| H2 | La session reste ouverte entre deux visites | Case « Se souvenir de moi » présente sur l’écran de connexion | Moyen |

Bonne ligne du tableau « Questions ouvertes » :
| Q1 | Que voit un utilisateur sans droits d’administration ? | Le menu Administration apparaît sur toutes les maquettes | Navigation et sécurité |""",
    "en": """These examples show the expected form and precision, not the content: do not copy them.

Good row of the "Macro layout" table:
| Header | Identification and global access | Logo, screen title, user menu | Fixed at the top on every screen; the user menu opens a contextual panel |

Good user flow:
### Flow 1: Sign in
1. The user enters their email and password → the fields switch to the filled state.
2. They click "Sign in" → the system opens the Home screen (prototype interaction).
3. Rejected credentials → "Invalid credentials" message below the form (layer hidden by default).

Good row of the "Hypotheses" table:
| H2 | The session stays open between visits | "Remember me" checkbox present on the sign-in screen | Medium |

Good row of the "Open questions" table:
| Q1 | What does a user without admin rights see? | The Administration menu appears on every mockup | Navigation and security |""",
}


def _tagged(tag: str, content: str) -> str:
    return f"<{tag}>\n{content.strip()}\n</{tag}>"


def _truncate_text(value: str | None, max_chars: int) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[Truncated: the end of the documents was cut to fit the prompt]"


def build_context_system_prompt(language: str) -> str:
    language_name = "French" if language == "fr" else "English"
    high, medium, low = CONFIDENCE_LEVELS[language]
    return (
        "You are a senior UX architect. You write the project context document (UX architecture overview: "
        "user flows, macro layout, navigation, UX patterns) on which the detailed specifications are then based.\n\n"
        "Evidence policy, which overrides every other instruction:\n"
        "1. Product intent, personas, user needs and business rules are facts only when they appear in "
        "<project_documents>.\n"
        "2. Screens, zones, components, navigation and interactions are facts only when they appear in "
        "<application_json> or <json_analysis>.\n"
        "3. <component_library> only refines terminology; it never proves that a component is used.\n"
        "4. Anything else, even plausible, goes in the hypotheses or open questions tables. Synthesis is better "
        "than exhaustiveness, and a reliable document better than a speculative one.\n\n"
        f"Confidence levels, in this exact wording: {high} = directly supported by the sources; {medium} = strong "
        f"inference combining several sources; {low} = assumption.\n\n"
        f"Write clean Markdown only, entirely in {language_name}, following <output_structure> verbatim "
        "(headings and table columns)."
    )


WRITING_RULES = """- Describe the product as an architecture: navigation logic, macro layout, fixed zones, contextual panels, interaction model and usage patterns, not a list of widgets.
- User flows: numbered steps, each written as "user action → system response", grouped by flow under a level 3 heading.
- Use the JSON signals: the feature groups are the real screens and zones of the file; `interactions` give navigation and flows; `properties`, `variantOptions` and layers with `visible: false` reveal states, feedback and errors.
- Personas only when the documents name or clearly describe them; otherwise put them in the hypotheses.
- Every required table stays a Markdown table, never bullets or paragraphs.
- When the JSON was shortened (`children_omitted`, compact analysis), do not describe the omitted parts.
- Do not quote technical paths ($.children[0]…) or ids."""


def _build_messages(
    *,
    language: str,
    detail_level: str,
    context_mode: str,
    json_source: str,
    analysis: dict[str, Any],
    priority_context_documents: str | None,
    component_library_summary: str | None,
) -> tuple[list[dict[str, str]], str]:
    profile = CONTEXT_PROMPT_PROFILES.get(context_mode, CONTEXT_PROMPT_PROFILES["standard"])
    lang = "fr" if language == "fr" else "en"
    structure = _get_expected_context_structure(lang, context_mode)
    max_context = max(2000, int(get_max_context_chars() * profile["context_share"]))

    sections = [
        _tagged(
            "project_documents",
            _truncate_text(priority_context_documents, max_context) or "No project documents provided.",
        )
    ]

    json_budget = int(get_max_json_chars() * profile["json_share"])
    if json_source and json_source.strip() and json_budget > 0:
        try:
            pruned = prune_json_for_prompt(json.loads(json_source), json_budget)
        except ValueError:
            pruned = None
        if pruned is not None:
            text, reduced = pruned
            note = "Application JSON pruned for the prompt (no geometry, styles or ids)."
            if reduced:
                note += " Long lists and deep levels were cut (`children_omitted`)."
            sections.append(_tagged("application_json", f"{note}\n{text}"))

    sections.append(
        _tagged(
            "json_analysis",
            format_analysis_for_prompt_compact(
                analysis,
                include_paths=False,
                max_feature_groups=profile["max_feature_groups"],
                max_components_per_group=profile["max_components_per_group"],
                max_fields=profile["max_fields"],
                max_labels=profile["max_labels"],
                max_placeholders=profile["max_placeholders"],
            ),
        )
    )
    if profile["include_component_library"] and component_library_summary and component_library_summary.strip():
        sections.append(_tagged("component_library", _truncate_text(component_library_summary, 4000)))

    sections.append(_tagged("output_structure", structure))
    sections.append(_tagged("writing_rules", WRITING_RULES))
    level = "compact" if context_mode == "light" else detail_level
    sections.append(_tagged("detail_level", DETAIL_LEVEL_RULES[lang].get(level, DETAIL_LEVEL_RULES[lang]["standard"])))
    if context_mode != "light":
        sections.append(_tagged("examples", _EXAMPLES[lang]))
    sections.append("Write the context document now.")

    messages = [
        {"role": "system", "content": build_context_system_prompt(lang)},
        {"role": "user", "content": "\n\n".join(sections)},
    ]
    return messages, structure


def _issues_message(issues: list[str]) -> str:
    return "\n".join(
        [
            "The document has the problems listed below (in French). Return the complete corrected document, "
            "in Markdown only, in the same output language, keeping everything else unchanged.",
            *(f"- {issue}" for issue in issues),
        ]
    )


def generate_context_markdown(
    json_source: str,
    language: str,
    detail_level: str,
    analysis: dict[str, Any],
    context_mode: str = "standard",
    component_library_summary: str | None = None,
    priority_context_documents: str | None = None,
) -> dict[str, Any]:
    """Returns {"markdown", "warnings", "corrected"}."""
    client = get_openai_client()
    lang = "fr" if language == "fr" else "en"
    messages, structure = _build_messages(
        language=lang,
        detail_level=detail_level,
        context_mode=context_mode,
        json_source=json_source,
        analysis=analysis,
        priority_context_documents=priority_context_documents,
        component_library_summary=component_library_summary,
    )

    response = client.chat.completions.create(model=get_model_name(), temperature=0.2, messages=messages)
    markdown = unwrap_markdown_fence(response.choices[0].message.content or "")
    if not markdown.strip():
        return {"markdown": "# Error\n\nNo content returned by model.\n", "warnings": [], "corrected": False}

    issues = check_against_structure(markdown, structure, lang)
    corrected = False
    if issues:
        # One correction pass with the precise list of problems.
        try:
            retry = client.chat.completions.create(
                model=get_model_name(),
                temperature=0,
                messages=[*messages, {"role": "assistant", "content": markdown}, {"role": "user", "content": _issues_message(issues)}],
            )
            fixed = unwrap_markdown_fence(retry.choices[0].message.content or "")
        except Exception:
            logger.warning("Context correction pass failed", exc_info=True)
            fixed = ""
        if fixed.strip():
            fixed_issues = check_against_structure(fixed, structure, lang)
            if len(fixed_issues) <= len(issues):
                markdown, issues, corrected = fixed, fixed_issues, True

    return {
        "markdown": markdown,
        "warnings": format_warnings({"structure": issues, "unknown_components": []}),
        "corrected": corrected,
    }
