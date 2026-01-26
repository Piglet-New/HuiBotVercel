from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncio
import httpx
from fastapi import APIRouter, HTTPException

from app.config import load_settings
from app.services.crawl import crawl_and_extract
from app.services.firestore import get_client, server_timestamp
from app.services.ledger import create_ledger_entry, create_transaction, delete_transaction, restore_undo, store_undo
from app.services.offers import get_active_offers
from app.services.recommend import format_recommendations, recommend_cards
from app.services.reminders import mark_cycle_paid
from app.telegram.callbacks import parse_callback
from app.telegram.formatting import format_currency
from app.telegram.parsing import (
    extract_confirm_parts,
    parse_amount_vnd,
    parse_delete_target,
    parse_intent,
    parse_recommendation_query,
)


router = APIRouter()


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    settings = load_settings()
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )


def _get_last_recommendation(user_id: str) -> dict[str, Any] | None:
    client = get_client()
    doc = (
        client.collection("users")
        .document(user_id)
        .collection("settings")
        .document("last_recommendation")
        .get()
    )
    return doc.to_dict() if doc.exists else None


def _store_last_recommendation(user_id: str, payload: dict[str, Any]) -> None:
    client = get_client()
    client.collection("users").document(user_id).collection("settings").document("last_recommendation").set(
        payload,
        merge=True,
    )


@router.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, update: dict[str, Any]) -> dict[str, str]:
    settings = load_settings()
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")
    if "callback_query" in update:
        await _handle_callback(update["callback_query"])
        return {"status": "ok"}
    if "message" in update:
        await _handle_message(update["message"])
        return {"status": "ok"}
    return {"status": "ignored"}


async def _handle_callback(callback: dict[str, Any]) -> None:
    data = callback.get("data") or ""
    parsed = parse_callback(data)
    if not parsed:
        return
    if parsed.action == "paid":
        mark_cycle_paid(parsed.payload)
        await send_message(int(callback["from"]["id"]), "✅ Đã ghi nhận bạn đã thanh toán. Cảm ơn!")


async def _handle_message(message: dict[str, Any]) -> None:
    chat_id = int(message["chat"]["id"])
    text = message.get("text", "")
    if not text:
        return
    intent = parse_intent(text)
    if intent.intent == "start":
        await send_message(
            chat_id,
            "Chào bạn! Mình là bot quản lý thẻ tín dụng. "
            "Bạn có thể hỏi tư vấn như: 'ăn uống 1tr2 haidilao'.",
        )
        return
    if intent.intent == "confirm":
        await _handle_confirm(chat_id, text)
        return
    if intent.intent == "delete_tx":
        await _handle_delete(chat_id, text)
        return
    if intent.intent == "undo_delete":
        await _handle_undo(chat_id)
        return
    if intent.intent == "select_category":
        await _handle_select_category(chat_id, text)
        return
    if intent.intent == "ingest_offer":
        await _handle_ingest(chat_id, text)
        return
    if intent.intent == "verify_offer":
        await _handle_verify_offer(chat_id, text)
        return
    if intent.intent == "statement_amount":
        await _handle_statement_amount(chat_id, text)
        return
    if intent.intent == "add_card":
        await _handle_add_card(chat_id, text)
        return
    if intent.intent == "list_cards":
        await _handle_list_cards(chat_id)
        return
    if intent.intent == "edit_card":
        await _handle_edit_card(chat_id, text)
        return
    if intent.intent == "delete_card":
        await _handle_delete_card(chat_id, text)
        return
    await _handle_recommend(chat_id, text)


async def _handle_recommend(chat_id: int, text: str) -> None:
    amount, category, merchant, location = parse_recommendation_query(text.lower())
    if amount is None:
        await send_message(
            chat_id,
            "Mình chưa hiểu số tiền. Ví dụ: 'ăn uống 1tr2 haidilao' hoặc 'đổ xăng 500k'.",
        )
        return
    offers = get_active_offers()
    scenario = {
        "amount_vnd": amount,
        "category": category,
        "merchant": merchant,
        "location": location,
    }
    recommendations = recommend_cards(str(chat_id), scenario, offers, use_statement_cycle="kỳ sao kê" in text)
    _store_last_recommendation(
        str(chat_id),
        {
            "scenario": scenario,
            "created_at": server_timestamp(),
            "confirmed": False,
            "reminder_sent": False,
        },
    )
    message = format_recommendations(recommendations)
    message += "\n\nNếu muốn lưu giao dịch, gửi: 'xác nhận <số tiền> <tên thẻ>'."
    await send_message(chat_id, message)
    asyncio.create_task(_maybe_send_reminder(chat_id))


async def _handle_confirm(chat_id: int, text: str) -> None:
    if text.strip().lower() == "xác nhận":
        client = get_client()
        pending_ref = (
            client.collection("users")
            .document(str(chat_id))
            .collection("settings")
            .document("pending_category")
        )
        pending_doc = pending_ref.get()
        if pending_doc.exists:
            payload = pending_doc.to_dict()
            await _apply_category_change(chat_id, payload)
            pending_ref.delete()
            return
    amount, card_alias = extract_confirm_parts(text)
    if amount is None or not card_alias:
        await send_message(chat_id, "Bạn cần gửi: xác nhận <số tiền> <tên thẻ>.")
        return
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    selected_card = None
    for card_doc in cards:
        card = card_doc.to_dict()
        if card_alias.lower() in card.get("alias", "").lower():
            card["card_id"] = card_doc.id
            selected_card = card
            break
    if not selected_card:
        await send_message(chat_id, "Không tìm thấy thẻ phù hợp. Hãy kiểm tra tên thẻ.")
        return
    last = _get_last_recommendation(str(chat_id))
    scenario = last.get("scenario") if last else {}
    offers = get_active_offers()
    recommendations = recommend_cards(str(chat_id), scenario, offers, use_statement_cycle=False)
    chosen = next((rec for rec in recommendations if rec["card"]["card_id"] == selected_card["card_id"]), None)
    reward_vnd = chosen["reward_vnd"] if chosen else 0
    offer_id = chosen["offer"]["offer_id"] if chosen and chosen.get("offer") else None
    tx = {
        "amount_vnd": amount,
        "category": scenario.get("category", "khac"),
        "merchant": scenario.get("merchant"),
        "location": scenario.get("location"),
        "card_id": selected_card["card_id"],
        "tx_date": datetime.utcnow().date().isoformat(),
        "status": "confirmed",
        "reward_estimate_vnd": reward_vnd,
    }
    tx_id = create_transaction(str(chat_id), tx)
    ledger = {
        "tx_id": tx_id,
        "user_id": str(chat_id),
        "card_id": selected_card["card_id"],
        "offer_id": offer_id,
        "reward_vnd": reward_vnd,
        "cap_bucket_key": datetime.utcnow().strftime("%Y-%m"),
    }
    create_ledger_entry(str(chat_id), ledger)
    _store_last_recommendation(
        str(chat_id),
        {
            "confirmed": True,
        },
    )
    await send_message(
        chat_id,
        f"✅ Đã lưu giao dịch {format_currency(amount)} cho thẻ {selected_card['alias']}.",
    )


async def _maybe_send_reminder(chat_id: int) -> None:
    await asyncio.sleep(600)
    last = _get_last_recommendation(str(chat_id))
    if not last or last.get("confirmed") or last.get("reminder_sent"):
        return
    await send_message(
        chat_id,
        "Bạn cần lưu giao dịch? Gửi 'xác nhận <số tiền> <tên thẻ>' để ghi nhận nhé.",
    )
    _store_last_recommendation(str(chat_id), {"reminder_sent": True})


async def _handle_delete(chat_id: int, text: str) -> None:
    target = parse_delete_target(text)
    if not target:
        await send_message(chat_id, "Bạn muốn xóa giao dịch nào? Ví dụ: xóa giao dịch mới nhất.")
        return
    client = get_client()
    tx_id = target
    if target == "latest":
        txs = (
            client.collection("users")
            .document(str(chat_id))
            .collection("transactions")
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        tx_doc = next(txs, None)
        if not tx_doc:
            await send_message(chat_id, "Chưa có giao dịch để xóa.")
            return
        tx_id = tx_doc.id
    tx_data = delete_transaction(str(chat_id), tx_id)
    if not tx_data:
        await send_message(chat_id, "Không tìm thấy giao dịch cần xóa.")
        return
    store_undo(str(chat_id), tx_data)
    await send_message(chat_id, "✅ Đã xóa giao dịch. Bạn có thể gửi 'hoàn tác' trong 5 phút.")


async def _handle_undo(chat_id: int) -> None:
    restored = restore_undo(str(chat_id))
    if not restored:
        await send_message(chat_id, "Không có giao dịch nào để hoàn tác hoặc đã hết thời gian.")
        return
    await send_message(chat_id, "✅ Đã hoàn tác giao dịch vừa xóa.")


async def _handle_select_category(chat_id: int, text: str) -> None:
    lowered = text.lower()
    parts = lowered.replace("chọn danh mục", "").replace("đổi danh mục", "").strip().split()
    if len(parts) < 2:
        await send_message(chat_id, "Ví dụ: chọn danh mục <thẻ> <danh mục>.")
        return
    card_alias = " ".join(parts[:-1])
    category = parts[-1]
    await send_message(chat_id, f"Bạn muốn đổi danh mục thẻ {card_alias} sang {category}? Trả lời 'xác nhận'.")
    client = get_client()
    client.collection("users").document(str(chat_id)).collection("settings").document("pending_category").set(
        {"card_alias": card_alias, "category": category, "created_at": server_timestamp()},
        merge=True,
    )


async def _apply_category_change(chat_id: int, payload: dict[str, Any]) -> None:
    card_alias = payload.get("card_alias")
    category = payload.get("category")
    if not card_alias or not category:
        await send_message(chat_id, "Không tìm thấy yêu cầu đổi danh mục.")
        return
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    target = None
    for card_doc in cards:
        card = card_doc.to_dict()
        if card_alias in card.get("alias", "").lower():
            target = card_doc.id
            break
    if not target:
        await send_message(chat_id, "Không tìm thấy thẻ để đổi danh mục.")
        return
    client.collection("users").document(str(chat_id)).collection("cards").document(target).set(
        {"selected_bonus_category": category, "updated_at": server_timestamp()},
        merge=True,
    )
    await send_message(chat_id, f"✅ Đã đổi danh mục của thẻ {card_alias} sang {category}.")


async def _handle_ingest(chat_id: int, text: str) -> None:
    url_match = text.split()
    url = url_match[-1] if url_match else ""
    settings = load_settings()
    try:
        offer_ids = await crawl_and_extract(url, settings.gemini_api_key)
    except Exception:
        await send_message(chat_id, "Không thể nạp ưu đãi từ URL này. Vui lòng thử lại sau.")
        return
    await send_message(chat_id, f"Đã nạp {len(offer_ids)} ưu đãi. Cần xác minh trước khi dùng chính thức.")


async def _handle_verify_offer(chat_id: int, text: str) -> None:
    parts = text.split()
    if len(parts) < 3:
        await send_message(chat_id, "Ví dụ: xác nhận ưu đãi <offer_id>.")
        return
    offer_id = parts[-1]
    client = get_client()
    client.collection("offers").document(offer_id).set(
        {"verified": True, "needs_confirmation": False, "last_verified_at": server_timestamp()},
        merge=True,
    )
    await send_message(chat_id, "✅ Đã xác nhận ưu đãi.")


async def _handle_statement_amount(chat_id: int, text: str) -> None:
    parts = text.split()
    if len(parts) < 3:
        await send_message(chat_id, "Ví dụ: sao kê <thẻ> <số tiền>.")
        return
    amount = parse_amount_vnd(parts[-1])
    if amount is None:
        await send_message(chat_id, "Không hiểu số tiền sao kê.")
        return
    card_alias = " ".join(parts[1:-1])
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    selected_card = None
    for card_doc in cards:
        card = card_doc.to_dict()
        if card_alias.lower() in card.get("alias", "").lower():
            selected_card = card_doc.id
            break
    if not selected_card:
        await send_message(chat_id, "Không tìm thấy thẻ để cập nhật sao kê.")
        return
    cycle_key = datetime.utcnow().strftime("%Y-%m")
    client.collection("users").document(str(chat_id)).collection("settings").document(
        f"statement_amount_{selected_card}_{cycle_key}"
    ).set(
        {"amount_vnd": amount, "updated_at": server_timestamp()},
        merge=True,
    )
    await send_message(chat_id, f"✅ Đã cập nhật số tiền sao kê {format_currency(amount)}.")


async def _handle_add_card(chat_id: int, text: str) -> None:
    parts = text.split()
    if len(parts) < 7:
        await send_message(
            chat_id,
            "Ví dụ: thêm thẻ <alias> <bank> <network> <bin6> <statement_day> <due_day>.",
        )
        return
    alias = parts[2]
    bank = parts[3]
    network = parts[4]
    bin_prefix = parts[5]
    statement_day = parts[6]
    due_day = parts[7] if len(parts) > 7 else "1"
    client = get_client()
    card_id = client.collection("users").document(str(chat_id)).collection("cards").document().id
    client.collection("users").document(str(chat_id)).collection("cards").document(card_id).set(
        {
            "alias": alias,
            "bank": bank,
            "network": network,
            "bin_prefix": bin_prefix,
            "statement_day": int(statement_day),
            "due_day": int(due_day),
            "created_at": server_timestamp(),
            "updated_at": server_timestamp(),
        },
    )
    await send_message(chat_id, f"✅ Đã thêm thẻ {alias}.")


async def _handle_list_cards(chat_id: int) -> None:
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    lines = ["📇 Danh sách thẻ:"]
    count = 0
    for card_doc in cards:
        card = card_doc.to_dict()
        lines.append(
            f"- {card.get('alias')} ({card.get('bank')}) BIN {card.get('bin_prefix')} "
            f"ngày sao kê {card.get('statement_day')}, hạn {card.get('due_day')}"
        )
        count += 1
    if count == 0:
        await send_message(chat_id, "Bạn chưa có thẻ nào. Dùng: thêm thẻ <alias> <bank> ...")
        return
    await send_message(chat_id, "\n".join(lines))


async def _handle_edit_card(chat_id: int, text: str) -> None:
    parts = text.split()
    if len(parts) < 4:
        await send_message(chat_id, "Ví dụ: sửa thẻ <alias> statement_day=25 due_day=10.")
        return
    alias = parts[2]
    updates = {}
    for part in parts[3:]:
        if "=" in part:
            key, value = part.split("=", 1)
            updates[key] = value
    if not updates:
        await send_message(chat_id, "Không có trường nào để cập nhật.")
        return
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    target = None
    for card_doc in cards:
        card = card_doc.to_dict()
        if alias.lower() in card.get("alias", "").lower():
            target = card_doc.id
            break
    if not target:
        await send_message(chat_id, "Không tìm thấy thẻ cần sửa.")
        return
    updates["updated_at"] = server_timestamp()
    client.collection("users").document(str(chat_id)).collection("cards").document(target).set(updates, merge=True)
    await send_message(chat_id, "✅ Đã cập nhật thông tin thẻ.")


async def _handle_delete_card(chat_id: int, text: str) -> None:
    parts = text.split()
    if len(parts) < 3:
        await send_message(chat_id, "Ví dụ: xóa thẻ <alias>.")
        return
    alias = " ".join(parts[2:])
    client = get_client()
    cards = (
        client.collection("users")
        .document(str(chat_id))
        .collection("cards")
        .stream()
    )
    target = None
    for card_doc in cards:
        card = card_doc.to_dict()
        if alias.lower() in card.get("alias", "").lower():
            target = card_doc.id
            break
    if not target:
        await send_message(chat_id, "Không tìm thấy thẻ cần xóa.")
        return
    client.collection("users").document(str(chat_id)).collection("cards").document(target).delete()
    await send_message(chat_id, "✅ Đã xóa thẻ.")
