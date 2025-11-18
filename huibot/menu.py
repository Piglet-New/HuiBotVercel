# huibot/menu.py
from bot import send_message
from .core import create_group, join_group
from .storage_pg import db

# --- helper: gửi menu inline ---
def _send_main_menu(chat_id: int):
    # Inline keyboard: mỗi nút bấm bot sẽ trả hướng dẫn/templated-command
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "➕ Tạo nhóm", "callback_data": "help_create"},
                {"text": "✅ Tham gia nhóm", "callback_data": "help_join"},
            ],
            [
                {"text": "📋 Lệnh nhanh", "callback_data": "help_menu"},
                {"text": "📊 Báo cáo", "callback_data": "help_report"},
            ],
            [
                {"text": "🔒 Đóng kỳ", "callback_data": "help_close"},
                {"text": "🛟 Backup", "callback_data": "help_backup"},
            ],
        ]
    }
    # Gửi bằng phương thức sendMessage trực tiếp (bot.py)
    import os, requests
    TOKEN = os.getenv("TELEGRAM_TOKEN","")
    if not TOKEN: 
        send_message(chat_id, "Thiếu TELEGRAM_TOKEN")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": "*Menu quản lý Hụi* — chọn thao tác:",
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    })

async def handle_update(update: dict):
    # 1) Xử lý callback từ inline keyboard
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data")
        chat_id = cq["message"]["chat"]["id"]
        if data == "help_create":
            send_message(chat_id,
                "➕ *Tạo nhóm mới*\n"
                "Dùng lệnh:\n"
                "`/create_group HUI001 Hui5trTuan 12 5000000`\n"
                "- CODE: mã nhóm (duy nhất)\n"
                "- NAME: tên nhóm (không dấu càng tốt)\n"
                "- CYCLES: số kỳ (vd 12)\n"
                "- STAKE: mệnh giá (vd 5000000)\n"
                "Sau khi tạo xong, gửi mã CODE cho thành viên để họ `/join CODE`."
            )
        elif data == "help_join":
            send_message(chat_id,
                "✅ *Tham gia nhóm*\n"
                "Dùng lệnh: `/join HUI001`\n"
                "Trong đó `HUI001` là mã nhóm chủ hụi cung cấp."
            )
        elif data == "help_menu":
            send_message(chat_id,
                "*Lệnh nhanh:*\n"
                "/menu — hiện menu\n"
                "/create_group HUI001 Hui5trTuan 12 5000000\n"
                "/join HUI001\n"
                "(Sắp thêm) /close_cycle — đóng kỳ hiện tại\n"
                "(Sắp thêm) /report — báo cáo tổng hợp"
            )
        elif data == "help_report":
            send_message(chat_id,
                "📊 *Báo cáo tổng quan*\n"
                "Phiên bản này sẽ bổ sung lệnh `/report` sau khi hoàn thiện logic.\n"
                "Tạm thời bạn có thể xem danh sách nhóm/chu kỳ qua SQL (Neon)."
            )
        elif data == "help_close":
            send_message(chat_id,
                "🔒 *Đóng kỳ*\n"
                "Tính năng `/close_cycle` sẽ có trong bản kế tiếp.\n"
                "Cơ chế: xác định group hiện tại → cycle_index → đánh dấu closed & mở kỳ kế tiếp."
            )
        elif data == "help_backup":
            send_message(chat_id,
                "🛟 *Backup*\n"
                "Bản Postgres không cần JSON backup tại serverless; sẽ thêm `/export` để xuất CSV sau."
            )
        return  # đã xong callback

    # 2) Xử lý message text như trước
    message = update.get("message") or update.get("edited_message")
    if not message: 
        return
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    tg_user = message["from"]
    tg_id = tg_user["id"]
    username = tg_user.get("username")
    display = tg_user.get("first_name")

    if text.startswith("/start"):
        send_message(chat_id, "Xin chào! Gõ /menu để xem chức năng.")
    elif text.startswith("/menu"):
        _send_main_menu(chat_id)
    elif text.startswith("/create_group"):
        try:
            parts = text.split(" ", 4)
            if len(parts) < 5:
                send_message(chat_id, "Cú pháp: `/create_group CODE NAME CYCLES STAKE`")
                return
            code, name, cycles, stake = parts[1], parts[2], int(parts[3]), float(parts[4])
            gid = create_group(db.url(), code, name, tg_id, cycles, stake)
            send_message(chat_id, f"Đã tạo nhóm *{code}* (id={gid}).")
        except Exception as e:
            send_message(chat_id, f"❗Không tạo được nhóm: `{e}`")
            raise
    elif text.startswith("/join"):
        try:
            parts = text.split(" ", 1)
            if len(parts) < 2:
                send_message(chat_id, "Cú pháp: `/join CODE`")
                return
            code = parts[1].strip()
            gid, uid = join_group(db.url(), code, tg_id, username, display)
            send_message(chat_id, f"Đã tham gia nhóm *{code}*.")
        except Exception as e:
            send_message(chat_id, f"❗Không tham gia được nhóm: `{e}`")
            raise
    else:
        _send_main_menu(chat_id)
