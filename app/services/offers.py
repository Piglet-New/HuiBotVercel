from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.models.enums import RewardType
from app.services.firestore import get_client, server_timestamp


def _fingerprint(offer: dict[str, Any]) -> str:
    key = "|".join(
        str(offer.get(field, "")).lower()
        for field in [
            "bank",
            "reward_type",
            "reward_percent",
            "reward_fixed_vnd",
            "cap_vnd",
            "min_spend_vnd",
            "category",
            "merchant",
            "location",
            "start_date",
            "end_date",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def seed_offers_from_yaml(path: str = "promos.yaml") -> int:
    file_path = Path(path)
    if not file_path.exists():
        return 0
    data = yaml.safe_load(file_path.read_text()) or []
    if not isinstance(data, list):
        return 0
    client = get_client()
    count = 0
    for entry in data:
        if not isinstance(entry, dict):
            continue
        offer_id = entry.get("offer_id") or client.collection("offers").document().id
        entry["offer_id"] = offer_id
        entry.setdefault("needs_confirmation", True)
        entry.setdefault("verified", False)
        entry.setdefault("reward_type", RewardType.cashback.value)
        entry["fingerprint"] = _fingerprint(entry)
        entry["last_seen_at"] = server_timestamp()
        client.collection("offers").document(offer_id).set(entry, merge=True)
        client.collection("offers_dedupe").document(entry["fingerprint"]).set(
            {"offer_id": offer_id, "last_seen_at": server_timestamp()},
            merge=True,
        )
        count += 1
    return count


def upsert_offer(offer: dict[str, Any]) -> str:
    client = get_client()
    offer.setdefault("reward_type", RewardType.cashback.value)
    offer["fingerprint"] = _fingerprint(offer)
    offer_id = offer.get("offer_id") or client.collection("offers").document().id
    offer["offer_id"] = offer_id
    offer["last_seen_at"] = server_timestamp()
    client.collection("offers").document(offer_id).set(offer, merge=True)
    client.collection("offers_dedupe").document(offer["fingerprint"]).set(
        {"offer_id": offer_id, "last_seen_at": server_timestamp()},
        merge=True,
    )
    return offer_id


def get_active_offers() -> list[dict[str, Any]]:
    client = get_client()
    offers_ref = client.collection("offers")
    offers = [doc.to_dict() for doc in offers_ref.stream()]
    return offers
