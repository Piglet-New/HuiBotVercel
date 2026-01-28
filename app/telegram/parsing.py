from __future__ import annotations

import re
from dataclasses import dataclass


AMOUNT_PATTERN = re.compile(r"(?P<value>[\d.,]+)\s*(?P<unit>tr|triệu|t|k|nghìn)?", re.IGNORECASE)

CATEGORY_SYNONYMS = {
    "y_te": ["bệnh viện", "khám", "y tế", "nhà thuốc", "thuốc"],
    "an_uong": ["ăn uống", "nhà hàng", "haidilao", "cafe", "quán ăn"],
    "sieu_thi": ["siêu thị", "coopmart", "winmart", "lottemart"],
    "bao_hiem": ["bảo hiểm"],
    "xang": ["xăng", "đổ xăng", "cây xăng"],
    "mua_sam": ["mua sắm", "shopping"],
    "online": ["online", "shopee", "lazada", "tiki"],
    "du_lich": ["du lịch", "khách sạn", "vé máy bay"],
    "giai_tri": ["giải trí", "rạp phim"],
    "giao_duc": ["giáo dục", "học phí"],
    "suc_khoe": ["sức khỏe", "gym", "spa"],
    "khac": [],
}

LOCATION_SYNONYMS = {
    "hcm": ["hcm", "sài gòn", "tp hcm", "tphcm"],
    "hanoi": ["hà nội", "hn", "hanoi"],
}


def parse_amount_vnd(text: str) -> int | None:
    cleaned = text.lower().replace(" ", "")
    if not cleaned:
        return None
    shorthand = re.search(r"(?P<million>\d+)tr(?P<hundred>\d+)", cleaned)
    if shorthand:
        return int(shorthand.group("million")) * 1_000_000 + int(shorthand.group("hundred")) * 100_000
    match = AMOUNT_PATTERN.search(cleaned)
    if not match:
        return None
    value_raw = match.group("value").replace(",", ".")
    if value_raw.count(".") > 1:
        value_raw = value_raw.replace(".", "")
    try:
        value = float(value_raw)
    except ValueError:
        return None
    unit = (match.group("unit") or "").lower()
    if unit in {"tr", "triệu", "t"}:
        return int(value * 1_000_000)
    if unit in {"k", "nghìn"}:
        return int(value * 1_000)
    return int(value)


@dataclass
class ParsedIntent:
    intent: str
    amount_vnd: int | None = None
    category_text: str | None = None
    merchant: str | None = None
    card_alias: str | None = None
    raw_text: str | None = None


def parse_intent(text: str) -> ParsedIntent:
    lowered = text.lower().strip()
    if lowered.startswith("xác nhận ưu đãi"):
    return ParsedIntent(intent="confirm_offer", raw_text=lowered)
    if lowered.startswith("xác nhận"):
        return ParsedIntent(intent="confirm", raw_text=lowered)
    if lowered.startswith("xoa ") or lowered.startswith("xóa "):
        return ParsedIntent(intent="delete_tx", raw_text=lowered)
    if lowered.startswith("hoàn tác"):
        return ParsedIntent(intent="undo_delete", raw_text=lowered)
    if lowered.startswith("chọn danh mục") or "đổi danh mục" in lowered:
        return ParsedIntent(intent="select_category", raw_text=lowered)
    if lowered.startswith("nạp ưu đãi") or lowered.startswith("ingest"):
        return ParsedIntent(intent="ingest_offer", raw_text=lowered)
    if lowered.startswith("xác nhận ưu đãi"):
        return ParsedIntent(intent="verify_offer", raw_text=lowered)
    if lowered.startswith("sao kê"):
        return ParsedIntent(intent="statement_amount", raw_text=lowered)
    if lowered.startswith("thêm thẻ") or lowered.startswith("them the"):
        return ParsedIntent(intent="add_card", raw_text=lowered)
    if lowered.startswith("liệt kê thẻ") or lowered.startswith("liet ke the") or lowered.startswith("danh sách thẻ"):
        return ParsedIntent(intent="list_cards", raw_text=lowered)
    if lowered.startswith("sửa thẻ") or lowered.startswith("sua the"):
        return ParsedIntent(intent="edit_card", raw_text=lowered)
    if lowered.startswith("xóa thẻ") or lowered.startswith("xoa the"):
        return ParsedIntent(intent="delete_card", raw_text=lowered)
    if lowered.startswith("/start"):
        return ParsedIntent(intent="start", raw_text=lowered)
    return ParsedIntent(intent="recommend", raw_text=lowered)


def extract_category(text: str) -> tuple[str, str | None]:
    for category, keywords in CATEGORY_SYNONYMS.items():
        for keyword in keywords:
            if keyword in text:
                return category, keyword
    return "khac", None


def extract_location(text: str) -> str | None:
    for location, keywords in LOCATION_SYNONYMS.items():
        for keyword in keywords:
            if keyword in text:
                return location.upper()
    return None


def parse_recommendation_query(text: str) -> tuple[int | None, str, str | None, str | None]:
    amount = parse_amount_vnd(text)
    category, matched_keyword = extract_category(text)
    location = extract_location(text)
    merchant = None
    tokens = text
    shorthand_match = re.search(r"\d+tr\d+", tokens)
    if shorthand_match:
        tokens = tokens.replace(shorthand_match.group(0), "")
    else:
        amount_match = AMOUNT_PATTERN.search(tokens)
        if amount_match:
            tokens = tokens.replace(amount_match.group(0), "")
    if matched_keyword:
        tokens = tokens.replace(matched_keyword, "")
    if tokens:
        merchant = tokens.strip()
    return amount, category, merchant, location


def extract_confirm_parts(text: str) -> tuple[int | None, str | None]:
    lowered = text.lower()
    tokens = lowered.replace("xác nhận", "").strip()
    match = AMOUNT_PATTERN.search(tokens)
    if not match:
        return None, None
    amount_text = match.group(0)
    amount = parse_amount_vnd(amount_text)
    remaining = tokens.replace(amount_text, "").strip()
    return amount, remaining or None


def parse_delete_target(text: str) -> str | None:
    lowered = text.lower().strip()

    # Ưu tiên case đặc biệt: "xóa giao dịch mới nhất"
    if lowered == "xóa giao dịch mới nhất":
        return "latest"

    match = re.search(r"xóa giao dịch\s+(.+)", lowered)
    if match:
        return match.group(1).strip()

    return None

