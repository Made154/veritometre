# Le Véritomètre™ — backend Pi + ECG Arduino

Faux détecteur de mensonge (thème Rick & Morty) tournant sur Raspberry Pi avec
écran tactile 800×480. Le backend Flask sert la page, dialogue avec n8n pour les
questions/verdicts, et — nouveauté — **lit un capteur ECG (Arduino + AD8232)**
qu'il affiche en temps réel comme un moniteur cardiaque.

## Installation

```bash
cd veritometre_pi
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer

```bash
python app.py
```

Puis ouvrir `http://localhost:5000`.

> **macOS :** le port 5000 est squatté par « AirPlay Receiver » (réponses 403).
> Lancer sur un autre port :
> ```bash
> VERITO_PORT=5001 python app.py     # puis http://localhost:5001
> ```
> (ou désactiver AirPlay Receiver dans Réglages → Général → AirDrop et Handoff.)

### Tester l'écran SANS matériel

L'ECG bascule automatiquement sur un **signal synthétique** si aucun Arduino
n'est branché — la courbe et le BPM fonctionnent donc tout de suite. Pour le
forcer :

```bash
VERITO_ECG_SIMULATE=1 VERITO_PORT=5001 python app.py
```

Raccourcis clavier utiles (dans la page) : `1`–`5` changent d'écran
(`3` = écran session avec la courbe ECG).

## Le capteur ECG (Arduino + AD8232)

### Câblage

| Module AD8232 | Arduino |
|---------------|---------|
| GND           | GND     |
| 3.3V          | **3.3V** (pas 5V) |
| OUTPUT        | A0      |
| LO+           | D11     |
| LO−           | D10     |

Électrodes : **RA** clavicule droite, **LA** clavicule gauche, **RL** (masse)
bas des côtes à droite.

### Le sketch Arduino

Le code tourne **déjà sur l'Arduino** : il envoie une mesure ECG brute
(`0..1023`) par ligne, ou `!` si une électrode se décroche. Il n'y a donc rien
à téléverser — juste à brancher l'Arduino en USB sur le Pi.

`arduino/veritometre_ecg/veritometre_ecg.ino` est fourni **à titre de
référence** (exemple AD8232 équivalent) ; inutile si votre sketch existe déjà.

> ⚠️ **Débit série (baud)** — le point le plus important à vérifier : le débit
> côté Pi doit être **identique** à celui du sketch Arduino. L'exemple AD8232
> classique tourne souvent en **9600**. Si la courbe est illisible/parasitée,
> c'est presque toujours ça :
> ```bash
> VERITO_SERIAL_BAUD=9600 python app.py
> ```
>
> ⚠️ Fermer le moniteur série de l'IDE Arduino avant de lancer `app.py` :
> un seul programme peut ouvrir le port à la fois.

### Réglages (variables d'environnement)

| Variable | Rôle | Défaut |
|----------|------|--------|
| `VERITO_PORT` | port HTTP de Flask | `5000` |
| `VERITO_SERIAL_PORT` | port série de l'Arduino | auto-détection |
| `VERITO_SERIAL_BAUD` | débit série | `115200` |
| `VERITO_ECG_SIMULATE` | `1` force le synthétique, `0` l'interdit, absent = auto | auto |

Trouver le port série :
```bash
python -c "import serial.tools.list_ports as p; [print(x.device, x.description) for x in p.comports()]"
# macOS  : /dev/cu.usbmodemXXXX   Linux : /dev/ttyACM0 / ttyUSB0   Windows : COM3
```

## Réponse à la voix (micro)

Il n'y a **plus de boutons OUI/NON** : le sujet répond à voix haute. C'est
`app.py` qui écoute le micro avec **Vosk** (hors-ligne) et relaie « oui »/« non »
à n8n, exactement comme le faisaient les boutons. n8n reste le juge : il décide
VRAI/FAUX et le verdict final.

Activer le micro sur le Pi (une seule fois) :

```bash
pip install vosk sounddevice
# modèle français léger, à décompresser en "vosk-model-fr" à côté de app.py :
#   https://alphacephei.com/vosk/models  (vosk-model-small-fr-0.22)
```

Sans micro configuré, l'app tourne quand même (elle affiche juste
« Micro désactivé… » au démarrage) — pratique pour tester l'écran.

## Comment ça circule

```
Arduino (AD8232) --série--> app.py (détection pics R -> BPM + écart)
                              |
                              +-- SSE /ecg-stream --> js/ecg-client.js
                                                        -> ajouterPointCourbe()  (courbe ECG)
                                                        -> jauge ÉCART + BPM

micro --Vosk (app.py)--> "oui"/"non" --HTTP--> n8n
n8n --HTTP /question--> app.py --polling /get-question--> js/flask-client.js
                                                        -> question, avis, verdict
```

- **`signal`** (0–1023) → tracé de la courbe (courbe.js, ~2 s visibles à 125 Hz).
- **`bpm`** → nombre affiché, calculé par détection des pics R (app.py).
- **`ecart`** → jauge magenta : accélération du cœur vs. sa baseline (indicateur
  de stress affiché à l'écran).
- **Verdict VRAI/FAUX** → calculé par **n8n**, pas localement.

## Fichiers ajoutés / modifiés

- `app.py` — lecture série ECG + détection BPM + flux SSE `/ecg-stream` + `VERITO_PORT`
- `veritometre/js/ecg-client.js` — client SSE navigateur (nouveau)
- `veritometre/js/courbe.js` — redessin fluide (rAF) + fenêtre ~2 s
- `veritometre/js/main.js` — trace `signal` ECG, démarre le flux, **boutons retirés**
- `veritometre/index.html` — inclut `ecg-client.js`, **boutons OUI/NON remplacés**
  par un indicateur micro
- `veritometre/css/style.css` — style de l'indicateur micro (à la place des boutons)
- `requirements.txt` — dépendances (nouveau)
- `arduino/veritometre_ecg/veritometre_ecg.ino` — sketch de **référence** (votre
  Arduino a déjà son code)
