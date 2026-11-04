import copy
import json

from json_analysis import analyze_json_structure
from spec_generator import _build_compact_json_source_for_prompt, get_max_json_chars, prune_json_for_prompt


def test_pruning_drops_geometry_and_keeps_ui(login_screen):
    text, reduced = prune_json_for_prompt(login_screen, 100_000)
    pruned = json.loads(text)
    assert not reduced
    assert "absoluteBoundingBox" not in text and "fills" not in text and '"id"' not in text
    form = pruned["children"][1]
    assert form["children"][0]["properties"] == {"State": "Default", "Show helper": "false"}
    assert form["children"][2]["visible"] is False
    assert form["children"][3]["interactions"] == ["ON_CLICK: NAVIGATE → 9:1"]


def test_medium_json_is_sent_pruned_instead_of_dropped(login_screen):
    source = json.dumps(login_screen, indent=2)
    assert len(source) > 4000  # used to be replaced by a summary
    prompt = _build_compact_json_source_for_prompt(source, analyze_json_structure(login_screen), "fr")
    assert prompt.startswith("JSON allégé")
    assert "Identifiants invalides" in prompt


def test_long_sibling_lists_are_cut_to_fit(login_screen):
    big = copy.deepcopy(login_screen)
    form = big["children"][1]
    form["children"] += [copy.deepcopy(form["children"][0]) for _ in range(400)]
    text, reduced = prune_json_for_prompt(big, 20_000)
    assert reduced and len(text) <= 20_000
    assert '"children_omitted"' in text


def test_summary_only_when_nothing_fits(login_screen):
    prompt = _build_compact_json_source_for_prompt(json.dumps(login_screen), analyze_json_structure(login_screen), "en")
    assert prompt.startswith("JSON source pruned")
    tiny = prune_json_for_prompt(login_screen, 50)
    assert tiny is None


def test_json_budget_comes_from_the_environment(monkeypatch):
    assert get_max_json_chars() == 80_000
    monkeypatch.setenv("CUSTOM_MAX_JSON_CHARS", "1234")
    assert get_max_json_chars() == 1234
    monkeypatch.setenv("CUSTOM_MAX_JSON_CHARS", "nope")
    assert get_max_json_chars() == 80_000
