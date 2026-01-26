from __future__ import annotations

import re
from typing import Any

import httpx

from app.services.gemini_extract import extract_offers_with_gemini
from app.services.offers import upsert_offer


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


async def crawl_and_extract(url: str, gemini_api_key: str | None) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        html = resp.text
    plain = _strip_html(html)
    offers: list[dict[str, Any]] = []
    if gemini_api_key:
        offers = await extract_offers_with_gemini(gemini_api_key, plain)
    if not offers:
        offers = [
            {
                "bank": "unknown",
                "reward_type": "cashback",
                "reward_percent": None,
                "reward_fixed_vnd": None,
                "cap_vnd": None,
                "min_spend_vnd": None,
                "category": "khac",
                "merchant": None,
                "location": "all",
                "start_date": "2024-01-01",
                "end_date": "2099-12-31",
                "needs_confirmation": True,
                "verified": False,
                "source_name": "crawl",
                "source_url": url,
            }
        ]
    offer_ids = []
    for offer in offers:
        offer.setdefault("needs_confirmation", True)
        offer.setdefault("verified", False)
        offer.setdefault("source_name", "crawl")
        offer.setdefault("source_url", url)
        offer_ids.append(upsert_offer(offer))
    return offer_ids
