from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.firestore import get_client
from app.telegram.formatting import format_currency


def _today() -> date:
    return date.today()


def _cap_bucket_key(card: dict[str, Any], use_statement_cycle: bool) -> str:
    today = _today()
    if not use_statement_cycle:
        return today.strftime("%Y-%m")
    statement_day = int(card.get("statement_day", 1))
    cycle_month = today.month
    cycle_year = today.year
    if today.day < statement_day:
        cycle_month -= 1
        if cycle_month == 0:
            cycle_month = 12
            cycle_year -= 1
    return f"{cycle_year:04d}-{cycle_month:02d}"


def _offer_applicable(offer: dict[str, Any], scenario: dict[str, Any], card: dict[str, Any]) -> bool:
    if offer.get("bank") and offer.get("bank").lower() != card.get("bank", "").lower():
        return False
    if offer.get("category") and offer["category"] != scenario["category"]:
        return False
    if offer.get("merchant") and scenario.get("merchant"):
        if offer["merchant"].lower() not in scenario["merchant"].lower():
            return False
    if offer.get("location") and offer.get("location") != "all":
        if scenario.get("location") != offer.get("location"):
            return False
    if offer.get("bin_prefixes") and card.get("bin_prefix"):
        if card["bin_prefix"] not in offer["bin_prefixes"]:
            return False
    if offer.get("bin_ranges") and card.get("bin_prefix"):
        matched = False
        for rng in offer.get("bin_ranges", []):
            start = str(rng.get("start", ""))
            end = str(rng.get("end", ""))
            if start and end and start <= card["bin_prefix"] <= end:
                matched = True
                break
        if not matched:
            return False
    start_date = offer.get("start_date")
    end_date = offer.get("end_date")
    if start_date and end_date:
        today = _today().isoformat()
        if not (start_date <= today <= end_date):
            return False
    min_spend = offer.get("min_spend_vnd")
    if min_spend and scenario["amount_vnd"] < min_spend:
        return False
    return True


def _remaining_cap(
    user_id: str,
    card_id: str,
    cap_bucket_key: str,
    cap_vnd: int | None,
) -> int | None:
    if not cap_vnd:
        return None
    client = get_client()
    ledger_ref = (
        client.collection("users")
        .document(user_id)
        .collection("ledger")
        .where("card_id", "==", card_id)
        .where("cap_bucket_key", "==", cap_bucket_key)
    )
    used = sum(doc.to_dict().get("reward_vnd", 0) for doc in ledger_ref.stream())
    remaining = max(cap_vnd - used, 0)
    return remaining


def recommend_cards(
    user_id: str,
    scenario: dict[str, Any],
    offers: list[dict[str, Any]],
    use_statement_cycle: bool,
) -> list[dict[str, Any]]:
    client = get_client()
    cards = []
    for doc in client.collection("users").document(user_id).collection("cards").stream():
        card = doc.to_dict()
        card["card_id"] = doc.id
        cards.append(card)
    recommendations: list[dict[str, Any]] = []
    for card in cards:
        applicable = [
            offer
            for offer in offers
            if _offer_applicable(offer, scenario, card)
        ]
        best_offer = None
        best_reward = 0
        warnings: list[str] = []
        cap_bucket_key = _cap_bucket_key(card, use_statement_cycle)
        for offer in applicable:
            if offer.get("activation_required") and offer.get("activation_mode") == "select_category":
                selected = card.get("selected_bonus_category")
                if selected != offer.get("category"):
                    warnings.append("⚠️ Chưa chọn danh mục ưu đãi")
                    reward = 0
                else:
                    reward = _compute_reward(scenario["amount_vnd"], offer, user_id, card["card_id"], cap_bucket_key)
            else:
                reward = _compute_reward(scenario["amount_vnd"], offer, user_id, card["card_id"], cap_bucket_key)
            if reward > best_reward:
                best_reward = reward
                best_offer = offer
        recommendations.append(
            {
                "card": card,
                "offer": best_offer,
                "reward_vnd": best_reward,
                "warnings": warnings,
                "cap_bucket_key": cap_bucket_key,
            }
        )
    recommendations.sort(key=lambda item: item["reward_vnd"], reverse=True)
    return recommendations


def _compute_reward(
    amount_vnd: int,
    offer: dict[str, Any],
    user_id: str,
    card_id: str,
    cap_bucket_key: str,
) -> int:
    reward_percent = offer.get("reward_percent")
    reward_fixed = offer.get("reward_fixed_vnd")
    reward = 0
    if reward_percent:
        reward = int(amount_vnd * float(reward_percent) / 100)
    elif reward_fixed:
        reward = int(reward_fixed)
    cap_remaining = _remaining_cap(user_id, card_id, cap_bucket_key, offer.get("cap_vnd"))
    if cap_remaining is not None:
        reward = min(reward, cap_remaining)
    return reward


def format_recommendations(recommendations: list[dict[str, Any]]) -> str:
    if not recommendations:
        return "Chưa có thẻ nào được lưu. Bạn hãy thêm thẻ trước nhé."
    lines = ["💳 Gợi ý thẻ tốt nhất:"]
    for idx, item in enumerate(recommendations[:5], start=1):
        card = item["card"]
        offer = item["offer"]
        reward = format_currency(item["reward_vnd"])
        line = f"{idx}. {card.get('alias')} ({card.get('bank')}) - Lợi ích ~ {reward}"
        if offer:
            line += f" | Ưu đãi: {offer.get('category')}"
            if offer.get("merchant"):
                line += f" @ {offer.get('merchant')}"
            if offer.get("needs_confirmation"):
                line += " ⚠️ chưa xác minh"
        else:
            line += " | Không có ưu đãi phù hợp"
        if item["warnings"]:
            line += " " + " ".join(item["warnings"])
        lines.append(line)
    return "\n".join(lines)
