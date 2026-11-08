"""Conversion of Mapline projects (.mapline, formerly .missionmap) to Markdown.

A Mapline file is JSON (see aminart/Mapline, src/model/types.ts and
serialize.ts). Version 2 holds a titled list of documents (mission maps,
flows, persona sheets); version 1 (before Mapline 0.10, no "version" key) is
a single mission map. Everything is read from the file, never from an AI.
Images (storyboard scenes, persona photos) are left out.
"""
from __future__ import annotations

import json
from typing import Any

MAPLINE_EXTENSIONS = {".mapline", ".missionmap"}
SUPPORTED_VERSION = 2

_ALT_SUFFIX = ":b"  # second card sharing a cell, see altKey() in Mapline
_DIVIDER_TOP = ""
_NODE_KINDS = {"start": "Début", "end": "Fin", "activity": "Activité", "choice": "Décision"}
_SOURCE_KINDS = {"phase": "la phase", "step": "l'étape", "act": "l'activité"}


class NotAMaplineFile(ValueError):
    pass


def convert_mapline(content: bytes, title: str = "Projet") -> str:
    try:
        raw = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotAMaplineFile("Ce fichier n'est pas un projet Mapline valide (JSON illisible).") from exc
    if not isinstance(raw, dict):
        raise NotAMaplineFile("Ce fichier n'est pas un projet Mapline valide.")
    version = raw.get("version")
    if isinstance(version, (int, float)) and version > SUPPORTED_VERSION:
        raise NotAMaplineFile("Ce projet vient d'une version plus récente de Mapline, que SpecGen ne sait pas encore lire.")

    if version in (None, 1):
        docs: list[Any] = [{"kind": "mission-map", "name": "", "map": raw}]
    else:
        docs = raw.get("docs")
        if not isinstance(docs, list) or not docs:
            raise NotAMaplineFile("Ce projet Mapline ne contient aucun document.")

    maps = {d.get("id"): d.get("map") for d in docs if isinstance(d, dict) and d.get("kind") == "mission-map"}
    lines = [f"# {_text(raw.get('title')) or title}", ""]
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind == "mission-map" and isinstance(doc.get("map"), dict):
            lines += _map_markdown(_text(doc.get("name")) or "Carte d'expérience", doc["map"])
        elif kind == "flow" and isinstance(doc.get("flow"), dict):
            lines += _flow_markdown(_text(doc.get("name")) or "Flow", doc["flow"], maps)
        elif kind == "persona" and isinstance(doc.get("sheet"), dict):
            lines += _sheet_markdown(doc["sheet"])
    if len(lines) <= 2:
        raise NotAMaplineFile("Aucun document lisible n'a été trouvé dans ce projet Mapline.")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- helpers

def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _tags(value: Any) -> str:
    tags = [t.strip() for t in value if isinstance(t, str) and t.strip()] if isinstance(value, list) else []
    return f" `{'` `'.join(tags)}`" if tags else ""


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;").replace("|", "#124;").replace("\n", " ")


# ---------------------------------------------------------------- mission map

def _phase_of_steps(phases: list[dict[str, Any]], step_count: int) -> list[str]:
    """Phase title of each step, following each phase's span in order."""
    out: list[str] = []
    for phase in phases:
        span = phase.get("span")
        span = int(span) if isinstance(span, (int, float)) and span > 0 else 1
        out += [_text(phase.get("title")) or "Phase sans titre"] * span
    return (out + [""] * step_count)[:step_count]


def _activity_line(activity: dict[str, Any], prefix: str = "") -> list[str]:
    text = _text(activity.get("text"))
    if activity.get("kind") == "choice":
        text = f"Décision : {text}"
    line = f"{prefix}{text or '_(carte vide)_'}{_tags(activity.get('tags'))}"
    lines = [line]
    note = _text(activity.get("note"))
    if note:
        resolved = " _(traité)_" if activity.get("noteResolved") else ""
        lines.append(f"  - Commentaire{resolved} : {note}")
    return lines


def _map_markdown(name: str, doc: dict[str, Any]) -> list[str]:
    steps = _list(doc.get("steps"))
    personas = _list(doc.get("personas"))
    activities = _dict(doc.get("activities"))
    scenes = _dict(doc.get("scenes"))
    text_rows = _list(doc.get("textRows"))
    if not text_rows and _dict(doc.get("infos")):  # single info row of files before Mapline 1.2
        text_rows = [{"title": doc.get("infoTitle"), "text": doc.get("infoText"), "cells": doc.get("infos")}]
    phase_of_step = _phase_of_steps(_list(doc.get("phases")), len(steps))

    lines = [f"## Carte : {name}", ""]
    objective = _text(doc.get("objective"))
    if objective:
        lines += [f"**Objectif** : {objective}", ""]

    if personas:
        lines += ["### Personas", ""]
        dividers = {d.get("after"): _text(d.get("label")) for d in _list(doc.get("dividers"))}
        if dividers.get(_DIVIDER_TOP):
            lines.append(f"- — {dividers[_DIVIDER_TOP]} —")
        for persona in personas:
            role = _text(persona.get("role"))
            lines.append(f"- **{_text(persona.get('name')) or 'Persona'}**" + (f" : {role}" if role else ""))
            if dividers.get(persona.get("id")):
                lines.append(f"- — {dividers[persona.get('id')]} —")
        lines.append("")

    labels: dict[str, str] = {}
    current_phase = None
    for index, step in enumerate(steps, start=1):
        phase = phase_of_step[index - 1]
        if phase and phase != current_phase:
            lines += [f"### Phase : {phase}", ""]
        current_phase = phase
        lines += [f"#### Étape {index} : {_text(step.get('title')) or 'sans titre'}", ""]
        scene = _text(_dict(scenes.get(step.get("id"))).get("text"))
        if doc.get("storyboard") and scene:
            lines += [f"_Storyboard_ : {scene}", ""]
        slots = step.get("slots") if isinstance(step.get("slots"), list) and step.get("slots") else [f"{step.get('id')}-0"]
        for persona in personas:
            cards: list[str] = []
            for slot in slots:
                key = f"{persona.get('id')}:{slot}"
                for activity, alt in ((activities.get(key), False), (activities.get(key + _ALT_SUFFIX), True)):
                    if not isinstance(activity, dict):
                        continue
                    if activity.get("id"):
                        labels[activity["id"]] = _text(activity.get("text")) or "carte vide"
                    if not (_text(activity.get("text")) or activity.get("tags") or _text(activity.get("note"))):
                        continue
                    joiner = (_text(activity.get("joiner")) or "ou") if alt else ""
                    cards += _activity_line(activity, f"_{joiner}_ " if joiner else "")
            if cards:
                lines.append(f"- **{_text(persona.get('name')) or 'Persona'}**")
                lines += [f"  - {card}" if not card.startswith("  ") else f"  {card}" for card in cards]
        for row in text_rows:
            cell = _text(_dict(row.get("cells")).get(step.get("id")))
            if cell:
                lines.append(f"- _{_text(row.get('title')) or 'Informations'}_ : {cell}")
        lines.append("")

    links = [link for link in _list(doc.get("links")) if link.get("from") in labels and link.get("to") in labels]
    if links:
        lines += ["### Liens entre activités", ""]
        for link in links:
            label = _text(link.get("label"))
            lines.append(f"- **{labels[link['from']]}** → **{labels[link['to']]}**" + (f" : {label}" if label else ""))
        lines.append("")
    return lines


# ---------------------------------------------------------------- flow

def _flow_markdown(name: str, flow: dict[str, Any], maps: dict[Any, Any]) -> list[str]:
    nodes = [n for n in _list(flow.get("nodes")) if n.get("id")]
    by_id = {n["id"]: n for n in nodes}
    links = [l for l in _list(flow.get("links")) if l.get("from") in by_id and l.get("to") in by_id]
    lines = [f"## Flow : {name}", ""]

    source = _dict(flow.get("source"))
    origin = _source_label(source, maps)
    if origin:
        lines += [f"_Détaille {origin}._", ""]
    brief = _text(flow.get("brief"))
    if brief:
        lines += [f"**{_text(flow.get('briefTitle')) or 'Objectifs'}** : {brief}", ""]
    if not nodes:
        return lines + ["_Flow vide._", ""]

    def label(node: dict[str, Any]) -> str:
        return _text(node.get("text")) or _NODE_KINDS.get(node.get("kind"), "Carte")

    ids = {node["id"]: f"n{i}" for i, node in enumerate(sorted(nodes, key=_grid_pos), start=1)}
    cols = {n.get("col") for n in nodes}
    rows = {n.get("row") for n in nodes}
    lines += ["```mermaid", f"flowchart {'LR' if len(cols) > len(rows) else 'TD'}"]
    for node in sorted(nodes, key=_grid_pos):
        text = _mermaid_text(label(node))
        kind = node.get("kind")
        if kind == "choice":
            lines.append(f'  {ids[node["id"]]}{{"{text}"}}')
        elif kind in ("start", "end"):
            lines.append(f'  {ids[node["id"]]}(["{text}"])')
        else:
            lines.append(f'  {ids[node["id"]]}["{text}"]')
    for link in links:
        arrow = "-.->" if link.get("style") in ("dashed", "dotted") else "-->"
        edge_label = _text(link.get("label"))
        edge_label = f"|{_mermaid_text(edge_label)}|" if edge_label else ""
        lines.append(f"  {ids[link['from']]} {arrow}{edge_label} {ids[link['to']]}")
    lines += ["```", ""]

    if links:
        lines += ["### Enchaînements", ""]
        for link in links:
            edge_label = _text(link.get("label"))
            lines.append(f"- **{label(by_id[link['from']])}** → **{label(by_id[link['to']])}**" + (f" : {edge_label}" if edge_label else ""))
        lines.append("")

    details = [n for n in sorted(nodes, key=_grid_pos) if n.get("tags") or _text(n.get("note"))]
    if details:
        lines += ["### Détails des cartes", ""]
        for node in details:
            lines.append(f"- **{label(node)}**{_tags(node.get('tags'))}")
            note = _text(node.get("note"))
            if note:
                resolved = " _(traité)_" if node.get("noteResolved") else ""
                lines.append(f"  - Commentaire{resolved} : {note}")
        lines.append("")
    return lines


def _grid_pos(node: dict[str, Any]) -> tuple[float, float]:
    row, col = node.get("row"), node.get("col")
    return (row if isinstance(row, (int, float)) else 0, col if isinstance(col, (int, float)) else 0)


def _source_label(source: dict[str, Any], maps: dict[Any, Any]) -> str:
    target = _dict(maps.get(source.get("docId")))
    kind, item_id = source.get("kind"), source.get("id")
    if not target or kind not in _SOURCE_KINDS:
        return ""
    if kind == "act":
        items = [a for a in _dict(target.get("activities")).values() if isinstance(a, dict)]
        key = "text"
    else:
        items = _list(target.get("phases" if kind == "phase" else "steps"))
        key = "title"
    found = next((_text(i.get(key)) for i in items if i.get("id") == item_id), "")
    return f"{_SOURCE_KINDS[kind]} « {found} »" if found else ""


# ---------------------------------------------------------------- persona sheet

def _sheet_markdown(sheet: dict[str, Any]) -> list[str]:
    name = _text(sheet.get("name")) or "Persona"
    role = _text(sheet.get("role"))
    lines = [f"## Persona : {name}" + (f" — {role}" if role else ""), ""]
    fields = [f for f in _list(sheet.get("fields")) if _text(f.get("value"))]
    for field in fields:
        lines.append(f"- **{_text(field.get('label')) or 'Champ'}** : {_text(field.get('value'))}")
    if fields:
        lines.append("")
    quote = _text(sheet.get("quote"))
    if quote:
        lines += [f"> {quote}", ""]
    tags = _tags(sheet.get("tags"))
    if tags:
        lines += [f"Étiquettes :{tags}", ""]
    for block in _list(sheet.get("blocks")):
        body: list[str] = []
        if block.get("view") == "text":
            text = _text(block.get("text"))
            if text:
                body.append(text)
        else:
            for item in _list(block.get("items")):
                text = _text(item.get("text"))
                if not text:
                    continue
                level = item.get("level")
                if block.get("view") == "gauges" and isinstance(level, (int, float)):
                    text += f" : {round(level)} %"
                body.append(f"- {text}")
        if body:
            lines += [f"### {_text(block.get('title')) or 'Bloc'}", "", *body, ""]
    return lines
