"""
payment_handler.py
------------------
Xử lý mua xu và mua package VIP.
Sau khi user gửi xác nhận + ảnh CK → thông báo admin bot kèm ảnh.

Giá xu:
  10.000đ  → 200 xu   (10 ảnh)
  20.000đ  → 450 xu   (22 ảnh)
  50.000đ  → 1200 xu  (60 ảnh)
  100.000đ → 2600 xu  (130 ảnh)
  200.000đ → 5500 xu  (275 ảnh)

Giá VIP:
  69.000đ  → VIP      (700 xu/ngày)
  149.000đ → VIP PRO  (3000 xu/ngày)
"""
import logging
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot as TGBot
)
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
QR_IMAGE_PATH = "image/qr.png"   # ảnh QR chuyển khoản

# Bot admin nhận thông báo thanh toán
ADMIN_BOT_TOKEN = "8712430335:AAGBsFNLflx7BXZpjgQ_fMesAqF76gAgUCk"
ADMIN_CHAT_ID   = 5933186992   # chat_id của @shadowbotnet99

COIN_PACKAGES = [
    {"id": "coin_10k",  "vnd": 10_000,  "coin": 200,  "image": 10,  "label": "200 xu  · 10 ảnh"},
    {"id": "coin_20k",  "vnd": 20_000,  "coin": 450,  "image": 22,  "label": "450 xu  · 22 ảnh"},
    {"id": "coin_50k",  "vnd": 50_000,  "coin": 1200, "image": 60,  "label": "1.200 xu · 60 ảnh"},
    {"id": "coin_100k", "vnd": 100_000, "coin": 2600, "image": 130, "label": "2.600 xu · 130 ảnh"},
    {"id": "coin_200k", "vnd": 200_000, "coin": 5500, "image": 275, "label": "5.500 xu · 275 ảnh"},
]

VIP_PACKAGES = [
    {
        "id":    "vip",
        "vnd":   69_000,
        "label": "VIP  ·  700 xu/ngày",
        "coin_per_day": 700,
        "desc":  "Nhận 700 xu mỗi ngày, không hàng chờ",
    },
    {
        "id":    "vip_pro",
        "vnd":   149_000,
        "label": "VIP PRO  ·  3.000 xu/ngày",
        "coin_per_day": 3000,
        "desc":  "Nhận 3.000 xu mỗi ngày, ưu tiên tối đa",
    },
]

COIN_MAP = {p["id"]: p for p in COIN_PACKAGES}
VIP_MAP  = {p["id"]: p for p in VIP_PACKAGES}


def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════

def kb_payment_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Mua Xu",             callback_data="pay_coin_menu")],
        [InlineKeyboardButton("👑 Mua VIP / VIP PRO",  callback_data="pay_vip_menu")],
        [InlineKeyboardButton("◀️ Quay Về",             callback_data="home")],
    ])

def kb_coin_menu():
    rows = []
    for p in COIN_PACKAGES:
        rows.append([InlineKeyboardButton(
            f"💎 {p['label']}  ·  {p['vnd']//1000}k",
            callback_data=f"pay_buy_{p['id']}"
        )])
    rows.append([InlineKeyboardButton("◀️ Quay Lại", callback_data="pay_menu")])
    return InlineKeyboardMarkup(rows)

def kb_vip_menu():
    rows = []
    for p in VIP_PACKAGES:
        rows.append([InlineKeyboardButton(
            f"👑 {p['label']}  ·  {p['vnd']//1000}k",
            callback_data=f"pay_buy_{p['id']}"
        )])
    rows.append([InlineKeyboardButton("◀️ Quay Lại", callback_data="pay_menu")])
    return InlineKeyboardMarkup(rows)

def kb_confirm_payment(pkg_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Gửi Ảnh Chuyển Khoản", callback_data=f"pay_sendphoto_{pkg_id}")],
        [InlineKeyboardButton("❌ Hủy",                   callback_data="pay_menu")],
    ])

def kb_after_pay_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Về Menu Chính", callback_data="home")],
    ])


# ══════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════

def msg_payment_menu(username: str, coin: int) -> str:
    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  💳  CLOTHESBOT  ·  PAYMENT  💳     ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        f"👤 `@{esc(username)}`   💰 Xu hiện có: `{coin}`\n\n"
        "Chọn loại gói bạn muốn mua:"
    )

def msg_coin_menu() -> str:
    lines = [
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  💰  MUA XU  ·  CLOTHESBOT  💰      ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        "📦 *Các gói xu:*\n\n"
    ]
    for p in COIN_PACKAGES:
        lines.append(
            f"  `{p['vnd']//1000:>3}k` → *{p['coin']:>4} xu*  \\({p['image']} ảnh\\)\n"
        )
    lines.append("\n👇 Chọn gói bên dưới:")
    return "".join(lines)

def msg_vip_menu() -> str:
    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  👑  MUA VIP  ·  CLOTHESBOT  👑     ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        "✨ *Gói VIP:*\n"
        "  `69k`  → *VIP*  ·  700 xu/ngày  ·  Không hàng chờ\n\n"
        "✨ *Gói VIP PRO:*\n"
        "  `149k` → *VIP PRO*  ·  3\\.000 xu/ngày  ·  Ưu tiên tối đa\n\n"
        "👇 Chọn gói bên dưới:"
    )

def msg_payment_qr(username: str, pkg_id: str, vnd: int, label: str) -> str:
    if pkg_id.startswith("coin"):
        content = f"@{username} \\- mua xu"
    else:
        content = f"@{username} \\- package"

    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  📲  THÔNG TIN CHUYỂN KHOẢN  📲     ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        f"📦 Gói: *{esc(label)}*\n"
        f"💵 Số tiền: `{vnd:,}đ`\n\n"
        "```\n"
        "┌──────────────────────────────┐\n"
        "│  Nội dung chuyển khoản:      │\n"
        f"│  {content:<28}│\n"
        "└──────────────────────────────┘\n"
        "```\n\n"
        "📸 *Quét mã QR bên dưới để chuyển khoản*\n\n"
        "⚠️ Sau khi chuyển khoản, bấm:\n"
        "*📸 Gửi Ảnh Chuyển Khoản*\n"
        "để gửi ảnh bill CK cho admin xác nhận\\."
    )

def msg_wait_photo(label: str) -> str:
    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  📸  GỬI ẢNH CHUYỂN KHOẢN  📸      ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        f"📦 Gói: *{esc(label)}*\n\n"
        "📲 *Vui lòng gửi ảnh chụp màn hình bill chuyển khoản vào chat này\\.*\n\n"
        "⏳ Admin sẽ duyệt trong *5\\-15 phút* sau khi nhận ảnh\\."
    )

def msg_pending_confirm(label: str) -> str:
    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  ⏳  ĐANG CHỜ XÁC NHẬN  ⏳          ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        f"✅ Đã ghi nhận yêu cầu mua: *{esc(label)}*\n\n"
        "📋 Ảnh CK và thông tin của bạn đã được gửi tới admin\\.\n"
        "⏱ Admin sẽ duyệt trong *5\\-15 phút*\\.\n\n"
        "💡 Nếu sau 30 phút chưa nhận được xu, liên hệ hỗ trợ\\."
    )


# ══════════════════════════════════════════════
#  ADMIN NOTIFICATION
# ══════════════════════════════════════════════

def notify_admin_payment(username: str, user_id: int,
                          pkg: dict, pkg_id: str,
                          photo_bytes: bytes | None = None):
    """
    Gửi thông báo thanh toán tới ADMIN_CHAT_ID qua ADMIN_BOT_TOKEN.
    Dùng requests thuần (sync) upload photo bytes thực tế.
    """
    import requests as _req
    import datetime as _dt
    try:
        vn_now   = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=7)))
        pkg_type = "mua xu" if pkg_id.startswith("coin") else "VIP package"
        caption = (
            f"💳 YÊU CẦU THANH TOÁN MỚI\n\n"
            f"👤 @{username} (ID: {user_id})\n"
            f"📦 Gói: {pkg['label']}\n"
            f"💵 Số tiền: {pkg['vnd']:,}đ\n"
            f"📝 Loại: {pkg_type}\n"
            f"🕐 {vn_now.strftime('%H:%M %d/%m/%Y')}\n\n"
            f"⚡ Lệnh duyệt (gõ vào bot chính @clothesbot):\n"
            f"/addcoins @{username} <số xu>\n"
            f"/setpackage @{username} vip\n"
            f"/setpackage @{username} vip_pro"
        )
        base = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}"
        if photo_bytes:
            # Upload bytes thực tế - tránh lỗi file_id cross-bot
            resp = _req.post(
                f"{base}/sendPhoto",
                data={"chat_id": ADMIN_CHAT_ID, "caption": caption},
                files={"photo": ("ck.jpg", photo_bytes, "image/jpeg")},
                timeout=30,
            )
        else:
            resp = _req.post(
                f"{base}/sendMessage",
                data={"chat_id": ADMIN_CHAT_ID, "text": caption},
                timeout=15,
            )
        if resp.ok:
            log.info(f"[PayNotify] Sent to admin for @{username}")
        else:
            log.error(f"[PayNotify] Telegram error: {resp.text}")
    except Exception as e:
        log.error(f"notify_admin_payment error: {e}")


# ══════════════════════════════════════════════
#  HANDLER (gọi từ btn() trong bottele.py)
# ══════════════════════════════════════════════

async def handle_payment_callback(d: str, q, u, user_db: dict, sessions_db: dict):
    """
    d           : callback_data
    q           : CallbackQuery
    u           : telegram User
    user_db     : dict từ database.get_or_create_user
    sessions_db : dict lưu session (để set state chờ ảnh CK)
    """
    from script.database import record_payment

    username = u.username or str(u.id)
    coin_cur = user_db.get("coin", 0)

    # ── Menu chính payment ──
    if d == "pay_menu":
        await q.edit_message_text(
            msg_payment_menu(username, coin_cur),
            reply_markup=kb_payment_menu(),
            parse_mode="MarkdownV2"
        )
        return

    # ── Menu mua xu ──
    if d == "pay_coin_menu":
        await q.edit_message_text(
            msg_coin_menu(),
            reply_markup=kb_coin_menu(),
            parse_mode="MarkdownV2"
        )
        return

    # ── Menu mua VIP ──
    if d == "pay_vip_menu":
        await q.edit_message_text(
            msg_vip_menu(),
            reply_markup=kb_vip_menu(),
            parse_mode="MarkdownV2"
        )
        return

    # ── Chọn gói → hiện QR ──
    if d.startswith("pay_buy_"):
        pkg_id = d[len("pay_buy_"):]
        pkg = COIN_MAP.get(pkg_id) or VIP_MAP.get(pkg_id)
        if not pkg:
            await q.answer("Gói không hợp lệ!", show_alert=True)
            return

        caption = msg_payment_qr(username, pkg_id, pkg["vnd"], pkg["label"])
        try:
            with open(QR_IMAGE_PATH, "rb") as f:
                await q.message.reply_photo(
                    photo        = f,
                    caption      = caption,
                    parse_mode   = "MarkdownV2",
                    reply_markup = kb_confirm_payment(pkg_id)
                )
            await q.answer()
        except FileNotFoundError:
            await q.edit_message_text(
                caption,
                reply_markup = kb_confirm_payment(pkg_id),
                parse_mode   = "MarkdownV2"
            )
        return

    # ── User bấm "Gửi Ảnh Chuyển Khoản" ──
    if d.startswith("pay_sendphoto_"):
        pkg_id = d[len("pay_sendphoto_"):]
        pkg = COIN_MAP.get(pkg_id) or VIP_MAP.get(pkg_id)
        if not pkg:
            await q.answer("Gói không hợp lệ!", show_alert=True)
            return

        # Lưu state vào session để chờ ảnh
        uid = str(u.id)
        if uid not in sessions_db:
            sessions_db[uid] = {}
        sessions_db[uid]["state"]             = "wait_payment_photo"
        sessions_db[uid]["pending_pkg_id"]    = pkg_id
        sessions_db[uid]["pending_pkg_label"] = pkg["label"]

        kb_cancel_pay = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Hủy", callback_data="pay_menu")]
        ])
        txt = msg_wait_photo(pkg["label"])

        # Tin nhắn hiện tại có thể là ảnh (QR) → không edit_message_text được
        # Thử edit caption trước, nếu không được thì reply tin nhắn mới
        try:
            await q.edit_message_caption(
                caption      = txt,
                reply_markup = kb_cancel_pay,
                parse_mode   = "MarkdownV2",
            )
        except Exception:
            try:
                await q.edit_message_text(
                    txt,
                    reply_markup = kb_cancel_pay,
                    parse_mode   = "MarkdownV2",
                )
            except Exception:
                await q.message.reply_text(
                    txt,
                    reply_markup = kb_cancel_pay,
                    parse_mode   = "MarkdownV2",
                )
        await q.answer()
        return


async def handle_payment_photo(photo_file_id: str, u, sessions_db: dict, bot=None):
    """
    Gọi khi user gửi ảnh trong trạng thái 'wait_payment_photo'.
    Ghi DB + thông báo admin kèm ảnh bytes (download qua bot chính).
    Trả về (success: bool, label: str)
    """
    from script.database import record_payment

    uid     = str(u.id)
    sess    = sessions_db.get(uid, {})
    pkg_id  = sess.get("pending_pkg_id")
    label   = sess.get("pending_pkg_label", "")

    if not pkg_id:
        return False, ""

    pkg = COIN_MAP.get(pkg_id) or VIP_MAP.get(pkg_id)
    if not pkg:
        return False, ""

    username = u.username or str(u.id)

    # Ghi vào DB (KHÔNG ghi lên DB - admin duyệt thủ công mới ghi)
    # record_payment chỉ ghi log pending, KHÔNG cộng xu/gói tự động
    record_payment(
        user_id    = uid,
        username   = username,
        pkg_id     = pkg_id,
        amount_vnd = pkg["vnd"],
    )

    # Download ảnh qua bot chính → gửi bytes sang bot payment
    photo_bytes = None
    if bot:
        try:
            tg_file = await bot.get_file(photo_file_id)
            ba = await tg_file.download_as_bytearray()
            photo_bytes = bytes(ba)
        except Exception as e:
            log.error(f"Download photo error: {e}")

    # Thông báo admin kèm ảnh CK (sync, dùng requests với bytes)
    notify_admin_payment(
        username    = username,
        user_id     = u.id,
        pkg         = pkg,
        pkg_id      = pkg_id,
        photo_bytes = photo_bytes,
    )

    # Reset state
    for key in ("state", "pending_pkg_id", "pending_pkg_label"):
        sess.pop(key, None)

    return True, label