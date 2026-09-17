#!/usr/bin/env bash
# Collecte l'état git + les routes d'app.py dans pi-diag.txt (pour diagnostiquer
# le 405 sur /demarrer). Usage : bash pidiag.sh
cd "$(dirname "$0")"
{
  echo "=== date ==="; date
  echo "=== pwd ==="; pwd
  echo "=== remote ==="; git remote -v
  echo "=== branch ==="; git branch -vv
  echo "=== log ==="; git log --oneline -6
  echo "=== status ==="; git status
  echo "=== @app.route dans veritometre_pi/app.py ==="; grep -n "@app.route" veritometre_pi/app.py
  echo "=== lignes 'demarrer' ==="; grep -n "demarrer" veritometre_pi/app.py || echo "  aucune dans le fichier"
  echo "=== tous les app.py ==="; find . -path ./.venv -prune -o -name app.py -print
} > pi-diag.txt 2>&1

echo "Écrit dans pi-diag.txt."
echo "Pour me l'envoyer, au choix :"
echo "  1) git add pi-diag.txt && git commit -m 'pi diag' && git push origin HEAD:Theo"
echo "  2) cat pi-diag.txt   (puis colle le résultat)"
echo "-----------------------------------------------"
cat pi-diag.txt
