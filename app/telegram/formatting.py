from __future__ import annotations

from datetime import datetime


def format_currency(amount_vnd: int | None) -> str:
    if amount_vnd is None:
        return "N/A"
    return f"{amount_vnd:,.0f}đ".replace(",", ".")


def format_offer_warning(needs_confirmation: bool, activation_required: bool) -> str:
    warnings = []
    if needs_confirmation:
        warnings.append("⚠️ Ưu đãi chưa xác minh")
    if activation_required:
        warnings.append("⚠️ Cần kích hoạt ưu đãi")
    return " ".join(warnings)


def format_datetime(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")
