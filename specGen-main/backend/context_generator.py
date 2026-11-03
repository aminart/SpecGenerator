from __future__ import annotations

from typing import Any

from json_analysis import format_analysis_for_prompt_compact
from openai_client import get_model_name, get_openai_client


MAX_ITEMS_PER_LIST = 8
MAX_FIELDS = 12

CONTEXT_PROMPT_PROFILES = {
    "standard": {
        "max_feature_groups": 5,
        "max_components_per_group": 2,
        "max_fields": 8,
        "max_labels": 10,
        "max_placeholders": 6,
        "summary_items": 8,
        "summary_fields": 12,
        "max_priority_context_chars": 12000,
        "include_component_library": True,
    },
    "light": {
        "max_feature_groups": 2,
        "max_components_per_group": 1,
        "max_fields": 4,
        "max_labels": 5,
        "max_placeholders": 3,
        "summary_items": 4,
        "summary_fields": 5,
        "max_priority_context_chars": 6000,
        "include_component_library": False,
    },
}


def _get_expected_context_structure(language: str, context_mode: str) -> str:
    if language == "fr":
        if context_mode == "light":
            return "# Vue d’ensemble du projet\n## Description globale\n## Parcours principaux\n# Architecture & Navigation\n## Macro layout\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Zone | Rôle | Contenu principal | Comportement / règles |\n|---|---|---|---|\n## Navigation\n# Patterns UX\n## Chargement et feedback\n# Hypothèses et questions ouvertes\n## Hypothèses\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Hypothèse | Justification | Niveau de confiance |\n|---|---|---|---|\n## Questions ouvertes\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Question | Contexte | Impact |\n|---|---|---|---|"
        return "# Vue d’ensemble du projet\n## Vue globale de l’application\n## Description globale\n## Personas\n# Parcours utilisateur\n# Architecture & Navigation\n## Macro layout\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Zone | Rôle | Contenu principal | Comportement / règles |\n|---|---|---|---|\n## Navigation\n## Architecture de l’information\n## Présentation des sous-niveaux\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| Niveau | Point d’entrée | Contenu affiché | Interaction / règle |\n|---|---|---|---|\n# Patterns UX\n## Stratégie de chargement\n## Notifications & alertes\n# Spécifications système et accessibilité\n## Grille d’espacement\n## Navigation clavier\n# Hypothèses et questions ouvertes\n## Hypothèses\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Hypothèse | Justification | Niveau de confiance |\n|---|---|---|---|\n## Questions ouvertes\nUtiliser un tableau Markdown avec exactement ces colonnes :\n| ID | Question | Contexte | Impact |\n|---|---|---|---|"

    if context_mode == "light":
        return "# Project overview\n## Global description\n## Main user flows\n# Architecture & Navigation\n## Macro layout\nUse a Markdown table with exactly these columns:\n| Zone | Role | Main content | Behavior / rules |\n|---|---|---|---|\n## Navigation pattern\n# UX patterns\n## Loading and feedback\n# Hypotheses and open questions\n## Hypotheses\nUse a Markdown table with exactly these columns:\n| ID | Hypothesis | Rationale | Confidence level |\n|---|---|---|---|\n## Open questions\nUse a Markdown table with exactly these columns:\n| ID | Question | Context | Impact |\n|---|---|---|---|"
    return "# Project overview\n## Global view of the application\n## Global description\n## Personas\n# User flow\n# Architecture & Navigation\n## Macro layout\nUse a Markdown table with exactly these columns:\n| Zone | Role | Main content | Behavior / rules |\n|---|---|---|---|\n## Navigation pattern\n## Information architecture\n## Sub-level presentation\nUse a Markdown table with exactly these columns:\n| Level | Entry point | Displayed content | Interaction / rule |\n|---|---|---|---|\n# UX patterns\n## Loading strategy\n## Notifications & alerts\n# System specifications and accessibility\n## Spacing grid\n## Keyboard navigation\n# Hypotheses and open questions\n## Hypotheses\nUse a Markdown table with exactly these columns:\n| ID | Hypothesis | Rationale | Confidence level |\n|---|---|---|---|\n## Open questions\nUse a Markdown table with exactly these columns:\n| ID | Question | Context | Impact |\n|---|---|---|---|"


def _join_items(items: list[str], fallback: str = "Aucun", limit: int = MAX_ITEMS_PER_LIST) -> str:
    filtered = [item for item in items if item]
    return ", ".join(filtered[:limit]) if filtered else fallback


def build_context_summary(analysis: dict[str, Any], mode: str = "standard") -> str:
    profile = CONTEXT_PROMPT_PROFILES.get(mode, CONTEXT_PROMPT_PROFILES["standard"])
    feature_groups = analysis.get("feature_groups", [])
    fields = analysis.get("fields", [])

    lines = [
        "# Synthèse structurée de l'application",
        "## Vue d'ensemble",
        f"- Nom racine : {analysis.get('root_name', 'Inconnu')}",
        f"- Nombre de noeuds analysés : {analysis.get('node_count', 0)}",
        f"- Nombre de sections détectées : {analysis.get('section_count', 0)}",
        f"- Nombre d'actions détectées : {analysis.get('action_count', 0)}",
        f"- Nombre de champs détectés : {analysis.get('field_count', 0)}",
        f"- Types de composants détectés : {_join_items(analysis.get('field_types', []), limit=profile['summary_items'])}",
        "## Sections principales détectées",
    ]

    sections = analysis.get("sections", [])
    if sections:
        lines.extend([f"- {section}" for section in sections[: profile['summary_items']]])
    else:
        lines.append("- Aucune section clairement détectée")

    lines.extend(
        [
            "## Actions et verbes d'interaction détectés",
        ]
    )

    actions = analysis.get("actions", [])
    if actions:
        lines.extend([f"- {action}" for action in actions[: profile['summary_items']]])
    else:
        lines.append("- Aucune action clairement détectée")

    lines.extend(
        [
            "## Groupes fonctionnels / zones UI détectées",
        ]
    )

    if feature_groups:
        for group in feature_groups[: profile['summary_items']]:
            lines.append(f"### {group.get('label', 'Feature')} ({group.get('component_count', 0)} composants)")
            lines.append(f"- Types principaux : {_join_items(group.get('component_types', []), limit=profile['summary_items'])}")
            lines.append(f"- Labels visibles : {_join_items(group.get('labels', []), limit=profile['summary_items'])}")
            lines.append(f"- Actions associées : {_join_items(group.get('actions', []), limit=profile['summary_items'])}")
            sample_components = group.get("sample_components", [])
            if sample_components:
                lines.append("- Exemples de composants :")
                for component in sample_components[: profile['max_components_per_group'] + 1]:
                    lines.append(
                        f"  - {component.get('name', 'Composant')} | type: {component.get('type', 'unknown')} | label: {component.get('label', '-') }"
                    )
    else:
        lines.append("- Aucun groupe fonctionnel détecté")

    lines.extend(
        [
            "## Champs et contrôles représentatifs",
        ]
    )

    if fields:
        for field in fields[: profile['summary_fields']]:
            lines.append(
                f"- {field.get('name', 'Champ')} | type: {field.get('type', 'unknown')} | label: {field.get('label', '-')} | placeholder: {field.get('placeholder', '-')}"
            )
    else:
        lines.append("- Aucun champ représentatif détecté")

    labels = analysis.get("labels", [])
    placeholders = analysis.get("placeholders", [])
    lines.extend(
        [
            "## Indices textuels utiles",
            f"- Labels visibles notables : {_join_items(labels, limit=profile['summary_items'])}",
            f"- Placeholders notables : {_join_items(placeholders, limit=profile['summary_items'])}",
        ]
    )

    lines.extend(
        [
            "## Interprétation UX attendue",
            "- Utiliser cette synthèse pour déduire la macro-architecture, la navigation, les zones fixes, les panneaux contextuels, les parcours probables et les patterns UX.",
            "- En cas d'incertitude, formuler des hypothèses explicites au lieu d'inventer des détails.",
        ]
    )

    return "\n".join(lines)


def _truncate_text(value: str | None, max_chars: int) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[Truncated for prompt efficiency]"


def generate_context_markdown(
    global_json_source: str,
    designer_description: str,
    language: str,
    detail_level: str,
    analysis: dict[str, Any],
    context_mode: str = "standard",
    component_library_summary: str | None = None,
    priority_context_documents: str | None = None,
) -> str:
    client = get_openai_client()
    profile = CONTEXT_PROMPT_PROFILES.get(context_mode, CONTEXT_PROMPT_PROFILES["standard"])
    context_summary = build_context_summary(analysis, mode=context_mode)
    expected_structure = _get_expected_context_structure(language, context_mode)
    trimmed_priority_context_documents = _truncate_text(
        priority_context_documents,
        profile["max_priority_context_chars"],
    )
    trimmed_component_library_summary = (
        _truncate_text(component_library_summary, 4000)
        if profile["include_component_library"]
        else "No component library provided."
    )

    system_prompt = (
        "You are a senior UX architecture and product discovery assistant. "
        "Generate a structured Markdown context document from a global application JSON and a free-form designer description. "
        "The output must resemble a UX architecture / HMI project overview document, not a simple note. "
        "Do not invent facts. Distinguish observations, hypotheses, and open questions. "
        "Return clean Markdown only."
    )

    user_prompt = "\n\n".join(
        [
            f"Output language: {'French' if language == 'fr' else 'English'}",
            f"Detail level: {detail_level}",
            f"Context generation mode: {context_mode}",
            f"Expected Markdown structure:\n{expected_structure}",
            f"Priority project context documents:\n{trimmed_priority_context_documents or 'No priority project context documents provided.'}",
            f"Designer free-form description:\n{_truncate_text(designer_description, 3000) or 'No designer description provided.'}",
            f"Structured JSON analysis:\n{format_analysis_for_prompt_compact(analysis, include_paths=False, max_feature_groups=profile['max_feature_groups'], max_components_per_group=profile['max_components_per_group'], max_fields=profile['max_fields'], max_labels=profile['max_labels'], max_placeholders=profile['max_placeholders'])}",
            f"Application summary derived from the JSON:\n{context_summary}",
            f"Component library reference summary:\n{trimmed_component_library_summary}",
            "Important constraints:\n"
            "- Use professional, clear, architecture-oriented wording.\n"
            "- Produce a document close to a UX architecture / project overview deliverable.\n"
            "- Do not focus only on visible widgets; describe navigation logic, macro layout, interaction model, and usage patterns.\n"
            "- Include user flow steps with user action and system feedback when they can be inferred.\n"
            "- Mention personas if they are explicit or strongly suggested by the provided material; otherwise mark them as hypotheses.\n"
            "- Describe fixed zones, contextual panels, navigation logic, and secondary interaction patterns when relevant.\n"
            "- Add loading, notifications, and accessibility/system considerations when they are supported by the context or are strong UX architecture implications.\n"
            "- If an item is uncertain, place it under hypotheses or open questions.\n"
            "- Produce a document usable as a foundation for later detailed specification work.\n"
            "- Treat the priority project context documents and the designer description as the primary sources for product intent, user needs, UX framing, research insights, and business rationale.\n"
            "- Use the structured analysis and the application summary derived from the JSON as secondary sources to validate structure, visible zones, navigation clues, and interaction hints.\n"
            + (
                "- For Architecture & Navigation, actively use the JSON-derived structure to identify fixed zones, panels, view hierarchy, primary navigation, secondary navigation, and likely entry points.\n"
                "- For User flow, combine business intent with the actions, labels, sections, and feature groups detected in the JSON to describe concrete step-by-step flows.\n"
                "- For UX patterns, actively look for evidence of loading, feedback, alerts, form behavior, filtering, contextual panels, and primary versus secondary actions in the JSON-derived material.\n"
                "- For System specifications and accessibility, extract or cautiously infer robust signals such as spacing logic, keyboard navigation, form density, feedback consistency, and recurring structural rules when supported by the JSON.\n"
                if language != "fr"
                else "- Pour la section Architecture & Navigation, exploiter activement la structure issue du JSON afin d’identifier les zones fixes, panneaux, hiérarchie des vues, navigation principale, navigation secondaire et points d’entrée probables.\n"
                "- Pour les parcours utilisateur, combiner l’intention métier avec les actions, labels, sections et groupes fonctionnels détectés dans le JSON afin de décrire des séquences concrètes étape par étape.\n"
                "- Pour les patterns UX, rechercher activement dans les éléments issus du JSON des indices de chargement, feedback, alertes, comportements de formulaires, filtres, panneaux contextuels et actions principales versus secondaires.\n"
                "- Pour les spécifications système et l’accessibilité, extraire ou inférer prudemment les signaux robustes tels que la logique d’espacement, la navigation clavier, la densité des formulaires, la cohérence du feedback et les règles structurelles récurrentes lorsqu’ils sont appuyés par le JSON.\n"
            )
            + "- Treat the component library as a tertiary design-system reference, not as proof that a component is present in the analyzed feature.\n"
            "- Use the component library only to refine terminology, likely variants, and standard interaction patterns when they are consistent with the primary sources.\n"
            "- Do not infer the presence of a component solely because it exists in the component library.\n"
            "- Do not restate raw technical paths unless they are useful for understanding the UX structure.\n"
            "- Prioritize synthesis over exhaustiveness.\n"
            + (
                "- Macro layout must be rendered as a Markdown table, not as bullet points.\n"
                "- Sub-level presentation must be rendered as a Markdown table when the section is present.\n"
                "- Hypotheses must be rendered as a Markdown table, not as bullet points.\n"
                "- Open questions must be rendered as a Markdown table, not as bullet points.\n"
                if language != "fr"
                else "- La section Macro layout doit être rendue sous forme de tableau Markdown, pas sous forme de puces.\n"
                "- La présentation des sous-niveaux doit être rendue sous forme de tableau Markdown lorsque la section est présente.\n"
                "- Les hypothèses doivent être rendues sous forme de tableau Markdown, pas sous forme de puces.\n"
                "- Les questions ouvertes doivent être rendues sous forme de tableau Markdown, pas sous forme de puces.\n"
            )
            + "- Use exactly the requested table column names when they are specified in the expected structure.\n"
            + (
                "- Do not replace these required tables with paragraphs, nested bullets, or '+' lists.\n"
                if language != "fr"
                else "- Ne remplacez pas ces tableaux obligatoires par des paragraphes, des sous-puces ou des listes commençant par '+'.\n"
            )
            + (
                "- In light mode, favor a shorter and more robust document over a highly detailed one."
                if language != "fr"
                else "- En mode light, privilégier un document plus court et plus robuste plutôt qu’un document trop détaillé."
            ),
        ]
    )

    response = client.chat.completions.create(
        model=get_model_name(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.choices[0].message.content or "# Error\n\nNo content returned by model."