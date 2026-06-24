from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime
import sqlite3
import os

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Mémoire de conversation par session (en mémoire RAM)
conversation_history = []

# ── SQLite init ──────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_message(role, content):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
              (role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]

init_db()

# ── Routes ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global conversation_history
    data       = request.get_json()
    user_msg   = data.get("message", "").strip()
    language   = data.get("language", "fr")

    if not user_msg:
        return jsonify({"error": "Message vide"}), 400

    # Système selon la langue choisie
    system_prompts = {
        "fr": "Tu es un assistant IA intelligent et utile. Réponds toujours en français de manière claire et concise.",
        "ar": "أنت مساعد ذكاء اصطناعي ذكي ومفيد. أجب دائماً باللغة العربية بشكل واضح وموجز.",
        "en": "You are a smart and helpful AI assistant. Always respond in English clearly and concisely."
    }

    system_message = {
        "role": "system",
        "content": system_prompts.get(language, system_prompts["fr"])
    }

    # Ajouter le message user à la mémoire
    conversation_history.append({"role": "user", "content": user_msg})

    # Garder max 20 messages en mémoire
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    # Appel Groq avec tout l'historique
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[system_message] + conversation_history,
        max_tokens=1024,
        temperature=0.7
    )

    bot_reply = response.choices[0].message.content

    # Ajouter la réponse à la mémoire
    conversation_history.append({"role": "assistant", "content": bot_reply})

    # Sauvegarder dans SQLite
    save_message("user", user_msg)
    save_message("assistant", bot_reply)

    return jsonify({"response": bot_reply})

@app.route("/history", methods=["GET"])
def history():
    return jsonify(get_history())

@app.route("/clear", methods=["POST"])
def clear():
    global conversation_history
    conversation_history = []
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)