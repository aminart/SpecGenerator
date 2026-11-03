from __future__ import annotations

import json
from typing import Any, Dict, List


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _collect_candidate_texts(node: Any, texts: List[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            lowered_key = key.lower()
            if lowered_key in {
                "name",
                "label",
                "title",
                "text",
                "placeholder",
                "value",
                "caption",
                "description",
                "type",
                "componenttype",
                "nodetype",
                "controltype",
            }:
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
                elif isinstance(value, dict):
                    characters = value.get("characters")
                    if isinstance(characters, str) and characters.strip():
                        texts.append(characters.strip())
            _collect_candidate_texts(value, texts)
    elif isinstance(node, list):
        for item in node:
            _collect_candidate_texts(item, texts)


def json_to_figma_like_context(data: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    root_name = analysis.get("root_name", "Imported JSON")
    labels = analysis.get("labels", [])[:30]
    actions = analysis.get("actions", [])[:20]
    sections = analysis.get("sections", [])[:20]
    field_types = analysis.get("field_types", [])[:20]
    placeholders = analysis.get("placeholders", [])[:20]

    candidate_texts: List[str] = []
    _collect_candidate_texts(data, candidate_texts)
    unique_candidate_texts = []
    seen = set()
    for item in candidate_texts:
        if item not in seen:
            seen.add(item)
            unique_candidate_texts.append(item)

    feature_groups = analysis.get("feature_groups", [])
    screens = []

    if feature_groups:
        for index, group in enumerate(feature_groups, start=1):
            group_labels = group.get("labels", [])[:12]
            group_actions = group.get("actions", [])[:12]
            component_types = group.get("component_types", [])[:12]
            sample_components = group.get("sample_components", [])
            child_blocks = [
                {"name": component.get("name", "Component"), "type": component.get("type", "unknown")}
                for component in sample_components[:8]
            ]
            texts = []
            texts.extend(group_labels)
            texts.extend(group_actions)
            texts.extend(component_types)
            texts.extend([component.get("name", "") for component in sample_components[:8]])
            texts = [text for text in texts if text]

            screens.append(
                {
                    "id": f"json-screen-{index}",
                    "name": group.get("label", f"Feature {index}"),
                    "page": root_name,
                    "type": "FRAME",
                    "score": max(40, group.get("component_count", 0) * 5),
                    "selected_by_user": False,
                    "selected_node_id": None,
                    "ui_summary": {
                        "buttons": group_actions,
                        "labels": group_labels,
                        "key_texts": texts[:40],
                        "short_texts": texts[:30],
                        "long_texts": [],
                        "text_overflow_count": max(0, len(texts) - 40),
                        "raw_text_count": len(texts),
                    },
                    "structure": {
                        "child_blocks": child_blocks,
                        "components": [component.get("name", "") for component in sample_components[:8]],
                        "instances": component_types[:8],
                        "component_count": group.get("component_count", 0),
                        "instance_count": len(component_types[:8]),
                        "child_block_count": len(child_blocks),
                    },
                }
            )

    if not screens:
        fallback_texts = labels + actions + sections + field_types + placeholders + unique_candidate_texts[:30]
        screens.append(
            {
                "id": "json-screen-1",
                "name": root_name,
                "page": root_name,
                "type": "FRAME",
                "score": 50,
                "selected_by_user": False,
                "selected_node_id": None,
                "ui_summary": {
                    "buttons": actions,
                    "labels": labels,
                    "key_texts": fallback_texts[:40],
                    "short_texts": fallback_texts[:30],
                    "long_texts": [],
                    "text_overflow_count": max(0, len(fallback_texts) - 40),
                    "raw_text_count": len(fallback_texts),
                },
                "structure": {
                    "child_blocks": [{"name": section, "type": "SECTION"} for section in sections[:8]],
                    "components": sections[:8],
                    "instances": field_types[:8],
                    "component_count": len(sections[:8]),
                    "instance_count": len(field_types[:8]),
                    "child_block_count": len(sections[:8]),
                },
            }
        )

    return {
        "source_type": "json_import_adapted_context",
        "summary": {
            "page_count": 1,
            "screen_count": len(screens),
            "main_screen_count": 1,
            "optimization": {
                "source": "imported_json",
            },
        },
        "main_screens": [
            {
                "page": root_name,
                "primary_screen": screens[0]["name"],
                "score": screens[0]["score"],
            }
        ],
        "global_signals": {
            "buttons": actions[:30],
            "labels": labels[:30],
            "key_texts": unique_candidate_texts[:60],
        },
        "pages": {
            root_name: screens,
        },
    }


def normalize_screen_text(screen: Dict[str, Any]) -> str:
    parts = [screen.get("name", ""), screen.get("page", ""), screen.get("type", "")]
    ui_summary = screen.get("ui_summary", {})
    structure = screen.get("structure", {})
    parts.extend(ui_summary.get("buttons", []))
    parts.extend(ui_summary.get("labels", []))
    parts.extend(ui_summary.get("key_texts", []))
    parts.extend(ui_summary.get("short_texts", []))
    parts.extend(ui_summary.get("long_texts", []))
    parts.extend(structure.get("components", []))
    parts.extend(structure.get("instances", []))
    parts.extend(block.get("name", "") for block in structure.get("child_blocks", []))
    return " ".join(part.lower() for part in parts if part)


def classify_screen(screen: Dict[str, Any]) -> List[str]:
    text = normalize_screen_text(screen)
    categories: List[str] = []

    map_keywords = {"map", "carte", "radar", "distance", "rings", "blind area", "visible"}
    settings_keywords = {"settings", "display", "altitude", "elevation", "asl", "agl", "layers", "position"}
    tooltip_keywords = {"tooltip", "tootltip", "max", "reached", "aide", "help"}
    modal_keywords = {"modal", "dialog", "cancel", "save", "reset", "confirmation"}
    cut_view_keywords = {"coupe", "section", "profile"}
    two_d_view_keywords = {"2d", "vue_2d", "carte"}

    if any(keyword in text for keyword in map_keywords):
        categories.append("map")
    if any(keyword in text for keyword in settings_keywords):
        categories.append("settings")
    if any(keyword in text for keyword in tooltip_keywords):
        categories.append("tooltip")
    if any(keyword in text for keyword in modal_keywords):
        categories.append("modal")
    if any(keyword in text for keyword in cut_view_keywords):
        categories.append("cut_view")
    if any(keyword in text for keyword in two_d_view_keywords):
        categories.append("2d_view")

    return categories or ["unclassified"]


def infer_screen_role(screen: Dict[str, Any]) -> str:
    name = screen.get("name", "")
    text = normalize_screen_text(screen)
    if "tooltip" in text or "tootltip" in text or "aide" in text:
        return "feedback_overlay"
    if "modal" in text or "dialog" in text or "confirmation" in text:
        return "confirmation_dialog"
    if "settings" in text or "display" in text or "altitude" in text or "param" in text:
        return "configuration"
    if "vue_en_coupe" in name.lower() or "coupe" in text or "section" in text:
        return "visualization_cross_section"
    if "vue_2d" in name.lower() or "2d" in text or "carte" in text or "map" in text:
        return "visualization_map"
    return "supporting_screen"


def flatten_screens(figma_like_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    screens: List[Dict[str, Any]] = []
    for page_name, page_screens in figma_like_context.get("pages", {}).items():
        for screen in page_screens:
            enriched = dict(screen)
            enriched["page"] = page_name
            enriched["categories"] = classify_screen(enriched)
            enriched["role"] = infer_screen_role(enriched)
            screens.append(enriched)
    return screens


def build_rule_based_journeys(figma_like_context: Dict[str, Any], prototype_links: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    screens = flatten_screens(figma_like_context)
    prototype_links = prototype_links or []

    screens_by_role: Dict[str, List[Dict[str, Any]]] = {}
    for screen in screens:
        screens_by_role.setdefault(screen["role"], []).append(screen)

    map_screens = screens_by_role.get("visualization_map", [])
    cut_screens = screens_by_role.get("visualization_cross_section", [])
    config_screens = screens_by_role.get("configuration", [])
    overlay_screens = screens_by_role.get("feedback_overlay", [])
    dialog_screens = screens_by_role.get("confirmation_dialog", [])

    journeys: List[Dict[str, Any]] = []

    if map_screens and config_screens:
        primary_map = map_screens[0]
        primary_config = config_screens[0]
        steps = [primary_map["name"], primary_config["name"]]
        if dialog_screens:
            steps.append(dialog_screens[0]["name"])
        journeys.append(
            {
                "name": "Parcours de configuration",
                "type": "principal",
                "objective": "Accéder aux paramètres depuis la vue principale et ajuster l'affichage.",
                "entry_points": [primary_map["name"]],
                "steps": steps,
                "decisions": ["Modifier un paramètre", "Valider ou annuler les changements"],
                "alternate_paths": [],
                "error_states": [],
                "related_screens": list(dict.fromkeys(steps)),
                "prototype_links": [],
            }
        )

    if map_screens and cut_screens:
        primary_map = map_screens[0]
        primary_cut = cut_screens[0]
        journeys.append(
            {
                "name": "Parcours de comparaison des vues",
                "type": "principal",
                "objective": "Comparer les informations entre la vue principale et la vue en coupe.",
                "entry_points": [primary_map["name"], primary_cut["name"]],
                "steps": [primary_map["name"], primary_cut["name"]],
                "decisions": ["Choisir la vue la plus adaptée"],
                "alternate_paths": [f"{primary_cut['name']} → {primary_map['name']}"],
                "error_states": [],
                "related_screens": [primary_map["name"], primary_cut["name"]],
                "prototype_links": [],
            }
        )

    if config_screens and overlay_screens:
        primary_config = config_screens[0]
        primary_overlay = overlay_screens[0]
        journeys.append(
            {
                "name": "Parcours d'aide contextuelle",
                "type": "secondaire",
                "objective": "Afficher une aide contextuelle pendant la configuration.",
                "entry_points": [primary_config["name"]],
                "steps": [primary_config["name"], primary_overlay["name"]],
                "decisions": ["Consulter l'aide puis revenir à la configuration"],
                "alternate_paths": [],
                "error_states": [],
                "related_screens": [primary_config["name"], primary_overlay["name"]],
                "prototype_links": [],
            }
        )

    if not journeys and screens:
        primary_screen = sorted(screens, key=lambda item: item.get("score", 0), reverse=True)[0]
        journeys.append(
            {
                "name": "Parcours principal",
                "type": "principal",
                "objective": "Explorer l'écran principal détecté dans le JSON fourni.",
                "entry_points": [primary_screen["name"]],
                "steps": [primary_screen["name"]],
                "decisions": [],
                "alternate_paths": [],
                "error_states": [],
                "related_screens": [primary_screen["name"]],
                "prototype_links": [],
            }
        )

    return {
        "source": "json_rule_based",
        "summary": {
            "screen_count": len(screens),
            "journey_count": len(journeys),
            "page_count": figma_like_context.get("summary", {}).get("page_count", 0),
            "prototype_link_count": len(prototype_links),
        },
        "journeys": journeys,
        "screens": screens,
        "prototype_links": prototype_links,
    }


def journeys_to_markdown(analysis: Dict[str, Any]) -> str:
    lines: List[str] = []
    summary = analysis.get("summary", {})
    journeys = analysis.get("journeys", [])

    lines.append("# Cartographie des parcours utilisateurs")
    lines.append("")
    lines.append("## Vue d'ensemble")
    lines.append(f"- Nombre d'écrans analysés : {summary.get('screen_count', 0)}")
    lines.append(f"- Nombre de parcours détectés : {summary.get('journey_count', 0)}")
    lines.append(f"- Nombre de pages : {summary.get('page_count', 0)}")
    lines.append("")

    if journeys:
        lines.append("## Parcours détectés")
        for journey in journeys:
            lines.append(f"- {journey['name']} ({journey['type']})")
        lines.append("")

    for journey in journeys:
        lines.append(f"## {journey['name']}")
        lines.append("")
        lines.append(f"- Type : {journey['type']}")
        lines.append(f"- Objectif : {journey['objective']}")
        lines.append(f"- Point(s) d'entrée : {', '.join(journey.get('entry_points', []))}")
        lines.append(f"- Étapes : {' → '.join(journey.get('steps', []))}")

        if journey.get("decisions"):
            lines.append("")
            lines.append("### Décisions")
            for item in journey["decisions"]:
                lines.append(f"- {item}")

        if journey.get("alternate_paths"):
            lines.append("")
            lines.append("### Chemins alternatifs")
            for item in journey["alternate_paths"]:
                lines.append(f"- {item}")

        if journey.get("error_states"):
            lines.append("")
            lines.append("### États d'erreur ou blocage")
            for item in journey["error_states"]:
                lines.append(f"- {item}")

        if journey.get("related_screens"):
            lines.append("")
            lines.append("### Écrans concernés")
            for item in journey["related_screens"]:
                lines.append(f"- {item}")

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def journeys_to_mermaid(analysis: Dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    node_ids: Dict[str, str] = {}
    node_index = 0
    declared_nodes = set()
    declared_edges = set()

    def get_node_id(label: str) -> str:
        nonlocal node_index
        if label not in node_ids:
            node_index += 1
            node_ids[label] = f"N{node_index}"
        return node_ids[label]

    for journey_index, journey in enumerate(analysis.get("journeys", []), start=1):
        subgraph_id = f"J{journey_index}"
        lines.append(f"    subgraph {subgraph_id}[\"{journey['name']}\"]")
        steps = journey.get("steps", [])
        for step in steps:
            node_id = get_node_id(step)
            if node_id not in declared_nodes:
                lines.append(f'        {node_id}["{step}"]')
                declared_nodes.add(node_id)
        for current_step, next_step in zip(steps, steps[1:]):
            current_id = get_node_id(current_step)
            next_id = get_node_id(next_step)
            edge = (current_id, next_id)
            if edge not in declared_edges:
                lines.append(f"        {current_id} --> {next_id}")
                declared_edges.add(edge)
        lines.append("    end")

    return "\n".join(lines) + "\n"


def _compute_confidence(journey: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    score += min(len(journey.get("steps", [])) * 12, 36)
    score += min(len(journey.get("related_screens", [])) * 8, 24)
    score += min(len(journey.get("decisions", [])) * 6, 18)
    score += min(len(journey.get("prototype_links", [])) * 10, 20)

    if journey.get("type") == "principal":
        score += 8
    elif journey.get("type") == "secondaire":
        score += 4

    score = min(score, 100)
    if score >= 75:
        label = "Élevée"
    elif score >= 45:
        label = "Moyenne"
    else:
        label = "Faible"

    return {"score": score, "label": label}


def _build_shared_screens_summary(journey_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    usage: Dict[str, Dict[str, Any]] = {}
    for journey in journey_analysis.get("journeys", []):
        for screen_name in journey.get("related_screens", []):
            if screen_name not in usage:
                usage[screen_name] = {
                    "screen_name": screen_name,
                    "journey_names": [],
                    "journey_count": 0,
                    "journey_types": [],
                }
            usage[screen_name]["journey_names"].append(journey.get("name", "Parcours"))
            usage[screen_name]["journey_types"].append(journey.get("type", "inconnu"))

    shared = []
    for item in usage.values():
        item["journey_names"] = list(dict.fromkeys(item["journey_names"]))
        item["journey_types"] = list(dict.fromkeys(item["journey_types"]))
        item["journey_count"] = len(item["journey_names"])
        if item["journey_count"] > 1:
            shared.append(item)

    shared.sort(key=lambda entry: (-entry["journey_count"], entry["screen_name"]))
    return shared


def analyze_user_journeys_from_json(data: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    figma_like_context = json_to_figma_like_context(data, analysis)
    journey_analysis = build_rule_based_journeys(figma_like_context, prototype_links=[])

    for journey in journey_analysis.get("journeys", []):
        journey["confidence"] = _compute_confidence(journey)
        journey["step_flow"] = " → ".join(journey.get("steps", []))

    shared_screens = _build_shared_screens_summary(journey_analysis)
    journey_analysis["shared_screens"] = shared_screens
    journey_analysis.setdefault("summary", {})["shared_screen_count"] = len(shared_screens)

    return {
        "figma_like_context": figma_like_context,
        "journey_analysis": journey_analysis,
        "journey_markdown": journeys_to_markdown(journey_analysis),
        "journey_mermaid": journeys_to_mermaid(journey_analysis),
        "journey_analysis_json": json.dumps(journey_analysis, ensure_ascii=False, indent=2),
    }
