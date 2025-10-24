from flask import Flask, request, jsonify
import os
import httpx
from adapter_huibot import handle_update  # bật lại handler bot

app = Flask(__name__)

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True, "msg": "online"})

@app.get("/api/")
def root():
    return jsonify({"ok": True})

@app.post("/api/webhook")
def webhook():
    try:
        update = request.get_json(force=True)
        handle_update(update)  # xử lý update từ Telegram
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/register-webhook")
def register_webhook():
    token = os.getenv("TELEGRAM_TOKEN")
    base_url = os.getenv("PUBLIC_URL")
    webhook_url = f"{base_url}/api/webhook"
    resp = httpx.get(f"https://api.telegram.org/bot{token}/setWebhook", params={"url": webhook_url})
    return jsonify(resp.json())
