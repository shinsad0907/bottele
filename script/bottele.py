import os, logging, uuid, random, string, asyncio, time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-lilac.vercel.app").rstrip("/")
INIT_COINS    = 1000000000000000000000000000000000000
BYPASS_REWARD = 20
COST_IMAGE    = 10

FIREBASE_KEY = "AIzaSyDkChmbBT5DiK0HNTA8Ffx8NJq7reWkS6I"
TEMP_DOMAINS = ["getmule.com", "fivemail.com", "vomoto.com", "mailnull.com"]
FIREBASE_HDR = {
    'accept': '*/*', 'content-type': 'application/json',
    'origin': 'https://undresswith.ai',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'x-browser-channel': 'stable',
    'x-browser-copyright': 'Copyright 2026 Google LLC. All Rights reserved.',
    'x-browser-validation': 'aSLd2f09Ia/YwdnAvb1HwCexgog=',
    'x-browser-year': '2026',
    'x-client-data': 'CI+2yQEIpLbJAQipncoBCOr9ygEIlKHLAQiFoM0B',
    'x-client-version': 'Chrome/JsCore/11.0.1/FirebaseCore-web',
    'x-firebase-gmpid': '1:453358396684:web:3d416bb1f03907914e1529',
}
API_HDR = {
    'accept': '*/*', 'content-type': 'application/json',
    'origin': 'https://undresswith.ai', 'referer': 'https://undresswith.ai/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# ══════════════════════════════════════════════
#  RAM DB — dùng global dict thay ctx.user_data
#  vì Vercel serverless reset ctx mỗi request
# ══════════════════════════════════════════════
users_db    = {}   # uid -> {coins, ...}
keys_db     = {}   # key -> {used, uid}
sessions_db = {}   # uid -> {state, photo_id, ...}

def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {"uid": uid, "coins": INIT_COINS, "total_bypassed": 0, "total_images": 0}
    return users_db[uid]

def add_coins(uid, n):
    u = get_user(uid); u["coins"] += n; return u["coins"]

def spend_coins(uid, n):
    u = get_user(uid)
    if u["coins"] < n: return False, u["coins"]
    u["coins"] -= n; return True, u["coins"]

def get_session(uid):
    uid = str(uid)
    if uid not in sessions_db:
        sessions_db[uid] = {}
    return sessions_db[uid]

def clear_session(uid):
    sessions_db[str(uid)] = {}

def new_key(uid):
    k = str(uuid.uuid4())
    keys_db[k] = {"used": False, "uid": str(uid)}
    return k

def validate_key(k):
    if k not in keys_db: return "invalid"
    if keys_db[k]["used"]: return "used"
    return "valid"

def use_key(k):
    if k in keys_db: keys_db[k]["used"] = True

# ══════════════════════════════════════════════
#  AI IMAGE API
# ══════════════════════════════════════════════
def random_email():
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{rnd}@{random.choice(TEMP_DOMAINS)}"

def create_account():
    email = random_email()
    r = requests.post(
        'https://identitytoolkit.googleapis.com/v1/accounts:signUp',
        params={'key': FIREBASE_KEY}, headers=FIREBASE_HDR,
        json={'returnSecureToken': True, 'email': email, 'password': email, 'clientType': 'CLIENT_TYPE_WEB'},
        timeout=15
    ).json()
    if 'idToken' not in r:
        raise Exception(f"Firebase loi: {r.get('error',{}).get('message', str(r))}")
    r2 = requests.post(
        'https://sv.aivideo123.site/api/user/init_data', headers=API_HDR,
        json={'token': r['idToken'], 'code': '-1', 'login_type': 0, 'current_uid': ''},
        timeout=15
    ).json()
    if r2.get('code') != 1:
        raise Exception(f"init_data loi: {r2}")
    return email, r2['data']['session_token']

def generate_image(image_bytes: bytes, filename: str, prompt: str) -> bytes:
    email, token = create_account()
    log.info(f"[AI] Account: {email}")
    headers = {**API_HDR, "x-session-token": token}

    r = requests.post("https://sv.aivideo123.site/api/item/get_pre_url",
        headers=headers, json={"file_name": filename, "file_type": 0}, timeout=15).json()
    if r["code"] != 1: raise Exception("get_pre_url that bai")
    s3_url = r["data"]["url"]; fields = r["data"]["fields"]; s3_key = fields["key"]

    up = requests.post(s3_url, data=fields,
        files={"file": (filename, image_bytes, "image/jpeg")}, timeout=30)
    if up.status_code not in [200, 201, 204]:
        raise Exception(f"Upload loi {up.status_code}")

    inf = requests.post("https://sv.aivideo123.site/api/item/inference2",
        headers=headers,
        json={"s3_path": s3_key, "mask_path": "", "prompt": prompt, "ai_model_type": 3},
        timeout=15).json()
    if inf["code"] != 1: raise Exception("Inference that bai")
    item_uid  = inf["data"]["item"]["uid"]
    time_need = inf["data"]["item"]["time_need"]
    log.info(f"[AI] Waiting {time_need}s...")
    time.sleep(time_need)

    r2 = requests.post("https://sv.aivideo123.site/api/item/get_items",
        headers=headers, json={"page": 0, "page_size": 50}, timeout=15).json()
    result_url = ""
    for item in r2["data"]["items"]:
        if item["uid"] == item_uid:
            result_url = item.get("thumbnail", ""); break
    if not result_url: raise Exception("Khong tim thay ket qua")

    img_resp = requests.get(result_url, timeout=20)
    return img_resp.content

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════
def kb_main(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Tao Anh AI", callback_data="img_start")],
        [InlineKeyboardButton("💎 So Du Xu",   callback_data="balance"),
         InlineKeyboardButton("🔗 Kiem Xu",    callback_data="bypass")],
        [InlineKeyboardButton("📖 Huong Dan",  callback_data="help")],
        [InlineKeyboardButton(f"💰 Vi: {coins} xu", callback_data="noop")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]])

def kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huy", callback_data="home")]])

# ══════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    user = get_user(u.id)
    clear_session(u.id)
    await update.message.reply_text(
        f"🌟 *AI IMAGE BOT*\n\n"
        f"👋 Chao *{esc(u.first_name or 'ban')}*\\!\n\n"
        f"💎 Xu cua ban: `{user['coins']} xu`\n"
        f"🎨 Chi phi tao anh: `{COST_IMAGE} xu / lan`\n\n"
        f"👇 Chon tinh nang:",
        reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    d    = q.data
    u    = q.from_user
    user = get_user(u.id)
    sess = get_session(u.id)

    if d == "noop": return

    if d == "home":
        clear_session(u.id)
        user = get_user(u.id)
        await q.edit_message_text(
            f"🏠 *Menu*\n\n💎 Xu: `{user['coins']}`",
            reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
        ); return

    if d == "balance":
        await q.edit_message_text(
            f"💰 *VI XU*\n\n👤 {esc(u.full_name or '')}\n🆔 `{u.id}`\n\n"
            f"💎 So du: `{user['coins']} xu`\n"
            f"🎨 Anh da tao: `{user.get('total_images',0)}`\n"
            f"🔗 Da vuot: `{user.get('total_bypassed',0)} lan`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    if d == "bypass":
        k    = new_key(u.id)
        link = f"{WEB_BASE_URL}/result/{k}"
        sess["pending_key"] = k
        await q.edit_message_text(
            f"🔗 *KIEM XU QUA LINK*\n\n"
            f"🎁 Phan thuong: `\\+{BYPASS_REWARD} xu`\n\n"
            f"1️⃣ Bam nut link ben duoi\n2️⃣ Hoan thanh tren web\n"
            f"3️⃣ Sao chep key\n4️⃣ Bam *Nhap Key* va dan vao\n\n"
            f"⚠️ Key chi dung *1 lan*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Bam Vao Day De Lay Key", url=link)],
                [InlineKeyboardButton("🔑 Nhap Key",  callback_data="key_enter")],
                [InlineKeyboardButton("🏠 Quay Lai",  callback_data="home")],
            ]), parse_mode="MarkdownV2"
        ); return

    if d == "key_enter":
        sess["state"] = "key"
        await q.edit_message_text(
            "🔑 *NHAP KEY*\n\nDan key tu trang web vao day:",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "img_start":
        if user["coins"] < COST_IMAGE:
            await q.edit_message_text(
                f"❌ *Khong du xu\\!*\n\nCan `{COST_IMAGE} xu` \\| Co `{user['coins']} xu`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiem Xu Ngay", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu",      callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_photo"
        await q.edit_message_text(
            f"🎨 *TAO ANH AI*\n\n"
            f"💎 So du: `{user['coins']} xu` \\| Chi phi: `{COST_IMAGE} xu`\n\n"
            f"📸 *Buoc 1:* Gui anh cua ban vao day\n"
            f"_\\(gui truc tiep, khong phai file\\)_",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "help":
        await q.edit_message_text(
            f"📖 *HUONG DAN*\n\n"
            f"🎨 *TAO ANH AI:*\n• Bam Tao Anh AI → gui anh → nhap prompt\n"
            f"• Chi phi: `{COST_IMAGE} xu` moi lan\n\n"
            f"🔗 *KIEM XU:*\n• Bam Kiem Xu → vao link → nhap key\n"
            f"• Moi lan: `\\+{BYPASS_REWARD} xu`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    sess = get_session(u.id)
    if sess.get("state") != "wait_photo":
        return
    photo = update.message.photo[-1]
    sess["photo_id"]   = photo.file_id
    sess["photo_name"] = f"photo_{photo.file_id[:8]}.jpg"
    sess["state"]      = "wait_prompt"
    await update.message.reply_text(
        "✅ *Da nhan anh\\!*\n\n"
        "✏️ *Buoc 2:* Nhap prompt \\(mo ta muon chinh anh nhu the nao\\)\n\n"
        "Vi du:\n"
        "`wear a red summer dress`\n"
        "`wearing a suit, professional`\n"
        "`anime style outfit`",
        reply_markup=kb_cancel(), parse_mode="MarkdownV2"
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    sess = get_session(u.id)
    state = sess.get("state")
    text  = update.message.text.strip()

    # ── Nhập key bypass ──
    if state == "key":
        status = validate_key(text)
        if status == "valid":
            use_key(text)
            nb   = add_coins(u.id, BYPASS_REWARD)
            user = get_user(u.id)
            user["total_bypassed"] = user.get("total_bypassed", 0) + 1
            await update.message.reply_text(
                f"🎉 *THANH CONG\\!*\n\n✅ Key hop le\\!\n"
                f"💎 Nhan duoc: `\\+{BYPASS_REWARD} xu`\n"
                f"💰 So du moi: `{nb} xu`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎨 Tao Anh Ngay", callback_data="img_start")],
                    [InlineKeyboardButton("🔗 Kiem Them",    callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu",      callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        elif status == "used":
            await update.message.reply_text(
                "⚠️ *Key da duoc su dung roi\\!*",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Lay Key Moi", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu",     callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                "❌ *Key khong hop le\\!*\n\nKiem tra lai key ban sao chep\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Nhap Lai", callback_data="key_enter")],
                    [InlineKeyboardButton("🏠 Ve Menu",  callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        clear_session(u.id); return

    # ── Nhập prompt tạo ảnh ──
    if state == "wait_prompt":
        photo_id   = sess.get("photo_id")
        photo_name = sess.get("photo_name", "photo.jpg")
        prompt     = text

        if not photo_id:
            await update.message.reply_text("❌ Khong tim thay anh\\. Gui lai anh nhe\\!", parse_mode="MarkdownV2")
            clear_session(u.id); return

        ok, new_bal = spend_coins(u.id, COST_IMAGE)
        if not ok:
            await update.message.reply_text(
                f"❌ *Khong du xu\\!* Can `{COST_IMAGE}` \\| Co `{new_bal}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiem Xu", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Ve Menu", callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        msg = await update.message.reply_text(
            f"⏳ *DANG XU LY\\.\\.\\.*\n\n"
            f"📝 Prompt: `{esc(prompt[:60])}`\n\n"
            f"📥 Dang tai anh\\.\\.\\.",
            parse_mode="MarkdownV2"
        )
        clear_session(u.id)

        try:
            photo_file  = await update.get_bot().get_file(photo_id)
            photo_bytes = await photo_file.download_as_bytearray()

            await msg.edit_text(
                f"⏳ *DANG XU LY\\.\\.\\.*\n\n"
                f"📝 Prompt: `{esc(prompt[:60])}`\n\n"
                f"🔑 Dang tao tai khoan AI\\.\\.\\.",
                parse_mode="MarkdownV2"
            )

            loop = asyncio.get_event_loop()
            result_bytes = await loop.run_in_executor(
                None, generate_image, bytes(photo_bytes), photo_name, prompt
            )

            await msg.edit_text(
                f"⏳ *DANG XU LY\\.\\.\\.*\n\n"
                f"📝 Prompt: `{esc(prompt[:60])}`\n\n"
                f"📤 Dang gui ket qua\\.\\.\\.",
                parse_mode="MarkdownV2"
            )

            user = get_user(u.id)
            user["total_images"] = user.get("total_images", 0) + 1

            await update.message.reply_photo(
                photo=result_bytes,
                caption=(
                    f"✨ *KET QUA TAO ANH AI*\n\n"
                    f"📝 `{esc(prompt[:80])}`\n\n"
                    f"💎 Con lai: `{new_bal} xu`"
                ),
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎨 Tao Anh Moi",   callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Ve Menu Chinh", callback_data="home")],
                ])
            )
            await msg.delete()

        except Exception as e:
            add_coins(u.id, COST_IMAGE)
            log.error(f"Generate error: {e}")
            await msg.edit_text(
                f"❌ *Co loi xay ra\\!*\n\nDa hoan lai `{COST_IMAGE} xu`\n\n"
                f"Loi: `{esc(str(e)[:100])}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thu Lai",  callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Ve Menu",  callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        return

    # ── Tin nhắn thường ──
    user = get_user(u.id)
    await update.message.reply_text(
        f"👋 Xin chao *{esc(u.first_name or 'ban')}*\\!\n💎 Xu: `{user['coins']}`",
        reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
    )

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


