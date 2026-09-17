#!/usr/bin/env python3
"""Dump BRUT du port série : montre les octets EXACTS envoyés par l'Arduino, à
plusieurs débits, pour diagnostiquer le format / le baud.
Usage : python3 serial_raw.py     (arrête app.py d'abord : un seul programme
ouvre le port série à la fois)."""
import serial
from serial.tools import list_ports

INDICES = ("ttyacm", "ttyusb", "usbmodem", "usbserial", "wch", "arduino",
           "ch340", "cp210")


def detecter():
    for p in list_ports.comports():
        t = f"{p.device} {p.description} {p.manufacturer}".lower()
        if any(h in t for h in INDICES):
            return p.device
    return None


print("Ports série visibles :")
for p in list_ports.comports():
    print("   ", p.device, "-", p.description)

port = detecter()
print("Port choisi :", port)
if not port:
    raise SystemExit("Aucun Arduino détecté (câble/USB, ou groupe 'dialout' ?).")

for baud in (115200, 9600, 57600, 38400):
    print(f"\n--- {baud} bauds (10 lignes brutes) ---")
    try:
        with serial.Serial(port, baud, timeout=2) as s:
            s.reset_input_buffer()
            for _ in range(10):
                print(repr(s.readline()))
    except Exception as e:
        print("err:", e)
