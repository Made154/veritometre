#!/usr/bin/env bash
# Redémarre proprement le Véritomètre sur le Pi :
#  - tue toute ancienne instance qui squatte le port,
#  - vérifie que la route /demarrer est bien dans le code (donc que le pull a pris),
#  - relance app.py avec le micro (device 2 par défaut).
# Usage : bash restart.sh          (Ctrl+C pour arrêter)
#         VERITO_MIC_DEVICE=1 bash restart.sh   (autre micro)
set -e
ICI="$(cd "$(dirname "$0")" && pwd)"

echo "--- Commit : $(git -C "$ICI" log --oneline -1 2>/dev/null) ---"

echo "--- Arrêt des anciennes instances app.py ---"
pkill -f "app.py" 2>/dev/null && sleep 1 || echo "  (aucune à tuer)"

APP="$ICI/veritometre_pi/app.py"
if grep -q '"/demarrer"' "$APP"; then
  echo "  Route /demarrer présente dans app.py ✅"
else
  echo "  Route /demarrer ABSENTE de app.py ❌"
  echo "  -> le 'git pull' n'a pas mis app.py à jour (conflit / modif locale ?)."
  echo "     Lance : git -C \"$ICI\" status   pour voir, puis on corrige."
  exit 1
fi

echo "--- Démarrage d'app.py ---"
cd "$ICI/veritometre_pi"
exec env VERITO_MIC_DEVICE="${VERITO_MIC_DEVICE:-2}" python app.py
