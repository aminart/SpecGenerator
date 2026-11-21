# Historique des versions de SpecGen

Format : chaque version liste ses changements par type (Ajouté, Modifié, Corrigé). Les numéros suivent
le [versionnage sémantique](https://semver.org/lang/fr/) : voir README, « Versions ».

## [Non publié]

## [1.4.1] — 2026-11-21

### Modifié

- Design system Night Navy 1.2.1 : les cases à cocher (réglages, listes de tâches de l'aperçu) prennent le style
  commun aux apps de la suite — contour gris foncé, coché en bleu marine, focus visible, clair et sombre.

## [1.4.0] — 2026-11-19

### Modifié

- Régénérer un contexte ou une spécification modifié ou traduit demande d'abord confirmation. La version
  remplacée reste disponible : « Restaurer la version précédente », sous le titre du document, permet de
  passer de l'une à l'autre.
- Une génération continue quand on change d'onglet : l'onglet affiche une roue tant qu'elle tourne, et la page
  montre de nouveau l'attente quand on y revient (plus de second lancement possible par erreur).
- L'attente pendant une génération ne simule plus l'avancement d'étapes, qui restait bloqué sur la dernière
  pendant plusieurs minutes : elle affiche le temps écoulé et la liste de ce que fait SpecGen.
- « Image de la feature » devient « Image d'illustration », avec la précision qu'elle est insérée dans le
  document et les exports mais n'est pas lue par l'IA.
- « Générer une spécification » prévient, sous le bouton, quand aucun contexte projet n'est fourni.
- La spécification signale quand le contexte projet a changé depuis sa génération (nouvelle génération,
  modification, traduction ou autre fichier importé), avec un bouton « Régénérer ».
- Traduire garde la version d'origine : un sélecteur Français / English permet de passer d'une version à
  l'autre, chacune avec ses propres modifications. « Retraduire » remplace la version de l'autre langue.
- Un seul bouton « Exporter » ouvre le choix du format (Word, Markdown, page web) ; en mode édition,
  « Terminer » n'est plus un second bouton plein à côté.
- « Points à vérifier » : chaque point mène à la section concernée (« Voir la section ») et peut être marqué
  « Traité » ; les points traités se réaffichent d'un clic.
- Les fichiers ajoutés sur « Convertir en Markdown » et pas encore convertis restent dans la liste quand on
  change d'onglet, et une conversion en cours continue (roue sur l'onglet).

### Corrigé

- Quand le bandeau « Génération désactivée » est affiché, le bas de la colonne des sources (bouton de
  génération et message) n'est plus coupé.
- En mode édition, la barre d'aide reste visible sous l'en-tête au lieu de passer derrière.

## [1.3.0] — 2026-11-17

### Ajouté

- Modèles d'IA de Studio Dock : quand Studio Dock fournit la connexion (Réglages › Modèles d'IA, commune à toutes
  les apps de la suite, y compris un modèle local d'Ollama), SpecGen l'utilise avec le modèle choisi pour lui.
  L'écran Paramètres l'affiche en lecture seule ; les paramètres propres à SpecGen sont gardés et reprennent la
  main si Studio Dock lui laisse sa configuration propre. Un fichier .env reste prioritaire.
- Choix du modèle parmi ceux de Studio Dock : champ « Modèle d'IA » dans « Créer un contexte » et « Générer une
  spécification », valable pour la session (traductions et schémas compris) ; modèle par défaut dans Paramètres.

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
