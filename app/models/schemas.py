from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import RewardType, TransactionStatus


@dataclass
class Card:
    card_id: str
    alias: str
    bank: str
    network: str | None
    bin_prefix: str | None
    statement_day: int
    due_day: int
    created_at: datetime
    updated_at: datetime
    selected_bonus_category: str | None = None


@dataclass
class Offer:
    offer_id: str
    bank: str
    reward_type: RewardType
    reward_percent: float | None
    reward_fixed_vnd: int | None
    cap_vnd: int | None
    min_spend_vnd: int | None
    category: str
    start_date: str
    end_date: str
    applicable_card_lines: list[str] = field(default_factory=list)
    network: str | None = None
    merchant: str | None = None
    location: str | None = None
    activation_required: bool = False
    activation_mode: str | None = None
    activation_note: str | None = None
    bin_prefixes: list[str] = field(default_factory=list)
    bin_ranges: list[dict[str, Any]] = field(default_factory=list)
    needs_confirmation: bool = True
    verified: bool = False
    source_name: str | None = None
    source_url: str | None = None
    last_seen_at: datetime | None = None
    last_verified_at: datetime | None = None
    fingerprint: str | None = None


@dataclass
class Transaction:
    tx_id: str
    amount_vnd: int
    category: str
    merchant: str | None
    location: str | None
    card_id: str
    tx_date: str
    created_at: datetime
    status: TransactionStatus
    reward_estimate_vnd: int | None = None
    note: str | None = None


@dataclass
class LedgerEntry:
    ledger_id: str
    tx_id: str
    user_id: str
    card_id: str
    offer_id: str | None
    reward_vnd: int
    cap_bucket_key: str
    created_at: datetime
