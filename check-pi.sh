#!/usr/bin/env bash
# Diagnostic côté Pi : app Flask locale + joignabilité de n8n (par nom mDNS et
# par IP). Usage : bash check-pi.sh
MAC_IP="${MAC_IP:-192.168.1.29}"   # IP du Mac sur le réseau maison (surchargeable)

echo "=== app Flask/kiosk locale (localhost:5000) ==="
curl -m5 -o /dev/null -w "  HTTP %{http_code}\n" http://localhost:5000/ 2>&1 || echo "  injoignable"

echo "=== processus app.py ? ==="
pgrep -fa "app.py" 2>/dev/null | head -2 || echo "  AUCUN (l'app ne tourne pas)"

echo "=== résolution de MacBook-Neo.local (mDNS) ==="
getent hosts MacBook-Neo.local 2>/dev/null || echo "  IMPOSSIBLE à résoudre (mDNS)"

echo "=== n8n via le nom (MacBook-Neo.local:5678) ==="
curl -m6 -o /dev/null -w "  HTTP %{http_code}\n" http://MacBook-Neo.local:5678/ 2>&1

echo "=== n8n via IP ($MAC_IP:5678) ==="
curl -m6 -o /dev/null -w "  HTTP %{http_code}\n" "http://$MAC_IP:5678/" 2>&1

echo "=== support mDNS installé ? ==="
if dpkg -l 2>/dev/null | grep -qi "libnss-mdns"; then
  echo "  libnss-mdns présent"
else
  echo "  libnss-mdns MANQUANT -> pour résoudre .local : sudo apt install -y libnss-mdns"
fi
