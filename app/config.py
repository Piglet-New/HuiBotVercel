from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    webhook_secret: str
    job_secret: str
    gcp_project_id: str
    region: str
    gemini_api_key: str | None
    admin_telegram_user_ids: set[str]


def load_settings() -> Settings:
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()
    job_secret = os.getenv("JOB_SECRET", "").strip()
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    region = os.getenv("REGION", "asia-southeast1").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    admin_ids_raw = os.getenv("ADMIN_TELEGRAM_USER_IDS", "")
    admin_ids = {item.strip() for item in admin_ids_raw.split(",") if item.strip()}
    if not telegram_bot_token or not webhook_secret or not job_secret or not gcp_project_id:
        missing = [
            key
            for key, value in {
                "TELEGRAM_BOT_TOKEN": telegram_bot_token,
                "WEBHOOK_SECRET": webhook_secret,
                "JOB_SECRET": job_secret,
                "GCP_PROJECT_ID": gcp_project_id,
            }.items()
            if not value
        ]
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return Settings(
        telegram_bot_token=telegram_bot_token,
        webhook_secret=webhook_secret,
        job_secret=job_secret,
        gcp_project_id=gcp_project_id,
        region=region,
        gemini_api_key=gemini_api_key,
        admin_telegram_user_ids=admin_ids,
    )
