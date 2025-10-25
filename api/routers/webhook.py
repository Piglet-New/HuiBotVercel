# /api/routes/webhook.py
from flask import Blueprint, request, jsonify
import os, httpx
from adapter_huibot import handle_update  # dùng handler sẵn có của bạn

bp = Blueprint("webhook", __name__)

@bp.post("/webhook")
def webhook():
    # Bảo vệ bằng secret token của Telegram (nên bật trong setWebhook)
    want = os.getenv("WEBHOOK_SECRET", "")
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

    if want and got != want:
        return jsonify({"ok": False, "error": "Invalid secret token"}), 403

    try:
        update = request.get_json(force=True, silent=False)
        handle_update(update)  # Giao cho adapter xử lý
        return jsonify({"ok": True})
    except Exception as e:
        # để dễ debug trên Vercel Logs
        print("✖ webhook error:", repr(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/register-webhook")
def register_webhook():
    """
    Gọi:  GET /api/register-webhook
    Tác dụng: Đăng ký Webhook cho bot → trỏ về /api/webhook
    """
    token = os.getenv("TELEGRAM_TOKEN")
    base_url = os.getenv("PUBLIC_URL")  # vd: https://hui-bot-vercel.vercel.app
    secret = os.getenv("WEBHOOK_SECRET", "")

    if not token or not base_url:
        return jsonify({"ok": False, "error": "Missing TELEGRAM_TOKEN or PUBLIC_URL"}), 500

    webhook_url = f"{base_url}/api/webhook"
    try:
        with httpx.Client(timeout=10) as cli:
            resp = cli.get(
                f"https://api.telegram.org/bot{token}/setWebhook",
                params={"url": webhook_url, "secret_token": secret} if secret else {"url": webhook_url},
            )
            return jsonify(resp.json())
    except Exception as e:
        print("✖ register_webhook error:", repr(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/test/getme")
def test_getme():
    """
    Gọi: GET /api/test/getme → test token Telegram
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        return jsonify({"ok": False, "error": "Missing TELEGRAM_TOKEN"}), 500

    try:
        with httpx.Client(timeout=10) as cli:
            r = cli.get(f"https://api.telegram.org/bot{token}/getMe")
            return jsonify(r.json())
    except Exception as e:
        print("✖ getMe error:", repr(e))
        return jsonify({"ok": False, "error": str(e)}), 500
