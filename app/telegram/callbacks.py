from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallbackData:
    action: str
    payload: str


def parse_callback(data: str) -> CallbackData | None:
    if ":" not in data:
        return None
    action, payload = data.split(":", 1)
    return CallbackData(action=action, payload=payload)
