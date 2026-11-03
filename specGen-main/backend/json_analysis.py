from __future__ import annotations

from collections import defaultdict
from typing import Any

FIELD_TYPE_HINTS = [
    "input",
    "text",
    "dropdown",
    "select",
    "toggle",
    "switch",
    "button",
    "modal",
    "radio",
    "checkbox",
    "textarea",
    "segmented",
    "slider",
    "date",
    "picker",
    "tooltip",
    "toolbar",
    "navigation",
    "rail",
    "header",
    "map",
]
SECTION_HINTS = ["section", "group", "panel", "block", "tab", "frame", "container", "card"]
ACTION_HINTS = [
    "save",
    "cancel",
    "close",
    "submit",
    "apply",
    "confirm",
    "delete",
    "continue",
    "next",
    "back",
    "edit",
    "create",
    "update",
    "logout",
    "measure",
    "zoom",
    "screenshot",
    "open",
]
FEATURE_HINT_GROUPS = {
    "header": ["header", "top bar", "app bar"],
    "rail_navigation": ["rail", "navigation", "sidebar", "side bar", "menu"],
    "map_tools": ["map tools", "toolbar", "zoom", "layers", "measure", "screenshot", "compass"],
    "panel": ["panel", "drawer", "side panel", "radar panel", "control panel"],
    "modal_settings": ["settings", "modal", "dialog", "preferences"],
    "tooltip": ["tooltip", "popover", "hint"],
    "map_view": ["map", "radar", "canvas", "viewport"],
    "cross_section": ["vue en coupe", "cross section", "azimut", "azimuth", "profile"],
}
FEATURE_LABELS = {
    "header": "Header",
    "rail_navigation": "Rail / Navigation",
    "map_tools": "Map tools",
    "panel": "Panel / Zone de contrôle",
    "modal_settings": "Modal / Settings",
    "tooltip": "Tooltip",
    "map_view": "Map / Vue principale",
    "cross_section": "Vue en coupe",
}
STATE_HINTS = [
    "default",
    "active",
    "inactive",
    "selected",
    "unselected",
    "disabled",
    "enabled",
    "hover",
    "focused",
    "focus",
    "error",
    "success",
    "warning",
    "loading",
    "open",
    "opened",
    "close",
    "closed",
    "expanded",
    "collapsed",
    "checked",
    "unchecked",
    "empty",
    "filled",
]
ERROR_HINTS = ["error", "invalid", "warning", "failed", "failure", "required", "alert"]
PRIMARY_ACTION_HINTS = ["save", "submit", "confirm", "continue", "next", "create"]
SECONDARY_ACTION_HINTS = ["cancel", "close", "back", "edit", "delete"]
VARIANT_HINTS = [
    "primary",
    "secondary",
    "tertiary",
    "ghost",
    "outline",
    "filled",
    "compact",
    "default",
    "active",
    "inactive",
    "selected",
    "disabled",
]


def to_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def detect_type(node: dict[str, Any]) -> str | None:
    component = node.get("component")
    component_name = None
    if isinstance(component, dict):
        main_component = component.get("mainComponent")
        if isinstance(main_component, dict):
            component_name = to_text(main_component.get("name"))

    candidates = [
        to_text(node.get("type")),
        to_text(node.get("kind")),
        to_text(node.get("component")),
        component_name,
        to_text(node.get("componentType")),
        to_text(node.get("nodeType")),
        to_text(node.get("controlType")),
        to_text(node.get("name")),
    ]
    candidates = [candidate for candidate in candidates if candidate]

    for candidate in candidates:
        lowered = candidate.lower()
        if any(hint in lowered for hint in FIELD_TYPE_HINTS):
            return candidate

    return candidates[0] if candidates else None


def infer_feature_groups(name: str, label: str | None, detected_type: str | None, path: str) -> list[str]:
    text_candidates = [name, label or "", detected_type or "", path]
    searchable_text = " ".join(text_candidates).lower()
    matched_groups: list[str] = []

    for group_key, hints in FEATURE_HINT_GROUPS.items():
        if any(hint in searchable_text for hint in hints):
            matched_groups.append(group_key)

    return matched_groups or ["panel"]



def _collect_text_signals(*values: str | None) -> str:
    return " ".join(value for value in values if value).lower()


def _extract_matching_hints(text: str, hints: list[str]) -> list[str]:
    return [hint for hint in hints if hint in text]


def analyze_json_structure(data: Any) -> dict[str, Any]:
    labels: set[str] = set()
    placeholders: set[str] = set()
    actions: set[str] = set()
    sections: set[str] = set()
    field_types: set[str] = set()
    fields: list[dict[str, str]] = []
    feature_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "label": "Autre feature",
            "components": [],
            "component_types": set(),
            "labels": set(),
            "actions": set(),
            "paths": set(),
        }
    )
    state_signals: set[str] = set()
    error_signals: set[str] = set()
    variant_signals: set[str] = set()
    interaction_clues: set[str] = set()
    component_hierarchy: list[dict[str, Any]] = []
    node_count = 0

    def visit(node: Any, path: str) -> None:
        nonlocal node_count
        node_count += 1

        if isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")
            return

        obj = as_dict(node)
        if not obj:
            return

        name = to_text(obj.get("name")) or to_text(obj.get("title")) or to_text(obj.get("id")) or path

        text_obj = obj.get("text") if isinstance(obj.get("text"), dict) else None
        text_characters = to_text(text_obj.get("characters")) if text_obj else None
        label = (
            to_text(obj.get("label"))
            or to_text(obj.get("text"))
            or text_characters
            or to_text(obj.get("title"))
        )
        placeholder = to_text(obj.get("placeholder"))
        detected_type = detect_type(obj)
        searchable_text = _collect_text_signals(name, label, detected_type, placeholder, path)
        matched_states = _extract_matching_hints(searchable_text, STATE_HINTS)
        matched_errors = _extract_matching_hints(searchable_text, ERROR_HINTS)
        matched_variants = _extract_matching_hints(searchable_text, VARIANT_HINTS)

        if label:
            labels.add(label)
            lowered_label = label.lower()
            if any(hint in lowered_label for hint in ACTION_HINTS):
                actions.add(label)

        if placeholder:
            placeholders.add(placeholder)

        for state in matched_states:
            state_signals.add(state)
        for error in matched_errors:
            error_signals.add(error)
        for variant in matched_variants:
            variant_signals.add(variant)

        if detected_type:
            field_types.add(detected_type)
            lowered_type = detected_type.lower()
            lowered_name = name.lower()

            if any(hint in lowered_type for hint in SECTION_HINTS) or obj.get("children"):
                sections.add(name)

            if any(hint in lowered_type for hint in ACTION_HINTS) or any(hint in lowered_name for hint in ACTION_HINTS):
                actions.add(name)

            if any(hint in searchable_text for hint in PRIMARY_ACTION_HINTS):
                interaction_clues.add(f"primary_action:{label or name}")
            if any(hint in searchable_text for hint in SECONDARY_ACTION_HINTS):
                interaction_clues.add(f"secondary_action:{label or name}")
            if any(hint in searchable_text for hint in ["filter", "search", "sort"]):
                interaction_clues.add(f"data_manipulation:{label or name}")

            is_interactive_field = any(hint in lowered_type for hint in FIELD_TYPE_HINTS)
            is_text_leaf = lowered_type == "text" and bool(label)
            is_named_control = any(hint in lowered_name for hint in FIELD_TYPE_HINTS)

            if is_interactive_field or is_text_leaf or is_named_control:
                fields.append(
                    {
                        "path": path,
                        "name": name,
                        "type": detected_type,
                        "label": label or "-",
                        "placeholder": placeholder or "-",
                        "states": ", ".join(matched_states) or "-",
                        "variants": ", ".join(matched_variants) or "-",
                    }
                )

        children = obj.get("children") if isinstance(obj.get("children"), list) else []
        if detected_type or label or children:
            component_hierarchy.append(
                {
                    "path": path,
                    "name": name,
                    "type": detected_type or "unknown",
                    "label": label or "-",
                    "child_count": len(children),
                    "states": matched_states[:4],
                    "variants": matched_variants[:4],
                    "errors": matched_errors[:4],
                }
            )

        inferred_groups = infer_feature_groups(name, label, detected_type, path)
        for group_key in inferred_groups:
            bucket = feature_buckets[group_key]
            bucket["label"] = FEATURE_LABELS.get(group_key, group_key)
            bucket["paths"].add(path)
            if label:
                bucket["labels"].add(label)
            if detected_type:
                bucket["component_types"].add(detected_type)
            if any(hint in (name or "").lower() for hint in ACTION_HINTS) or any(
                hint in (label or "").lower() for hint in ACTION_HINTS
            ):
                bucket["actions"].add(label or name)

            if detected_type or label:
                bucket["components"].append(
                    {
                        "name": name,
                        "type": detected_type or "unknown",
                        "label": label or "-",
                        "path": path,
                    }
                )

        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                visit(value, f"{path}.{key}")

    visit(data, "$")

    root = as_dict(data) or {}
    component_root = as_dict(root.get("component")) or {}
    root_name = (
        to_text(root.get("name"))
        or to_text(root.get("title"))
        or to_text(component_root.get("name"))
        or "Untitled component"
    )

    feature_groups = []
    for key, bucket in feature_buckets.items():
        feature_groups.append(
            {
                "key": key,
                "label": bucket["label"],
                "component_count": len(bucket["components"]),
                "component_types": sorted(bucket["component_types"])[:12],
                "labels": sorted(bucket["labels"])[:12],
                "actions": sorted(value for value in bucket["actions"] if value)[:12],
                "sample_components": bucket["components"][:8],
            }
        )

    feature_groups.sort(key=lambda item: (-item["component_count"], item["label"]))
    component_hierarchy.sort(key=lambda item: (-item["child_count"], item["name"]))

    analysis = {
        "root_name": root_name,
        "node_count": node_count,
        "field_count": len(fields),
        "action_count": len(actions),
        "section_count": len(sections),
        "field_types": sorted(field_types)[:20],
        "labels": sorted(labels)[:40],
        "placeholders": sorted(placeholders)[:40],
        "actions": sorted(actions)[:20],
        "sections": sorted(sections)[:20],
        "fields": fields[:50],
        "feature_groups": feature_groups[:12],
        "state_signals": sorted(state_signals)[:20],
        "variant_signals": sorted(variant_signals)[:20],
        "error_signals": sorted(error_signals)[:20],
        "interaction_clues": sorted(interaction_clues)[:20],
        "component_hierarchy": component_hierarchy[:20],
    }
    analysis["component_scope"] = classify_component_scope(analysis)
    return analysis


def classify_component_scope(analysis: dict[str, Any]) -> dict[str, Any]:
    child_counts = [item.get("child_count", 0) for item in analysis.get("component_hierarchy", [])[:8]]
    max_child_count = max(child_counts) if child_counts else 0
    feature_group_count = len(analysis.get("feature_groups", []))
    field_count = analysis.get("field_count", 0)
    action_count = analysis.get("action_count", 0)
    distinct_types = len(analysis.get("field_types", []))

    if feature_group_count >= 3 or max_child_count >= 8 or (field_count >= 10 and action_count >= 3):
        scope = "feature_zone"
        label = "Zone fonctionnelle"
        rationale = "Structure étendue avec plusieurs groupes, sous-composants ou interactions."
    elif max_child_count >= 2 or field_count >= 3 or distinct_types >= 3:
        scope = "composite_component"
        label = "Composant composite"
        rationale = "Bloc UI structuré avec plusieurs sous-composants significatifs."
    else:
        scope = "atomic_component"
        label = "Composant atomique"
        rationale = "Élément UI simple avec peu de sous-structure fonctionnelle."

    return {
        "scope": scope,
        "label": label,
        "rationale": rationale,
        "signals": {
            "max_child_count": max_child_count,
            "feature_group_count": feature_group_count,
            "field_count": field_count,
            "action_count": action_count,
            "distinct_types": distinct_types,
        },
    }


def extract_component_focus(data: Any, component_query: str) -> tuple[Any, str] | None:
    normalized_query = (component_query or "").strip().lower()
    if not normalized_query:
        return None

    best_match: tuple[Any, str, int] | None = None

    def visit(node: Any, path: str) -> None:
        nonlocal best_match

        if isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")
            return

        obj = as_dict(node)
        if not obj:
            return

        name = to_text(obj.get("name")) or ""
        title = to_text(obj.get("title")) or ""
        identifier = to_text(obj.get("id")) or ""
        label = to_text(obj.get("label")) or ""
        detected_type = detect_type(obj) or ""
        search_blob = " ".join([name, title, identifier, label, detected_type, path]).lower()

        score = 0
        if normalized_query == path.lower():
            score = 100
        elif normalized_query == identifier.lower() and identifier:
            score = 95
        elif normalized_query == name.lower() and name:
            score = 90
        elif normalized_query == label.lower() and label:
            score = 85
        elif normalized_query in search_blob:
            score = 60

        if score > 0 and (best_match is None or score > best_match[2]):
            best_match = (obj, path, score)

        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                visit(value, f"{path}.{key}")

    visit(data, "$")

    if not best_match:
        return None

    return best_match[0], best_match[1]


def format_analysis_for_prompt(analysis: dict[str, Any]) -> str:
    return format_analysis_for_prompt_compact(analysis, include_paths=True)


def format_analysis_for_prompt_compact(
    analysis: dict[str, Any],
    *,
    include_paths: bool = False,
    max_feature_groups: int = 6,
    max_components_per_group: int = 3,
    max_fields: int = 10,
    max_labels: int = 12,
    max_placeholders: int = 8,
) -> str:
    lines = [
        f"Nom racine: {analysis['root_name']}",
        f"Nombre de noeuds: {analysis['node_count']}",
        f"Nombre de champs détectés: {analysis['field_count']}",
        f"Nombre de sections détectées: {analysis['section_count']}",
        f"Nombre d’actions détectées: {analysis['action_count']}",
        f"Type de cible détecté: {analysis.get('component_scope', {}).get('label', 'Inconnu')}",
        f"Types détectés: {', '.join(analysis['field_types'][:10]) or 'Aucun'}",
        f"Sections: {', '.join(analysis['sections'][:10]) or 'Aucune'}",
        f"Actions: {', '.join(analysis['actions'][:10]) or 'Aucune'}",
        f"États détectés: {', '.join(analysis.get('state_signals', [])[:10]) or 'Aucun'}",
        f"Variantes détectées: {', '.join(analysis.get('variant_signals', [])[:10]) or 'Aucune'}",
        f"Signaux d’erreur: {', '.join(analysis.get('error_signals', [])[:10]) or 'Aucun'}",
        f"Indices d’interaction: {', '.join(analysis.get('interaction_clues', [])[:10]) or 'Aucun'}",
        f"Labels visibles: {' | '.join(analysis['labels'][:max_labels]) or 'Aucun'}",
        f"Placeholders: {' | '.join(analysis['placeholders'][:max_placeholders]) or 'Aucun'}",
        f"Justification du type de cible: {analysis.get('component_scope', {}).get('rationale', 'Aucune')}",
        "Groupes de features détectés:",
    ]

    if analysis.get("feature_groups"):
        for group in analysis["feature_groups"][:max_feature_groups]:
            lines.append(
                f"- {group['label']} | composants: {group['component_count']} | types: {', '.join(group['component_types'][:6]) or 'Aucun'} | labels: {' | '.join(group['labels'][:6]) or 'Aucun'} | actions: {', '.join(group['actions'][:6]) or 'Aucune'}"
            )
            for component in group["sample_components"][:max_components_per_group]:
                component_line = (
                    f"  - composant: {component['name']} | type: {component['type']} | label: {component['label']}"
                )
                if include_paths:
                    component_line += f" | path: {component['path']}"
                lines.append(component_line)
    else:
        lines.append("- Aucun groupe de feature détecté")

    lines.append("Champs détectés:")

    if analysis["fields"]:
        for field in analysis["fields"][:max_fields]:
            field_line = (
                f"- {field['name']} | type: {field['type']} | label: {field['label']} | placeholder: {field['placeholder']} | états: {field.get('states', '-')} | variantes: {field.get('variants', '-')}"
            )
            if include_paths:
                field_line += f" | path: {field['path']}"
            lines.append(field_line)
    else:
        lines.append("- Aucun champ détecté")

    lines.append("Hiérarchie de composants représentative:")
    if analysis.get("component_hierarchy"):
        for component in analysis["component_hierarchy"][:max_fields]:
            component_line = (
                f"- {component['name']} | type: {component['type']} | label: {component['label']} | enfants: {component['child_count']} | états: {', '.join(component.get('states', [])) or '-'} | variantes: {', '.join(component.get('variants', [])) or '-'} | erreurs: {', '.join(component.get('errors', [])) or '-'}"
            )
            if include_paths:
                component_line += f" | path: {component['path']}"
            lines.append(component_line)
    else:
        lines.append("- Aucune hiérarchie représentative détectée")

    return "\n".join(lines)
