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


def test_generic_layers_get_a_readable_name():
    from json_analysis import is_generic_layer_name

    assert is_generic_layer_name("Frame 01010") and is_generic_layer_name("frame01010") and is_generic_layer_name("Group 12")
    assert not is_generic_layer_name("Input email") and not is_generic_layer_name("Button/Primary")
    screen = {
        "id": "1:1", "name": "Écran", "type": "FRAME", "children": [
            {"id": "1:2", "name": "Frame 01010", "type": "FRAME", "children": [
                {"id": "1:3", "name": "Label", "type": "TEXT", "characters": "Valider la commande"}]},
            {"id": "1:4", "name": "Group 12", "type": "INSTANCE", "componentId": "9:9"},
            {"id": "1:5", "name": "Rectangle 3", "type": "RECTANGLE"},
        ],
        "components": {"9:9": {"name": "Button/Secondary"}},
    }
    pruned = json.loads(prune_json_for_prompt(screen, 100_000)[0])
    frame, group, rectangle = pruned["children"]
    assert frame["readable_name"] == "« Valider la commande »"
    assert group["readable_name"] == "Button/Secondary"  # main component from the REST components map
    assert "readable_name" not in rectangle  # nothing to say about it
    assert "readable_name" not in pruned  # "Écran" is a real name
