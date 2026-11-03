from __future__ import annotations

import json
import os
from typing import Any

from json_analysis import (
    NON_STRUCTURAL_KEYS,
    collect_node_names,
    extract_component_properties,
    extract_interactions,
    extract_property_definitions,
    format_analysis_for_prompt,
    format_analysis_for_prompt_compact,
    to_text,
)
from openai_client import get_model_name, get_openai_client
from templates import TEMPLATES


def _get_ux_hmi_language_rules(language: str) -> str:
    if language == "fr":
        return """Mandatory output structure for this UX/HMI specification in French:
# Nom de la feature

## Vue d’ensemble de la feature
### Vue globale
Décrire la vue d’ensemble globale de la feature analysée dans l’application.
Ajouter explicitement la ligne suivante :
- Image de la feature à fournir : [à compléter / capture attendue]

### Objectif
Expliquer l’objectif de la feature, son utilité et sa valeur pour l’utilisateur et pour le produit.

### Moyens d’accès
Décrire précisément comment l’utilisateur accède à la feature depuis l’application : navigation, menu, bouton, entrée contextuelle, condition d’apparition, prérequis éventuels.

## Variantes de la feature
Utiliser un tableau Markdown avec exactement ces colonnes :
| ID | Variante | Contexte d’affichage | Différences visuelles / comportementales | Conditions / règles |
|---|---|---|---|---|
Si aucune variante fiable n’est identifiable, conserver quand même cette section et ajouter une seule ligne indiquant explicitement qu’aucune variante confirmée n’a pu être déduite à partir des données disponibles.

## Détail de la feature
Utiliser un tableau Markdown avec exactement ces colonnes :
| ID | Composant Figma | Type de composant | État par défaut | Comportement | Niveau de confiance |
|---|---|---|---|---|---|

## Erreurs possibles
Lister les erreurs potentiellement rencontrées dans cette feature.
Quand possible, préciser pour chaque erreur :
- Contexte :
- Message ou symptôme visible :
- Impact utilisateur :
- Comportement attendu du système :

## Hypothèses
Lister les hypothèses raisonnables déduites des données quand certains comportements ou éléments UI ne sont pas explicitement confirmés.

## Questions ouvertes
Lister les questions restant à clarifier pour finaliser la spécification, en particulier quand le JSON ou le contexte métier ne suffisent pas.

Critical formatting rules:
- All section titles, subtitles, labels and explanatory text must be in French.
- Use exactly the French section titles written above.
- Use exactly the table column names written above.
- Include the Variantes de la feature section and its table even when the source data is partial.
- Do not output English headings anywhere in the document.
"""

    return """Mandatory output structure for this UX/HMI specification in English:
# Feature name

## Feature overview
### Global view
Describe the overall view of the analyzed feature within the application.
Explicitly add the following line:
- Feature image to be provided: [to be completed / expected screenshot]

### Goal
Explain the purpose of the feature, what it is used for, and its value for the user and the product.

### Ways of access
Describe precisely how the user accesses this feature from the application: navigation path, menu, button, contextual entry point, display condition, and prerequisites if any.

## Feature variants
Use a Markdown table with exactly these columns:
| ID | Variant | Display context | Visual / behavioral differences | Conditions / rules |
|---|---|---|---|---|
If no reliable variant can be identified, still keep this section and add a single row explicitly stating that no confirmed variant could be inferred from the available data.

## Feature details
Use a Markdown table with exactly these columns:
| ID | Figma component | Component type | Default state | Behavior | Confidence level |
|---|---|---|---|---|---|

## Possible errors
List the errors that may potentially be encountered in this feature.
When possible, specify for each error:
- Context:
- Visible message or symptom:
- User impact:
- Expected system behavior:

## Assumptions
List the reasonable assumptions inferred from the available data when some behaviors or UI elements are not explicitly confirmed.

## Open questions
List the points that still need clarification to finalize the specification, especially when the JSON or business context is insufficient.

Critical formatting rules:
- All section titles, subtitles, labels and explanatory text must be in English.
- Use exactly the English section titles written above.
- Use exactly the table column names written above.
- Include the Feature variants section and its table even when the source data is partial.
- Do not output French headings anywhere in the document.
"""


DEFAULT_MAX_JSON_CHARS = 40000
MAX_JSON_CHARS_VARIABLE = "CUSTOM_MAX_JSON_CHARS"
# Keys kept as-is when pruning the JSON sent to the model; everything else that is a
# scalar is dropped unless it is a short text (custom exports may name things differently).
_PRUNE_DROPPED_SCALAR_KEYS = {
    "id",
    "key",
    "blendMode",
    "opacity",
    "x",
    "y",
    "width",
    "height",
    "rotation",
    "cornerRadius",
    "strokeWeight",
    "strokeAlign",
    "layoutAlign",
    "layoutGrow",
    "layoutMode",
    "layoutPositioning",
    "layoutSizingHorizontal",
    "layoutSizingVertical",
    "primaryAxisAlignItems",
    "counterAxisAlignItems",
    "primaryAxisSizingMode",
    "counterAxisSizingMode",
    "itemSpacing",
    "paddingLeft",
    "paddingRight",
    "paddingTop",
    "paddingBottom",
    "clipsContent",
    "isMask",
    "scrollBehavior",
    "locked",
    "componentId",
    "remote",
    "documentationLinks",
}
_MAX_SCALAR_TEXT = 300


def get_max_json_chars() -> int:
    try:
        value = int(os.getenv(MAX_JSON_CHARS_VARIABLE, ""))
    except ValueError:
        return DEFAULT_MAX_JSON_CHARS
    return value if value > 0 else DEFAULT_MAX_JSON_CHARS


def _prune_node(
    value: Any, node_names: dict[str, str], depth: int, max_depth: int | None, max_children: int | None = None
) -> Any:
    if isinstance(value, list):
        items = [_prune_node(item, node_names, depth, max_depth, max_children) for item in value]
        return [item for item in items if item not in (None, {}, [])]
    if not isinstance(value, dict):
        return value

    pruned: dict[str, Any] = {}
    for key, item in value.items():
        if key == "children" and isinstance(item, list):
            if max_depth is not None and depth >= max_depth:
                if item:
                    pruned["children_omitted"] = len(item)
                continue
            kept = item if max_children is None else item[:max_children]
            children = _prune_node(kept, node_names, depth + 1, max_depth, max_children)
            if children:
                pruned["children"] = children
            if len(kept) < len(item):
                pruned["children_omitted"] = len(item) - len(kept)
        elif key == "visible":
            if item is False:
                pruned["visible"] = False
        elif key == "mainComponent" and isinstance(item, dict):
            name = to_text(item.get("name"))
            if name:
                pruned["mainComponent"] = name
        elif key in ("variantProperties", "componentProperties") and isinstance(value, dict):
            continue
        elif key == "componentPropertyDefinitions" and isinstance(item, dict):
            definitions = extract_property_definitions(value)
            if definitions:
                pruned["variantOptions"] = definitions
        elif key in ("reactions", "interactions") and isinstance(item, list):
            described = extract_interactions(value, node_names)
            if described:
                pruned["interactions"] = described
        elif key in NON_STRUCTURAL_KEYS or key in _PRUNE_DROPPED_SCALAR_KEYS:
            continue
        elif isinstance(item, (dict, list)):
            nested = _prune_node(item, node_names, depth, max_depth, max_children)
            if nested not in (None, {}, []):
                pruned[key] = nested
        elif isinstance(item, str):
            if item.strip() and len(item) <= _MAX_SCALAR_TEXT:
                pruned[key] = item
        elif isinstance(item, bool):
            pruned[key] = item

    properties = extract_component_properties(value)
    if properties:
        pruned["properties"] = properties
    return pruned


def _max_children_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, list):
        return max((_max_children_depth(item, depth) for item in value), default=depth)
    if not isinstance(value, dict):
        return depth
    best = depth
    for key, item in value.items():
        if isinstance(item, (dict, list)):
            best = max(best, _max_children_depth(item, depth + 1 if key == "children" else depth))
    return best


def prune_json_for_prompt(data: Any, max_chars: int) -> tuple[str, bool] | None:
    """The JSON reduced to what describes the UI (names, texts, variants, visibility,
    interactions, hierarchy), without geometry and styling. When it is still too long, long
    lists of siblings are cut first (repeated rows, items…), then the deepest levels.
    Returns (json, reduced), or None when even a shallow version does not fit."""
    node_names = collect_node_names(data)

    def dump(max_depth: int | None, max_children: int | None) -> str:
        pruned = _prune_node(data, node_names, 0, max_depth, max_children)
        return json.dumps(pruned, ensure_ascii=False, separators=(",", ":"))

    text = dump(None, None)
    if len(text) <= max_chars:
        return text, False
    attempts = [(None, limit) for limit in (50, 20, 10)]
    attempts += [(depth, 10) for depth in range(_max_children_depth(data) - 1, 0, -1)]
    for max_depth, max_children in attempts:
        text = dump(max_depth, max_children)
        if len(text) <= max_chars:
            return text, True
    return None


def _build_compact_json_source_for_prompt(json_source: str, analysis: dict[str, Any]) -> str:
    normalized = (json_source or "").strip()
    if not normalized:
        return "No raw JSON source provided."

    max_chars = get_max_json_chars()
    try:
        data = json.loads(normalized)
    except ValueError:
        data = None

    if data is not None:
        pruned = prune_json_for_prompt(data, max_chars)
        if pruned is not None:
            text, depth_reduced = pruned
            header = (
                "JSON source pruned for the prompt: geometry, styling and ids removed; names, texts, "
                "variant properties (`properties`, `variantOptions`), hidden elements (`visible: false`), "
                "prototype interactions and hierarchy kept."
            )
            if depth_reduced:
                header += (
                    " It was shortened to fit: long lists of siblings and possibly the deepest levels were cut "
                    "(`children_omitted` gives the number of children removed). Do not assume that omitted "
                    "children differ from the ones kept; rely on the structured analysis for them."
                )
            return f"{header}\n{text}"
    elif len(normalized) <= max_chars:
        return normalized

    compact_analysis = format_analysis_for_prompt_compact(
        analysis,
        include_paths=False,
        max_feature_groups=8,
        max_components_per_group=4,
        max_fields=20,
        max_labels=16,
        max_placeholders=10,
    )

    return "\n".join(
        [
            "Raw JSON omitted because the source is too large for reliable model processing.",
            "Use the structured analysis below as the canonical source for inference.",
            "Compact source summary:",
            compact_analysis,
        ]
    )


_CONFIDENCE_LEVELS = {"fr": ("Élevé", "Moyen", "Faible"), "en": ("High", "Medium", "Low")}

DETAIL_LEVEL_RULES = {
    "fr": {
        "compact": (
            "Niveau synthétique : document court, lisible en deux minutes.\n"
            "- Vue d’ensemble : deux à trois phrases par sous-section.\n"
            "- Détail de la feature : seulement les composants interactifs et les conteneurs structurants, une ligne par élément répété (environ 8 lignes au plus). Comportement en une phrase.\n"
            "- Erreurs possibles : les deux ou trois erreurs principales.\n"
            "- Hypothèses et questions ouvertes : les plus importantes seulement."
        ),
        "standard": (
            "Niveau standard : document de handoff complet sans cas limites.\n"
            "- Détail de la feature : chaque composant interactif et chaque conteneur significatif ; regrouper les éléments répétés sur une ligne.\n"
            "- Comportement : état par défaut, interaction principale et résultat visible.\n"
            "- Erreurs possibles : toutes les erreurs présentes dans le JSON, plus les erreurs usuelles des champs présents, marquées comme hypothèses."
        ),
        "detailed": (
            "Niveau détaillé : document exhaustif pour le développement et la recette.\n"
            "- Détail de la feature : une ligne par composant interactif, y compris les sous-composants significatifs.\n"
            "- Comportement : tous les états (par défaut, survol, focus, désactivé, erreur, chargement), les transitions entre états et les cas limites (vide, texte long, absence de droits). Ce qui n’est pas dans le JSON est marqué comme hypothèse.\n"
            "- Erreurs possibles : chaque erreur avec ses quatre rubriques.\n"
            "- Questions ouvertes : tout point bloquant pour le développement ou la recette."
        ),
    },
    "en": {
        "compact": (
            "Compact level: short document, readable in two minutes.\n"
            "- Feature overview: two to three sentences per subsection.\n"
            "- Feature details: only interactive components and structural containers, one row per repeated element (about 8 rows at most). Behavior in one sentence.\n"
            "- Possible errors: the two or three main errors.\n"
            "- Assumptions and open questions: the most important ones only."
        ),
        "standard": (
            "Standard level: complete handoff document without edge cases.\n"
            "- Feature details: every interactive component and every significant container; group repeated elements in one row.\n"
            "- Behavior: default state, main interaction and visible result.\n"
            "- Possible errors: every error present in the JSON, plus the usual errors of the fields present, marked as assumptions."
        ),
        "detailed": (
            "Detailed level: exhaustive document for development and QA.\n"
            "- Feature details: one row per interactive component, including significant sub-components.\n"
            "- Behavior: every state (default, hover, focus, disabled, error, loading), the transitions between states and edge cases (empty, long text, missing permissions). Anything not in the JSON is marked as an assumption.\n"
            "- Possible errors: each error with its four items.\n"
            "- Open questions: every point blocking development or QA."
        ),
    },
}

SCOPE_RULES = {
    "atomic_component": "Atomic component: keep the specification concise and focused on this single element, its states and its direct behavior.",
    "composite_component": "Composite component: document the root component and its significant sub-components, how they relate and their internal interaction logic.",
    "feature_zone": "Feature zone: document the target as a functional block with its main internal components, user intent, ways of access and structural variants.",
}

_EXAMPLES = {
    "fr": """Ces exemples montrent la forme et le niveau de précision attendus, pas le contenu : ne les recopiez pas.

Bonne ligne du tableau « Détail de la feature » :
| #3 | Button/Primary | Bouton principal | Actif, libellé « Se connecter » | Au clic, soumet le formulaire et ouvre l’écran Home (interaction de prototype). Désactivé tant que les champs obligatoires sont vides (hypothèse). | Élevé |

À éviter (chemin JSON au lieu du nom Figma, comportement vague, confiance non justifiée) :
| #3 | $.children[2] | Button | Default | Gère le clic | Élevé |

Bonne ligne du tableau « Variantes de la feature » :
| V2 | Erreur d’identification | Après validation avec des identifiants refusés | Message « Identifiants invalides » affiché sous le formulaire | Calque « Error message » masqué par défaut (visible=false) |

Bonne erreur :
- **Identifiants refusés**
  - Contexte : clic sur « Se connecter » avec un mot de passe incorrect.
  - Message ou symptôme visible : « Identifiants invalides » sous le formulaire.
  - Impact utilisateur : connexion impossible tant que la saisie n’est pas corrigée.
  - Comportement attendu du système : conserver l’email saisi et placer le focus sur le mot de passe (hypothèse).""",
    "en": """These examples show the expected form and precision, not the content: do not copy them.

Good row of the "Feature details" table:
| #3 | Button/Primary | Primary button | Enabled, label "Sign in" | On click, submits the form and opens the Home screen (prototype interaction). Disabled while required fields are empty (assumption). | High |

Avoid (JSON path instead of the Figma name, vague behavior, unjustified confidence):
| #3 | $.children[2] | Button | Default | Handles click | High |

Good row of the "Feature variants" table:
| V2 | Sign-in error | After submitting rejected credentials | "Invalid credentials" message shown below the form | "Error message" layer hidden by default (visible=false) |

Good error:
- **Rejected credentials**
  - Context: click on "Sign in" with a wrong password.
  - Visible message or symptom: "Invalid credentials" below the form.
  - User impact: cannot sign in until the input is corrected.
  - Expected system behavior: keep the email entered and move focus to the password (assumption).""",
}


def _tagged(tag: str, content: str) -> str:
    return f"<{tag}>\n{content.strip()}\n</{tag}>"


def build_spec_system_prompt(language: str) -> str:
    language_name = "French" if language == "fr" else "English"
    high, medium, low = _CONFIDENCE_LEVELS["fr" if language == "fr" else "en"]
    return (
        "You are a senior UX/HMI specification writer. You write design-to-development handoff documents "
        "that product, design, engineering and QA review.\n\n"
        "Evidence policy, which overrides every other instruction:\n"
        "1. Visible UI (components, texts, states, variants, interactions) is a fact only when it appears in "
        "<screen_json> or <json_analysis>.\n"
        "2. Product intent (goal, user need, business rule) is a fact only when it appears in <project_context>.\n"
        "3. <component_library> only refines terminology and standard states; it never proves that a component "
        "is present in the feature.\n"
        "4. Anything else, even plausible or conventional, is an assumption or an open question. A shorter "
        "reliable specification is better than a detailed speculative one.\n\n"
        f"Confidence levels, in this exact wording: {high} = directly supported by the JSON or the project "
        f"context; {medium} = strong inference combining several sources; {low} = assumption.\n\n"
        f"Write clean Markdown only, entirely in {language_name}, following <output_structure> verbatim "
        "(headings and table columns)."
    )


def generate_spec(
    json_source: str,
    business_context: str,
    language: str,
    detail_level: str,
    template_key: str,
    analysis: dict[str, Any],
    custom_template: str | None,
    component_library_summary: str | None = None,
    priority_context_documents: str | None = None,
    component_focus_label: str | None = None,
    component_focus_path: str | None = None,
    component_scope_label: str | None = None,
    component_scope_rationale: str | None = None,
) -> str:
    client = get_openai_client()
    lang = "fr" if language == "fr" else "en"

    # Sources first, then what to produce: models follow instructions placed after the data better.
    context_parts = [part.strip() for part in (priority_context_documents, business_context) if part and part.strip()]
    if len(context_parts) == 2 and context_parts[1] in context_parts[0]:
        context_parts = context_parts[:1]
    sections = [
        _tagged("project_context", "\n\n".join(context_parts) or "No project context provided."),
        _tagged("screen_json", _build_compact_json_source_for_prompt(json_source, analysis)),
        _tagged("json_analysis", format_analysis_for_prompt(analysis)),
    ]
    if component_library_summary and component_library_summary.strip():
        sections.append(_tagged("component_library", component_library_summary))

    scope_key = analysis.get("component_scope", {}).get("scope")
    target_lines = []
    if component_scope_label:
        target_lines.append(f"Detected scope: {component_scope_label}")
    if component_scope_rationale:
        target_lines.append(f"Why: {component_scope_rationale}")
    if scope_key in SCOPE_RULES:
        target_lines.append(SCOPE_RULES[scope_key])
    if component_focus_label:
        target_lines.append(
            f"Focus on the component {component_focus_label} and its direct substructure rather than the whole screen."
        )
    if component_focus_path:
        target_lines.append(f"Its location in the JSON (strongest locator): {component_focus_path}")
    if target_lines:
        sections.append(_tagged("target", "\n".join(target_lines)))

    if template_key == "ux_hmi_detailed":
        output_structure = _get_ux_hmi_language_rules(lang)
    else:
        output_structure = TEMPLATES[template_key]["prompt"]
    if custom_template and custom_template.strip():
        output_structure += f"\n\nCustom template to follow:\n{custom_template.strip()}"
    sections.append(_tagged("output_structure", output_structure))

    low = _CONFIDENCE_LEVELS[lang][2]
    sections.append(
        _tagged(
            "writing_rules",
            "\n".join(
                [
                    "- Organize the document by feature and UI zone, not as a raw list of fields; do not paraphrase the JSON mechanically.",
                    "- Figma component column: the exact layer or component `name` from the JSON (e.g. Button/Primary, Input email). Never a JSON path, never the words JSON or analysis. A row supported only by the project context gets a dash (-).",
                    "- Use the Figma signals: `properties` and `variantOptions` feed the variants table and the states; layers with `visible: false` are usually alternative states or error messages; `interactions` give the behaviors and the ways of access.",
                    f"- Each row of the feature details table gets a confidence level; {low} rows must match an item in the assumptions section.",
                    "- When the JSON was shortened (`children_omitted`, compact summary), do not describe the omitted parts beyond what the analysis states.",
                    "- Always include the assumptions and open questions sections, stating that none was identified when that is the case.",
                ]
            ),
        )
    )
    sections.append(_tagged("detail_level", DETAIL_LEVEL_RULES[lang].get(detail_level, DETAIL_LEVEL_RULES[lang]["standard"])))
    if template_key == "ux_hmi_detailed":
        sections.append(_tagged("examples", _EXAMPLES[lang]))
    sections.append("Write the specification now.")

    response = client.chat.completions.create(
        model=get_model_name(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": build_spec_system_prompt(lang)},
            {"role": "user", "content": "\n\n".join(sections)},
        ],
    )

    return response.choices[0].message.content or "# Error\n\nNo content returned by model."
