import os, json, logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from huibot.menu import handle_update
from huibot.storage_pg import run_sql_file

logging.basicConfig(level=logging.INFO)
app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","")
PUBLIC_URL = os.getenv("PUBLIC_URL","")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET","")
DATABASE_URL = os.getenv("DATABASE_URL","")

def _assert_secret(req: Request):
    secret = req.query_params.get("secret")
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/health")
def health():
    ok = bool(TELEGRAM_TOKEN and PUBLIC_URL)
    return {"ok": ok}

@app.post("/api/register-webhook")
async def register_webhook(request: Request):
    _assert_secret(request)
    if not TELEGRAM_TOKEN or not PUBLIC_URL:
        raise HTTPException(400, "Missing TELEGRAM_TOKEN or PUBLIC_URL")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    resp = requests.post(url, json={"url": f"{PUBLIC_URL}/webhook"})
    return JSONResponse(resp.json())

@app.post("/api/migrate")
async def migrate(request: Request):
    _assert_secret(request)
    path = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")
    run_sql_file(DATABASE_URL, path)
    return {"migrated": True}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    try:
        await handle_update(update)
    except Exception as e:
        logging.exception("Update handling failed: %s", e)
    return {"ok": True}

@app.get("/api/cron/reminders")
async def cron_reminders(request: Request):
    _assert_secret(request)
    # TODO: build group-wise reminders
    return {"scheduled": True}

@app.get("/api/cron/monthly")
async def cron_monthly(request: Request):
    _assert_secret(request)
    # TODO: monthly jobs (closing cycles/report)
    return {"scheduled": True}