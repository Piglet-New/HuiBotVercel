# api/index.py
# Minimal Flask API for Vercel serverless
# - /api/healthz                 : health check
# - /api/register-webhook        : set Telegram webhook to /api/telegram/webhook
# - /api/telegram/webhook (POST) : receive Telegram updates (simple reply)
# - /api/test/send               : send a test message to a chat_id

import os, json
from flask import Flask, request, jsonify
import httpx

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
PUBLIC_URL     = os.environ.get("PUBLIC_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

app = Flask(__name__)

def tg_api(method: str, **params):
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "Missing TELEGRAM_TOKEN"}
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    with httpx.Client(timeout=10) as client:
        r = client.post(url, json=params)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "status_code": r.status_code, "text": r.text}

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True})

@app.get("/api/")
def root():
    return jsonify({"ok": True, "service": "huibot-vercel"})

@app.get("/api/register-webhook")
def register_webhook():
    if not TELEGRAM_TOKEN or not PUBLIC_URL:
        return jsonify({"ok": False, "error": "Missing TELEGRAM_TOKEN or PUBLIC_URL"}), 400
    params = {"url": f"{PUBLIC_URL.rstrip('/')}/api/telegram/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET
    with httpx.Client(timeout=10) as client:
        r = client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", params=params)
        return jsonify(r.json())

@app.post("/api/telegram/webhook")
def telegram_webhook():
    # (khuyến nghị) xác thực secret token nếu có cấu hình
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            return jsonify({"ok": False, "error": "Bad secret"}), 401

    update = request.get_json(silent=True) or {}
    msg = update.get("message") or update.get("edited_message")
    if msg and TELEGRAM_TOKEN:
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()

        # trả lời tối thiểu để xác nhận webhook hoạt động
        if text.lower().startswith("/start"):
            tg_api("sendMessage", chat_id=chat_id,
                   text="✅ Webhook OK! Bot đã online. (Logic đầy đủ sẽ được bật sau)")
        elif text:
            tg_api("sendMessage", chat_id=chat_id,
                   text=f"Bạn vừa gửi: {text}\n\nWebhook đã nhận OK.")

    return jsonify({"ok": True})

@app.get("/api/test/send")
def test_send():
    chat_id = request.args.get("chat_id")
    text = request.args.get("text", "Hello from Vercel")
    if not chat_id:
        return jsonify({"ok": False, "error": "Missing chat_id"}), 400
    data = tg_api("sendMessage", chat_id=int(chat_id), text=text)
    return jsonify(data)
