# app.py (bổ sung import)
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from bot import send_message  # dùng để báo lỗi về chat nếu có

def _check_secret(secret: str):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/migrate")
def migrate_get(secret: str = Query(...)):
    _check_secret(secret)
    path = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")
    run_sql_file(DATABASE_URL, path)
    return {"migrated": True}

@app.post("/api/migrate")
async def migrate_post(request: Request):
    _check_secret(request.query_params.get("secret"))
    path = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")
    run_sql_file(DATABASE_URL, path)
    return {"migrated": True}

@app.get("/api/register-webhook")
def register_webhook_get(secret: str = Query(...)):
    _check_secret(secret)
    if not TELEGRAM_TOKEN or not PUBLIC_URL:
        raise HTTPException(400, "Missing TELEGRAM_TOKEN or PUBLIC_URL")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    resp = requests.post(url, json={"url": f"{PUBLIC_URL}/webhook"})
    return JSONResponse(resp.json())

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    try:
        await handle_update(update)
    except Exception as e:
        # Báo lỗi ra log + cố gắng gửi về chat để bạn thấy ngay
        logging.exception("Update handling failed: %s", e)
        try:
            chat_id = (update.get("message") or {}).get("chat", {}).get("id")
            if chat_id:
                send_message(chat_id, f"❗Lỗi xử lý lệnh: {e}")
        except Exception:
            pass
    return {"ok": True}
