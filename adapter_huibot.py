
"""Serverless adapter for Neon Postgres version.
Parses commands and executes DB logic with simple request→response.
"""
from typing import Dict, Any, List, Union
from hui_bot_fresh import (
    init_tables_if_needed, load_cfg, save_cfg, list_text,
    parse_user_date, to_iso_str, to_user_str, parse_money, k_date,
    load_line_full, get_bids, best_k_var, compute_profit_var,
)
from hui_bot_fresh import _int_like  # reuse
from hui_bot_fresh import exec_sql, insert_and_get_id

init_tables_if_needed()

def handle_update(update: dict) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id:
        return []

    if text.startswith("/start") or text.startswith("/lenh"):
        return {"chat_id": chat_id, "text": list_text()}

    if text.startswith("/baocao"):
        parts = text.split()
        cfg = load_cfg()
        if len(parts) >= 2:
            try: cid = int(parts[1])
            except Exception: return {"chat_id": chat_id, "text": "❌ `chat_id` không hợp lệ."}
        else:
            cid = chat_id
        cfg["report_chat_id"] = cid; save_cfg(cfg)
        return {"chat_id": chat_id, "text": f"✅ Đã lưu nơi nhận báo cáo/nhắc: {cid}"}

    if text.startswith("/danhsach"):
        return {"chat_id": chat_id, "text": list_text()}

    if text.startswith("/tao"):
        parts = text.split()
        if len(parts) < 9:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /tao <tên> <tuần|tháng> <DD-MM-YYYY> <số_chân> <mệnh_giá> <sàn%> <trần%> <đầu_thảo%>"}
        name, kind, start_user, legs, contrib, base_rate, cap_rate, thau_rate = parts[1:9]
        from hui_bot_fresh import parse_user_date
        period_days = 7 if kind.lower() in ["tuan","tuần","t","week","weekly"] else 30
        start_iso = to_iso_str(parse_user_date(start_user))
        contrib_i = parse_money(contrib)
        base_i = float(base_rate); cap_i = float(cap_rate); thau_i = float(thau_rate)
        if not (0 <= base_i <= cap_i <= 100):
            return {"chat_id": chat_id, "text": "❌ sàn% <= trần% và nằm trong [0..100]"}
        line_id = insert_and_get_id(
            "INSERT INTO lines(name,period_days,start_date,legs,contrib,bid_type,bid_value,status,base_rate,cap_rate,thau_rate,remind_hour,remind_min,last_remind_iso) VALUES(%s,%s,%s,%s,%s,'dynamic',0,'OPEN',%s,%s,%s,8,0,NULL)",
            (name, period_days, start_iso, int(legs), contrib_i, base_i, cap_i, thau_i)
        )
        return {"chat_id": chat_id, "text": (f"✅ Tạo dây #{line_id} ({name}) — {'Hụi Tuần' if period_days==7 else 'Hụi Tháng'}\n"
                                            f"• Mở: {start_user} · Chân: {int(legs)} · Mệnh giá: {contrib_i:,} VND\n"
                                            f"• Sàn {base_i:.2f}% · Trần {cap_i:.2f}% · Đầu thảo {thau_i:.2f}% (trên M)\n"
                                            f"⏰ Nhắc mặc định: 08:00 (đổi bằng /hen {line_id} HH:MM)\n"
                                            f"➡️ Nhập thăm: /tham {line_id} <kỳ> <số_tiền_thăm> [DD-MM-YYYY]")}

    if text.startswith("/tham"):
        parts = text.split()
        if len(parts) < 4:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /tham <mã_dây> <kỳ> <số_tiền_thăm> [DD-MM-YYYY]"}
        try:
            line_id = _int_like(parts[1]); k = _int_like(parts[2]); bid = parse_money(parts[3])
            rdate_iso = to_iso_str(parse_user_date(parts[4])) if len(parts) >= 5 else None
            line, _ = load_line_full(line_id)
            if not line: return {"chat_id": chat_id, "text": "❌ Không tìm thấy dây."}
            N = int(line["legs"]); M = int(line["contrib"])
            min_bid = int(round(M * float(line.get("base_rate", 0)) / 100.0))
            max_bid = int(round(M * float(line.get("cap_rate", 100)) / 100.0))
            if bid < min_bid or bid > max_bid:
                return {"chat_id": chat_id, "text": f"❌ Thăm phải trong [{min_bid:,} .. {max_bid:,}] VND (Sàn {line['base_rate']}% · Trần {line['cap_rate']}% · M={M:,})"}
            if not (1 <= k <= N):
                return {"chat_id": chat_id, "text": f"❌ Kỳ hợp lệ 1..{N}."}
            exec_sql(
                "INSERT INTO rounds(line_id,k,bid,round_date) VALUES(%s,%s,%s,%s) ON CONFLICT(line_id,k) DO UPDATE SET bid=EXCLUDED.bid, round_date=EXCLUDED.round_date",
                (line_id, k, bid, rdate_iso)
            )
            extra = (f" · ngày {parts[4]}" if len(parts) >= 5 else "")
            return {"chat_id": chat_id, "text": f"✅ Lưu thăm kỳ {k} cho dây #{line_id}: {bid:,} VND{extra}"}
        except Exception as e:
            return {"chat_id": chat_id, "text": f"❌ Lỗi: {e}"}

    if text.startswith("/hen"):
        parts = text.split()
        if len(parts) != 3:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /hen <mã_dây> <HH:MM>  (VD: /hen 1 07:45)"}
        try:
            line_id = _int_like(parts[1]); hh, mm = parts[2].split(":"); hh = int(hh); mm = int(mm)
            if not (0 <= hh <= 23 and 0 <= mm <= 59): raise ValueError("giờ/phút không hợp lệ")
            exec_sql("UPDATE lines SET remind_hour=%s, remind_min=%s WHERE id=%s", (hh, mm, line_id))
            return {"chat_id": chat_id, "text": f"✅ Đã đặt giờ nhắc cho dây #{line_id}: {hh:02d}:{mm:02d}"}
        except Exception as e:
            return {"chat_id": chat_id, "text": f"❌ Tham số không hợp lệ: {e}"}

    if text.startswith("/tomtat"):
        parts = text.split()
        if len(parts) != 2:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /tomtat <mã_dây>"}
        try:
            line_id = _int_like(parts[1])
            line, _ = load_line_full(line_id)
            if not line: return {"chat_id": chat_id, "text": "❌ Không tìm thấy dây."}
            bids = get_bids(line_id)
            M, N = int(line["contrib"]), int(line["legs"])
            k_now = max(1, min(len(bids)+1, N))
            p, r, po, paid = compute_profit_var(line, k_now, bids)
            bestk, (bp, br, bpo, bpaid) = best_k_var(line, bids, metric="roi")
            msg = (
                f"📌 Dây #{line['id']} · {line['name']}\n"
                f"• Kỳ hiện tại ước tính: {k_now} · Payout: {po:,} · Đã đóng: {paid:,} → Lãi: {int(round(p)):,} (ROI {r*100:.2f}%)\n"
                f"⭐ Đề xuất: kỳ {bestk} · Payout {bpo:,} · Đã đóng {bpaid:,} · Lãi {int(round(bp)):,} · ROI {br*100:.2f}%"
            )
            return {"chat_id": chat_id, "text": msg}
        except Exception as e:
            return {"chat_id": chat_id, "text": f"❌ Lỗi: {e}"}

    if text.startswith("/hottot"):
        parts = text.split()
        if len(parts) < 2:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /hottot <mã_dây> [Roi%|Lãi]"}
        try:
            line_id = _int_like(parts[1])
            metric = "roi"
            if len(parts) >= 3 and parts[2].lower().replace('%','') in ("roi","lai"):
                metric = parts[2].lower().replace('%','')
            line, _ = load_line_full(line_id)
            if not line: return {"chat_id": chat_id, "text": "❌ Không tìm thấy dây."}
            bids = get_bids(line_id)
            bestk, (bp, br, bpo, bpaid) = best_k_var(line, bids, metric=("roi" if metric=="roi" else "lai"))
            return {"chat_id": chat_id, "text": (f"🔎 Gợi ý theo {'ROI%' if metric=='roi' else 'Lãi'}:\n"
                                                f"• Nên hốt kỳ: {bestk}\n"
                                                f"• Ngày dự kiến: {to_iso_str(k_date(line,bestk))}\n"
                                                f"• Payout kỳ đó: {bpo:,}\n"
                                                f"• Đã đóng trước đó: {bpaid:,}\n"
                                                f"• Lãi ước tính: {int(round(bp)):,} — ROI: {br*100:.2f}%")}
        except Exception as e:
            return {"chat_id": chat_id, "text": f"❌ Lỗi: {e}"}

    if text.startswith("/dong"):
        parts = text.split()
        if len(parts) != 2:
            return {"chat_id": chat_id, "text": "❌ Cú pháp: /dong <mã_dây>"}
        try:
            line_id = _int_like(parts[1])
            exec_sql("UPDATE lines SET status='CLOSED' WHERE id=%s", (line_id,))
            return {"chat_id": chat_id, "text": f"🗂️ Đã đóng & lưu trữ dây #{line_id}."}
        except Exception as e:
            return {"chat_id": chat_id, "text": f"❌ Lỗi: {e}"}

    return {"chat_id": chat_id, "text": list_text()}
