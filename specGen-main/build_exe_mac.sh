#!/usr/bin/env bash
# Builds SpecGenerator.exe from a Mac.
#
# PyInstaller cannot cross-compile: a Windows .exe has to be built on Windows.
# This script has the build done by the Windows machine of GitHub Actions
# (.github/workflows/build-windows-exe.yml), follows it, then downloads the
# result into dist/windows/.
#
# Prerequisite (once): brew install gh && gh auth login
# Usage: ./build_exe_mac.sh
set -euo pipefail

WORKFLOW="build-windows-exe.yml"
ARTIFACT="SpecGenerator-windows"
OUT_DIR="dist/windows"

cd "$(dirname "$0")"

if ! command -v gh >/dev/null 2>&1; then
  echo "La commande GitHub 'gh' est absente. Installez-la avec : brew install gh"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "Connexion à GitHub nécessaire (une seule fois)."
  gh auth login
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  echo "Attention : des modifications ne sont pas commitées ; elles ne seront pas dans l'exe."
fi

# The build runs on GitHub: the current commit must be pushed.
git fetch --quiet origin "$branch" 2>/dev/null || true
commit="$(git rev-parse HEAD)"
if [ "$(git rev-parse "origin/$branch" 2>/dev/null || true)" != "$commit" ]; then
  read -r -p "Le commit courant n'est pas sur GitHub. Le pousser sur '$branch' maintenant ? [o/N] " answer
  case "$answer" in
    o|O|oui|y|Y) git push -u origin "$branch" ;;
    *) echo "Abandon : poussez vos commits puis relancez le script."; exit 1 ;;
  esac
fi

find_run() {
  gh run list --workflow "$WORKFLOW" --commit "$commit" --limit 1 --json databaseId -q '.[0].databaseId // empty'
}

echo "Recherche d'un build pour le commit ${commit:0:7}…"
run_id=""
for _ in 1 2 3 4 5 6; do
  run_id="$(find_run)"
  [ -n "$run_id" ] && break
  sleep 5
done

if [ -z "$run_id" ]; then
  echo "Aucun build automatique : lancement manuel du workflow sur '$branch'."
  if ! gh workflow run "$WORKFLOW" --ref "$branch"; then
    echo "Lancement impossible. Le lancement manuel exige que le workflow soit présent sur la branche par défaut du dépôt."
    exit 1
  fi
  for _ in $(seq 1 24); do
    sleep 5
    run_id="$(find_run)"
    [ -n "$run_id" ] && break
  done
fi

if [ -z "$run_id" ]; then
  echo "Le build n'a pas démarré. Consultez l'onglet Actions du dépôt sur GitHub."
  exit 1
fi

echo "Build en cours sur Windows (environ 5 minutes)…"
if ! gh run watch "$run_id" --exit-status --interval 15; then
  echo "Le build a échoué. Détail des erreurs :"
  gh run view "$run_id" --log-failed | tail -40
  exit 1
fi

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
gh run download "$run_id" --name "$ARTIFACT" --dir "$OUT_DIR"

echo
echo "Terminé : $OUT_DIR/SpecGenerator.exe"
ls -lh "$OUT_DIR"
