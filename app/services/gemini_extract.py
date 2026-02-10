from __future__ import annotations

from typing import Any

import httpx


async def extract_offers_with_gemini(api_key: str, text: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    prompt = (
        "Trích xuất danh sách ưu đãi thẻ tín dụng từ văn bản sau. "
        "Trả về JSON array với các trường: bank, reward_type, reward_percent, reward_fixed_vnd, "
        "cap_vnd, min_spend_vnd, category, merchant, location, start_date, end_date, "
        "activation_required, activation_mode, activation_note, bin_prefixes."
        f"\n\nVăn bản:\n{text[:8000]}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
            params={"key": api_key},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    text_response = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    try:
        import json

        return json.loads(text_response)
    except Exception:
        return []
