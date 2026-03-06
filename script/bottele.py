import os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

# ══════════════════════════════════════════════
#  LƯU TRỮ TẠM TRONG BỘ NHỚ (không cần Supabase)
#  Lưu ý: dữ liệu sẽ mất khi Vercel restart instance
# ══════════════════════════════════════════════
users_db = {}   # uid -> {"coins": int, ...}
keys_db  = {}   # raw_key -> {"used": bool, "uid": str}

INIT_COINS    = 50
COST_IMAGE    = 10
BYPASS_REWARD = 20
WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app/").rstrip("/")

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {"uid": uid, "coins": INIT_COINS, "total_images": 0, "total_bypassed": 0}
    return users_db[uid]

def set_user(uid, patch):
    uid = str(uid)
    if uid not in users_db:
        get_user(uid)
    users_db[uid].update(patch)

def add_coins(uid, n):
    u = get_user(uid)
    u["coins"] += n
    return u["coins"]

def spend_coins(uid, n):
    u = get_user(uid)
    if u["coins"] < n:
        return False, u["coins"]
    u["coins"] -= n
    return True, u["coins"]

import uuid as _uuid

def create_key(uid):
    raw_key = str(_uuid.uuid4())
    keys_db[raw_key] = {"used": False, "uid": str(uid)}
    return raw_key

def validate_key(raw_key):
    if raw_key not in keys_db:
        return {"valid": False, "already_used": False}
    if keys_db[raw_key]["used"]:
        return {"valid": False, "already_used": True}
    return {"valid": True, "already_used": False}

def mark_key_used(raw_key):
    if raw_key in keys_db:
        keys_db[raw_key]["used"] = True

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════

def kb_main(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 So Du Xu", callback_data="balance"),
         InlineKeyboardButton("🔗 Kiem Xu",  callback_data="bypass")],
        [InlineKeyboardButton("📖 Huong Dan", callback_data="help")],
        [InlineKeyboardButton(f"━━━ 💰 Vi: {coins} xu ━━━", callback_data="noop")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]])

def kb_bypass(link, raw_key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Nhan Vao Day De Lay Key", url=link)],
        [InlineKeyboardButton("🔑 Nhap Key Nhan Xu", callback_data="key_enter")],
        [InlineKeyboardButton("🏠 Quay Lai", callback_data="home")],
    ])

def kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huy", callback_data="home")]])

# ══════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id)
    await update.message.reply_text(
        f"🌟 *BOT KIEM XU*\n\n"
        f"👋 Chao *{u.first_name}*\\!\n\n"
        f"💎 Xu cua ban: `{user['coins']} xu`\n\n"
        f"👇 Chon tinh nang:",
        reply_markup=kb_main(user["coins"]),
        parse_mode="MarkdownV2"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user
    user = get_user(u.id)

    if d == "noop":
        return

    if d == "home":
        user = get_user(u.id)
        await q.edit_message_text(
            f"🏠 *Menu Chinh*\n\n💎 Xu: `{user['coins']}`",
            reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
        )
        ctx.user_data.clear()
        return

    if d == "balance":
        await q.edit_message_text(
            f"💰 *VI XU*\n\n👤 {u.full_name}\n🆔 `{u.id}`\n\n"
            f"💎 So du: `{user['coins']} xu`\n"
            f"🔗 Link da vuot: `{user.get('total_bypassed', 0)}`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        )
        return

    if d == "bypass":
        raw_key = create_key(u.id)
        link = f"{WEB_BASE_URL}/result/{raw_key}" if WEB_BASE_URL else f"KEY: {raw_key}"
        ctx.user_data["pending_key"] = raw_key
        await q.edit_message_text(
            f"🔗 *VUOT LINK KIEM XU*\n\n"
            f"🎁 Phan thuong: `\\+{BYPASS_REWARD} xu`\n\n"
            f"1️⃣ Bam nut ben duoi\n"
            f"2️⃣ Hoan thanh cac buoc tren web\n"
            f"3️⃣ Sao chep key hien thi\n"
            f"4️⃣ Bam *Nhap Key* \\& dan vao\n\n"
            f"⚠️ Moi key chi dung duoc *1 lan*",
            reply_markup=kb_bypass(link, raw_key), parse_mode="MarkdownV2"
        )
        return

    if d == "key_enter":
        ctx.user_data["state"] = "key"
        await q.edit_message_text(
            "🔑 *NHAP KEY*\n\nDan key tu trang web vao day:",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        )
        return

    if d == "help":
        await q.edit_message_text(
            f"📖 *HUONG DAN*\n\n"
            f"🔗 *KIEM XU:*\n"
            f"• Bam Kiem Xu → vao link → hoan thanh → nhap key\n"
            f"• Moi lan thanh cong: `\\+{BYPASS_REWARD} xu`\n\n"
            f"💎 *XU DUNG DE LAM GI:*\n"
            f"• Su dung cac tinh nang tra phi cua bot",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        )
        return

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    state = ctx.user_data.get("state")
    text = update.message.text.strip()

    if state == "key":
        result = validate_key(text)
        if result["valid"]:
            mark_key_used(text)
            nb = add_coins(u.id, BYPASS_REWARD)
            set_user(u.id, {"total_bypassed": get_user(u.id).get("total_bypassed", 0) + 1})
            await update.message.reply_text(
                f"🎉 *NHAN XU THANH CONG\\!*\n\n"
                f"✅ Key hop le\\!\n"
                f"💎 Nhan duoc: `\\+{BYPASS_REWARD} xu`\n"
                f"💰 So du moi: `{nb} xu`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiem Them Xu", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu", callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        elif result["already_used"]:
            await update.message.reply_text(
                "⚠️ *Key nay da duoc su dung roi\\!*\n\nVui long lay key moi\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Lay Key Moi", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu", callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                "❌ *Key khong hop le\\!*\n\nKiem tra lai key ban sao chep\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Nhap Lai", callback_data="key_enter")],
                    [InlineKeyboardButton("🏠 Ve Menu", callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        ctx.user_data.clear()
        return

    user = get_user(u.id)
    await update.message.reply_text(
        f"👋 Xin chao *{u.first_name}*\\!\n💎 Xu: `{user['coins']}`",
        reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
    )

# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application