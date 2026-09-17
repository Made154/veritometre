#!/usr/bin/env bash
# Diagnostic de la liaison Pi -> n8n (Mac). Usage : bash check-n8n.sh
ICI="$(cd "$(dirname "$0")" && pwd)"
URL="${VERITO_N8N_URL:-http://192.168.50.241:5678/webhook/interrogatoire}"
BASE="$(echo "$URL" | sed -E 's#(https?://[^/]+).*#\1#')"

echo "commit     : $(git -C "$ICI" log --oneline -1 2>/dev/null)"
echo "URL app.py :"; grep -n "192.168" "$ICI/veritometre_pi/app.py" 2>/dev/null
echo "cible      : $URL"
echo -n "base $BASE -> "; curl -m5 -o /dev/null -w "HTTP %{http_code}\n" "$BASE/" 2>&1
echo "webhook POST ->"
curl -m20 -sS -X POST "$URL" -H 'Content-Type: application/json' \
  -d '{"answer":"oui","session_id":"diag1"}'; echo
