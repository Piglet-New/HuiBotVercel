from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.firestore import get_client, server_timestamp


def create_transaction(user_id: str, tx: dict[str, Any]) -> str:
    client = get_client()
    tx_id = client.collection("users").document(user_id).collection("transactions").document().id
    tx["tx_id"] = tx_id
    tx["created_at"] = server_timestamp()
    client.collection("users").document(user_id).collection("transactions").document(tx_id).set(tx)
    return tx_id


def create_ledger_entry(user_id: str, entry: dict[str, Any]) -> str:
    client = get_client()
    ledger_id = client.collection("users").document(user_id).collection("ledger").document().id
    entry["ledger_id"] = ledger_id
    entry["created_at"] = server_timestamp()
    client.collection("users").document(user_id).collection("ledger").document(ledger_id).set(entry)
    return ledger_id


def delete_transaction(user_id: str, tx_id: str) -> dict[str, Any] | None:
    client = get_client()
    tx_ref = client.collection("users").document(user_id).collection("transactions").document(tx_id)
    tx_doc = tx_ref.get()
    if not tx_doc.exists:
        return None
    tx_data = tx_doc.to_dict()
    tx_ref.delete()
    ledger_ref = (
        client.collection("users")
        .document(user_id)
        .collection("ledger")
        .where("tx_id", "==", tx_id)
    )
    for doc in ledger_ref.stream():
        doc.reference.delete()
    return tx_data


def store_undo(user_id: str, tx_data: dict[str, Any]) -> None:
    client = get_client()
    client.collection("users").document(user_id).collection("settings").document("undo_last").set(
        {"tx_data": tx_data, "created_at": server_timestamp()},
        merge=True,
    )


def restore_undo(user_id: str) -> dict[str, Any] | None:
    client = get_client()
    doc_ref = client.collection("users").document(user_id).collection("settings").document("undo_last")
    doc = doc_ref.get()
    if not doc.exists:
        return None
    payload = doc.to_dict()
    tx_data = payload.get("tx_data")
    if not tx_data:
        return None
    created_at = payload.get("created_at")
    if isinstance(created_at, datetime):
        elapsed = datetime.utcnow() - created_at.replace(tzinfo=None)
        if elapsed.total_seconds() > 300:
            return None
    tx_id = tx_data.get("tx_id")
    if not tx_id:
        return None
    client.collection("users").document(user_id).collection("transactions").document(tx_id).set(tx_data)
    doc_ref.delete()
    return tx_data
