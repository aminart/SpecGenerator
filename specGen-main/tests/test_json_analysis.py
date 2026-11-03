from json_analysis import analyze_json_structure, format_analysis_for_prompt


def test_reads_figma_variant_properties(login_screen):
    analysis = analyze_json_structure(login_screen)
    properties = {item["name"]: item["properties"] for item in analysis["component_properties"]}
    assert properties["Input email"] == "State=Default, Show helper=false"  # "#12:3" id suffix removed
    assert properties["Input password"] == "State=Focused"
    assert {"Default", "Focused"} <= set(analysis["state_signals"])
    assert "Type=Primary" in analysis["variant_signals"]


def test_reads_component_set_definitions(app_document):
    analysis = analyze_json_structure(app_document)
    (variant_set,) = analysis["variant_sets"]
    assert variant_set["name"] == "Button"
    assert variant_set["properties"]["State"] == ["Default", "Hover", "Disabled"]
    assert {"Hover", "Disabled"} <= set(analysis["state_signals"])


def test_reads_hidden_layers_and_interactions(app_document):
    analysis = analyze_json_structure(app_document)
    assert analysis["hidden_elements"] == ["Error message"]
    (interaction,) = analysis["interactions"]
    assert interaction["source"] == "Button/Primary"
    assert interaction["interaction"] == "ON_CLICK: NAVIGATE → Home"  # destination id resolved to its name


def test_reads_top_level_characters_as_labels(login_screen):
    labels = analyze_json_structure(login_screen)["labels"]
    assert {"Connexion", "Se connecter", "Mot de passe oublié ?"} <= set(labels)


def test_feature_groups_follow_the_file_hierarchy(login_screen):
    analysis = analyze_json_structure(login_screen)
    assert analysis["feature_group_source"] == "hierarchy"
    assert [group["label"] for group in analysis["feature_groups"]] == ["Header", "Form", "Footer"]


def test_wrapper_nodes_are_skipped_for_groups(app_document):
    # Document > Page > three frames: the frames are the groups, not the page.
    labels = [group["label"] for group in analyze_json_structure(app_document)["feature_groups"]]
    assert labels == ["Header", "Form", "Footer", "Home", "Button"]


def test_keyword_groups_only_without_hierarchy():
    analysis = analyze_json_structure({"items": [{"name": "Header bar", "type": "header"}, {"name": "Email", "type": "input"}]})
    assert analysis["feature_group_source"] == "keywords"
    assert {group["label"] for group in analysis["feature_groups"]} == {"Header", "Formulaire"}


def test_styling_keys_are_not_walked_as_nodes(login_screen):
    analysis = analyze_json_structure(login_screen)
    assert "SOLID" not in analysis["field_types"]
    assert "VARIANT" not in analysis["field_types"]


def test_prompt_lists_the_figma_signals(app_document):
    text = format_analysis_for_prompt(analyze_json_structure(app_document))
    assert "Button | Type: Primary, Secondary, Ghost ; State: Default, Hover, Disabled" in text
    assert "Button/Primary | ON_CLICK: NAVIGATE → Home" in text
    assert "Éléments masqués" in text and "Error message" in text
