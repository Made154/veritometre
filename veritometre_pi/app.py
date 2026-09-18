import os
import json
import time
import math
import queue
import threading
from collections import deque

import requests
from flask import Flask, request, jsonify, send_from_directory, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "veritometre")  # contient index.html, css/, js/


def _trouver_modele_vosk():
    """Localise le modèle vocal Vosk. Il peut être committé à la racine du dépôt
    (vosk-model-fr.22, comme l'a fait Theo), posé à côté de app.py, ou pointé par
    la variable d'environnement VOSK_MODEL_PATH."""
    candidats = [
        os.environ.get("VOSK_MODEL_PATH"),
        os.path.join(BASE_DIR, "vosk-model-fr"),
        os.path.join(BASE_DIR, "..", "vosk-model-fr.22"),
        os.path.join(BASE_DIR, "..", "vosk-model-fr"),
    ]
    for chemin in candidats:
        if chemin and os.path.isdir(chemin):
            return os.path.abspath(chemin)
    return os.path.join(BASE_DIR, "vosk-model-fr")  # défaut (sert au message d'erreur)


VOSK_MODEL_PATH = _trouver_modele_vosk()

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# --- À ADAPTER : adresse du PC qui fait tourner n8n, sur le même réseau que le Pi ---
N8N_WEBHOOK_URL = os.environ.get(
    "VERITO_N8N_URL", "http://192.168.50.241:5678/webhook/interrogatoire"
)  # IP du Mac (n8n) au réseau de l'école. On préfère l'IP au nom mDNS car,
   # avec OrbStack, MacBook-Neo.local s'annonce sur plusieurs interfaces
   # (dont des IP Docker injoignables). Surchargeable :
   # VERITO_N8N_URL=http://<ip>:5678/webhook/interrogatoire

# Le LLM (Ollama) peut être lent sur CPU -> on laisse le temps de répondre.
N8N_TIMEOUT = int(os.environ.get("VERITO_N8N_TIMEOUT", "90"))
SESSION_ID = "session1"  # valeur par défaut
# Session courante : renouvelée à chaque démarrage pour repartir d'un état n8n
# vierge (sinon n8n croit l'interrogatoire déjà fini et renvoie direct le verdict).
session_courante = SESSION_ID

# État courant affiché à l'écran. Mis à jour par le nœud "HTTP Request" de n8n.
etat_courant = {
    "etat": "attente",          # 'attente' | 'session' | 'avis' | 'verdict'
    "question_suivante": None,
    "avis": None,                # 'vrai' | 'faux' | None — jugement sur la DERNIÈRE réponse
    "verdict": None,            # 'mensonge' | 'verite' | None (verdict FINAL)
    "score": None,               # 0-100 (verdict final)
}

# True dès qu'une question est affichée et qu'on attend une réponse (bouton OU micro).
# Passe à False dès qu'une réponse est envoyée, pour éviter les doublons.
en_attente_reponse = False

# Durée d'affichage de la révélation (VÉRITÉ / CONTACT PERDU) avant la question
# suivante. Réglable : VERITO_DUREE_REVELATION=6 bash restart.sh
DUREE_AFFICHAGE_AVIS = float(os.environ.get("VERITO_DUREE_REVELATION", "5"))


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


def appliquer_etat_n8n(data, est_demarrage=False):
    """Met à jour l'écran à partir de la réponse de n8n.

    Le workflow n8n ("Détecteur de mensonge") renvoie À CHAQUE tour :
      { "reaction": "...", "question_suivante": "...",
        "verdict": "mensonge"|"verite" }
    Ici, 'verdict' est le JUGEMENT DE LA DERNIÈRE RÉPONSE (pas une fin), et une
    'question_suivante' est presque toujours fournie. On mappe donc :
      - verdict 'mensonge' -> avis 'faux' (FAUX),  'verite' -> avis 'vrai' (VRAI)
      - on affiche ce flash VRAI/FAUX, puis on bascule sur question_suivante.
    Cas particuliers :
      - démarrage : pas de réponse à juger -> on affiche direct la 1ʳᵉ question.
      - verdict SANS question_suivante -> vraie fin -> écran verdict final.
    """
    global etat_courant, en_attente_reponse

    data = data or {}
    reaction = data.get("reaction")
    question_suivante = data.get("question_suivante")
    verdict = data.get("verdict")
    score = data.get("score")

    # 'verdict' par tour -> avis VRAI/FAUX. Tolérant à la casse, aux accents ET
    # aux troncatures du LLM ("Mensonge", "men", "VÉRITÉ", "ver", "vrai", "faux").
    v = str(verdict or "").strip().lower()
    if v.startswith(("men", "fau")):
        avis = "faux"
    elif v.startswith(("ver", "vér", "vra")):
        avis = "vrai"
    else:
        avis = data.get("avis")  # compat éventuelle
    print("Verdict brut n8n :", repr(verdict), "-> avis :", avis)

    if reaction:
        print("Réaction n8n :", reaction)

    en_attente_reponse = False  # on coupe l'écoute le temps d'afficher l'avis/le verdict

    if verdict and not question_suivante:
        # Plus de question : c'est une vraie fin d'interrogatoire.
        etat_courant = {
            "etat": "verdict", "question_suivante": None,
            "avis": None, "verdict": verdict, "score": score,
        }
        print("Verdict FINAL reçu de n8n :", etat_courant)

    elif avis and not est_demarrage:
        # Jugement de la réponse : plein écran dramatique quelques secondes,
        # puis on enchaîne automatiquement sur la question suivante.
        #   verite   -> écran verdict "VÉRITÉ" (sans score)
        #   mensonge -> écran "CONTACT PERDU"
        if avis == "vrai":
            etat_courant = {
                "etat": "verdict", "question_suivante": None,
                "avis": None, "verdict": "verite", "score": None,
            }
        else:
            etat_courant = {
                "etat": "perdu", "question_suivante": None,
                "avis": None, "verdict": None, "score": None,
            }
        print("Jugement :", avis, "-> écran", etat_courant["etat"],
              "; prochaine question dans", DUREE_AFFICHAGE_AVIS, "s")

        def basculer_vers_question():
            global etat_courant, en_attente_reponse
            etat_courant = {
                "etat": "session", "question_suivante": question_suivante,
                "avis": None, "verdict": None, "score": None,
            }
            en_attente_reponse = bool(question_suivante)

        threading.Timer(DUREE_AFFICHAGE_AVIS, basculer_vers_question).start()

    else:
        # Démarrage (ou pas de jugement) : on affiche directement la question.
        etat_courant = {
            "etat": "session", "question_suivante": question_suivante,
            "avis": None, "verdict": None, "score": None,
        }
        en_attente_reponse = bool(question_suivante)
        print("Question affichée :", question_suivante)

    return etat_courant


@app.route("/question", methods=["POST"])
def receive_question():
    """Compat : ancien mode où n8n POSTe l'état ici (nœud HTTP Request)."""
    data = request.get_json(force=True, silent=True) or {}
    appliquer_etat_n8n(data)
    return jsonify({"status": "ok", **etat_courant})


@app.route("/get-question", methods=["GET"])
def get_question():
    """Interrogé en boucle par la page HTML pour savoir quoi afficher."""
    return jsonify(etat_courant)


def _est_fallback_n8n(data):
    """Vrai si n8n a renvoyé son secours de parsing (le petit LLM a produit un
    JSON invalide) : verdict 'indéterminé' ou la question 'peux-tu répéter…'."""
    d = data or {}
    v = str(d.get("verdict", "")).lower()
    q = str(d.get("question_suivante", "")).lower()
    return v.startswith("ind") or "répéter ta réponse" in q or "repeter ta reponse" in q


def _poster_n8n(payload, contexte, est_demarrage=False):
    """POST vers n8n. n8n renvoie l'état suivant (reaction, question_suivante,
    verdict) DANS LA RÉPONSE. Réessaie une fois si n8n renvoie son fallback de
    parsing (JSON LLM invalide). Retourne le code HTTP, ou None si injoignable."""
    r = None
    data = {}
    for essai in range(2):
        try:
            r = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=N8N_TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"Erreur en contactant n8n ({contexte}) :", e)
            return None
        print(f"{contexte} -> n8n (status {r.status_code})")
        try:
            data = r.json()
        except ValueError:
            print("  Réponse n8n non-JSON :", r.text[:200])
            data = {}
        if isinstance(data, list):        # n8n renvoie parfois [ {...} ]
            data = data[0] if data else {}
        if not _est_fallback_n8n(data):
            break
        print("  n8n a renvoyé son fallback (JSON LLM invalide) — nouvel essai…")

    # Verdict piloté par l'ECG : sur un tour de réponse, si le corps s'agite
    # au-dessus de sa baseline -> "mensonge", sinon -> "verite". n8n garde la
    # réaction et la question suivante ; c'est le CORPS qui tranche.
    if not est_demarrage and ECG_VERDICT:
        ratio = _ecg_stress.get("ratio", 1.0)
        verdict_ecg = "mensonge" if ratio >= SEUIL_STRESS else "verite"
        print(f"ECG stress ratio={ratio} (seuil {SEUIL_STRESS}) -> verdict {verdict_ecg} "
              f"(n8n disait {data.get('verdict')})")
        data["verdict"] = verdict_ecg

    appliquer_etat_n8n(data, est_demarrage=est_demarrage)  # affiche question/avis/verdict
    return r.status_code


def envoyer_reponse_n8n(reponse):
    """Relaie une réponse ('oui'/'non') captée au micro à n8n, puis affiche la
    question/le verdict que n8n renvoie."""
    global en_attente_reponse

    if not en_attente_reponse:
        print(f"Réponse '{reponse}' ignorée : aucune question en attente.")
        return None

    en_attente_reponse = False  # on coupe l'écoute tout de suite pour éviter les doublons
    statut = _poster_n8n({"answer": reponse, "session_id": session_courante}, f"réponse '{reponse}'")
    if statut is None:
        en_attente_reponse = True  # échec réseau -> on réarme pour permettre un nouvel essai
    return statut


def demarrer_interrogatoire():
    """Lance l'interrogatoire : premier appel à n8n, qui renvoie la 1ʳᵉ question.
    Reproduit l'appel « à lancer en premier » (cf. test PowerShell)."""
    global session_courante
    session_courante = f"session-{int(time.time())}"  # nouvelle session -> n8n repart de zéro
    print("Nouvelle session :", session_courante)
    return _poster_n8n({"answer": "oui", "session_id": session_courante},
                       "démarrage", est_demarrage=True)


@app.route("/reponse", methods=["POST"])
def transmettre_reponse():
    """Appelé par les boutons OUI/NON de l'écran. Relaie la réponse à n8n
    (évite tout souci de CORS : le navigateur ne parle qu'à Flask)."""
    data = request.get_json(force=True, silent=True) or {}
    reponse = data.get("answer")

    if reponse not in ("oui", "non"):
        return jsonify({"status": "erreur", "message": "answer doit être 'oui' ou 'non'"}), 400

    status = envoyer_reponse_n8n(reponse)
    if status is None:
        return jsonify({"status": "erreur", "message": "réponse ignorée ou n8n injoignable"}), 502

    return jsonify({"status": "ok", "n8n_status": status})


@app.route("/demarrer", methods=["POST"])
def demarrer():
    """Déclenché par un appui sur l'écran d'attente : lance l'interrogatoire
    (premier appel à n8n) et affiche la première question qu'il renvoie."""
    if en_attente_reponse:
        # une question est déjà en cours : on ne relance pas
        return jsonify({"status": "ok", "deja_en_cours": True, **etat_courant})

    status = demarrer_interrogatoire()
    if status is None:
        return jsonify({"status": "erreur", "message": "n8n injoignable"}), 502

    return jsonify({"status": "ok", **etat_courant})


# ---------------------------------------------------------------------------
# Reconnaissance vocale locale (Vosk) : écoute "oui" / "non" au micro pendant
# qu'une question est affichée, et envoie automatiquement la réponse détectée.
# Fonctionne entièrement hors-ligne, pas besoin d'Internet ni de clé API.
# ---------------------------------------------------------------------------
MOTS_ATTENDUS = ["oui", "non"]


def demarrer_ecoute_micro():
    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer
    except ImportError:
        print("Micro désactivé : installe 'vosk' et 'sounddevice' (voir README) pour l'activer.")
        return

    if not os.path.isdir(VOSK_MODEL_PATH):
        print(f"Micro désactivé : modèle Vosk introuvable dans {VOSK_MODEL_PATH}")
        return

    # Sur le Pi, le micro USB n'est PAS le périphérique par défaut et tourne
    # souvent à 48 kHz (cf. test_vosk.py de Theo). On rend donc configurable :
    #   VERITO_MIC_DEVICE : index du micro (voir la liste affichée ci-dessous)
    #   VERITO_MIC_RATE   : fréquence (sinon = fréquence native du périphérique)
    env_device = os.environ.get("VERITO_MIC_DEVICE")
    device = int(env_device) if env_device not in (None, "") else None

    try:
        infos = sd.query_devices()
        print("🎤 Périphériques d'entrée disponibles :")
        for i, d in enumerate(infos):
            if d.get("max_input_channels", 0) > 0:
                marque = " <-- choisi (VERITO_MIC_DEVICE)" if i == device else ""
                print(f"   [{i}] {d['name']} ({int(d['default_samplerate'])} Hz){marque}")
    except Exception as e:
        print("  (impossible de lister les périphériques :", e, ")")

    # Fréquence native du micro choisi (48000 sur le Pi) — sinon rien n'est capté.
    try:
        rate_natif = int(sd.query_devices(device, "input")["default_samplerate"])
    except Exception:
        rate_natif = 48000
    env_rate = os.environ.get("VERITO_MIC_RATE")
    samplerate = int(env_rate) if env_rate else rate_natif

    try:
        modele = Model(VOSK_MODEL_PATH)
    except Exception as e:
        print("Micro désactivé : impossible de charger le modèle Vosk :", e)
        return

    # Grammaire fermée : force la reconnaissance sur seulement ces mots, bien
    # plus fiable qu'une reconnaissance libre pour un vocabulaire aussi réduit.
    grammaire = json.dumps(MOTS_ATTENDUS + ["[unk]"])

    audio_queue = queue.Queue()

    def callback_audio(indata, frames, time_info, status):
        if status:
            print("Statut audio :", status)   # p.ex. "input overflow" si le Pi sature
        audio_queue.put(bytes(indata))

    def boucle():
        # Écoute À LA DEMANDE : le micro n'est ouvert QUE pendant qu'une question
        # attend une réponse. Le reste du temps (avis, verdict, n8n qui réfléchit,
        # écran d'attente) le flux est fermé -> plus d'"input overflow" à vide, et
        # ça colle au déroulé : question -> on écoute -> réponse -> n8n conclut ->
        # question suivante -> on rouvre.
        print(f"🎤 Micro prêt — device={device} @ {samplerate} Hz "
              f"(ouverture à chaque question)")
        while True:
            # 1) attendre qu'une question soit posée
            while not en_attente_reponse:
                time.sleep(0.05)

            # 2) question posée : recognizer neuf + tampon propre, puis on ouvre
            recognizer = KaldiRecognizer(modele, samplerate, grammaire)
            with audio_queue.mutex:
                audio_queue.queue.clear()
            try:
                flux = sd.RawInputStream(samplerate=samplerate, blocksize=8000,
                                         dtype="int16", channels=1, device=device,
                                         callback=callback_audio)
            except Exception as e:
                print("Micro : impossible d'ouvrir le flux audio :", e)
                print("  -> ajuste VERITO_MIC_DEVICE / VERITO_MIC_RATE (voir la liste)")
                time.sleep(0.5)
                continue

            with flux:
                print("🎤 J'écoute la réponse…")
                # on écoute tant que la question est active (envoyer_reponse_n8n
                # remet en_attente_reponse à False dès qu'une réponse part)
                while en_attente_reponse:
                    try:
                        data = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        texte = json.loads(recognizer.Result()).get("text", "").strip()
                        if texte:
                            print("🎤 Entendu :", repr(texte))
                        if texte in MOTS_ATTENDUS:
                            print("🎤 Réponse détectée :", texte)
                            envoyer_reponse_n8n(texte)
                            break
            print("🎤 Micro en pause (attente de la prochaine question).")

    threading.Thread(target=boucle, daemon=True).start()


# ---------------------------------------------------------------------------
# Capteur ECG (Arduino + module AD8232) : on lit le port série, on trace la
# courbe, on estime le BPM et un "écart" (accélération du cœur vs. baseline),
# puis on pousse tout ça au navigateur via SSE (Server-Sent Events).
#
# Le format série attendu (voir arduino/veritometre_ecg/veritometre_ecg.ino) :
#   "512\n" -> échantillon ECG brut 0..1023
#   "!\n"   -> électrode décrochée (leads-off)
#
# Réglages via variables d'environnement :
#   VERITO_SERIAL_PORT  ex: /dev/cu.usbmodem14101  (auto-détection si absent)
#   VERITO_SERIAL_BAUD  débit série (auto-détecté si absent)
#   VERITO_ECG_SIMULATE 1 pour forcer un ECG synthétique (test sans matériel)
#                       0 pour l'interdire. Absent = auto (simule si pas de port).
# ---------------------------------------------------------------------------
# Débit série : imposé par VERITO_SERIAL_BAUD, sinon auto-détecté (_auto_baud).
SERIAL_BAUD_ENV = os.environ.get("VERITO_SERIAL_BAUD")
BAUDS_CANDIDATS = [115200, 9600, 57600, 38400, 250000]
FREQ_ECG = 125  # Hz — doit correspondre à la cadence du sketch Arduino

# --- Verdict influencé par l'ECG ---------------------------------------------
# On mesure l'"agitation" du signal (écart-type court) vs une baseline lente :
# un sursaut d'agitation au moment de répondre -> le corps te trahit -> mensonge.
ECG_VERDICT = os.environ.get("VERITO_ECG_VERDICT", "1") != "0"
SEUIL_STRESS = float(os.environ.get("VERITO_ECG_SEUIL", "1.15"))  # ratio agit/baseline
_ecg_stress = {"ratio": 1.0, "agit": 0.0}

_abonnes_ecg = []                 # liste de queue.Queue, un par onglet connecté
_abonnes_lock = threading.Lock()


def _diffuser_ecg(payload):
    """Envoie un point de mesure à tous les navigateurs connectés en SSE."""
    with _abonnes_lock:
        for q in list(_abonnes_ecg):
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass  # navigateur trop lent : on saute ce point plutôt que bloquer


class AnalyseurECG:
    """Détecte les pics R du signal ECG pour en déduire le BPM, et compare le
    BPM courant à une baseline lente pour produire un 'écart' (%) — c'est lui
    qui alimente la jauge facon détecteur de mensonge."""

    def __init__(self):
        self.fenetre = deque(maxlen=2 * FREQ_ECG)  # ~2 s pour le seuil dynamique
        self.dernier_pic = None                    # instant (monotonic) du dernier R
        self.au_dessus = False                     # hystérésis anti-rebond
        self.intervalles = deque(maxlen=6)         # derniers intervalles RR (s)
        self.bpm_courant = None
        self.bpm_base = None                       # baseline (EMA lente)
        self.signal_lisse = None                   # signal filtré pour l'affichage
        self.court = deque(maxlen=max(10, FREQ_ECG // 2))  # ~0,5 s : agitation instantanée
        self.agit_base = None                      # baseline lente de l'agitation
        self.bpm_affiche = None                    # BPM affiché (dérivé du stress, lissé)

    def ajouter(self, valeur, t):
        self.fenetre.append(valeur)
        if len(self.fenetre) < 20:
            return  # pas assez de recul pour un seuil fiable

        vmin, vmax = min(self.fenetre), max(self.fenetre)
        amplitude = vmax - vmin
        seuil = vmax + 1 if amplitude < 40 else vmin + 0.62 * amplitude

        if not self.au_dessus and valeur > seuil:
            self.au_dessus = True
            if self.dernier_pic is None or (t - self.dernier_pic) > 0.3:  # réfractaire 0,3 s
                if self.dernier_pic is not None:
                    rr = t - self.dernier_pic
                    if 0.3 <= rr <= 2.0:  # 30..200 BPM : plausible
                        self.intervalles.append(rr)
                        moyenne_rr = sum(self.intervalles) / len(self.intervalles)
                        self.bpm_courant = 60.0 / moyenne_rr
                        if self.bpm_base is None:
                            self.bpm_base = self.bpm_courant
                        else:
                            self.bpm_base += 0.05 * (self.bpm_courant - self.bpm_base)
                self.dernier_pic = t
        elif self.au_dessus and valeur < seuil - 0.1 * amplitude:
            self.au_dessus = False

    def etat(self, valeur, leads_off=False):
        # Lissage pour l'affichage : le signal brut est très bruité (secteur 50 Hz),
        # un filtre passe-bas simple (EMA) donne une courbe lisible.
        if self.signal_lisse is None:
            self.signal_lisse = float(valeur)
        else:
            self.signal_lisse += 0.25 * (valeur - self.signal_lisse)

        # Agitation instantanée (écart-type court) vs baseline lente -> ratio de stress.
        self.court.append(valeur)
        ratio = 1.0
        if len(self.court) >= 10:
            moy = sum(self.court) / len(self.court)
            agit = (sum((x - moy) ** 2 for x in self.court) / len(self.court)) ** 0.5
            if self.agit_base is None:
                self.agit_base = agit
            else:
                self.agit_base += 0.003 * (agit - self.agit_base)   # baseline ~4 s
            ratio = agit / max(1.0, self.agit_base)
            _ecg_stress["ratio"] = round(ratio, 2)
            _ecg_stress["agit"] = round(agit, 1)

        # BPM : le signal est trop bruité pour une vraie détection de pics (ça
        # donnait un BPM constamment très haut). On affiche un BPM CRÉDIBLE dérivé
        # de l'agitation : repos ~72, il monte quand le corps s'emballe. Lissé pour
        # bouger naturellement.
        cible_bpm = max(58, min(125, 72 + (ratio - 1) * 70))
        if self.bpm_affiche is None:
            self.bpm_affiche = cible_bpm
        else:
            self.bpm_affiche += 0.05 * (cible_bpm - self.bpm_affiche)

        return {
            "signal": round(self.signal_lisse),          # courbe lissée
            "bpm": round(self.bpm_affiche),
            "ecart": round((ratio - 1) * 100, 1),        # jauge = agitation vs baseline
            "leadsOff": leads_off,
        }


def _detecter_port_serie():
    """Cherche un port qui ressemble à un Arduino (macOS / Linux / Windows)."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    indices = ("usbmodem", "usbserial", "wchusbserial", "ttyusb", "ttyacm",
               "arduino", "ch340", "ch910", "cp210", "wch")
    for port in list_ports.comports():
        texte = f"{port.device} {port.description} {port.manufacturer}".lower()
        if any(ind in texte for ind in indices):
            return port.device
    return None


def _auto_baud(port):
    """Essaie plusieurs débits et garde celui qui produit le plus de lignes ECG
    valides (entiers 0..1023 ou '!'), pour ne pas avoir à connaître le baud du
    sketch Arduino."""
    import serial  # pyserial
    meilleur, meilleur_score = None, 0
    for baud in BAUDS_CANDIDATS:
        try:
            with serial.Serial(port, baud, timeout=0.4) as ser:
                ser.reset_input_buffer()
                time.sleep(0.2)
                valides = 0
                for _ in range(40):
                    ligne = ser.readline().decode("ascii", "ignore").strip()
                    if ligne == "!" or (ligne.lstrip("-").isdigit() and 0 <= int(ligne) <= 1023):
                        valides += 1
        except Exception:
            continue
        print(f"❤️  ECG : test {baud} bauds -> {valides}/40 lignes valides")
        if valides > meilleur_score:
            meilleur, meilleur_score = baud, valides
        if valides >= 15:          # largement suffisant : on s'arrête là
            return baud
    return meilleur or 115200


def _boucle_serie(port, baud):
    import serial  # pyserial
    analyseur = AnalyseurECG()
    print(f"❤️  ECG : ouverture du port série {port} @ {baud} bauds")
    with serial.Serial(port, baud, timeout=1) as ser:
        ser.reset_input_buffer()
        while True:
            ligne = ser.readline().decode("ascii", "ignore").strip()
            if not ligne:
                continue
            if ligne == "!":
                _diffuser_ecg({"signal": None, "bpm": "--", "ecart": 0.0, "leadsOff": True})
                continue
            try:
                valeur = int(ligne)
            except ValueError:
                continue  # ligne parasite (bruit au démarrage, etc.)
            t = time.monotonic()
            analyseur.ajouter(valeur, t)
            _diffuser_ecg(analyseur.etat(valeur))


def _echantillon_ecg(phase):
    """Un battement ECG synthétique (P-QRS-T) pour la phase [0,1). ~[-0.3, 1.0]."""
    def g(centre, largeur, amplitude):
        return amplitude * math.exp(-((phase - centre) ** 2) / (2 * largeur * largeur))
    return (g(0.15, 0.020, 0.10)    # onde P
            - g(0.38, 0.008, 0.12)  # Q
            + g(0.40, 0.010, 1.00)  # R
            - g(0.42, 0.010, 0.25)  # S
            + g(0.60, 0.040, 0.25)) # onde T


def _boucle_synthetique():
    """Génère un ECG crédible sans matériel : pratique pour tester l'écran."""
    print("❤️  ECG : aucun Arduino détecté — génération d'un ECG synthétique.")
    analyseur = AnalyseurECG()
    dt = 1.0 / FREQ_ECG
    phase = 0.0
    tk = 0.0
    prochain = time.monotonic()
    while True:
        # Rythme cardiaque qui respire un peu autour de 72 BPM + bruit léger.
        bpm_cible = 72 + 6 * math.sin(tk * 0.20) + (os.urandom(1)[0] - 128) / 128 * 1.5
        rr = 60.0 / bpm_cible
        phase += dt / rr
        if phase >= 1.0:
            phase -= 1.0
        bruit = (os.urandom(1)[0] - 128) / 128 * 0.02
        valeur = int(max(0, min(1023, 512 + (_echantillon_ecg(phase) + bruit) * 350)))

        t = time.monotonic()
        analyseur.ajouter(valeur, t)
        _diffuser_ecg(analyseur.etat(valeur))

        tk += dt
        prochain += dt
        retard = prochain - time.monotonic()
        if retard > 0:
            time.sleep(retard)
        else:
            prochain = time.monotonic()  # on a pris du retard : on se recale


def demarrer_lecture_ecg():
    """Lance, dans un thread de fond, la lecture de l'ECG (série ou synthétique)."""
    force = os.environ.get("VERITO_ECG_SIMULATE")
    port = os.environ.get("VERITO_SERIAL_PORT") or _detecter_port_serie()

    if force == "1":
        cible = _boucle_synthetique
    elif force == "0":
        if not port:
            print("❤️  ECG désactivé : aucun port série et simulation interdite (VERITO_ECG_SIMULATE=0)")
            return
        cible = lambda: _demarrer_serie_robuste(port)
    else:  # auto
        cible = (lambda: _demarrer_serie_robuste(port)) if port else _boucle_synthetique

    threading.Thread(target=cible, daemon=True).start()


def _demarrer_serie_robuste(port):
    """Relance la lecture série si l'Arduino est débranché/rebranché."""
    while True:
        try:
            baud = int(SERIAL_BAUD_ENV) if SERIAL_BAUD_ENV else _auto_baud(port)
            _boucle_serie(port, baud)
        except Exception as e:
            print("❤️  ECG : erreur série, nouvelle tentative dans 2 s :", e)
            time.sleep(2)
            port = os.environ.get("VERITO_SERIAL_PORT") or _detecter_port_serie() or port


@app.route("/ecg-stream")
def ecg_stream():
    """Flux SSE consommé par le navigateur (js/ecg-client.js) pour tracer l'ECG."""
    def flux():
        q = queue.Queue(maxsize=200)
        with _abonnes_lock:
            _abonnes_ecg.append(q)
        try:
            yield ": ok\n\n"  # ouvre le flux tout de suite
            while True:
                payload = q.get()
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            with _abonnes_lock:
                if q in _abonnes_ecg:
                    _abonnes_ecg.remove(q)

    return Response(flux(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    port = int(os.environ.get("VERITO_PORT", "5000"))  # 5000 sur le Pi ; sur macOS, AirPlay
                                                        # occupe 5000 -> lancer avec VERITO_PORT=5001
    demarrer_ecoute_micro()
    demarrer_lecture_ecg()
    # threaded=True : indispensable, le flux SSE garde une connexion ouverte.
    app.run(host="0.0.0.0", port=port, threaded=True)
