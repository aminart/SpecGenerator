# SpecGen

Générateur de documents UX à destination des développeurs :

0. **Convertir en Markdown** (optionnel) — convertit des documents existants (DOCX, PDF, PPTX, XLSX, HTML, TXT) en Markdown réutilisable comme source de contexte. Les schémas **draw.io** (`.drawio`, `.xml`, ou PNG / SVG exportés avec le schéma inclus) sont convertis sans IA : un diagramme Mermaid par page, la liste des relations dans le sens exact des flèches, les regroupements (swimlanes), et une alerte pour chaque flèche non accrochée à deux formes, dont le sens ne peut pas être garanti.
1. **Contexte projet** — à partir de documents Markdown et des JSON de l'application, génère un document d'architecture UX (parcours, macro layout, navigation…) et un schéma de parcours Mermaid.
2. **Spécification** — à partir du contexte, du JSON d'un écran ou composant et d'une capture optionnelle, génère une spec UX / HMI détaillée (variantes, états, comportements, erreurs), exportable en Word, HTML ou Markdown.

## Architecture

```
backend/    API FastAPI (Python) : conversion Markdown, pipeline de génération LLM, analyse JSON, exports DOCX/HTML/MD
frontend/   Interface React + TypeScript + Tailwind (Vite)
```

En production, le backend sert le frontend compilé (`frontend/dist`) : un seul processus, une seule URL.

## Installation Windows

- **Exécutable (recommandé)** : `SpecGenerator.exe`, sans prérequis. Il est produit par le workflow GitHub Actions « Build Windows exe » (artefact `SpecGenerator-windows`, à chaque push), ou :
  - depuis un **Mac** : `./build_exe_mac.sh` (prérequis une fois : `brew install gh && gh auth login`). PyInstaller ne compilant pas pour Windows depuis macOS, le script fait construire l'exe par GitHub Actions, suit le build et télécharge le résultat dans `dist/windows/` ;
  - depuis un **PC Windows** : `build_exe.bat` (Python 3.11+ et Node.js 20+).
- **Depuis les sources** : `install_windows.bat` puis `start_app.bat`.

Voir `README_WINDOWS.txt`.

## Connexion au service IA

Elle se configure dans l'écran **Paramètres** de l'application (URL, clé API, certificat `.crt`, modèle, délai) avec un bouton de test qui diagnostique l'erreur (certificat, URL, clé). Les paramètres sont stockés dans `%APPDATA%\SpecGenerator` (`~/.config/specgenerator` hors Windows) ; la clé API est chiffrée avec le compte Windows (DPAPI).

Un fichier `.env` placé à côté de l'exe (ou à la racine du projet) est prioritaire, champ par champ : voir `.env.example`.

Pour la spec, le JSON de l'écran est envoyé au modèle sous une forme élaguée (sans géométrie ni styles). Sa taille maximale est de 40 000 caractères par défaut ; avec un modèle à grande fenêtre de contexte, on peut l'augmenter dans le `.env` avec `CUSTOM_MAX_JSON_CHARS=120000`. Au-delà, les longues listes et les niveaux les plus profonds sont coupés.

## Templates Word

Les exports DOCX partent des fichiers `Template_Documentatio_{Specs,Context}_{fr,en}.docx`. Pour les personnaliser, ouvrez-les dans Word :

- gardez ce qui doit apparaître tel quel : page de garde, en-têtes / pieds de page, logo, tableaux de suivi, sommaire, styles (`Titre 1`, `Titre 2`, `Normal`, tableaux…) ;
- placez **`{{CONTENT}}`** seul sur une ligne, là où l'application doit écrire le document (sans cette balise, le contenu est ajouté à la fin) ;
- balises facultatives, utilisables partout, y compris dans l'en-tête : `{{DOC_TITLE}}` (titre du document), `{{DOC_SUBTITLE}}`, `{{GENERATED_ON}}` (date de génération). Quand `{{DOC_TITLE}}` est dans le corps (page de garde), le titre n'est pas répété et les sections du document deviennent des `Titre 1`.

Le sommaire est mis à jour par Word à l'ouverture (Word demande confirmation).

Avec l'exécutable, déposez le template modifié **à côté de `SpecGenerator.exe`**, sous le même nom : il remplace celui intégré.

## Développement

```bash
# Backend (port 8000)
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn main:app --app-dir backend --reload --port 8000

# Frontend (port 5173, proxy /api vers le backend)
cd frontend
npm install
npm run dev
```

Build de production : `cd frontend && npm run build`, puis `uvicorn main:app --app-dir backend` et ouvrir http://127.0.0.1:8000.

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
