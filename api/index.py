# api/index.py
# Serverless Flask on Vercel
# Routes:
# - GET  /api/healthz
# - GET  /api/register-webhook
# - POST /api/telegram/webhook
# - GET  /api/test/send?chat_id=...&text=...

import os
from flask import Flask, request, jsonify
import httpx

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
PUBLIC_URL     = os.environ.get("PUBLIC_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

app = Flask(__name__)

def tg_call(method: str, **params):
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "Missing TELEGRAM_TOKEN"}
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    with httpx.Client(timeout=10) as client:
        r = client.post(url, json=params)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "status": r.status_code, "text": r.text}

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True, "service": "huibot-vercel"})

@app.get("/api/")
def root():
    return jsonify({"ok": True})

@app.get("/api/register-webhook")
def register_webhook():
    if not PUBLIC_URL or not TELEGRAM_TOKEN:
        return jsonify({"ok": False, "error": "Missing PUBLIC_URL or TELEGRAM_TOKEN"}), 400
    params = {"url": f"{PUBLIC_URL.rstrip('/')}/api/telegram/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET
    with httpx.Client(timeout=10) as client:
        r = client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", params=params)
        return jsonify(r.json())

@app.post("/api/telegram/webhook")
def telegram_webhook():
    # optional: verify secret token
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return jsonify({"ok": False, "error": "bad secret"}), 401

    update = request.get_json(silent=True) or {}
    msg = update.get("message") or update.get("edited_message")
    if msg:
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        if text.lower().startswith("/start"):
            tg_call("sendMessage", chat_id=chat_id, text="✅ Webhook OK! Bot đã online.")
        elif text:
            tg_call("sendMessage", chat_id=chat_id, text=f"Echo: {text}")
    return jsonify({"ok": True})

@app.get("/api/test/send")
def test_send():
    chat_id = request.args.get("chat_id")
    text = request.args.get("text", "Hello from Vercel")
    if not chat_id:
        return jsonify({"ok": False, "error": "Missing chat_id"}), 400
    return jsonify(tg_call("sendMessage", chat_id=int(chat_id), text=text))
