import os, base64, logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import anthropic
from script.create_key import KeyManager

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
WEB_BASE_URL      = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app/").rstrip("/")

COST_IMAGE    = 10
BYPASS_REWARD = 20
INIT_COINS    = 50

km = KeyManager()

def get_user(uid):
    res = km.client.table("bot_users").select("*").eq("uid", str(uid)).limit(1).execute()
    if res.data:
        return res.data[0]
    new_user = {"uid": str(uid), "coins": INIT_COINS, "total_images": 0, "total_bypassed": 0, "joined": datetime.now().isoformat()}
    km.client.table("bot_users").insert(new_user).execute()
    return new_user

def set_user(uid, patch):
    km.client.table("bot_users").update(patch).eq("uid", str(uid)).execute()

def add_coins(uid, n):
    u = get_user(uid); nb = u["coins"] + n
    set_user(uid, {"coins": nb}); return nb

def spend_coins(uid, n):
    u = get_user(uid)
    if u["coins"] < n: return False, u["coins"]
    nb = u["coins"] - n; set_user(uid, {"coins": nb}); return True, nb

PRESET_PROMPTS = [
    ("🌸 Anime",      "Chuyen thanh nhan vat anime phong cach Studio Ghibli"),
    ("🌆 Cyberpunk",  "Them hieu ung cyberpunk, anh den neon xanh tim"),
    ("🎨 Son Dau",    "Ve lai theo phong cach tranh son dau co dien"),
    ("✨ Fantasy",    "Bien thanh nhan vat the gioi fantasy, phep thuat"),
    ("📸 Studio",     "Chinh sua nhu anh chup studio chuyen nghiep"),
    ("🌊 Watercolor", "Ve lai bang mau nuoc, net mem mai"),
    ("🔥 Dragon Ball","Phong cach Dragon Ball Z, aura nang luong"),
    ("🌙 Lo-fi",      "Phong cach lo-fi aesthetic, mau toi am"),
]

def kb_main(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨✨ TAO ANH AI ✨🎨", callback_data="img_start")],
        [InlineKeyboardButton("💎 So Du Xu", callback_data="balance"), InlineKeyboardButton("🔗 Kiem Xu", callback_data="bypass")],
        [InlineKeyboardButton("📊 Thong Ke", callback_data="stats"), InlineKeyboardButton("📖 Huong Dan", callback_data="help")],
        [InlineKeyboardButton(f"━━━ 💰 Vi: {coins} xu ━━━", callback_data="noop")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ve Menu Chinh", callback_data="home")]])

def kb_prompts():
    rows = []
    for i in range(0, len(PRESET_PROMPTS), 2):
        row = [InlineKeyboardButton(PRESET_PROMPTS[i][0], callback_data=f"preset_{i}")]
        if i + 1 < len(PRESET_PROMPTS):
            row.append(InlineKeyboardButton(PRESET_PROMPTS[i+1][0], callback_data=f"preset_{i+1}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("✏️ Tu Nhap Prompt", callback_data="custom_prompt")])
    rows.append([InlineKeyboardButton("🔄 Doi Anh Khac", callback_data="img_upload")])
    rows.append([InlineKeyboardButton("🏠 Quay Lai", callback_data="home")])
    return InlineKeyboardMarkup(rows)

def kb_bypass(link):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Nhan Vao Day Lay Key", url=link)],
        [InlineKeyboardButton("🔑 Nhap Key Nhan Xu", callback_data="key_enter")],
        [InlineKeyboardButton("🏠 Quay Lai", callback_data="home")],
    ])

def kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huy Bo", callback_data="home")]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id)
    set_user(u.id, {"username": u.username or "", "full_name": u.full_name or ""})
    await update.message.reply_text(
        f"🌟 *AI IMAGE BOT*\n\n👋 Chao *{u.first_name}*\\!\n\n💎 Xu cua ban: `{user['coins']} xu`\n🎨 Chi phi tao anh: `{COST_IMAGE} xu / lan`\n\n👇 Chon tinh nang:",
        reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data; u = q.from_user; user = get_user(u.id)

    if d == "noop": return
    if d == "home":
        user = get_user(u.id)
        await q.edit_message_text(f"🏠 *Menu Chinh*\n\n💎 Xu: `{user['coins']}`", reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2")
        ctx.user_data.clear(); return
    if d == "balance":
        await q.edit_message_text(
            f"💰 *VI XU*\n\n👤 {u.full_name}\n🆔 `{u.id}`\n\n💎 So du: `{user['coins']} xu`\n🎨 Anh da tao: `{user.get('total_images',0)}`\n🔗 Link da vuot: `{user.get('total_bypassed',0)}`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"); return
    if d == "bypass":
        result = km.get_or_create_key(user=str(u.id), ip=str(u.id), full_url=WEB_BASE_URL)
        await q.edit_message_text(
            f"🔗 *VUOT LINK KIEM XU*\n\n🎁 Phan thuong: `\\+{BYPASS_REWARD} xu`\n\n📋 Cach lam:\n1️⃣ Bam nut ben duoi\n2️⃣ Hoan thanh cac buoc tren web\n3️⃣ Sao chep key hien thi\n4️⃣ Bam *Nhap Key* \\& dan vao\n\n⚠️ Moi key chi dung duoc *1 lan*",
            reply_markup=kb_bypass(result["link_key"]), parse_mode="MarkdownV2"); return
    if d == "key_enter":
        ctx.user_data["state"] = "key"
        await q.edit_message_text("🔑 *NHAP KEY*\n\nDan UUID key tu trang web:\n\n✏️ Gui key vao day:", reply_markup=kb_cancel(), parse_mode="MarkdownV2"); return
    if d == "stats":
        res = km.client.table("ppapikey").select("key,used").execute()
        rows = res.data or []; total_k = len(rows); used_k = sum(1 for r in rows if r.get("used"))
        res2 = km.client.table("bot_users").select("uid").execute(); total_u = len(res2.data or [])
        await q.edit_message_text(
            f"📊 *THONG KE BOT*\n\n👥 Tong thanh vien: *{total_u}*\n🔑 Key da tao: *{total_k}*\n✅ Key da dung: *{used_k}*\n\n👤 *Ban:*\n├ 💎 Xu: `{user['coins']}`\n├ 🎨 Anh tao: `{user.get('total_images',0)}`\n└ 🔗 Link vuot: `{user.get('total_bypassed',0)}`",
            reply_markup=kb_back(), parse_mode="MarkdownV2"); return
    if d == "help":
        await q.edit_message_text(
            f"📖 *HUONG DAN SU DUNG*\n\n🎨 *TAO ANH AI:*\n• Ton `{COST_IMAGE} xu` moi lan\n• Gui anh → Chon phong cach → Nhan ket qua\n\n🔗 *VUOT LINK KIEM XU:*\n• Moi lan vuot thanh cong: `\\+{BYPASS_REWARD} xu`\n• Lam theo huong dan → Nhap key → Nhan xu",
            reply_markup=kb_back(), parse_mode="MarkdownV2"); return
    if d == "img_start":
        await q.edit_message_text(
            f"🎨 *TAO ANH AI*\n\n💎 So du: `{user['coins']} xu` \\| Chi phi: `{COST_IMAGE} xu`\n\n📸 Buoc 1: Gui anh\n🎨 Buoc 2: Chon phong cach\n✨ Buoc 3: Nhan ket qua\\!\n\n👇 Nhan nut ben duoi:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📸 Gui Anh De Tao", callback_data="img_upload")],[InlineKeyboardButton("🏠 Quay Lai", callback_data="home")]]),
            parse_mode="MarkdownV2"); return
    if d == "img_upload":
        if user["coins"] < COST_IMAGE:
            await q.edit_message_text(f"❌ *Khong du xu\\!*\n\nCan `{COST_IMAGE} xu` \\| Co `{user['coins']} xu`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Vuot Link Kiem Xu", callback_data="bypass")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]),
                parse_mode="MarkdownV2"); return
        ctx.user_data["state"] = "wait_photo"
        await q.edit_message_text("📸 *GUI ANH CUA BAN*\n\n• Gui truc tiep \\(khong phai file\\)\n• Anh ro net → ket qua dep hon\n\n📲 Gui anh vao day:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ve Menu Chinh", callback_data="home")]]), parse_mode="MarkdownV2"); return
    if d.startswith("preset_"):
        idx = int(d.split("_")[1]); _, prompt = PRESET_PROMPTS[idx]
        ctx.user_data["prompt"] = prompt; ctx.user_data["state"] = "generating"
        await _generate(q, ctx, u); return
    if d == "custom_prompt":
        ctx.user_data["state"] = "wait_custom_prompt"
        await q.edit_message_text("✏️ *NHAP PROMPT CUA BAN*\n\nVi du: `Bien thanh phu thuy, ao choang tim`\n\n✏️ Nhap prompt:", reply_markup=kb_cancel(), parse_mode="MarkdownV2"); return

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("state") != "wait_photo": return
    photo = update.message.photo[-1]
    ctx.user_data["photo_id"] = photo.file_id; ctx.user_data["state"] = "wait_prompt_choice"
    await update.message.reply_text("✅ *DA NHAN ANH\\!*\n\n🎨 Chon phong cach AI:", reply_markup=kb_prompts(), parse_mode="MarkdownV2")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; state = ctx.user_data.get("state"); text = update.message.text.strip()
    if state == "key":
        result = km.validate_key(text)
        if result["valid"]:
            km.mark_key_used(text); nb = add_coins(u.id, BYPASS_REWARD)
            set_user(u.id, {"total_bypassed": get_user(u.id).get("total_bypassed", 0) + 1})
            await update.message.reply_text(f"🎉 *NHAN XU THANH CONG\\!*\n\n✅ Key hop le\\!\n💎 Nhan duoc: `\\+{BYPASS_REWARD} xu`\n💰 So du moi: `{nb} xu`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Tao Anh Ngay\\!", callback_data="img_start")],[InlineKeyboardButton("🔗 Vuot Them Link", callback_data="bypass")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]),
                parse_mode="MarkdownV2")
        elif result["already_used"]:
            await update.message.reply_text("⚠️ *Key nay da duoc su dung roi\\!*\n\nVui long lay key moi\\.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Lay Key Moi", callback_data="bypass")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]), parse_mode="MarkdownV2")
        else:
            await update.message.reply_text("❌ *Key khong ton tai\\!*\n\nKiem tra lai key ban sao chep\\.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔑 Nhap Lai", callback_data="key_enter")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]), parse_mode="MarkdownV2")
        ctx.user_data.clear(); return
    if state == "wait_custom_prompt":
        ctx.user_data["prompt"] = text; ctx.user_data["state"] = "generating"
        await _generate_from_msg(update, ctx, u); return
    user = get_user(u.id)
    await update.message.reply_text(f"👋 Xin chao *{u.first_name}*\\!\n💎 Xu: `{user['coins']}`", reply_markup=kb_main(user["coins"]), parse_mode="MarkdownV2")

async def _generate(q, ctx, u):
    photo_id = ctx.user_data.get("photo_id"); prompt = ctx.user_data.get("prompt", "")
    if not photo_id:
        await q.edit_message_text("❌ Khong tim thay anh\\. Vui long bat dau lai\\.", reply_markup=kb_back(), parse_mode="MarkdownV2"); return
    ok, new_bal = spend_coins(u.id, COST_IMAGE)
    if not ok:
        await q.edit_message_text(f"❌ *Khong du xu\\!*\n\nCan `{COST_IMAGE}` \\| Co `{new_bal}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Vuot Link", callback_data="bypass")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]), parse_mode="MarkdownV2"); return
    await q.edit_message_text(f"⏳ *DANG TAO ANH AI\\.\\.\\.*\n\nDa tru `{COST_IMAGE} xu` \\| Con: `{new_bal} xu`", parse_mode="MarkdownV2")
    try:
        photo_file = await q.get_bot().get_file(photo_id)
        photo_bytes = await photo_file.download_as_bytearray()
        img_b64 = base64.standard_b64encode(bytes(photo_bytes)).decode()
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": f'Nguoi dung muon: "{prompt}"\nFormat:\nPROMPT: ...\nMO TA: ...\nTIPS: ...'}
            ]}])
        ai_text = resp.content[0].text
        set_user(u.id, {"total_images": get_user(u.id).get("total_images", 0) + 1})
        ctx.user_data.clear()
        await q.get_bot().send_photo(chat_id=q.message.chat_id, photo=photo_id,
            caption=f"✨ *KET QUA TAO ANH AI*\n\n🎨 {prompt[:60]}\n\n{ai_text}\n\n💎 Con lai: `{new_bal} xu`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Tao Anh Moi", callback_data="img_start")],[InlineKeyboardButton("🏠 Ve Menu Chinh", callback_data="home")]]))
        await q.delete_message()
    except Exception as e:
        add_coins(u.id, COST_IMAGE); log.error(f"Generate error: {e}")
        await q.edit_message_text(f"❌ *Co loi xay ra\\!*\n\nDa hoan xu\\.\n`{str(e)[:80]}`", reply_markup=kb_back(), parse_mode="MarkdownV2")

async def _generate_from_msg(update: Update, ctx, u):
    photo_id = ctx.user_data.get("photo_id"); prompt = ctx.user_data.get("prompt", "")
    if not photo_id:
        await update.message.reply_text("❌ Khong tim thay anh\\. Gui lai anh nhe\\!", reply_markup=kb_back(), parse_mode="MarkdownV2"); return
    ok, new_bal = spend_coins(u.id, COST_IMAGE)
    if not ok:
        await update.message.reply_text(f"❌ Khong du xu\\! Can `{COST_IMAGE}` \\| Co `{new_bal}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Vuot Link", callback_data="bypass")],[InlineKeyboardButton("🏠 Ve Menu", callback_data="home")]]), parse_mode="MarkdownV2"); return
    proc = await update.message.reply_text(f"⏳ *Dang tao anh AI\\.\\.\\.*\nDa tru `{COST_IMAGE} xu` \\| Con: `{new_bal} xu`", parse_mode="MarkdownV2")
    try:
        photo_file = await update.get_bot().get_file(photo_id)
        photo_bytes = await photo_file.download_as_bytearray()
        img_b64 = base64.standard_b64encode(bytes(photo_bytes)).decode()
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": f'Nguoi dung muon: "{prompt}"\nPROMPT: ...\nMO TA: ...\nTIPS: ...'}
            ]}])
        ai_text = resp.content[0].text
        set_user(u.id, {"total_images": get_user(u.id).get("total_images", 0) + 1})
        ctx.user_data.clear(); await proc.delete()
        await update.message.reply_photo(photo=photo_id,
            caption=f"✨ *KET QUA*\n\n🎨 {prompt[:60]}\n\n{ai_text}\n\n💎 Con lai: `{new_bal} xu`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Tao Anh Moi", callback_data="img_start")],[InlineKeyboardButton("🏠 Ve Menu Chinh", callback_data="home")]]))
    except Exception as e:
        add_coins(u.id, COST_IMAGE); log.error(f"Generate error: {e}")
        await proc.edit_text(f"❌ *Loi\\!* Da hoan xu\\.\n`{str(e)[:80]}`", reply_markup=kb_back(), parse_mode="MarkdownV2")

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application