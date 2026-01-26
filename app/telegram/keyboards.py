from __future__ import annotations


def paid_reminder_keyboard(callback_data: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Đã thanh toán",
                    "callback_data": callback_data,
                }
            ]
        ]
    }
