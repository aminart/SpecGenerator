from __future__ import annotations

from typing import Any

from json_analysis import format_analysis_for_prompt, format_analysis_for_prompt_compact
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


def _build_compact_json_source_for_prompt(json_source: str, analysis: dict[str, Any]) -> str:
    normalized = (json_source or "").strip()
    if not normalized:
        return "No raw JSON source provided."

    if len(normalized) <= 4000:
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

    system_prompt = (
        "You are a senior product specification assistant specialized in UX/HMI and functional documentation. "
        "Generate a structured product specification from UI JSON analysis and business context. "
        "Treat the analyzed screen/component JSON as the central structural source for the specification. "
        "Do not invent facts. If information is uncertain, place it under open questions or as a hypothesis. "
        "Use a strict evidence policy: visible UI facts must be grounded in the JSON or structured JSON analysis; product intent facts must be grounded in the priority context documents or explicit business context. "
        "When the requested format is UX/HMI-oriented, describe the feature from a design-to-development perspective: visible components, default states, interactions, variants, and error handling. "
        "Strictly follow the requested output language. "
        "Strictly follow any exact section titles, subtitles, labels, and table columns provided in the instructions. "
        "If exact headings are requested, reproduce them verbatim. "
        "Return clean Markdown only."
    )

    template_instruction = TEMPLATES[template_key]["prompt"]
    compact_json_source = _build_compact_json_source_for_prompt(json_source, analysis)

    prompt_sections = [
        f"Output language: {'French' if language == 'fr' else 'English'}",
        f"Detail level: {detail_level}",
        f"Selected template instruction:\n{template_instruction}",
    ]

    if component_focus_label:
        prompt_sections.append(f"Component focus target:\n{component_focus_label}")
    if component_focus_path:
        prompt_sections.append(f"Component focus path:\n{component_focus_path}")
    if component_scope_label:
        prompt_sections.append(f"Detected target scope:\n{component_scope_label}")
    if component_scope_rationale:
        prompt_sections.append(f"Target scope rationale:\n{component_scope_rationale}")

    if template_key == "ux_hmi_detailed":
        prompt_sections.append(_get_ux_hmi_language_rules(language))

    if custom_template and custom_template.strip():
        prompt_sections.append(f"Custom template:\n{custom_template.strip()}")

    prompt_sections.extend(
        [
            f"Priority context documents:\n{priority_context_documents or 'No priority context documents provided.'}",
            f"Business context:\n{business_context or 'No business context provided.'}",
            f"Structured JSON analysis:\n{format_analysis_for_prompt(analysis)}",
            f"Component library reference summary:\n{component_library_summary or 'No component library provided.'}",
            f"Raw JSON source or compact fallback:\n{compact_json_source}",
            "Important constraints:\n"
            "- Separate facts, inferred behaviors, and open questions when needed.\n"
            "- Keep the output practical and professional.\n"
            "- Apply a strict evidence policy across the whole document.\n"
            "- Treat the analyzed JSON as the central source for visible UI structure, components, states, variants, and interaction clues.\n"
            "- Treat the priority context documents as the primary source for product intent, user needs, research insights, business rationale, and UX framing.\n"
            "- Use the business context as a primary supporting source when it is aligned with the priority context documents.\n"
            "- Reconcile the contextual intent with the JSON evidence instead of replacing the JSON with contextual assumptions.\n"
            "- Avoid repeating raw JSON mechanically.\n"
            "- Produce a document that can be reviewed by product, design, engineering, and QA.\n"
            "- If the structure suggests a UI feature, organize the output around feature intent, ways of access, variants, component states, behaviors, and error handling.\n"
            "- Prefer explicit Markdown tables when the selected format asks for component-by-component details.\n"
            "- Use the JSON analysis to infer visible UI building blocks, but clearly mark uncertain points as hypotheses or open questions.\n"
            "- A visible component, visible state, visible variant, visible error, or visible interaction may be presented as a fact only if it is directly supported by the raw JSON or the structured JSON analysis.\n"
            "- Product intent, user need, or business rationale may be presented as a fact only if supported by the priority context documents or explicit business context.\n"
            "- If a statement is only plausible or conventional but not directly evidenced by the primary sources, classify it as a hypothesis, not as a fact.\n"
            "- In the feature details table, the Figma component column must contain the exact Figma layer or component name as written in the JSON `name` field (e.g. Button/Primary, Header, Input email). Never write JSON paths such as $.children[0], never write the words JSON or structured analysis there. If a row is only supported by the context documents, write a dash (-) in that column.\n"
            "- When filling the feature details table, assign a confidence level for each row using only High, Medium, or Low.\n"
            "- High confidence requires direct support from JSON or explicit supporting documents. Medium confidence is allowed only for strong cross-source inference. Low confidence must remain conservative and should usually correspond to hypotheses.\n"
            "- Treat the component library as a tertiary design-system reference, not as proof that a component is present in the analyzed feature.\n"
            "- Use the component library only after the priority context documents, business context, and JSON analysis have been considered.\n"
            "- Use the component library only to refine terminology, likely variants, default states, and standard interaction patterns when they are consistent with the primary sources.\n"
            "- Do not infer the presence of a component solely because it exists in the component library.\n"
            "- Never use the component library as the sole basis for asserting presence, state, behavior, or variant of a component in the analyzed feature.\n"
            "- If the raw JSON is omitted or compacted, rely primarily on the priority context documents, business context, structured analysis, and compact summary rather than assuming missing details.\n"
            "- If the UX/HMI structure defines exact headings and exact table columns, they are mandatory and must be reproduced verbatim.\n"
            "- The document must be fully monolingual in the requested language.\n"
            "- Do not mix French and English in titles, labels, tables, or bullet points.\n"
            "- Include only sections that are supported by the data, except mandatory sections explicitly required by the prompt.\n"
            "- Always include the final sections for hypotheses and open questions, even if they are brief or explicitly state that no additional item was identified.\n"
            "- If the evidence is weak for a component-level statement, prefer a shorter but reliable specification over a detailed speculative one.\n"
            "- If a component focus target is provided, center the specification on that component and its direct substructure rather than the whole screen.\n"
            "- If a component focus path is provided, treat it as the strongest locator for the target component within the JSON structure.\n"
            "- If the detected target scope is atomic component, keep the specification concise and focused on the single UI element, its states, and its direct behavior.\n"
            "- If the detected target scope is composite component, document the root component and its significant sub-components, their relationships, and internal interaction logic.\n"
            "- If the detected target scope is feature zone, document the target as a broader functional block with its main internal components, user intent, access paths, and structural variants.",
        ]
    )

    user_prompt = "\n\n".join(prompt_sections)

    response = client.chat.completions.create(
        model=get_model_name(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.choices[0].message.content or "# Error\n\nNo content returned by model."
