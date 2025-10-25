from flask import Flask, request, jsonify
import os
import httpx
from adapter_huibot import handle_update

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
        handle_update(update)
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/register-webhook")
def register_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        base_url = os.getenv("PUBLIC_URL")

        print("ENV TELEGRAM_TOKEN length:", len(token) if token else None)
        print("ENV PUBLIC_URL:", base_url)

        if not token or not base_url:
            raise ValueError("Missing TELEGRAM_TOKEN or PUBLIC_URL")

        webhook_url = f"{base_url}/api/webhook"
        resp = httpx.get(
            f"https://api.telegram.org/bot{token}/setWebhook",
            params={"url": webhook_url},
            timeout=10,
        )
        print("🔗 Telegram setWebhook raw:", resp.status_code, resp.text)
        return jsonify(resp.json())

    except Exception as e:
        print("❌ register_webhook error:", repr(e))
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/test/getme")
def test_getme():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise ValueError("Missing TELEGRAM_TOKEN")
        r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        print("🔎 getMe raw:", r.status_code, r.text)
        return jsonify(r.json())
    except Exception as e:
        print("❌ getMe error:", repr(e))
        return jsonify({"ok": False, "error": str(e)}), 500
