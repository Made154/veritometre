#!/usr/bin/env python3
"""Moniteur série ECG (playtest). Affiche en direct les valeurs envoyées par
l'Arduino sous forme d'une "vague" ASCII + un BPM estimé. Auto-détecte le port
et le débit série.

Usage :
  python3 serial_monitor.py                  # auto port + auto baud
  python3 serial_monitor.py /dev/ttyACM0     # port imposé, baud auto
  python3 serial_monitor.py /dev/ttyACM0 9600

IMPORTANT : arrête app.py d'abord — un seul programme peut ouvrir le port série.
"""
import sys
import time
from collections import deque

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial manquant : pip install pyserial")

INDICES = ("usbmodem", "usbserial", "wchusbserial", "ttyusb", "ttyacm",
           "arduino", "ch340", "cp210", "wch")
BAUDS = (115200, 9600, 57600, 38400, 250000)


def detecter_port():
    for p in list_ports.comports():
        t = f"{p.device} {p.description} {p.manufacturer}".lower()
        if any(h in t for h in INDICES):
            return p.device
    return None


def _valide(ligne):
    return ligne == "!" or (ligne.lstrip("-").isdigit() and 0 <= int(ligne) <= 1023)


def auto_baud(port):
    print("Auto-détection du débit…")
    meilleur, score = None, 0
    for baud in BAUDS:
        try:
            with serial.Serial(port, baud, timeout=0.4) as s:
                s.reset_input_buffer()
                time.sleep(0.2)
                ok = sum(1 for _ in range(40)
                         if _valide(s.readline().decode("ascii", "ignore").strip()))
            print(f"  {baud:>6} bauds -> {ok}/40 lignes valides")
            if ok > score:
                meilleur, score = baud, ok
            if ok >= 15:
                return baud
        except Exception:
            pass
    return meilleur or 115200


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else detecter_port()
    if not port:
        sys.exit("Aucun port série trouvé. Branche l'Arduino (et arrête app.py).")
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else auto_baud(port)
    print(f"\n== Moniteur ECG : {port} @ {baud} bauds ==  (Ctrl+C pour quitter)\n")

    fenetre = deque(maxlen=250)           # pour min/max glissants
    dernier_pic, au_dessus = None, False
    rr = deque(maxlen=6)
    bpm = None
    LARG = 50
    n = 0
    try:
        with serial.Serial(port, baud, timeout=1) as s:
            s.reset_input_buffer()
            while True:
                ligne = s.readline().decode("ascii", "ignore").strip()
                if not ligne:
                    continue
                if ligne == "!":
                    print("!! électrode décrochée (leads-off) — vérifie le contact")
                    continue
                try:
                    v = int(ligne)
                except ValueError:
                    continue

                fenetre.append(v)
                n += 1
                t = time.monotonic()

                # détection simple des pics R -> BPM
                if len(fenetre) >= 20:
                    vmin, vmax = min(fenetre), max(fenetre)
                    amp = vmax - vmin
                    seuil = vmax + 1 if amp < 40 else vmin + 0.62 * amp
                    if not au_dessus and v > seuil:
                        au_dessus = True
                        if dernier_pic and 0.3 <= (t - dernier_pic) <= 2.0:
                            rr.append(t - dernier_pic)
                            bpm = round(60.0 / (sum(rr) / len(rr)))
                        dernier_pic = t
                    elif au_dessus and v < seuil - 0.1 * amp:
                        au_dessus = False

                # affichage allégé (1 ligne sur 10 ~= 12/s à 125 Hz)
                if n % 10 == 0 and len(fenetre) >= 20:
                    vmin, vmax = min(fenetre), max(fenetre)
                    pos = int((v - vmin) / max(1, vmax - vmin) * (LARG - 1))
                    vague = " " * pos + "#"
                    print(f"{v:4d} |{vague:<{LARG}}| BPM {bpm if bpm else '--'}")
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
