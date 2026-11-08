# SpecGen

Générateur de documents UX à destination des développeurs :

0. **Convertir en Markdown** (optionnel) — convertit des documents existants (DOCX, PDF, PPTX, XLSX, HTML, TXT) en Markdown réutilisable comme source de contexte. Les schémas **draw.io** (`.drawio`, `.xml`, ou PNG / SVG exportés avec le schéma inclus) sont convertis sans IA : un diagramme Mermaid par page, la liste des relations dans le sens exact des flèches, les regroupements (swimlanes), et une alerte pour chaque flèche non accrochée à deux formes, dont le sens ne peut pas être garanti. Les projets **Mapline** (`.mapline`, ou `.missionmap` des anciennes versions) sont aussi convertis sans IA : chaque carte d'expérience par phase, étape et persona (activités, étiquettes, commentaires, liens), chaque flow en diagramme Mermaid avec la liste de ses enchaînements, et chaque fiche persona. Les images (storyboard, photos) sont laissées de côté.
1. **Contexte projet** — à partir de documents Markdown et des JSON de l'application, génère un document d'architecture UX (parcours, macro layout, navigation…). Les parcours détectés sans IA dans les interactions du prototype servent de source au modèle, et le schéma Mermaid du parcours est placé dans la section « Parcours utilisateur » du document.
2. **Spécification** — à partir du contexte, du JSON d'un écran ou composant et d'une capture optionnelle, génère une spec UX / HMI détaillée (variantes, états, comportements, erreurs), exportable en Word, HTML ou Markdown.

Le contexte et la spécification se modifient directement dans l'aperçu (bouton **Modifier**) : texte saisi dans la page, tableaux cellule par cellule (ajout et suppression de lignes et de colonnes), code des diagrammes Mermaid. Les exports utilisent la version modifiée, et la spécification utilise le contexte modifié. La version générée reste disponible tant que le document n'est pas régénéré.

Après la génération, le bouton **Traduire en anglais** (ou **en français**) traduit le contexte ou la spécification affichés, modifications comprises, sans relancer la génération. Le document est envoyé au modèle section par section ; une section dont la structure change (titres, lignes de tableau, blocs de code) est redemandée une fois, puis signalée dans « Points à vérifier ». Les libellés d'interface cités entre « », les noms de calques Figma, les chemins JSON et le code ne sont pas traduits ; un diagramme Mermaid qui ne s'affiche plus après traduction reprend sa version d'origine. La traduction remplace le document affiché et devient la référence pour l'édition et les exports.

## Architecture

```
backend/    API FastAPI (Python) : conversion Markdown, pipeline de génération LLM, analyse JSON, exports DOCX/HTML/MD
frontend/   Interface React + TypeScript + Tailwind (Vite)
```

En production, le backend sert le frontend compilé (`frontend/dist`) : un seul processus, une seule URL.

## Installation Windows

- **Exécutable (recommandé)** : `SpecGenerator.exe`, sans prérequis. Chaque release GitHub contient `SpecGenerator-X.Y.Z.exe`, fabriqué par le workflow « Build Windows exe » (voir « Versions »). Le même workflow produit aussi l'artefact `SpecGenerator-windows` à chaque push, et l'exe peut être fabriqué :
  - depuis un **Mac** : `./build_exe_mac.sh` (prérequis une fois : `brew install gh && gh auth login`). PyInstaller ne compilant pas pour Windows depuis macOS, le script fait construire l'exe par GitHub Actions, suit le build et télécharge le résultat dans `dist/windows/` ;
  - depuis un **PC Windows** : `build_exe.bat` (Python 3.11+ et Node.js 20+).
- **Depuis les sources** : `install_windows.bat` puis `start_app.bat`.

Voir `README_WINDOWS.txt`.

## Connexion au service IA

Elle se configure dans l'écran **Paramètres** de l'application (URL, clé API, certificat `.crt`, modèle, délai) avec un bouton de test qui diagnostique l'erreur (certificat, URL, clé). Les paramètres sont stockés dans `%APPDATA%\SpecGenerator` (`~/.config/specgenerator` hors Windows) ; la clé API est chiffrée avec le compte Windows (DPAPI).

Un fichier `.env` placé à côté de l'exe (ou à la racine du projet) est prioritaire, champ par champ : voir `.env.example`.

Réglages de génération (facultatifs, dans le `.env`), pensés pour Mistral Small (128 000 tokens de contexte) :

- `CUSTOM_MAX_JSON_CHARS` (80 000 par défaut) : taille maximale du JSON d'écran envoyé pour la spec, sous forme allégée (sans géométrie ni styles). Au-delà, les longues listes puis les niveaux les plus profonds sont coupés. Le contexte en utilise la moitié pour le JSON de l'application.
- `CUSTOM_MAX_CONTEXT_CHARS` (80 000 par défaut) : taille maximale des documents Markdown du contexte.
- `CUSTOM_MAX_OUTPUT_TOKENS` (16 000 par défaut) : longueur maximale d'une réponse. Une réponse coupée est automatiquement poursuivie (3 fois au plus). Si le service refuse cette valeur, l'appel est refait sans.

Le bouton **Tester la connexion** vérifie aussi ce dont la génération a besoin : la longueur de réponse demandée, le mode JSON et la plus grande taille de prompt envoyée. Si un réglage doit être baissé, il l'indique (le test peut durer jusqu'à 3 minutes).

Pour analyser les résultats, cochez **Enregistrer un journal des générations** dans les options avancées des Paramètres (ou `CUSTOM_GENERATION_LOG=1` dans le `.env`). Chaque génération écrit alors un fichier JSON dans le dossier `journal` des paramètres : prompts envoyés, réponses brutes, motif de fin de réponse, corrections, avertissements et durées. Seuls les 100 derniers fichiers sont conservés, et ils restent sur le poste.

Le délai par défaut est de 300 secondes : une génération peut enchaîner plusieurs appels (inventaire, rédaction, correction).

## Templates Word

Les exports DOCX partent des fichiers `Template_Documentatio_{Specs,Context}_{fr,en}.docx`. Pour les personnaliser, ouvrez-les dans Word :

- gardez ce qui doit apparaître tel quel : page de garde, en-têtes / pieds de page, logo, tableaux de suivi, sommaire, styles (`Titre 1`, `Titre 2`, `Normal`, tableaux…) ;
- placez **`{{CONTENT}}`** seul sur une ligne, là où l'application doit écrire le document (sans cette balise, le contenu est ajouté à la fin) ;
- balises facultatives, utilisables partout, y compris dans l'en-tête : `{{DOC_TITLE}}` (titre du document), `{{DOC_SUBTITLE}}`, `{{GENERATED_ON}}` (date de génération). Quand `{{DOC_TITLE}}` est dans le corps (page de garde), le titre n'est pas répété et les sections du document deviennent des `Titre 1`.

Le sommaire est mis à jour par Word à l'ouverture (Word demande confirmation).

Avec l'exécutable, déposez le template modifié **à côté de `SpecGenerator.exe`**, sous le même nom : il remplace celui intégré.

## Lancement par le portail

SpecGen respecte le contrat commun aux applications de la suite :

| | |
|---|---|
| Port par défaut | **8010** |
| Options | `--port N` (port imposé : échec explicite, code 2, s'il est pris par une autre application), `--no-browser`, `--version` |
| État | `GET /health` → `{"status": "ok", "app": "specgen", "name": "SpecGen", "version": "…"}` |

Exemples : `SpecGenerator.exe --port 8010 --no-browser`, ou depuis les sources `python backend/launcher.py --no-browser`. La version vient du fichier `VERSION` (voir « Versions »).

## Versions

Le numéro de version vit à **un seul endroit** : le fichier `VERSION`, à la racine de `specGen-main`. Le backend (`/health`, `--version`), l'interface (bas de l'accueil) et l'exe (Propriétés › Détails sous Windows) le lisent tous là. Les changements sont notés au fil de l'eau dans `CHANGELOG.md`, section « Non publié ».

Numérotation `MAJEUR.MINEUR.CORRECTIF` ([versionnage sémantique](https://semver.org/lang/fr/)) :

| Changement | Exemple | Nouvelle version |
|---|---|---|
| Correction sans nouvelle fonction | un export qui plantait | `1.0.0` → `1.0.1` (`patch`) |
| Nouvelle fonction, rien ne casse | mode sombre, nouvel export | `1.0.1` → `1.1.0` (`minor`) |
| Changement qui casse l'existant | paramètres enregistrés illisibles par l’ancienne version | `1.1.0` → `2.0.0` (`major`) |

Publier une version :

1. Vérifier que `CHANGELOG.md` décrit bien ce qui a changé, sous « Non publié ».
2. `python scripts/bump_version.py minor` (ou `patch`, `major`, ou un numéro `1.2.0`) : met à jour `VERSION`, la version du frontend et date la section du journal.
3. Committer, fusionner sur `main`.
4. Sur GitHub : *Releases › Draft a new release*, tag **`vX.Y.Z`** (le même numéro que `VERSION`), coller la section du journal en description, *Publish release*.
5. Le workflow « Build Windows exe » fabrique l'exe et le joint à la release sous le nom `SpecGenerator-X.Y.Z.exe` (une dizaine de minutes). Si le tag ne correspond pas à `VERSION`, il s'arrête avec un message.

## Développement

```bash
# Backend (port 8010)
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn main:app --app-dir backend --reload --port 8010

# Frontend (port 5173, proxy /api vers le backend)
cd frontend
npm install
npm run dev
```

Tests (backend, sans appel au modèle : un client simulé renvoie des réponses préparées) :

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Les tests utilisent deux exports Figma de démonstration dans `tests/fixtures` (régénérables avec `python tests/make_fixture.py`). Ils couvrent l'analyse JSON, l'allègement du JSON, les vérifications de structure, l'appel au modèle (reprise des réponses coupées, options refusées) et les routes de l'API. Le workflow GitHub « Tests » les lance à chaque push, avec la vérification des types et le build du frontend.

Build de production : `cd frontend && npm run build`, puis `python backend/launcher.py` (ouvre http://127.0.0.1:8010).

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | État de la configuration LLM |
| GET / PUT / DELETE | `/api/settings` | Paramètres de connexion (la clé n'est jamais renvoyée) |
| POST | `/api/settings/certificate` | Import du certificat `.crt` (PEM ou DER) |
| POST | `/api/settings/test` | Test de connexion avec diagnostic |
| POST | `/api/markdown/convert` | Conversion d'un document en Markdown (multipart) |
| POST | `/api/markdown/bundle` | Archive ZIP de plusieurs Markdown |
| POST | `/api/context/generate` | Document de contexte + parcours détectés |
| POST | `/api/context/mermaid` | Schéma de parcours Mermaid depuis le contexte |
| POST | `/api/spec/generate` | Spécification UX / HMI |
| POST | `/api/export/{context\|spec}/{md\|html\|docx}` | Export du document |
