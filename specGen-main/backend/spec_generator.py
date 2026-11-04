from __future__ import annotations

import json
import logging
import os
import re
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
from markdown_cleanup import replace_json_paths_with_names, unwrap_markdown_fence
from spec_validation import collect_json_names, collect_json_texts, context_screen_names, format_issues_for_model, normalize_name, format_warnings, validate_spec
from openai_client import complete, get_openai_client
from templates import TEMPLATES

logger = logging.getLogger(__name__)


def _get_ux_hmi_language_rules(language: str) -> str:
    if language == "fr":
        return """Structure obligatoire de cette spécification UX / HMI :
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
Une ligne par élément que le développeur doit implémenter : composant interactif, conteneur qui porte une logique (liste, formulaire, onglets) ou élément dont l’affichage change selon un état. Les éléments qui n’ont pas de comportement propre (unité ou suffixe comme « h », « € » ou « % », icône décorative, séparateur, libellé statique d’un champ, texte d’aide) ne reçoivent pas de ligne : les mentionner dans la ligne du composant auquel ils appartiennent (ex. « Champ durée, suffixe « h » »).

## Textes de l’interface
Lister, recopiés mot pour mot, les textes que le développeur doit intégrer et dont le contenu ou l’affichage n’est pas évident à la lecture de la maquette : titres, libellés de boutons et d’actions, placeholders, messages d’erreur, de confirmation, d’état vide ou de chargement, info-bulles, textes des calques masqués. Ne pas lister les unités, symboles, chiffres, valeurs d’exemple (elles vont dans Données affichées) ni les textes d’un seul caractère. Tableau Markdown avec exactement ces colonnes :
| Composant Figma | Texte | Type de texte | Condition d’affichage |
|---|---|---|---|
Type de texte : titre, libellé de bouton, placeholder, message d’erreur, message de confirmation, état vide, info-bulle… Condition d’affichage : « Toujours » pour un texte permanent, sinon l’état ou l’événement qui l’affiche (ex. « Après validation avec un email invalide »).

## Données affichées
Lister les données variables affichées (valeurs saisies, contenus dynamiques, compteurs, dates, listes) dans un tableau Markdown avec exactement ces colonnes :
| Donnée | Composant Figma | Format | Cas vide / long |
|---|---|---|---|
Quand le format, la source ou le cas limite ne figure pas dans les sources, l’écrire comme hypothèse. S’il n’y a aucune donnée variable, garder la section avec une seule ligne qui l’indique.

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

Règles de mise en forme impératives :
- Tous les titres, sous-titres, libellés et textes sont en français.
- Reprendre exactement les titres de sections ci-dessus.
- Reprendre exactement les noms de colonnes ci-dessus.
- Garder la section Variantes de la feature et son tableau même quand les sources sont partielles.
- Aucun titre en anglais dans le document.
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
One row per element the developer has to implement: interactive component, container carrying logic (list, form, tabs) or element whose display depends on a state. Elements with no behavior of their own (unit or suffix such as "h", "€" or "%", decorative icon, separator, static field label, helper text) get no row: mention them in the row of the component they belong to (e.g. "Duration field, suffix "h"").

## Interface texts
List, copied verbatim, the texts the developer has to integrate and whose content or display is not obvious from the mockup: titles, button and action labels, placeholders, error, confirmation, empty-state and loading messages, tooltips, texts of hidden layers. Do not list units, symbols, numbers, sample values (they go in Displayed data) or one-character texts. Markdown table with exactly these columns:
| Figma component | Text | Text type | Display condition |
|---|---|---|---|
Text type: title, button label, placeholder, error message, confirmation message, empty state, tooltip… Display condition: "Always" for a permanent text, otherwise the state or event that shows it (e.g. "After submitting an invalid email").

## Displayed data
List the variable data shown (entered values, dynamic content, counters, dates, lists) in a Markdown table with exactly these columns:
| Data | Figma component | Format | Empty / long case |
|---|---|---|---|
When the format, source or edge case is not in the sources, write it as an assumption. If there is no variable data, keep the section with a single row saying so.

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


DEFAULT_MAX_JSON_CHARS = 80000
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


def _build_compact_json_source_for_prompt(json_source: str, analysis: dict[str, Any], language: str = "en") -> str:
    texts = TEXTS["fr" if language == "fr" else "en"]
    normalized = (json_source or "").strip()
    if not normalized:
        return texts["no_json"]

    max_chars = get_max_json_chars()
    try:
        data = json.loads(normalized)
    except ValueError:
        data = None

    if data is not None:
        pruned = prune_json_for_prompt(data, max_chars)
        if pruned is not None:
            text, depth_reduced = pruned
            header = texts["pruned"]
            if depth_reduced:
                header += texts["pruned_reduced"]
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

    return "\n".join([*texts["json_omitted"], compact_analysis])


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
            "- Détail de la feature : une ligne par composant interactif ou porteur de logique ; le détail va dans les états et le comportement, pas dans le nombre de lignes. Les sous-éléments sans comportement propre (unités, icônes décoratives, libellés statiques) sont décrits dans la ligne de leur composant.\n"
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
            "- Feature details: one row per interactive or logic-carrying component; the detail goes into the states and the behavior, not into the number of rows. Sub-elements with no behavior of their own (units, decorative icons, static labels) are described in the row of their component.\n"
            "- Behavior: every state (default, hover, focus, disabled, error, loading), the transitions between states and edge cases (empty, long text, missing permissions). Anything not in the JSON is marked as an assumption.\n"
            "- Possible errors: each error with its four items.\n"
            "- Open questions: every point blocking development or QA."
        ),
    },
}

SCOPE_RULES = {
    "en": {
        "atomic_component": "Atomic component: focus the specification on this single element, all its states and its direct behavior.",
        "composite_component": "Composite component: document the root component and its significant sub-components, how they relate and their internal interaction logic.",
        "feature_zone": "Feature zone: document the target as a functional block with its main internal components, user intent, ways of access and structural variants.",
    },
    "fr": {
        "atomic_component": "Composant atomique : centrer la spécification sur ce seul élément, tous ses états et son comportement direct.",
        "composite_component": "Composant composite : documenter le composant racine et ses sous-composants significatifs, leurs relations et leur logique d’interaction interne.",
        "feature_zone": "Zone fonctionnelle : documenter la cible comme un bloc fonctionnel, avec ses principaux composants internes, l’intention utilisateur, les moyens d’accès et les variantes structurelles.",
    },
}

# Instructions are written in the output language: a small model then keeps that language
# more reliably. Tag names stay in English in both.
TEXTS = {
    "en": {
        "no_context": "No project context provided.",
        "detected_scope": "Detected scope: {}",
        "why": "Why: {}",
        "focus": "Focus on the component {} and its direct substructure rather than the whole screen.",
        "focus_path": "Its location in the JSON (strongest locator): {}",
        "custom_template": "Custom template to follow:",
        "write_now": "Write the specification now.",
        "writing_rules": [
            "- Organize the document by feature and UI zone, not as a raw list of fields; do not paraphrase the JSON mechanically.",
            "- Figma component column: the exact layer or component `name` from the JSON (e.g. Button/Primary, Input email). Never a JSON path, never the words JSON or analysis. A row supported only by the project context gets a dash (-).",
            "- Use the Figma signals: `properties` and `variantOptions` feed the variants table and the states; layers with `visible: false` are usually alternative states or error messages; `interactions` give the behaviors and the ways of access.",
            "- Each row of the feature details table gets a confidence level; {low} rows must match an item in the assumptions section.",
            "- When the JSON was shortened (`children_omitted`, compact summary), do not describe the omitted parts beyond what the analysis states.",
            "- Always include the assumptions and open questions sections, stating that none was identified when that is the case.",
        ],
        "inventory_rule": "- <component_inventory> lists what the JSON contains, zone by zone: every interactive or logic-carrying component in it must be covered by the feature details table (repeated ones grouped in one row); the others are described in the row of their parent component.",
        "pruned": (
            "JSON source pruned for the prompt: geometry, styling and ids removed; names, texts, variant properties "
            "(`properties`, `variantOptions`), hidden elements (`visible: false`), prototype interactions and hierarchy kept."
        ),
        "pruned_reduced": (
            " It was shortened to fit: long lists of siblings and possibly the deepest levels were cut "
            "(`children_omitted` gives the number of children removed). Do not assume that omitted children differ "
            "from the ones kept; rely on the structured analysis for them."
        ),
        "no_json": "No raw JSON source provided.",
        "json_omitted": [
            "Raw JSON omitted because the source is too large for reliable model processing.",
            "Use the structured analysis below as the canonical source for inference.",
            "Compact source summary:",
        ],
    },
    "fr": {
        "no_context": "Aucun contexte projet fourni.",
        "detected_scope": "Portée détectée : {}",
        "why": "Pourquoi : {}",
        "focus": "Centrer la spécification sur le composant {} et sa sous-structure directe, pas sur tout l’écran.",
        "focus_path": "Son emplacement dans le JSON (repère le plus fiable) : {}",
        "custom_template": "Modèle personnalisé à suivre :",
        "write_now": "Rédigez maintenant la spécification.",
        "writing_rules": [
            "- Organiser le document par feature et par zone d’interface, pas comme une liste brute de champs ; ne pas paraphraser le JSON.",
            "- Colonne Composant Figma : le `name` exact du calque ou du composant dans le JSON (ex. Button/Primary, Input email). Jamais un chemin JSON, jamais les mots JSON ou analyse. Une ligne appuyée seulement par le contexte projet reçoit un tiret (-).",
            "- Exploiter les signaux Figma : `properties` et `variantOptions` alimentent le tableau des variantes et les états ; les calques `visible: false` sont en général des états alternatifs ou des messages d’erreur ; `interactions` donne les comportements et les moyens d’accès.",
            "- Chaque ligne du tableau Détail de la feature reçoit un niveau de confiance ; chaque ligne {low} correspond à une entrée de la section Hypothèses.",
            "- Quand le JSON a été raccourci (`children_omitted`, résumé compact), ne pas décrire les parties omises au-delà de ce que dit l’analyse.",
            "- Toujours inclure les sections Hypothèses et Questions ouvertes, en indiquant qu’aucun élément n’a été identifié le cas échéant.",
        ],
        "inventory_rule": "- <component_inventory> liste ce que contient le JSON, zone par zone : chacun de ses composants interactifs ou porteurs de logique doit apparaître dans le tableau Détail de la feature (les éléments répétés regroupés sur une ligne) ; les autres sont décrits dans la ligne de leur composant parent.",
        "pruned": (
            "JSON allégé pour le prompt : géométrie, styles et ids retirés ; noms, textes, propriétés de variantes "
            "(`properties`, `variantOptions`), éléments masqués (`visible: false`), interactions de prototype et hiérarchie conservés."
        ),
        "pruned_reduced": (
            " Il a été raccourci : les longues listes d’éléments frères, et parfois les niveaux les plus profonds, ont été "
            "coupés (`children_omitted` donne le nombre d’enfants retirés). Ne pas supposer que les enfants omis diffèrent "
            "de ceux conservés ; s’appuyer sur l’analyse structurée pour eux."
        ),
        "no_json": "Aucun JSON fourni.",
        "json_omitted": [
            "JSON brut omis : la source est trop volumineuse pour être traitée de façon fiable.",
            "Utiliser l’analyse structurée ci-dessous comme source de référence.",
            "Résumé compact de la source :",
        ],
    },
}

CONTEXT_USAGE = {
    "fr": """Le contexte projet est un document produit en amont. Utilisez chacune de ses sections pour la partie correspondante de la spécification :
| Section du contexte | Sert à remplir |
|---|---|
| Vue d’ensemble du projet, Description globale | Objectif (valeur pour l’utilisateur et le produit) |
| Personas | Objectif (pour qui), Hypothèses |
| Glossaire métier | Vocabulaire de tout le document : employer exactement ces termes |
| Liste des écrans | Moyens d’accès (écran d’origine), Vue globale (écran où se trouve la feature) |
| Navigation, Parcours utilisateur | Moyens d’accès (action, condition, prérequis), Comportement |
| Macro layout, Présentation des sous-niveaux | Vue globale (place de la feature dans l’écran) |
| Patterns UX (chargement, notifications, alertes) | Comportement, Erreurs possibles |
| Spécifications système et accessibilité | Comportement (clavier, focus, espacements) |
| Hypothèses et questions ouvertes | Reprendre celles qui concernent la feature dans Hypothèses et Questions ouvertes |
Dans Moyens d’accès, nommer les écrans exactement comme dans la Liste des écrans du contexte.""",
    "en": """The project context is a document produced upstream. Use each of its sections for the matching part of the specification:
| Context section | Used for |
|---|---|
| Project overview, Global description | Goal (value for the user and the product) |
| Personas | Goal (for whom), Assumptions |
| Business glossary | Vocabulary of the whole document: use exactly these terms |
| Screen list | Ways of access (screen of origin), Global view (screen holding the feature) |
| Navigation pattern, User flow | Ways of access (action, condition, prerequisites), Behavior |
| Macro layout, Sub-level presentation | Global view (place of the feature on the screen) |
| UX patterns (loading, notifications, alerts) | Behavior, Possible errors |
| System specifications and accessibility | Behavior (keyboard, focus, spacing) |
| Hypotheses and open questions | Carry over those about the feature into Assumptions and Open questions |
In Ways of access, name the screens exactly as in the context Screen list.""",
}

_EXAMPLES = {
    "fr": """Ces exemples montrent la forme et le niveau de précision attendus, pas le contenu : ne les recopiez pas.

Bonne ligne du tableau « Détail de la feature » :
| #3 | Button/Primary | Bouton principal | Actif, libellé « Se connecter » | Au clic, soumet le formulaire et ouvre l’écran Home (interaction de prototype). Désactivé tant que les champs obligatoires sont vides (hypothèse). | Élevé |

À éviter (chemin JSON au lieu du nom Figma, comportement vague, confiance non justifiée) :
| #3 | $.children[2] | Button | Default | Gère le clic | Élevé |

À éviter aussi (ligne pour un élément sans comportement propre, à décrire dans la ligne du champ) :
| #7 | Unit | Texte | « h » | Affiche l’unité | Élevé |

Bonne ligne du tableau « Variantes de la feature » :
| V2 | Erreur d’identification | Après validation avec des identifiants refusés | Message « Identifiants invalides » affiché sous le formulaire | Calque « Error message » masqué par défaut (visible=false) |

Bonnes lignes des tableaux « Textes de l’interface » et « Données affichées » :
| Error message | Identifiants invalides | Message d’erreur | Après validation avec des identifiants refusés |
| Email saisi | Input email | Adresse email, 254 caractères au plus (hypothèse) | Vide : placeholder « Email » ; long : texte tronqué avec points de suspension (hypothèse) |

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

Avoid too (row for an element with no behavior of its own, to describe in the field row):
| #7 | Unit | Text | "h" | Shows the unit | High |

Good row of the "Feature variants" table:
| V2 | Sign-in error | After submitting rejected credentials | "Invalid credentials" message shown below the form | "Error message" layer hidden by default (visible=false) |

Good rows of the "Interface texts" and "Displayed data" tables:
| Error message | Invalid credentials | Error message | After submitting rejected credentials |
| Entered email | Input email | Email address, 254 characters at most (assumption) | Empty: "Email" placeholder; long: text truncated with an ellipsis (assumption) |

Good error:
- **Rejected credentials**
  - Context: click on "Sign in" with a wrong password.
  - Visible message or symptom: "Invalid credentials" below the form.
  - User impact: cannot sign in until the input is corrected.
  - Expected system behavior: keep the email entered and move focus to the password (assumption).""",
}


INVENTORY_SYSTEM_PROMPT = (
    "You extract a component inventory from a UI JSON export (Figma). You only report what the JSON shows: "
    "never add a component, state or interaction that is not in it. Return one JSON object and nothing else."
)
INVENTORY_INSTRUCTIONS = """Return a JSON object with this shape:
{
  "zones": [
    {
      "name": "exact `name` of the zone container in the JSON",
      "components": [
        {
          "figma_name": "exact `name` of the layer in the JSON",
          "type": "button, input, text, icon, list, card…",
          "texts": ["visible texts"],
          "default_state": "state shown in the JSON, or null",
          "states": ["states or variants found in properties, variantOptions or hidden layers"],
          "interactions": ["prototype interactions, as written in the JSON"],
          "repeated": 1
        }
      ]
    }
  ],
  "hidden_layers": ["names of layers with visible: false"],
  "error_signals": ["error messages or error layers found in the JSON"]
}
Rules:
- One zone per functional block (header, form, list, panel…), in reading order.
- Group identical repeated elements in one component with "repeated" set to their number.
- Skip purely decorative layers (backgrounds, dividers, vectors without meaning).
- Use null or [] when the JSON says nothing; do not guess."""


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*\n(.*?)\n```", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _filter_inventory(inventory: dict[str, Any], json_names: set[str]) -> dict[str, Any]:
    """Drops the components whose name is not in the JSON: the inventory must not carry inventions."""
    zones = []
    for zone in inventory.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        components = [
            component
            for component in zone.get("components") or []
            if isinstance(component, dict) and _normalize_name(component.get("figma_name")) in json_names
        ]
        if components:
            zones.append({**zone, "components": components})
    return {**inventory, "zones": zones}


def _normalize_name(value: Any) -> str:
    return normalize_name(value) if isinstance(value, str) else ""


def extract_component_inventory(client: Any, screen_json: str, analysis_text: str, json_names: set[str]) -> str | None:
    """First pass for feature zones: an inventory of what the JSON contains, so that the
    writing pass covers every component instead of picking a few."""
    content = complete(
        client,
        [
            {"role": "system", "content": INVENTORY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "\n\n".join(
                    [_tagged("screen_json", screen_json), _tagged("json_analysis", analysis_text), INVENTORY_INSTRUCTIONS]
                ),
            },
        ],
        temperature=0,
        json_mode=True,
    )
    inventory = _parse_json_object(content)
    if not inventory:
        return None
    inventory = _filter_inventory(inventory, json_names)
    if not inventory["zones"]:
        return None
    return json.dumps(inventory, ensure_ascii=False, indent=1)


def _tagged(tag: str, content: str) -> str:
    return f"<{tag}>\n{content.strip()}\n</{tag}>"


def build_spec_system_prompt(language: str) -> str:
    language_name = "French" if language == "fr" else "English"
    high, medium, low = _CONFIDENCE_LEVELS["fr" if language == "fr" else "en"]
    if language == "fr":
        return (
            "Vous êtes un rédacteur senior de spécifications UX / HMI. Vous écrivez des documents de passation "
            "design vers développement, relus par le produit, le design, les développeurs et la recette.\n\n"
            "Politique de preuve, prioritaire sur toute autre consigne :\n"
            "1. L’interface visible (composants, textes, états, variantes, interactions) n’est un fait que si elle "
            "figure dans <screen_json> ou <json_analysis>.\n"
            "2. L’intention produit (objectif, besoin utilisateur, règle métier) n’est un fait que si elle figure "
            "dans <project_context>.\n"
            "3. <project_context> est aussi une source valable pour la navigation, les parcours, les écrans, les "
            "patterns UX (chargement, notifications, erreurs) et le vocabulaire. Ce qu’il dit de l’interface sans que "
            "le JSON le confirme reçoit la confiance Moyen ; s’il contredit le JSON, le JSON l’emporte et l’écart "
            "va dans les questions ouvertes.\n"
            "4. <component_library> sert seulement à préciser le vocabulaire et les états standard ; elle ne prouve "
            "jamais qu’un composant est présent dans la feature.\n"
            "5. Tout le reste, même plausible ou habituel, est une hypothèse ou une question ouverte. Une "
            "spécification fiable vaut mieux qu’une spécification spéculative.\n\n"
            f"Niveaux de confiance, avec exactement ces mots : {high} = appuyé directement par le JSON ou le "
            f"contexte projet ; {medium} = déduction solide croisant plusieurs sources ; {low} = hypothèse.\n\n"
            "Répondez uniquement en Markdown, entièrement en français, en suivant <output_structure> à la lettre "
            "(titres et colonnes des tableaux)."
        )
    return (
        "You are a senior UX/HMI specification writer. You write design-to-development handoff documents "
        "that product, design, engineering and QA review.\n\n"
        "Evidence policy, which overrides every other instruction:\n"
        "1. Visible UI (components, texts, states, variants, interactions) is a fact only when it appears in "
        "<screen_json> or <json_analysis>.\n"
        "2. Product intent (goal, user need, business rule) is a fact only when it appears in <project_context>.\n"
        "3. <project_context> is also a valid source for navigation, user flows, screens, UX patterns (loading, "
        "notifications, errors) and vocabulary. What it says about the interface without the JSON confirming it "
        "gets the Medium confidence; when it contradicts the JSON, the JSON wins and the gap goes to the open "
        "questions.\n"
        "4. <component_library> only refines terminology and standard states; it never proves that a component "
        "is present in the feature.\n"
        "5. Anything else, even plausible or conventional, is an assumption or an open question. A reliable "
        "specification is better than a speculative one.\n\n"
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
) -> dict[str, Any]:
    """Returns {"markdown", "warnings", "corrected", "inventory"}."""
    client = get_openai_client()
    lang = "fr" if language == "fr" else "en"

    # Sources first, then what to produce: models follow instructions placed after the data better.
    context_parts = [part.strip() for part in (priority_context_documents, business_context) if part and part.strip()]
    if len(context_parts) == 2 and context_parts[1] in context_parts[0]:
        context_parts = context_parts[:1]
    texts = TEXTS[lang]
    screen_json = _build_compact_json_source_for_prompt(json_source, analysis, lang)
    analysis_text = format_analysis_for_prompt(analysis)
    try:
        data = json.loads(json_source) if json_source and json_source.strip() else None
    except ValueError:
        data = None
    json_names = collect_json_names(data) if data is not None else set()
    json_texts = collect_json_texts(data) if data is not None else set()
    context_screens = context_screen_names("\n\n".join(context_parts))

    sections = [
        _tagged("project_context", "\n\n".join(context_parts) or texts["no_context"]),
        _tagged("screen_json", screen_json),
        _tagged("json_analysis", analysis_text),
    ]

    scope_key = analysis.get("component_scope", {}).get("scope")
    inventory = None
    if scope_key == "feature_zone" and template_key == "ux_hmi_detailed" and json_names:
        try:
            inventory = extract_component_inventory(client, screen_json, analysis_text, json_names)
        except Exception:  # The inventory only helps: the spec is still written without it.
            logger.warning("Component inventory pass failed", exc_info=True)
        if inventory:
            sections.append(_tagged("component_inventory", inventory))
    if component_library_summary and component_library_summary.strip():
        sections.append(_tagged("component_library", component_library_summary))

    target_lines = []
    if component_scope_label:
        target_lines.append(texts["detected_scope"].format(component_scope_label))
    if component_scope_rationale:
        target_lines.append(texts["why"].format(component_scope_rationale))
    if scope_key in SCOPE_RULES[lang]:
        target_lines.append(SCOPE_RULES[lang][scope_key])
    if component_focus_label:
        target_lines.append(texts["focus"].format(component_focus_label))
    if component_focus_path:
        target_lines.append(texts["focus_path"].format(component_focus_path))
    if target_lines:
        sections.append(_tagged("target", "\n".join(target_lines)))

    if template_key == "ux_hmi_detailed":
        output_structure = _get_ux_hmi_language_rules(lang)
    else:
        output_structure = TEMPLATES[template_key]["prompt"]
    if custom_template and custom_template.strip():
        output_structure += f"\n\n{texts['custom_template']}\n{custom_template.strip()}"
    if context_parts:
        sections.append(_tagged("context_usage", CONTEXT_USAGE[lang]))
    sections.append(_tagged("output_structure", output_structure))

    low = _CONFIDENCE_LEVELS[lang][2]
    rules = [rule.replace("{low}", low) for rule in texts["writing_rules"]]
    if inventory:
        rules.append(texts["inventory_rule"])
    sections.append(_tagged("writing_rules", "\n".join(rules)))
    sections.append(_tagged("detail_level", DETAIL_LEVEL_RULES[lang].get(detail_level, DETAIL_LEVEL_RULES[lang]["standard"])))
    if template_key == "ux_hmi_detailed":
        sections.append(_tagged("examples", _EXAMPLES[lang]))
    sections.append(texts["write_now"])

    messages = [
        {"role": "system", "content": build_spec_system_prompt(lang)},
        {"role": "user", "content": "\n\n".join(sections)},
    ]
    markdown = _clean_output(complete(client, messages), data)
    if not markdown.strip():
        return {"markdown": "# Error\n\nNo content returned by model.\n", "warnings": [], "corrected": False, "inventory": False}

    corrected = False
    issues: dict[str, list[str]] = {"structure": [], "unknown_components": [], "unknown_texts": []}
    if template_key == "ux_hmi_detailed":
        issues = validate_spec(markdown, lang, json_names, json_texts, context_screens)
        if _issue_count(issues):
            # One correction pass with the precise list of problems; a second one rarely helps.
            try:
                retry = complete(
                    client,
                    [
                        *messages,
                        {"role": "assistant", "content": markdown},
                        {"role": "user", "content": format_issues_for_model(issues, lang)},
                    ],
                    temperature=0,
                )
                fixed = _clean_output(retry, data)
            except Exception:
                logger.warning("Spec correction pass failed", exc_info=True)
                fixed = ""
            if fixed.strip():
                fixed_issues = validate_spec(fixed, lang, json_names, json_texts, context_screens)
                # Keep the correction unless it made things worse.
                if _issue_count(fixed_issues) <= _issue_count(issues):
                    markdown, issues, corrected = fixed, fixed_issues, True

    return {
        "markdown": markdown,
        "warnings": format_warnings(issues),
        "corrected": corrected,
        "inventory": bool(inventory),
    }


def _issue_count(issues: dict[str, list[str]]) -> int:
    return sum(len(values) for values in issues.values())


def _clean_output(content: str | None, data: Any) -> str:
    markdown = unwrap_markdown_fence(content or "")
    return replace_json_paths_with_names(markdown, data) if data is not None else markdown
