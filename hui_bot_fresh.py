
# ===================== hui_bot_fresh.py (Neon Postgres) =====================
# Telegram Hui Bot — Webhook-first, Serverless-friendly
# Dependencies: python-telegram-bot==20.3, pandas, psycopg2-binary
import os, json, asyncio, random, re, unicodedata
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple, Dict, List, Any

import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
)

from db_pg import db, init_db, ensure_schema, cfg_get, cfg_set

# ========= CONFIG =========
TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("Missing TELEGRAM_TOKEN/BOT_TOKEN in environment variables")

REPORT_HOUR = 8                 # 08:00 gửi báo cáo tháng (chỉ mùng 1)
REMINDER_TICK_SECONDS = 60      # vòng lặp check nhắc hẹn

ISO_FMT = "%Y-%m-%d"   # lưu DB

# ====== UTIL ======
def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def parse_iso(s: str) -> datetime:
    # accepts YYYY-MM-DD (string) or date object
    if hasattr(s, "year"):
        return datetime(s.year, s.month, s.day)
    return datetime.strptime(str(s), ISO_FMT)

def _smart_parse_dmy(s: str) -> Tuple[int,int,int]:
    s = s.strip().replace("/", "-")
    parts = s.split("-")
    if len(parts) != 3:
        raise ValueError(f"Không hiểu ngày: {s}")
    d, m, y = parts
    d, m, y = int(d), int(m), int(y)
    if y < 100:  y += 2000
    datetime(y, m, d)  # validate
    return d, m, y

def parse_user_date(s: str) -> datetime:
    d, m, y = _smart_parse_dmy(s)
    return datetime(y, m, d)

def to_iso_str(d: datetime) -> str:
    return d.strftime(ISO_FMT)

def to_user_str(d: datetime) -> str:
    return d.strftime("%d-%m-%Y")

# ----- MONEY PARSER -----
def parse_money(text: str) -> int:
    s = str(text).strip().lower().replace(",", "").replace("_", "").replace(" ", "").replace(".", "")
    if s.isdigit():
        return int(s)
    try:
        if s.endswith("tr"): return int(float(s[:-2]) * 1_000_000)
        if s.endswith(("k","n")): return int(float(s[:-1]) * 1_000)
        if s.endswith(("m","t")): return int(float(s[:-1]) * 1_000_000)
        return int(float(s))
    except Exception:
        raise ValueError(f"Không hiểu giá trị tiền: {text}")

# ---------- DB Logic ----------
def init_tables_if_needed():
    init_db(); ensure_schema()

def get_all(query: str, params: tuple = ()):
    import psycopg2.extras
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def exec_sql(query: str, params: tuple = ()):
    conn = db()
    cur = conn.cursor()
    cur.execute(query, params)
    cur.close(); conn.close()

def insert_and_get_id(query: str, params: tuple = ()):
    conn = db()
    cur = conn.cursor()
    cur.execute(query + " RETURNING id", params)
    new_id = cur.fetchone()[0]
    cur.close(); conn.close()
    return new_id

def load_cfg() -> dict:
    return cfg_get("bot_cfg", {}) or {}

def save_cfg(cfg: dict):
    cfg_set("bot_cfg", cfg)

# ---------- Business helpers ----------
def k_date(line, k: int) -> datetime:
    return parse_iso(line["start_date"]) + timedelta(days=(k-1)*int(line["period_days"]))

def roi_to_str(r: float) -> str:
    return f"{r*100:.2f}%"

def get_bids(line_id: int):
    rows = get_all("SELECT k, bid FROM rounds WHERE line_id=%s ORDER BY k", (line_id,))
    return {int(r["k"]): int(r["bid"]) for r in rows}

def payout_at_k(line, bids: dict, k: int) -> int:
    M, N = int(line["contrib"]), int(line["legs"])
    T_k = int(bids.get(k, 0))
    D   = int(round(M * float(line.get("thau_rate", 0)) / 100.0))
    return (k-1)*M + (N - k)*(M - T_k) - D

def paid_so_far_if_win_at_k(bids: dict, M: int, k: int) -> int:
    return sum((M - int(bids.get(j, 0))) for j in range(1, k))

def compute_profit_var(line, k: int, bids: dict):
    M = int(line["contrib"])
    po = payout_at_k(line, bids, k)
    paid = paid_so_far_if_win_at_k(bids, M, k)
    base = paid if paid > 0 else M
    profit = po - paid
    roi = profit / base if base else 0.0
    return profit, roi, po, paid

def best_k_var(line, bids: dict, metric="roi"):
    bestk, bestkey, bestinfo = 1, -1e18, None
    for k in range(1, int(line["legs"]) + 1):
        p, r, po, paid = compute_profit_var(line, k, bids)
        key = r if metric == "roi" else p
        if key > bestkey:
            bestk, bestkey, bestinfo = k, key, (p, r, po, paid)
    return bestk, bestinfo

def is_finished(line) -> bool:
    if line["status"] == "CLOSED": return True
    last = k_date(line, int(line["legs"])).date()
    return datetime.now().date() >= last

def load_line_full(line_id: int):
    rows = get_all("SELECT * FROM lines WHERE id=%s", (line_id,))
    if not rows:
        return None, pd.DataFrame()
    line = rows[0]
    pays = get_all("SELECT pay_date, amount FROM payments WHERE line_id=%s ORDER BY pay_date", (line_id,))
    df = pd.DataFrame(pays) if pays else pd.DataFrame(columns=["pay_date","amount"])
    return line, df

# ============= HELP TEXT =============
def help_text() -> str:
    return (
        "👋 **HỤI BOT – Neon Postgres (bền dữ liệu)**\n\n"
        "🌟 **LỆNH CHÍNH** (không dấu, ngày **DD-MM-YYYY**):\n\n"
        "1) Tạo dây (đủ tham số):\n"
        "   /tao <tên> <tuần|tháng> <DD-MM-YYYY> <số_chân> <mệnh_giá> <giá_sàn_%> <giá_trần_%> <đầu_thảo_%>\n"
        "   Ví dụ:\n"
        "   ` /tao Hui10tr tuần 10-10-2025 12 10tr 8 20 50 `\n\n"
        "2) Nhập thăm kỳ:\n"
        "   /tham <mã_dây> <kỳ> <số_tiền_thăm> [DD-MM-YYYY]\n"
        "   Ví dụ: ` /tham 1 1 2tr 10-10-2025 `\n\n"
        "3) Đặt giờ nhắc riêng:\n"
        "   /hen <mã_dây> <HH:MM>\n\n"
        "4) Danh sách / Tóm tắt / Gợi ý hốt:\n"
        "   /danhsach\n"
        "   /tomtat <mã_dây>\n"
        "   /hottot <mã_dây> [Roi%|Lãi]\n\n"
        "5) Đóng dây: /dong <mã_dây>\n\n"
        "6) Cài nơi nhận báo cáo & nhắc (gửi vào chat hiện tại nếu không nhập):\n"
        "   /baocao [chat_id]\n\n"
        "📜 Gõ /lenh bất cứ lúc nào để hiện lại danh sách lệnh."
    )

# ---------- Minimal UI helpers ----------
def list_text() -> str:
    rows = get_all("SELECT id,name,period_days,start_date,legs,contrib,base_rate,cap_rate,thau_rate,status,remind_hour,remind_min FROM lines ORDER BY id DESC")
    if not rows: return "📂 Chưa có dây nào."
    out = ["📋 **Danh sách dây**:"]
    for r in rows:
        kind = "Tuần" if int(r["period_days"])==7 else "Tháng"
        out.append(
            f"• #{r['id']} · {r['name']} · {kind} · mở {to_user_str(parse_iso(r['start_date']))} · chân {r['legs']} · M {int(r['contrib']):,} VND · "
            f"sàn {float(r['base_rate']):.2f}% · trần {float(r['cap_rate']):.2f}% · thầu {float(r['thau_rate']):.2f}% · nhắc {int(r['remind_hour']):02d}:{int(r['remind_min']):02d} · {r['status']}"
        )
    return "\n".join(out)

# ---------- Commands using Postgres ----------
def _int_like(s: str) -> int:
    m = re.search(r"-?\d+", s or "")
    if not m: raise ValueError(f"Không phải số: {s}")
    return int(m.group(0))

async def cmd_setreport(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = load_cfg()
    if ctx.args:
        try: cid = int(ctx.args[0])
        except Exception: return await upd.message.reply_text("❌ `chat_id` không hợp lệ.")
    else:
        cid = upd.effective_chat.id
    cfg["report_chat_id"] = cid
    save_cfg(cfg)
    await upd.message.reply_text(f"✅ Đã lưu nơi nhận báo cáo/nhắc: {cid}")

async def _create_line_and_reply(upd: Update, name, kind, start_user, legs, contrib, base_rate, cap_rate, thau_rate):
    kind_l = str(kind).lower()
    period_days = 7 if kind_l in ["tuan","tuần","t","week","weekly"] else 30
    start_dt  = parse_user_date(start_user)
    start_iso = to_iso_str(start_dt)
    legs      = int(legs)
    contrib_i = parse_money(contrib)
    base_rate = float(base_rate); cap_rate = float(cap_rate); thau_rate = float(thau_rate)
    if not (0 <= base_rate <= cap_rate <= 100): raise ValueError("sàn% <= trần% và nằm trong [0..100]")
    if not (0 <= thau_rate <= 100): raise ValueError("đầu thảo% trong [0..100]")

    line_id = insert_and_get_id(
        """
        INSERT INTO lines(name,period_days,start_date,legs,contrib,bid_type,bid_value,status,base_rate,cap_rate,thau_rate,remind_hour,remind_min,last_remind_iso)
        VALUES(%s,%s,%s,%s,%s,'dynamic',0,'OPEN',%s,%s,%s,8,0,NULL)
        """,
        (name, period_days, start_iso, legs, contrib_i, base_rate, cap_rate, thau_rate)
    )

    await upd.message.reply_text(
        f"✅ Tạo dây #{line_id} ({name}) — {'Hụi Tuần' if period_days==7 else 'Hụi Tháng'}\n"
        f"• Mở: {to_user_str(start_dt)} · Chân: {legs} · Mệnh giá: {contrib_i:,} VND\n"
        f"• Sàn {base_rate:.2f}% · Trần {cap_rate:.2f}% · Đầu thảo {thau_rate:.2f}% (trên M)\n"
        f"⏰ Nhắc mặc định: 08:00 (đổi bằng /hen {line_id} HH:MM)\n"
        f"➡️ Nhập thăm: /tham {line_id} <kỳ> <số_tiền_thăm> [DD-MM-YYYY]"
    )

async def _save_tham_msg(upd: Update, line_id: int, k: int, bid: int, rdate_iso: Optional[str]):
    rows = get_all("SELECT * FROM lines WHERE id=%s", (line_id,))
    if not rows:  return await upd.message.reply_text("❌ Không tìm thấy dây.")
    line = rows[0]
    if not (1 <= k <= int(line["legs"])): return await upd.message.reply_text(f"❌ Kỳ hợp lệ 1..{line['legs']}.")
    M = int(line["contrib"])
    min_bid = int(round(M * float(line.get("base_rate", 0)) / 100.0))
    max_bid = int(round(M * float(line.get("cap_rate", 100)) / 100.0))
    if bid < min_bid or bid > max_bid:
        return await upd.message.reply_text(
            f"❌ Thăm phải trong [{min_bid:,} .. {max_bid:,}] VND "
            f"(Sàn {line['base_rate']}% · Trần {line['cap_rate']}% · M={M:,})"
        )

    exec_sql(
        """
        INSERT INTO rounds(line_id,k,bid,round_date) VALUES(%s,%s,%s,%s)
        ON CONFLICT(line_id,k) DO UPDATE SET bid=EXCLUDED.bid, round_date=EXCLUDED.round_date
        """,
        (line_id, k, bid, rdate_iso)
    )
    await upd.message.reply_text(
        f"✅ Lưu thăm kỳ {k} cho dây #{line_id}: {bid:,} VND" + (f" · ngày {to_user_str(parse_iso(rdate_iso))}" if rdate_iso else "")
    )

async def cmd_set_remind(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 2:
        return await upd.message.reply_text("❌ Cú pháp: /hen <mã_dây> <HH:MM>  (VD: /hen 1 07:45)")
    try:
        line_id = _int_like(ctx.args[0])
        hh, mm = ctx.args[1].split(":"); hh = int(hh); mm = int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59): raise ValueError("giờ/phút không hợp lệ")
    except Exception as e:
        return await upd.message.reply_text(f"❌ Tham số không hợp lệ: {e}")
    rows = get_all("SELECT id FROM lines WHERE id=%s", (line_id,))
    if not rows: return await upd.message.reply_text("❌ Không tìm thấy dây.")
    exec_sql("UPDATE lines SET remind_hour=%s, remind_min=%s WHERE id=%s", (hh, mm, line_id))
    await upd.message.reply_text(f"✅ Đã đặt giờ nhắc cho dây #{line_id}: {hh:02d}:{mm:02d}")

# ----- List / Summary / Suggest / Close -----
async def cmd_list(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await upd.message.reply_text(list_text())

async def cmd_summary(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: line_id = _int_like(ctx.args[0])
    except Exception: return await upd.message.reply_text("❌ Cú pháp: /tomtat <mã_dây>")
    line, _ = load_line_full(line_id)
    if not line: return await upd.message.reply_text("❌ Không tìm thấy dây.")
    bids = get_bids(line_id)
    M, N = int(line["contrib"]), int(line["legs"])
    cfg_line = f"Sàn {float(line.get('base_rate',0)):.2f}% · Trần {float(line.get('cap_rate',100)):.2f}% · Đầu thảo {float(line.get('thau_rate',0)):.2f}% (trên M)"
    k_now = max(1, min(len(bids)+1, N))
    p, r, po, paid = compute_profit_var(line, k_now, bids)
    bestk, (bp, br, bpo, bpaid) = best_k_var(line, bids, metric="roi")
    msg = [
        f"📌 Dây #{line['id']} · {line['name']} · {'Tuần' if int(line['period_days'])==7 else 'Tháng'}",
        f"• Mở: {to_user_str(parse_iso(line['start_date']))} · Chân: {N} · Mệnh giá/kỳ: {M:,} VND",
        f"• {cfg_line} · Nhắc {int(line.get('remind_hour',8)):02d}:{int(line.get('remind_min',0)):02d}",
        f"• Thăm: " + (", ".join([f"k{kk}:{int(b):,}" for kk,b in sorted(bids.items())]) if bids else "(chưa có)"),
        f"• Kỳ hiện tại ước tính: {k_now} · Payout: {po:,} · Đã đóng: {paid:,} → Lãi: {int(round(p)):,} (ROI {roi_to_str(r)})",
        f"⭐ Đề xuất (ROI): kỳ {bestk} · ngày {to_user_str(k_date(line,bestk))} · Payout {bpo:,} · Đã đóng {bpaid:,} · Lãi {int(round(bp)):,} · ROI {roi_to_str(br)}"
    ]
    if is_finished(line): msg.append("✅ Dây đã đến hạn — /dong để lưu trữ.")
    await upd.message.reply_text("\n".join(msg))

async def cmd_whenhot(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 1: return await upd.message.reply_text("❌ Cú pháp: /hottot <mã_dây> [Roi%|Lãi]")
    try: line_id = _int_like(ctx.args[0])
    except Exception: return await upd.message.reply_text("❌ mã_dây phải là số.")
    metric = "roi"
    if len(ctx.args) >= 2:
        raw = strip_accents(ctx.args[1].strip().lower().replace("%", ""))
        if raw in ("roi", "lai"): metric = raw
    line, _ = load_line_full(line_id)
    if not line: return await upd.message.reply_text("❌ Không tìm thấy dây.")
    bids = get_bids(line_id)
    bestk, (bp, br, bpo, bpaid) = best_k_var(line, bids, metric=("roi" if metric=="roi" else "lai"))
    await upd.message.reply_text(
        f"🔎 Gợi ý theo {'ROI%' if metric=='roi' else 'Lãi'}:\n"
        f"• Nên hốt kỳ: {bestk}\n"
        f"• Ngày dự kiến: {to_user_str(k_date(line,bestk))}\n"
        f"• Payout kỳ đó: {bpo:,}\n"
        f"• Đã đóng trước đó: {bpaid:,}\n"
        f"• Lãi ước tính: {int(round(bp)):,} — ROI: {roi_to_str(br)}"
    )

async def cmd_close(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: line_id = _int_like(ctx.args[0])
    except Exception: return await upd.message.reply_text("❌ Cú pháp: /dong <mã_dây>")
    exec_sql("UPDATE lines SET status='CLOSED' WHERE id=%s", (line_id,))
    await upd.message.reply_text(f"🗂️ Đã đóng & lưu trữ dây #{line_id}.")

# ---------- /huy & wizard placeholders ----------
async def cmd_cancel(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await upd.message.reply_text("🛑 Huỷ wizard (serverless không dùng wizard nhiều bước).")

async def handle_text(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await upd.message.reply_text("💡 Vui lòng dùng các lệnh: /tao, /tham, /hen, /danhsach, /tomtat, /hottot, /dong")

# ---------- MAIN (only used if you run locally with polling/webhook) ----------
def main():
    init_tables_if_needed()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_list))
    app.add_handler(CommandHandler("lenh",     cmd_list))
    app.add_handler(CommandHandler("baocao",   cmd_setreport))
    app.add_handler(CommandHandler("tao",      lambda u,c: _create_line_and_reply(u, *c.args[:8])))
    app.add_handler(CommandHandler("tham",     lambda u,c: _save_tham_msg(u, int(c.args[0]), int(c.args[1]), parse_money(c.args[2]), to_iso_str(parse_user_date(c.args[3])) if len(c.args)>=4 else None)))
    app.add_handler(CommandHandler("hen",      cmd_set_remind))
    app.add_handler(CommandHandler("danhsach", cmd_list))
    app.add_handler(CommandHandler("tomtat",   cmd_summary))
    app.add_handler(CommandHandler("hottot",   cmd_whenhot))
    app.add_handler(CommandHandler("dong",     cmd_close))
    app.add_handler(CommandHandler("huy",      cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
