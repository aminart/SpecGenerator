from context_generator import _get_expected_context_structure
from spec_validation import (
    check_against_structure,
    collect_json_names,
    collect_json_texts,
    parse_expected_structure,
    validate_spec,
)


def issues_for(markdown, login_screen):
    return validate_spec(markdown, "fr", collect_json_names(login_screen), collect_json_texts(login_screen))


def test_good_spec_has_no_issue(good_spec_fr, login_screen):
    assert issues_for(good_spec_fr, login_screen) == {"structure": [], "unknown_components": [], "unknown_texts": []}


def test_missing_heading(good_spec_fr, login_screen):
    issues = issues_for(good_spec_fr.replace("## Questions ouvertes\n", ""), login_screen)
    assert issues["structure"] == ["Titre manquant : ## Questions ouvertes"]


def test_wrong_table_columns(good_spec_fr, login_screen):
    markdown = good_spec_fr.replace("| Donnée | Composant Figma | Format | Cas vide / long |", "| Donnée | Format |")
    (issue,) = issues_for(markdown, login_screen)["structure"]
    assert issue.startswith("Le tableau de « Données affichées » doit avoir exactement les colonnes")


def test_confidence_wording_follows_the_language(good_spec_fr, login_screen):
    (issue,) = issues_for(good_spec_fr.replace("| Ouvre Home | Élevé |", "| Ouvre Home | High |"), login_screen)["structure"]
    assert "Élevé, Moyen, Faible" in issue and "High" in issue


def test_apostrophes_and_case_do_not_matter(good_spec_fr, login_screen):
    markdown = good_spec_fr.replace("## Vue d’ensemble de la feature", "## vue d'ensemble de la feature")
    assert issues_for(markdown, login_screen)["structure"] == []


def test_invented_components_are_flagged_in_every_figma_column(good_spec_fr, login_screen):
    markdown = good_spec_fr.replace("| #2 | Button/Primary |", "| #2 | Bouton Annuler |").replace(
        "| Email saisi | Input email |", "| Email saisi | Champ email |"
    )
    assert issues_for(markdown, login_screen)["unknown_components"] == ["Bouton Annuler", "Champ email"]


def test_texts_must_come_from_the_json(good_spec_fr, login_screen):
    markdown = good_spec_fr.replace("| Identifiants invalides |", "| Mot de passe incorrect |")
    assert issues_for(markdown, login_screen)["unknown_texts"] == ["Mot de passe incorrect"]


def test_context_structure_is_parsed_from_the_expected_structure():
    headings, tables = parse_expected_structure(_get_expected_context_structure("fr", "standard"))
    assert (2, "Glossaire métier") in headings and (2, "Liste des écrans") in headings
    assert tables["Liste des écrans"] == ["Écran", "Rôle", "Accès depuis", "Specs liées"]
    assert tables["Hypothèses"] == ["ID", "Hypothèse", "Justification", "Niveau de confiance"]


def test_context_checks(app_document):
    structure = _get_expected_context_structure("fr", "light")
    lines = []
    for line in structure.splitlines():
        if line.startswith("Utiliser"):
            continue
        lines.append(line)
        if line.startswith("|---"):
            cells = ["x"] * (lines[-2].count("|") - 1)
            if "confiance" in lines[-2]:
                cells[-1] = "Moyen"
            lines.append("| " + " | ".join(cells) + " |")
    good = "\n".join(lines)
    assert check_against_structure(good, structure, "fr") == []
    bad = good.replace("## Navigation\n", "").replace("| Moyen |", "| Medium |")
    assert check_against_structure(bad, structure, "fr") == [
        "Titre manquant : ## Navigation",
        "Le niveau de confiance doit valoir Élevé, Moyen, Faible (trouvé dans « Hypothèses » : Medium)",
    ]


CONTEXT_WITH_SCREENS = """# Architecture & Navigation
## Liste des écrans
| Écran | Rôle | Accès depuis | Specs liées |
|---|---|---|---|
| Accueil | Point d’entrée | Connexion | Tableau de bord |
| Connexion | Authentifier | Lancement de l’application | Formulaire de connexion |
"""


def test_screens_are_read_from_the_context():
    from spec_validation import context_screen_names

    assert context_screen_names(CONTEXT_WITH_SCREENS) == ["Accueil", "Connexion"]
    assert context_screen_names("# Sans tableau") == []


def test_ways_of_access_must_name_a_context_screen(good_spec_fr, login_screen):
    names, texts = collect_json_names(login_screen), collect_json_texts(login_screen)
    # The good spec names "Connexion" in its title only, not in Moyens d’accès / Vue globale.
    issues = validate_spec(good_spec_fr, "fr", names, texts, ["Accueil", "Profil"])
    assert issues["structure"] == [
        "La section « Moyens d’accès » ne cite aucun écran de la Liste des écrans du contexte (Accueil, Profil) : "
        "indiquer depuis quel écran et par quelle action on accède à la feature."
    ]
    cited = good_spec_fr.replace("Lancement de l’application (hypothèse).", "Depuis l’écran Accueil, menu Profil.")
    assert validate_spec(cited, "fr", names, texts, ["Accueil", "Profil"])["structure"] == []
    assert validate_spec(good_spec_fr, "fr", names, texts, [])["structure"] == []
