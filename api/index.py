from flask import Flask, request, jsonify
import os
import httpx
from adapter_huibot import handle_update
from db_pg import init_db

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

try:
    init_db(DATABASE_URL)
    print("✅ Database connected")
except Exception as e:
    print("⚠️ Database init failed:", e)

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True, "msg": "online"})

@app.get("/api/")
def root():
    return jsonify({"ok": True, "service": "huibot-vercel"})

@app.get("/api/register-webhook")
def register_webhook():
    if not TELEGRAM_TOKEN or not PUBLIC_URL:
        return jsonify({"ok": False, "error": "Missing TELEGRAM_TOKEN or PUBLIC_URL"}), 400

    url = f"{PUBLIC_URL.rstrip('/')}/api/telegram/webhook"
    params = {"url": url}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET

    with httpx.Client(timeout=10) as client:
        r = client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", params=params)
        return jsonify(r.json())

@app.post("/api/telegram/webhook")
def telegram_webhook():
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            return jsonify({"ok": False, "error": "Invalid secret"}), 401

    update = request.get_json(silent=True) or {}
    try:
        handle_update(update)
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ Error handling update:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/test/send")
def test_send():
    chat_id = request.args.get("chat_id")
    text = request.args.get("text", "Xin chào từ HuiBot!")
    if not chat_id:
        return jsonify({"ok": False, "error": "Missing chat_id"}), 400

    with httpx.Client(timeout=10) as client:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = client.post(url, json={"chat_id": chat_id, "text": text})
        return jsonify(r.json())
