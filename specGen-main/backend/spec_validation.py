"""Checks run on a generated UX/HMI specification before it is returned.

They find what can be verified without the model: the mandatory headings and table
columns, the confidence wording, and Figma component names that do not exist in the
analyzed JSON (a strong sign of an invented component). Messages are in French: they are
shown in the (French) interface and sent back to the model for the correction pass.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from json_analysis import NON_STRUCTURAL_KEYS

CONFIDENCE_LEVELS = {"fr": ("Élevé", "Moyen", "Faible"), "en": ("High", "Medium", "Low")}

EXPECTED_HEADINGS = {
    "fr": [
        (2, "Vue d’ensemble de la feature"),
        (3, "Vue globale"),
        (3, "Objectif"),
        (3, "Moyens d’accès"),
        (2, "Variantes de la feature"),
        (2, "Détail de la feature"),
        (2, "Erreurs possibles"),
        (2, "Hypothèses"),
        (2, "Questions ouvertes"),
    ],
    "en": [
        (2, "Feature overview"),
        (3, "Global view"),
        (3, "Goal"),
        (3, "Ways of access"),
        (2, "Feature variants"),
        (2, "Feature details"),
        (2, "Possible errors"),
        (2, "Assumptions"),
        (2, "Open questions"),
    ],
}

EXPECTED_TABLES = {
    "fr": {
        "Variantes de la feature": ["ID", "Variante", "Contexte d’affichage", "Différences visuelles / comportementales", "Conditions / règles"],
        "Détail de la feature": ["ID", "Composant Figma", "Type de composant", "État par défaut", "Comportement", "Niveau de confiance"],
    },
    "en": {
        "Feature variants": ["ID", "Variant", "Display context", "Visual / behavioral differences", "Conditions / rules"],
        "Feature details": ["ID", "Figma component", "Component type", "Default state", "Behavior", "Confidence level"],
    },
}

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_EMPTY_CELL = {"", "-", "—", "–", "n/a", "na"}


def normalize_name(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("’", "'").replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _sections(markdown: str) -> list[tuple[int, str, list[str]]]:
    """(level, title, body lines) for each heading, in order."""
    sections: list[tuple[int, str, list[str]]] = []
    in_code = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _HEADING.match(line)
        if match:
            sections.append((len(match.group(1)), match.group(2), []))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _first_table(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    rows = [line for line in lines if line.strip().startswith("|")]
    if len(rows) < 2:
        return None
    header = _split_row(rows[0])
    body = [_split_row(row) for row in rows[1:] if not re.fullmatch(r"\|?[\s:|-]+\|?", row.strip())]
    return header, body


def _find_section(markdown: str, title: str) -> list[str] | None:
    wanted = normalize_name(title)
    for _, heading, lines in _sections(markdown):
        if normalize_name(heading) == wanted:
            return lines
    return None


def check_structure(markdown: str, language: str) -> list[str]:
    lang = "fr" if language == "fr" else "en"
    issues: list[str] = []
    sections = _sections(markdown)
    if not sections or sections[0][0] != 1:
        issues.append("Le document doit commencer par un titre de niveau 1 contenant le nom de la feature.")

    present = {(level, normalize_name(title)) for level, title, _ in sections}
    for level, title in EXPECTED_HEADINGS[lang]:
        if (level, normalize_name(title)) not in present:
            issues.append(f"Titre manquant : {'#' * level} {title}")

    for title, columns in EXPECTED_TABLES[lang].items():
        lines = _find_section(markdown, title)
        if lines is None:
            continue
        table = _first_table(lines)
        if table is None:
            issues.append(f"La section « {title} » doit contenir un tableau Markdown avec les colonnes : {' | '.join(columns)}")
            continue
        header, rows = table
        if [normalize_name(cell) for cell in header] != [normalize_name(cell) for cell in columns]:
            issues.append(
                f"Le tableau de « {title} » doit avoir exactement les colonnes {' | '.join(columns)} "
                f"(trouvé : {' | '.join(header)})"
            )
        elif title in ("Détail de la feature", "Feature details"):
            allowed = {normalize_name(level) for level in CONFIDENCE_LEVELS[lang]}
            wrong = sorted({row[-1] for row in rows if len(row) == len(columns) and normalize_name(row[-1]) not in allowed})
            if wrong:
                issues.append(
                    f"Le niveau de confiance doit valoir {', '.join(CONFIDENCE_LEVELS[lang])} (trouvé : {', '.join(wrong)})"
                )
    return issues


def collect_json_names(data: Any) -> set[str]:
    names: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                names.add(normalize_name(name))
            for key, item in value.items():
                # mainComponent holds the component name of an instance: a valid name too.
                if isinstance(item, (dict, list)) and (key not in NON_STRUCTURAL_KEYS or key == "mainComponent"):
                    collect(item)

    collect(data)
    return names


def unknown_component_names(markdown: str, language: str, json_names: set[str]) -> list[str]:
    """Names in the Figma component column that match no `name` of the JSON."""
    if not json_names:
        return []
    lang = "fr" if language == "fr" else "en"
    title, columns = next(
        (title, columns) for title, columns in EXPECTED_TABLES[lang].items() if title in ("Détail de la feature", "Feature details")
    )
    lines = _find_section(markdown, title)
    table = _first_table(lines) if lines is not None else None
    if table is None:
        return []
    header, rows = table
    normalized_header = [normalize_name(cell) for cell in header]
    column = normalize_name(columns[1])
    if column not in normalized_header:
        return []
    index = normalized_header.index(column)

    unknown: list[str] = []
    for row in rows:
        if index >= len(row):
            continue
        cell = row[index]
        if normalize_name(cell) in _EMPTY_CELL or normalize_name(cell) in json_names:
            continue
        # A row may group repeated elements: "Input email, Input password".
        parts = [part for part in re.split(r"\s*(?:,|;|<br\s*/?>|\s\+\s)\s*", cell) if normalize_name(part) not in _EMPTY_CELL]
        if not parts or any(normalize_name(part) not in json_names for part in parts):
            if cell not in unknown:
                unknown.append(cell)
    return unknown


def validate_spec(markdown: str, language: str, json_names: set[str]) -> dict[str, list[str]]:
    return {
        "structure": check_structure(markdown, language),
        "unknown_components": unknown_component_names(markdown, language, json_names),
    }


def format_issues_for_model(issues: dict[str, list[str]], language: str) -> str:
    low = CONFIDENCE_LEVELS["fr" if language == "fr" else "en"][2]
    lines = [
        "The document has the problems listed below (in French). Return the complete corrected document, "
        "in Markdown only, in the same output language, keeping everything else unchanged."
    ]
    lines.extend(f"- {issue}" for issue in issues["structure"])
    if issues["unknown_components"]:
        lines.append(
            "- These values of the Figma component column match no `name` in the JSON: "
            + ", ".join(f'"{name}"' for name in issues["unknown_components"])
            + ". Replace each with the exact `name` of the layer in the JSON. If the row is not supported by the "
            f"JSON, write a dash (-) in that column and set its confidence to {low}, or remove the row."
        )
    return "\n".join(lines)


def format_warnings(issues: dict[str, list[str]]) -> list[str]:
    warnings = list(issues["structure"])
    warnings.extend(
        f"Composant absent du JSON : « {name} » (peut-être inventé)" for name in issues["unknown_components"]
    )
    return warnings
