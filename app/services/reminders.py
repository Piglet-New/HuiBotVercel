from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.services.firestore import get_client, server_timestamp
from app.telegram.keyboards import paid_reminder_keyboard


def _cycle_key(card: dict[str, Any], today: date) -> str:
    statement_day = int(card.get("statement_day", 1))
    cycle_month = today.month
    cycle_year = today.year
    if today.day < statement_day:
        cycle_month -= 1
        if cycle_month == 0:
            cycle_month = 12
            cycle_year -= 1
    return f"{cycle_year:04d}-{cycle_month:02d}"


def _cycle_period(card: dict[str, Any], today: date) -> tuple[date, date]:
    statement_day = int(card.get("statement_day", 1))
    cycle_key = _cycle_key(card, today)
    year, month = map(int, cycle_key.split("-"))
    start_date = date(year, month, statement_day)
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1
    end_date = date(next_year, next_month, statement_day) - timedelta(days=1)
    return start_date, end_date


def _due_date(card: dict[str, Any], today: date) -> date:
    due_day = int(card.get("due_day", 1))
    cycle_key = _cycle_key(card, today)
    year, month = map(int, cycle_key.split("-"))
    due_month = month + 1
    due_year = year
    if due_month == 13:
        due_month = 1
        due_year += 1
    return date(due_year, due_month, due_day)


def _statement_amount(user_id: str, card_id: str, cycle_key: str) -> int:
    client = get_client()
    doc_ref = (
        client.collection("users")
        .document(user_id)
        .collection("settings")
        .document(f"statement_amount_{card_id}_{cycle_key}")
    )
    doc = doc_ref.get()
    if doc.exists:
        return int(doc.to_dict().get("amount_vnd", 0))
    return 0


def _sum_transactions(user_id: str, card_id: str, start: date, end: date) -> int:
    client = get_client()
    tx_ref = (
        client.collection("users")
        .document(user_id)
        .collection("transactions")
        .where("card_id", "==", card_id)
        .where("tx_date", ">=", start.isoformat())
        .where("tx_date", "<=", end.isoformat())
    )
    return sum(doc.to_dict().get("amount_vnd", 0) for doc in tx_ref.stream())


def _should_notify(today: date, due_date: date, reminder_doc: dict[str, Any] | None) -> bool:
    if today < due_date - timedelta(days=5) or today > due_date:
        return False
    if reminder_doc and reminder_doc.get("paid"):
        return False
    last_notified = reminder_doc.get("last_notified_date") if reminder_doc else None
    return last_notified != today.isoformat()


async def send_daily_reminders(bot_token: str) -> int:
    client = get_client()
    users = [doc.id for doc in client.collection("users").stream()]
    sent = 0
    async with httpx.AsyncClient(timeout=10) as http:
        for user_id in users:
            cards = (
                client.collection("users")
                .document(user_id)
                .collection("cards")
                .stream()
            )
            for card_doc in cards:
                card = card_doc.to_dict()
                today = date.today()
                cycle_key = _cycle_key(card, today)
                reminder_id = f"{user_id}_{card_doc.id}_{cycle_key}"
                reminder_ref = client.collection("reminders").document(reminder_id)
                reminder_doc = reminder_ref.get()
                reminder_data = reminder_doc.to_dict() if reminder_doc.exists else None
                due_date = _due_date(card, today)
                if not _should_notify(today, due_date, reminder_data):
                    continue
                start_date, end_date = _cycle_period(card, today)
                manual_amount = _statement_amount(user_id, card_doc.id, cycle_key)
                total_amount = manual_amount or _sum_transactions(user_id, card_doc.id, start_date, end_date)
                message = (
                    f"🔔 Nhắc thanh toán thẻ {card.get('alias')}.\n"
                    f"Số tiền cần thanh toán: {total_amount:,.0f}đ\n"
                    f"Hạn thanh toán: {due_date.strftime('%d/%m/%Y')}"
                ).replace(",", ".")
                callback = f"paid:{reminder_id}"
                payload = {
                    "chat_id": int(user_id),
                    "text": message,
                    "reply_markup": paid_reminder_keyboard(callback),
                }
                await http.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json=payload,
                )
                reminder_ref.set(
                    {
                        "user_id": user_id,
                        "card_id": card_doc.id,
                        "cycle_key": cycle_key,
                        "paid": False,
                        "last_notified_date": today.isoformat(),
                        "updated_at": server_timestamp(),
                    },
                    merge=True,
                )
                sent += 1
    return sent


def mark_cycle_paid(reminder_id: str) -> None:
    client = get_client()
    reminder_ref = client.collection("reminders").document(reminder_id)
    reminder_ref.set(
        {
            "paid": True,
            "paid_at": server_timestamp(),
        },
        merge=True,
    )
