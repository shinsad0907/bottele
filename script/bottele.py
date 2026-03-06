import os, logging, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

users_db = {}
keys_db  = {}

INIT_COINS    = 50
BYPASS_REWARD = 20
WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app").rstrip("/")

def esc(text: str) -> str:
    """Escape ký tự đặc biệt cho MarkdownV2"""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {"uid": uid, "coins": INIT_COINS, "total_bypassed": 0}
    return users_db[uid]

def add_coins(uid, n):
    u = get_user(uid)
    u["coins"] += n
    return u["coins"]

def new_key(uid):
    k = str(uuid.uuid4())
    keys_db[k] = {"used": False, "uid": str(uid)}
    return k

def validate_key(k):
    if k not in keys_db:
        return "invalid"
    if keys_db[k]["used"]:
        return "used"
    return "valid"

def use_key(k):
    if k in keys_db:
        keys_db[k]["used"] = True

def kb_main(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 So Du Xu", callback_data="balance"),
         InlineKeyboardButton("🔗 Kiem Xu",  callback_data="bypass")],
        [InlineKeyboardButton("📖 Huong Dan", callback_data="help")],
        [InlineKeyboardButton(f"💰 Vi: {coins} xu", callback_data="noop")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]])

def kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huy", callback_data="home")]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    user = get_user(u.id)
    name = esc(u.first_name or "ban")
    await update.message.reply_text(
        f"🌟 *BOT KIEM XU*\n\n"
        f"👋 Chao *{name}*\\!\n\n"
        f"💎 Xu cua ban: `{user['coins']} xu`\n\n"
        f"👇 Chon tinh nang:",
        reply_markup=kb_main(user["coins"]),
        parse_mode="MarkdownV2"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    d    = q.data
    u    = q.from_user
    user = get_user(u.id)

    if d == "noop":
        return

    if d == "home":
        user = get_user(u.id)
        await q.edit_message_text(
            f"🏠 *Menu*\n\n💎 Xu: `{user['coins']}`",
            reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
        )
        ctx.user_data.clear()
        return

    if d == "balance":
        name = esc(u.full_name or "")
        await q.edit_message_text(
            f"💰 *VI XU*\n\n"
            f"👤 {name}\n"
            f"🆔 `{u.id}`\n\n"
            f"💎 So du: `{user['coins']} xu`\n"
            f"🔗 Da vuot: `{user.get('total_bypassed', 0)} lan`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        )
        return

    if d == "bypass":
        k    = new_key(u.id)
        link = f"{WEB_BASE_URL}/result/{k}"
        ctx.user_data["pending_key"] = k
        await q.edit_message_text(
            f"🔗 *KIEM XU QUA LINK*\n\n"
            f"🎁 Phan thuong: `\\+{BYPASS_REWARD} xu`\n\n"
            f"1️⃣ Bam nut link ben duoi\n"
            f"2️⃣ Hoan thanh cac buoc tren web\n"
            f"3️⃣ Sao chep key hien thi\n"
            f"4️⃣ Bam *Nhap Key* va dan vao\n\n"
            f"⚠️ Key chi dung duoc *1 lan*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Bam Vao Day De Lay Key", url=link)],
                [InlineKeyboardButton("🔑 Nhap Key",  callback_data="key_enter")],
                [InlineKeyboardButton("🏠 Quay Lai",  callback_data="home")],
            ]),
            parse_mode="MarkdownV2"
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
            f"🔗 Bam *Kiem Xu* → vao link → hoan thanh → nhap key\n"
            f"🎁 Moi lan thanh cong nhan `\\+{BYPASS_REWARD} xu`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        )
        return

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u     = update.effective_user
    state = ctx.user_data.get("state")
    text  = update.message.text.strip()

    if state == "key":
        status = validate_key(text)
        if status == "valid":
            use_key(text)
            nb   = add_coins(u.id, BYPASS_REWARD)
            user = get_user(u.id)
            user["total_bypassed"] = user.get("total_bypassed", 0) + 1
            await update.message.reply_text(
                f"🎉 *THANH CONG\\!*\n\n"
                f"✅ Key hop le\\!\n"
                f"💎 Nhan duoc: `\\+{BYPASS_REWARD} xu`\n"
                f"💰 So du moi: `{nb} xu`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiem Them", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu",   callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        elif status == "used":
            await update.message.reply_text(
                "⚠️ *Key da duoc su dung roi\\!*\n\nVui long lay key moi\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Lay Key Moi", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu",     callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                "❌ *Key khong hop le\\!*\n\nKiem tra lai key ban sao chep\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Nhap Lai", callback_data="key_enter")],
                    [InlineKeyboardButton("🏠 Ve Menu",  callback_data="home")],
                ]),
                parse_mode="MarkdownV2"
            )
        ctx.user_data.clear()
        return

    user = get_user(u.id)
    name = esc(u.first_name or "ban")
    await update.message.reply_text(
        f"👋 Xin chao *{name}*\\!\n💎 Xu: `{user['coins']}`",
        reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
    )

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application
