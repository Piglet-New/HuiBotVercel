import os
import httpx

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_message(chat_id, text):
    httpx.get(f"{TG_API}/sendMessage", params={
        "chat_id": chat_id,
        "text": text
    })

def handle_update(update):
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        # Gửi phản hồi
        reply = f"Bạn nói: {text}"
        send_message(chat_id, reply)
