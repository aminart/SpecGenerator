TEMPLATES = {
    "spec_fonctionnelle": {
        "label": "Spec fonctionnelle",
        "prompt": """Structure la sortie en Markdown avec les sections :
1. Objet
2. Finalité
3. Structure générale
4. Description des champs
5. Comportements
6. Règles métier
7. Critères d’acceptation
8. Questions ouvertes
""",
    },
    "ux_hmi_detailed": {
        "label": "Spec UX / HMI détaillée",
        "prompt": """Structure la sortie comme une spécification UX / HMI détaillée orientée feature, proche d’un document de handoff design-to-dev.

La langue du document, y compris tous les titres, sous-titres, labels, noms de colonnes et libellés, doit suivre strictement la langue de sortie demandée.
- Si la langue demandée est le français, tout le document doit être en français.
- Si la langue demandée est l’anglais, tout le document doit être en anglais.
- Ne pas mélanger français et anglais dans un même document.

Attendus de structure Markdown :
- Utiliser exactement les intitulés de sections, sous-sections et colonnes fournis par les consignes de langue transmises dans le prompt principal.
- Ne pas inventer d’autres titres si des titres exacts sont imposés.

Contenu attendu :
- Une vue globale de la feature analysée.
- Une ligne explicite indiquant qu’une image / capture de la feature est à fournir.
- L’objectif de la feature.
- Les façons d’accéder à la feature dans l’application.
- Un tableau détaillant les composants de la feature avec leurs états par défaut et leurs comportements.
- Une dernière partie sur les erreurs potentiellement rencontrées.

Contraintes de rédaction :
- Raisonner par feature ou zone UI et non comme une simple liste brute de champs.
- Décrire les composants d’interface, les états par défaut, les interactions, les effets visibles et les dépendances fonctionnelles.
- Distinguer faits observables, hypothèses raisonnables et questions ouvertes si nécessaire.
- Utiliser un ton professionnel, exploitable par design, produit, dev et QA.
- Si le JSON ne permet pas d’affirmer un comportement, le formuler comme hypothèse ou question ouverte.
- Respecter exactement les intitulés de sections demandés ci-dessus.
- Respecter exactement les colonnes du tableau demandées ci-dessus.
""",
    },
    "user_stories": {
        "label": "User stories",
        "prompt": """Structure la sortie en Markdown avec les sections :
1. Contexte
2. User stories
3. Critères d’acceptation
4. Questions ouvertes
""",
    },
    "field_matrix": {
        "label": "Tableau champs / validations",
        "prompt": """Structure la sortie en Markdown avec les sections :
1. Résumé
2. Tableau des champs
3. Validations
4. Comportements
5. Questions ouvertes

Le tableau des champs doit inclure les colonnes : Champ | Type | Label | Placeholder | Validation | Comportement
""",
    },
}

DEFAULT_TEMPLATE_TEXT = """# Nom de la feature

## Vue d’ensemble de la feature
### Vue globale
- Image de la feature à fournir : [à compléter / capture attendue]

### Objectif

### Moyens d’accès

## Détail de la feature
| ID | Type de composant | État par défaut | Comportement |
|---|---|---|---|
| #1 |  |  |  |

## Erreurs possibles
- Contexte :
- Message ou symptôme visible :
- Impact utilisateur :
- Comportement attendu du système :
"""
