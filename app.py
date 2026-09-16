import os
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "veritometre")  # contient index.html, css/, js/

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

question = "En attente d'une question..."


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/question", methods=["POST"])
def receive_question():
    global question

    data = request.get_json()
    question = data.get("question_suivante", question)

    print("Nouvelle question :", question)

    return jsonify({
        "status": "ok",
        "question": question
    })


@app.route("/get-question", methods=["GET"])
def get_question():
    return jsonify({
        "question": question
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
