from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from app.config import load_settings
from app.services.crawl import crawl_and_extract
from app.services.offers import seed_offers_from_yaml
from app.services.reminders import send_daily_reminders
from app.telegram.router import router as telegram_router


app = FastAPI(title="HuiBot Telegram")
app.include_router(telegram_router)


@app.on_event("startup")
async def startup() -> None:
    seed_offers_from_yaml()


@app.post("/jobs/crawl_offers")
async def job_crawl_offers(request: Request) -> dict[str, int]:
    settings = load_settings()
    secret = request.headers.get("JOB_SECRET") or request.query_params.get("job_secret")
    if secret != settings.job_secret:
        raise HTTPException(status_code=403, detail="Invalid job secret")
    payload = await request.json()
    urls = payload.get("urls", [])
    count = 0
    for url in urls:
        await crawl_and_extract(url, settings.gemini_api_key)
        count += 1
    return {"crawled": count}


@app.post("/jobs/send_reminders")
async def job_send_reminders(request: Request) -> dict[str, int]:
    settings = load_settings()
    secret = request.headers.get("JOB_SECRET") or request.query_params.get("job_secret")
    if secret != settings.job_secret:
        raise HTTPException(status_code=403, detail="Invalid job secret")
    sent = await send_daily_reminders(settings.telegram_bot_token)
    return {"sent": sent}
