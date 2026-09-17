#!/usr/bin/env bash
# Diagnostic Véritomètre sur le Pi : vérifie que la bonne app.py tourne et que
# la route /demarrer répond. Usage : bash diag.sh   (ou ./diag.sh)

PORT="${VERITO_PORT:-5000}"

echo "--- Qui écoute sur :$PORT ---"
lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P 2>/dev/null || echo "  (rien / lsof indisponible)"

echo "--- Processus app.py en cours ---"
pgrep -fa app.py 2>/dev/null || echo "  (aucun)"

echo "--- POST /demarrer (attendu : 200 ou 502, PAS 405) ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "http://localhost:$PORT/demarrer" \
  || echo "  (curl a échoué : l'app ne tourne pas ?)"

echo "--- Commit actuel ---"
git -C "$(dirname "$0")" log --oneline -1 2>/dev/null || echo "  (pas un dépôt git)"
