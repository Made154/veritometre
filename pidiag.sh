#!/usr/bin/env bash
# Collecte l'état git + les routes d'app.py pour diagnostiquer le 405 sur
# /demarrer — SANS fuiter de secret : on n'affiche pas `git remote -v`, et tout
# token éventuellement présent dans une URL est masqué (***).
# Usage : bash pidiag.sh   puis colle le texte affiché.
cd "$(dirname "$0")"
{
  echo "=== date ==="; date
  echo "=== pwd ==="; pwd
  echo "=== branch (suivi) ==="; git branch -vv
  echo "=== log ==="; git log --oneline -8
  echo "=== status ==="; git status
  echo "=== @app.route dans veritometre_pi/app.py ==="; grep -n "@app.route" veritometre_pi/app.py
  echo "=== lignes 'demarrer' ==="; grep -n "demarrer" veritometre_pi/app.py || echo "  aucune dans le fichier"
  echo "=== tous les app.py ==="; find . -path ./.venv -prune -o -name app.py -print
} 2>&1 | sed -E 's#(https?://)[^@/[:space:]]+@#\1***@#g' | tee pi-diag.txt

echo
echo "-> Copie/colle tout le texte ci-dessus (les tokens sont masqués : rien à pousser)."
