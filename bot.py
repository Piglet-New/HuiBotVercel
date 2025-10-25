import os
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN","")

def send_message(chat_id, text):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})