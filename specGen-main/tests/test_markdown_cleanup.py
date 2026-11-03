from markdown_cleanup import replace_json_paths_with_names, unwrap_markdown_fence


def test_unwraps_a_fenced_document():
    assert unwrap_markdown_fence("```markdown\n# Titre\n\nTexte\n```") == "# Titre\n\nTexte\n"


def test_keeps_an_unfenced_document():
    assert unwrap_markdown_fence("# Titre\n") == "# Titre\n"


def test_json_paths_become_layer_names(login_screen):
    markdown = "| #1 | `$.children[1].children[3]` |"
    assert replace_json_paths_with_names(markdown, login_screen) == "| #1 | Button/Primary |"
