"""
payment_handler.py
------------------
Xử lý mua xu và mua package VIP.

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
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
QR_IMAGE_PATH = "image/qr.png"   # ảnh QR chuyển khoản

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
        [InlineKeyboardButton("💰 Mua Xu",         callback_data="pay_coin_menu")],
        [InlineKeyboardButton("👑 Mua VIP / VIP PRO", callback_data="pay_vip_menu")],
        [InlineKeyboardButton("◀️ Quay Về",         callback_data="home")],
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
        [InlineKeyboardButton("✅ Tôi Đã Chuyển Khoản", callback_data=f"pay_confirm_{pkg_id}")],
        [InlineKeyboardButton("❌ Hủy",                  callback_data="pay_menu")],
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
    """Nội dung tin nhắn kèm QR để chuyển khoản."""
    # Phân biệt nội dung chuyển khoản
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
        "*✅ Tôi Đã Chuyển Khoản*\n"
        "Admin sẽ duyệt và cộng xu trong *5\\-15 phút*\\."
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
        "📋 Thông tin của bạn đã được gửi tới admin\\.\n"
        "⏱ Admin sẽ duyệt trong *5\\-15 phút*\\.\n\n"
        "💡 Nếu sau 30 phút chưa nhận được xu, liên hệ hỗ trợ\\."
    )


# ══════════════════════════════════════════════
#  HANDLER (gọi từ btn() trong bottele.py)
# ══════════════════════════════════════════════

async def handle_payment_callback(d: str, q, u, user_db: dict,
                                  payment_bot_token: str | None = None):
    """
    d          : callback_data
    q          : CallbackQuery
    u          : telegram User
    user_db    : dict từ database.get_or_create_user
    payment_bot_token: (tuỳ chọn) token bot payment riêng để gửi thông báo
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
                    photo=f,
                    caption=caption,
                    parse_mode="MarkdownV2",
                    reply_markup=kb_confirm_payment(pkg_id)
                )
            await q.answer()
        except FileNotFoundError:
            # Nếu chưa có file QR thì gửi text
            await q.edit_message_text(
                caption,
                reply_markup=kb_confirm_payment(pkg_id),
                parse_mode="MarkdownV2"
            )
        return

    # ── User bấm "Đã chuyển khoản" ──
    if d.startswith("pay_confirm_"):
        pkg_id = d[len("pay_confirm_"):]
        pkg = COIN_MAP.get(pkg_id) or VIP_MAP.get(pkg_id)
        if not pkg:
            await q.answer("Gói không hợp lệ!", show_alert=True)
            return

        # Ghi vào bảng payment (trạng thái pending)
        record_payment(
            user_id   = str(u.id),
            username  = username,
            package_or_coin = pkg_id,
            amount_vnd      = pkg["vnd"],
        )

        # Thông báo cho bot payment (nếu có token riêng)
        if payment_bot_token:
            try:
                from telegram import Bot as TGBot
                pay_bot = TGBot(token=payment_bot_token)
                pkg_type = "mua xu" if pkg_id.startswith("coin") else "package"
                notify_text = (
                    f"💳 *YÊU CẦU THANH TOÁN MỚI*\n\n"
                    f"👤 @{username} \\(`{u.id}`\\)\n"
                    f"📦 Gói: `{pkg['label']}`\n"
                    f"💵 Số tiền: `{pkg['vnd']:,}đ`\n"
                    f"📝 Loại: *{pkg_type}*\n"
                    f"🕐 `{__import__('datetime').datetime.now().strftime('%H:%M %d/%m/%Y')}`"
                )
                # Gửi tới admin qua payment bot (cần chat_id admin)
                # await pay_bot.send_message(chat_id=ADMIN_CHAT_ID, text=notify_text, parse_mode="MarkdownV2")
                async with pay_bot:
                    pass  # placeholder
            except Exception as e:
                log.error(f"payment_bot notify error: {e}")

        await q.edit_message_text(
            msg_pending_confirm(pkg["label"]),
            reply_markup=kb_after_pay_confirm(),
            parse_mode="MarkdownV2"
        )
        return