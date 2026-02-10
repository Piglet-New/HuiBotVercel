from __future__ import annotations

from enum import Enum


class RewardType(str, Enum):
    cashback = "cashback"
    discount = "discount"
    points = "points"
    miles = "miles"


class TransactionStatus(str, Enum):
    confirmed = "confirmed"


class ReminderStatus(str, Enum):
    paid = "paid"
    unpaid = "unpaid"
