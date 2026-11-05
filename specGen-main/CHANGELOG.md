# Historique des versions de SpecGen

Format : chaque version liste ses changements par type (Ajouté, Modifié, Corrigé). Les numéros suivent
le [versionnage sémantique](https://semver.org/lang/fr/) : voir README, « Versions ».

## [Non publié]

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
