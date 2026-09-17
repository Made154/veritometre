import os
import json
import queue
import threading

import requests
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "veritometre")  # contient index.html, css/, js/
VOSK_MODEL_PATH = os.path.join(BASE_DIR, "vosk-model-fr")  # dossier du modèle téléchargé

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# --- À ADAPTER : adresse du PC qui fait tourner n8n, sur le même réseau que le Pi ---
N8N_WEBHOOK_URL = "http://192.168.50.XXX:5678/webhook/interrogatoire"
SESSION_ID = "session1"  # un seul écran/session pour l'instant

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

DUREE_AFFICHAGE_AVIS = 3.0  # secondes pendant lesquelles VRAI/FAUX reste affiché


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/question", methods=["POST"])
def receive_question():
    """Appelé par n8n (nœud HTTP Request) après chaque réponse. Le JSON envoyé
    par n8n doit ressembler à :
      { "avis": "vrai"|"faux"|null, "question_suivante": "..."|null,
        "verdict": "mensonge"|"verite"|null, "score": 0-100|null }

    - Si 'verdict' est présent : fin de l'interrogatoire, on affiche direct l'écran verdict.
    - Si 'avis' est présent : on affiche VRAI/FAUX quelques secondes, PUIS on bascule
      automatiquement sur 'question_suivante' (déjà fournie dans le même appel).
    - Sinon (ex: toute première question, pas encore de réponse à juger) : on affiche
      la question directement.
    """
    global etat_courant, en_attente_reponse

    data = request.get_json(force=True, silent=True) or {}
    avis = data.get("avis")
    question_suivante = data.get("question_suivante")
    verdict = data.get("verdict")
    score = data.get("score")

    en_attente_reponse = False  # on coupe l'écoute tant que l'avis/le verdict n'est pas passé

    if verdict:
        etat_courant = {
            "etat": "verdict", "question_suivante": None,
            "avis": None, "verdict": verdict, "score": score,
        }
        print("Verdict final reçu de n8n :", etat_courant)

    elif avis:
        etat_courant = {
            "etat": "avis", "question_suivante": None,
            "avis": avis, "verdict": None, "score": None,
        }
        print("Avis reçu de n8n :", avis, "— prochaine question dans", DUREE_AFFICHAGE_AVIS, "s")

        def basculer_vers_question():
            global etat_courant, en_attente_reponse
            etat_courant = {
                "etat": "session", "question_suivante": question_suivante,
                "avis": None, "verdict": None, "score": None,
            }
            en_attente_reponse = bool(question_suivante)

        threading.Timer(DUREE_AFFICHAGE_AVIS, basculer_vers_question).start()

    else:
        etat_courant = {
            "etat": "session", "question_suivante": question_suivante,
            "avis": None, "verdict": None, "score": None,
        }
        en_attente_reponse = bool(question_suivante)
        print("Nouvelle question reçue de n8n :", etat_courant)

    return jsonify({"status": "ok", **etat_courant})


@app.route("/get-question", methods=["GET"])
def get_question():
    """Interrogé en boucle par la page HTML pour savoir quoi afficher."""
    return jsonify(etat_courant)


def envoyer_reponse_n8n(reponse):
    """Relaie une réponse ('oui'/'non') à n8n. Utilisé à la fois par les boutons
    tactiles (/reponse) et par l'écoute du micro."""
    global en_attente_reponse

    if not en_attente_reponse:
        print(f"Réponse '{reponse}' ignorée : aucune question en attente.")
        return None

    en_attente_reponse = False  # on coupe l'écoute tout de suite pour éviter les doublons

    try:
        r = requests.post(
            N8N_WEBHOOK_URL,
            json={"answer": reponse, "session_id": SESSION_ID},
            timeout=10,
        )
        print(f"Réponse '{reponse}' transmise à n8n (status {r.status_code})")
        return r.status_code
    except requests.exceptions.RequestException as e:
        print("Erreur en contactant n8n :", e)
        en_attente_reponse = True  # on réarme puisque l'envoi a échoué
        return None


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

    try:
        modele = Model(VOSK_MODEL_PATH)
    except Exception as e:
        print("Micro désactivé : impossible de charger le modèle Vosk :", e)
        return

    # Grammaire fermée : force la reconnaissance sur seulement ces mots, bien
    # plus fiable qu'une reconnaissance libre pour un vocabulaire aussi réduit.
    grammaire = json.dumps(MOTS_ATTENDUS + ["[unk]"])
    recognizer = KaldiRecognizer(modele, 16000, grammaire)

    audio_queue = queue.Queue()

    def callback_audio(indata, frames, time_info, status):
        if status:
            print("Statut audio :", status)
        audio_queue.put(bytes(indata))

    def boucle():
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                                channels=1, callback=callback_audio):
            print("🎤 Écoute du micro démarrée (oui / non)")
            while True:
                data = audio_queue.get()

                if not en_attente_reponse:
                    continue  # on n'écoute que quand une réponse est attendue

                if recognizer.AcceptWaveform(data):
                    resultat = json.loads(recognizer.Result())
                    texte = resultat.get("text", "").strip()
                    if texte in MOTS_ATTENDUS:
                        print("🎤 Réponse détectée :", texte)
                        envoyer_reponse_n8n(texte)

    threading.Thread(target=boucle, daemon=True).start()


if __name__ == "__main__":
    demarrer_ecoute_micro()
    app.run(host="0.0.0.0", port=5000)
