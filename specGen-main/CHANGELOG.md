# Historique des versions de SpecGen

Format : chaque version liste ses changements par type (Ajouté, Modifié, Corrigé). Les numéros suivent
le [versionnage sémantique](https://semver.org/lang/fr/) : voir README, « Versions ».

## [Non publié]

### Ajouté

- Schémas Mermaid en mode édition : un clic sur une boîte, une flèche ou un titre de groupe ouvre un champ pour
  renommer son libellé, sans toucher au code. Le code est mis à jour seulement si le schéma s'affiche encore.

## [1.2.1] — 2026-11-09

### Modifié

- Exécutable environ deux fois plus léger : la conversion en Markdown appelle directement le convertisseur de
  chaque format (le type vient de l'extension) au lieu de la détection automatique de MarkItDown, qui embarquait
  un modèle d'IA (Magika, onnxruntime, numpy) ; Excel est lu directement avec openpyxl (sans pandas). Retirés aussi
  de l'exe : pypdfium2 (aperçus de pages PDF, inutilisés), yaml, watchfiles, uvloop.
- Excel : cellules vides laissées vides (plus de « NaN » ni de « Unnamed: 0 »), entiers sans « .0 », lignes et
  colonnes vides ignorées.

### Corrigé

- Fichiers texte enregistrés sous Windows (accents en Windows-1252) : accents correctement lus.

## [1.2.0] — 2026-11-08

### Ajouté

- Convertisseur Markdown : les projets **Mapline** (`.mapline`, et `.missionmap` des anciennes versions) sont
  convertis sans IA. Cartes d'expérience par phase, étape et persona, flows en diagramme Mermaid avec leurs
  enchaînements, fiches personas ; les images sont laissées de côté.
- Nouvelle icône SpecGen, commune avec Studio Dock : icône de l'exe, logo de l'en-tête et icône de l'onglet (dossier `icone/`).
- Releases : un zip contenant l'exe est joint en plus de l'exe.

### Modifié

- En-tête commun à la suite (design system Night Navy 1.1.0) : icône et nom, onglets, puis badge LLM, thème et
  paramètres. Le nom affiché devient « SpecGen » partout.
- Accueil : titre aligné à gauche, « Tout effacer » déplacé dans l'en-tête de la page, étapes numérotées.
- Titres de page en noir (plus en bleu), comme dans les autres apps.

## [1.1.0] — 2026-11-05

### Ajouté

- Versionnement : fichier `VERSION` unique, ce journal, `scripts/bump_version.py`, version affichée sur
  l'accueil et dans les propriétés de l'exe, workflow qui fabrique l'exe et le joint à chaque release GitHub.
- Contrat du portail : `GET /health`, options `--port`, `--no-browser` et `--version` du lanceur.
- Traduction après génération : bouton **Traduire en anglais / en français** sur le contexte et la
  spécification. Le document affiché, modifications comprises, est traduit section par section ; la
  traduction devient la version de référence pour l'édition et les exports (titres et modèles Word dans
  la nouvelle langue). Les libellés d'interface entre « », les noms de calques et le code restent tels quels.

### Modifié

- Port par défaut : 8010 (au lieu de 8000, partagé avec Analyse documentaire). `start_app.bat` passe par
  le lanceur.

### Corrigé

- Contexte : plus aucune balise `<br>` (personas notamment) dans l'aperçu, l'édition et les exports Word,
  HTML et Markdown. Dans un tableau, les éléments sont séparés par « ; », ailleurs par un retour à la ligne.
  Les documents déjà générés sont nettoyés à l'ouverture de l'app.

## [1.0.0] — version de référence

État de l'application avant le versionnement.

- Conversion de documents en Markdown (DOCX, PDF, PPTX, XLSX, HTML, TXT) et des schémas draw.io sans IA.
- Génération du contexte projet et du parcours Mermaid.
- Génération de spécifications UX / HMI, exports Word, HTML et Markdown, templates Word personnalisables.
- Écran Paramètres de connexion au service IA, clé chiffrée avec le compte Windows.
- Exécutable Windows `SpecGenerator.exe`.
