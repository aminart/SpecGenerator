INSTALLATION WINDOWS - SPECGENERATOR
====================================

OPTION 1 (RECOMMANDEE) : L'EXECUTABLE
-------------------------------------
Aucun prerequis : ni Python, ni Node.js.

1. Copiez SpecGenerator.exe dans un dossier, par exemple C:\SpecGenerator
2. Double-cliquez sur SpecGenerator.exe
   - une fenetre noire s'ouvre : gardez-la ouverte pendant l'utilisation,
     la fermer arrete l'application ;
   - le navigateur s'ouvre sur http://127.0.0.1:8000
3. Au premier lancement, l'ecran "Parametres de connexion" s'affiche :
   - URL du service
   - Cle API
   - Certificat de l'entreprise (fichier .crt)
   Cliquez sur "Tester la connexion", puis "Enregistrer et commencer".

Les parametres sont enregistres dans %APPDATA%\SpecGenerator (la cle API est
chiffree avec votre compte Windows). Ils se modifient a tout moment via la
pastille "LLM connecte" / "Mode apercu" en haut a droite.

Windows SmartScreen peut afficher "Windows a protege votre ordinateur" au
premier lancement (executable non signe) : cliquez sur "Informations
complementaires" puis "Executer quand meme".

Deploiement sur plusieurs postes : un fichier .env place a cote de
SpecGenerator.exe est prioritaire sur l'ecran Parametres (voir .env.example).

Ou trouver l'executable : onglet "Actions" du depot GitHub, workflow
"Build Windows exe", artefact "SpecGenerator-windows". Ou construisez-le
avec build_exe.bat (necessite Python 3.11+ et Node.js 20+).


OPTION 2 : DEPUIS LES SOURCES
-----------------------------
Prerequis : Python 3.11+ (cochez "Add Python to PATH") et Node.js 20+.

1. Dezippez le code source dans un dossier.
2. Double-cliquez sur install_windows.bat
3. Double-cliquez sur start_app.bat
4. Configurez la connexion dans l'ecran Parametres (comme pour l'option 1).

Mise a jour : remplacez les fichiers puis relancez install_windows.bat.


PERSONNALISER LES TEMPLATES WORD
--------------------------------
Les fichiers Template_Documentatio_*.docx livres avec l'executable servent aux
exports Word. Gardez-les a cote de SpecGenerator.exe et modifiez-les dans Word :
- page de garde, en-tete, logo, styles : tout est conserve tel quel ;
- la ligne {{CONTENT}} indique ou l'application ecrit le document ;
- {{DOC_TITLE}} et {{GENERATED_ON}} sont remplaces par le titre et la date.


PROBLEMES FREQUENTS
-------------------
- "Certificat non reconnu" : le fichier .crt n'est pas celui attendu par le
  serveur ; demandez le bon certificat a votre service informatique.
- "Serveur injoignable" : verifiez l'URL et votre connexion au reseau de
  l'entreprise (VPN).
- "Cle API refusee" : verifiez que la cle a ete copiee en entier.
- Ne supprimez pas les fichiers backend\Template_Documentatio_*.docx (option 2) :
  ils servent aux exports Word.
