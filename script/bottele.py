import os, logging, uuid, random, string, asyncio, time
import requests, re, json, base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from script.database       import (
    get_or_create_user, get_user, update_user_field,
    add_coins as db_add_coins, spend_coins as db_spend_coins,
    inc_image_count, inc_video_count, inc_proxy,
    set_package, record_payment,
    do_rollcall, ROLLCALL_REWARD, ROLLCALL_BY_PKG,
    admin_add_coins, admin_set_package, get_user_by_username,
)
from script.queue_manager  import enter_queue, leave_queue
from script.payment_handler import (
    handle_payment_callback,
    handle_payment_photo,
    kb_payment_menu, msg_payment_menu,
    msg_pending_confirm, kb_after_pay_confirm,
    COIN_MAP, VIP_MAP,
)
from script.create_key import KeyManager


log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app").rstrip("/")
COST_IMAGE    = 20
COST_VIDEO    = 35

REQUIRED_CHANNEL     = "@ClothessAI"
REQUIRED_CHANNEL_URL = "https://t.me/ClothessAI"

# Admin duy nhất
ADMIN_USERNAME = "shadowbotnet99"   # không có @

# ══════════════════════════════════════════════
#  CHANNEL GATE
# ══════════════════════════════════════════════
async def check_join(bot_instance, user_id: int) -> bool:
    try:
        member = await bot_instance.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        log.warning(f"check_join error: {e}")
        return False

async def send_join_prompt(reply_fn):
    text = (
        "```\n╔══════════════════════════════════════╗\n"
        "║  🔒  CLOTHESBOT  ·  YÊU CẦU  🔒     ║\n"
        "╚══════════════════════════════════════╝\n```\n\n"
        "⚠️ *BẠN CHƯA THAM GIA CHANNEL\\!*\n\n"
        "1️⃣ Bấm nút bên dưới\n2️⃣ Join channel\n3️⃣ Quay lại bấm /start"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👗 Tham Gia Channel Ngay!", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Đã Join → Bắt Đầu",     callback_data="check_join")],
    ])
    await reply_fn(text, reply_markup=kb, parse_mode="MarkdownV2")

# ══════════════════════════════════════════════
#  FIREBASE / IMAGE / VIDEO APIs
# ══════════════════════════════════════════════
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
PIKA_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
MAILTM  = "https://api.mail.tm"

# ══════════════════════════════════════════════
#  RAM SESSION DB
# ══════════════════════════════════════════════
sessions_db: dict = {}
keys_db:     dict = {}

def get_session(uid):
    uid = str(uid)
    if uid not in sessions_db:
        sessions_db[uid] = {}
    return sessions_db[uid]

def clear_session(uid):
    uid = str(uid)
    preserved = {}
    if uid in sessions_db:
        for key in ("last_image_bytes", "last_image_name"):
            if key in sessions_db[uid]:
                preserved[key] = sessions_db[uid][key]
    sessions_db[uid] = preserved

def full_clear_session(uid):
    sessions_db[str(uid)] = {}

# ══════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════
INIT_COINS = 100

IMG_ICONS = ["👗","✨","🎨","💫","🌀","⚡","🔮","🧵"]
VID_ICONS = ["🎬","👗","✨","🌀","🎞️","💫","⚡","🎥"]
SPINNER   = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
PROGRESS_BLOCKS = [
    "░░░░░░░░░░","█░░░░░░░░░","██░░░░░░░░","███░░░░░░░",
    "████░░░░░░","█████░░░░░","██████░░░░","███████░░░",
    "████████░░","█████████░","██████████"
]

def progress_bar(step, total=10):
    idx = min(int(step/total*10), 10)
    return f"{PROGRESS_BLOCKS[idx]} {int(step/total*100)}%"

def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def coin_bar(coins, max_coins=500):
    filled = min(int(coins/max_coins*10), 10)
    return f"[{'█'*filled}{'░'*(10-filled)}]"

def rank_badge(coins):
    if coins >= 2000: return "👑 LEGEND"
    if coins >= 1000: return "💎 DIAMOND"
    if coins >= 500:  return "🥇 GOLD"
    if coins >= 200:  return "🥈 SILVER"
    return "🥉 BRONZE"

def pkg_badge(package: str) -> str:
    return {"vip": "👑 VIP", "vip_pro": "💎 VIP PRO"}.get(package, "🆓 FREE")

def render_log_step(step, total_steps, lines, eta="", tick=0):
    bar  = progress_bar(step, total_steps)
    icon = IMG_ICONS[tick % len(IMG_ICONS)]
    spin = SPINNER[tick % len(SPINNER)]
    body = "\n".join(lines[-12:])
    eta_line = f"\n  {spin} ETA: {eta}" if eta else ""
    return (f"```\n╔══ {icon} CLOTHESBOT · PROCESSING {icon} ══╗\n"
            f"║  {bar}\n╠══════════════════════════════════════╣\n"
            f"{body}\n╚══════════════════════════════════════╝{eta_line}\n```")

def render_video_log(step, total_steps, lines, eta="", tick=0):
    bar  = progress_bar(step, total_steps)
    icon = VID_ICONS[tick % len(VID_ICONS)]
    spin = SPINNER[tick % len(SPINNER)]
    body = "\n".join(lines[-12:])
    eta_line = f"\n  {spin} ETA: {eta}" if eta else ""
    return (f"```\n╔══ {icon} CLOTHESBOT · RENDERING {icon} ══╗\n"
            f"║  {bar}\n╠══════════════════════════════════════╣\n"
            f"{body}\n╚══════════════════════════════════════╝{eta_line}\n```")

BANNER_SUCCESS = "╔══════════════════════════════════════╗\n║  ✅  CLOTHESBOT  ·  SUCCESS  ✅     ║\n╠══════════════════════════════════════╣"
BANNER_ERROR   = "╔══════════════════════════════════════╗\n║  ⚠️   CLOTHESBOT  ·  ERROR   ⚠️    ║\n╠══════════════════════════════════════╣"
BANNER_WALLET  = "╔══════════════════════════════════════╗\n║  💎  CLOTHESBOT  ·  WALLET  💎      ║\n╠══════════════════════════════════════╣"

# ══════════════════════════════════════════════
#  SPLASH
# ══════════════════════════════════════════════
SPLASH_F1 = """```
╔══════════════════════════════════════╗
║       [ ĐANG KHỞI ĐỘNG... ]          ║
╚══════════════════════════════════════╝
```"""
SPLASH_F2 = """```
╔══════════════════════════════════════╗
║  ✨  C L O T H E S B O T  ✨        ║
║  ▓▓▓▓▓▓▓░░░░░░░░░░░░░░  ⚡ LOADING  ║
╚══════════════════════════════════════╝
```"""
SPLASH_F3 = """```
╔══════════════════════════════════════╗
║  ██████╗██╗      ██████╗ ████████╗  ║
║ ██╔════╝██║     ██╔═══██╗╚══██╔══╝  ║
║ ██║     ██║     ██║   ██║   ██║     ║
║ ╚██████╗███████╗╚██████╔╝   ██║     ║
║  ╚═════╝╚══════╝ ╚═════╝    ╚═╝     ║
║   👗  H E S B O T  ·  STUDIO  👗   ║
╚══════════════════════════════════════╝
```"""

def splash_final(name, coins, total_images, total_videos=0, package="free", roll_called=False):
    bar   = coin_bar(coins)
    badge = rank_badge(coins)
    pkg   = pkg_badge(package)
    pkg_rc_reward = ROLLCALL_BY_PKG.get(package, 300)
    rc_status = "✅ Đã điểm danh hôm nay" if roll_called else f"🎁 Chưa điểm danh \\(\\+{pkg_rc_reward} xu\\)"
    return (
        "```\n╔══════════════════════════════════════╗\n"
        "║    ██████╗██╗      ██████╗ ████████╗ ║\n"
        "║   ██╔════╝██║     ██╔═══██╗╚══██╔══╝ ║\n"
        "║   ██║     ██║     ██║   ██║   ██║    ║\n"
        "║   ╚██████╗███████╗╚██████╔╝   ██║    ║\n"
        "║    ╚═════╝╚══════╝ ╚═════╝    ╚═╝    ║\n"
        "║    👗  H E S B O T  ·  STUDIO  👗    ║\n"
        "╚══════════════════════════════════════╝\n```\n\n"
        f"👋 Xin chào, *{esc(name)}*\\!\n\n"
        f"┌─ 📊 *THÔNG TIN TÀI KHOẢN* ──┐\n"
        f"│  {badge}  ·  {pkg}\n"
        f"│  💰 Xu: `{coins}` {bar}\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}`\n"
        f"│  🎬 Video đã tạo: `{total_videos}`\n"
        f"│  📅 {rc_status}\n"
        f"└────────────────────────────────┘\n\n"
        f"⚡ Chi phí tạo ảnh: `{COST_IMAGE} xu / lần`\n"
        f"🎬 Chi phí tạo video: `{COST_VIDEO} xu / lần`\n"
        f"📅 Điểm danh hàng ngày: `+{ROLLCALL_REWARD} xu`\n\n"
        f"👇 *Chọn tính năng bên dưới:*"
    )

async def animated_splash(message_obj, tg_user, user_db: dict):
    m = await message_obj.reply_text(SPLASH_F1, parse_mode="Markdown")
    await asyncio.sleep(0.55)
    try: await m.edit_text(SPLASH_F2, parse_mode="Markdown")
    except: pass
    await asyncio.sleep(0.55)
    try: await m.edit_text(SPLASH_F3, parse_mode="Markdown")
    except: pass
    await asyncio.sleep(0.65)
    final = splash_final(
        tg_user.first_name or "bạn",
        user_db.get("coin", INIT_COINS),
        user_db.get("number_create_image", 0),
        user_db.get("number_create_video", 0),
        user_db.get("package", "free"),
        user_db.get("roll_call", False),
    )
    try:
        await m.edit_text(
            final,
            reply_markup=kb_main(user_db.get("coin", INIT_COINS), user_db.get("package","free"), user_db.get("roll_call", False)),
            parse_mode="MarkdownV2"
        )
    except: pass
    return m

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════
def kb_main(coins, package="free", roll_called=False):
    badge     = rank_badge(coins)
    pkg       = pkg_badge(package)
    pkg_rc_reward = ROLLCALL_BY_PKG.get(package, 300)
    rc_label  = "✅ Đã Điểm Danh" if roll_called else f"📅 Điểm Danh (+{pkg_rc_reward}xu)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton("🎨 ✨  TẠO ẢNH  ✨ 🎨",     callback_data="img_start")],
        [InlineKeyboardButton("🎬 ✨  TẠO VIDEO  ✨ 🎬",    callback_data="vid_start")],
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton("💎 Ví Xu",                   callback_data="balance"),
         InlineKeyboardButton(rc_label,                     callback_data="rollcall")],
        [InlineKeyboardButton("💳 Mua Xu / VIP",            callback_data="pay_menu")],
        [InlineKeyboardButton("🔗 Vượt link lấy xu?",             callback_data="external_link")],
        [InlineKeyboardButton("📊 Thống Kê",                callback_data="stats"),
         InlineKeyboardButton("📖 Hướng Dẫn",               callback_data="help")],
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton(f"{badge} · {pkg}  |  💰 {coins} xu", callback_data="balance")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️  Quay Về Menu", callback_data="home")]])

def kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌  Hủy Thao Tác", callback_data="home")]])

def kb_after_image(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 ✨ Tạo Video Từ Ảnh Này!", callback_data="vid_from_last_image")],
        [InlineKeyboardButton("🎨 Tạo Ảnh Mới",             callback_data="img_start"),
         InlineKeyboardButton("🏠 Menu Chính",               callback_data="home")],
        [InlineKeyboardButton(f"💰 Còn lại: {coins} xu",     callback_data="balance")],
    ])

def kb_after_video(coins):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Tạo Video Mới",  callback_data="vid_start"),
         InlineKeyboardButton("🎨 Tạo Ảnh Mới",   callback_data="img_start")],
        [InlineKeyboardButton("🏠 Menu Chính",     callback_data="home")],
        [InlineKeyboardButton(f"💰 Còn lại: {coins} xu", callback_data="balance")],
    ])

# ══════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════
def msg_balance(full_name, uid, coins, total_images, total_videos=0, package="free"):
    bar   = coin_bar(coins)
    badge = rank_badge(coins)
    pkg   = pkg_badge(package)
    spent = total_images * COST_IMAGE + total_videos * COST_VIDEO
    return (
        f"```\n{BANNER_WALLET}\n```\n\n"
        f"👤 *{esc(full_name or 'User')}*\n🆔 ID: `{uid}`\n\n"
        f"┌─ 💎 *SỐ DƯ* ────────────────┐\n"
        f"│  {badge}  ·  {pkg}\n"
        f"│  💰 Xu hiện có: `{coins} xu`\n"
        f"│  {bar}\n└──────────────────────────────┘\n\n"
        f"┌─ 📈 *LỊCH SỬ* ──────────────┐\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}` lần\n"
        f"│  🎬 Video đã tạo: `{total_videos}` lần\n"
        f"│  💸 Đã chi:       `{spent} xu`\n"
        f"└──────────────────────────────┘"
    )

def msg_stats(uid, coins, total_images, total_videos=0, package="free"):
    badge = rank_badge(coins)
    pkg   = pkg_badge(package)
    spent = total_images * COST_IMAGE + total_videos * COST_VIDEO
    return (
        f"📊 *CLOTHESBOT · THỐNG KÊ*\n\n"
        f"🆔 ID: `{uid}`\n🏆 Hạng: *{badge}*  ·  {pkg}\n\n"
        f"┌─ 💰 *COINS* ─────────────────┐\n"
        f"│  Hiện có:   `{coins} xu`\n│  {coin_bar(coins)}\n"
        f"│  Đã tiêu:   `{spent} xu`\n└──────────────────────────────┘\n\n"
        f"┌─ 👗 *HOẠT ĐỘNG* ─────────────┐\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}` lần\n"
        f"│  🎬 Video đã tạo: `{total_videos}` lần\n"
        f"└──────────────────────────────┘"
    )

def msg_help():
    return (
        "📖 *CLOTHESBOT · HƯỚNG DẪN*\n\n"
        f"🎨 ✨ *TẠO ẢNH* · `{COST_IMAGE} xu/lần`\n"
        "1\\. Bấm `🎨 ✨ Tạo Ảnh`\n2\\. Gửi ảnh gốc\n3\\. Nhập prompt \\(EN\\)\n4\\. Đợi ~20\\-40 giây\n\n"
        f"🎬 ✨ *TẠO VIDEO* · `{COST_VIDEO} xu/lần`\n"
        "1\\. Bấm `🎬 ✨ Tạo Video`\n2\\. Gửi ảnh\n3\\. Nhập mô tả chuyển động\n4\\. Đợi ~2\\-5 phút\n\n"
        "📅 *ĐIỂM DANH HÀNG NGÀY*\n"
        "```\n"
        "  Gói FREE    → +300 xu/ngày\n"
        "  Gói VIP     → +1.500 xu/ngày\n"
        "  Gói VIP PRE → +5.000 xu/ngày\n"
        "```\n"
        "Reset lúc 00:00 giờ Việt Nam\n\n"
        "💰 *GÓI MUA XU*\n"
        "```\n"
        "   20k  →  1.000 xu  (50 anh / 33 vid)\n"
        "   50k  →  3.000 xu  (150 anh / 100 vid)\n"
        "  100k  →  7.000 xu  (350 anh / 233 vid)\n"
        "  200k  → 16.000 xu  (800 anh / 533 vid)\n"
        "```\n\n"
        "💳 *MUA VIP*\n"
        "Bấm `💳 Mua Xu / VIP` → chọn gói → CK → gửi bill\n"
        "Admin duyệt trong 5\\-15 phút\\."
    )

# ══════════════════════════════════════════════
#  IMAGE API
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
        raise Exception(f"Firebase error: {r.get('error',{}).get('message', str(r))}")
    r2 = requests.post(
        'https://sv.aivideo123.site/api/user/init_data', headers=API_HDR,
        json={'token': r['idToken'], 'code': '-1', 'login_type': 0, 'current_uid': ''},
        timeout=15
    ).json()
    if r2.get('code') != 1:
        raise Exception(f"init_data error: {r2}")
    return email, r2['data']['session_token']

def generate_image(image_bytes, filename, prompt, log_cb=None):
    lines = []; step_counter = [0]
    def push(line, step_inc=1):
        lines.append(line); step_counter[0] = min(step_counter[0]+step_inc, 9)
        if log_cb:
            try: log_cb(list(lines), step_counter[0])
            except: pass
    push(f"  ◈ Target  : {filename[:22]}", 0)
    push(f"  ◈ Prompt  : {prompt[:28]}...", 0)
    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  [01/07] 🔐 Initializing engine...")
    email, token = create_account()
    push(f"  [02/07] ✅ Auth OK → {email[:20]}")
    headers = {**API_HDR, "x-session-token": token}
    push(f"  [03/07] 📡 Requesting upload slot...")
    r = requests.post("https://sv.aivideo123.site/api/item/get_pre_url",
        headers=headers, json={"file_name": filename, "file_type": 0}, timeout=15).json()
    if r["code"] != 1: raise Exception("get_pre_url failed")
    s3_url = r["data"]["url"]; fields = r["data"]["fields"]; s3_key = fields["key"]
    push(f"  [03/07] ✅ Upload slot secured!")
    push(f"  [04/07] 📤 Uploading {len(image_bytes)//1024} KB...")
    up = requests.post(s3_url, data=fields,
        files={"file": (filename, image_bytes, "image/jpeg")}, timeout=30)
    if up.status_code not in [200, 201, 204]: raise Exception(f"Upload failed {up.status_code}")
    push(f"  [04/07] ✅ HTTP {up.status_code} — Upload accepted!")
    push(f"  [05/07] 👗 ✨ Processing outfit...")
    inf = requests.post("https://sv.aivideo123.site/api/item/inference2",
        headers=headers,
        json={"s3_path": s3_key, "mask_path": "", "prompt": prompt, "ai_model_type": 3},
        timeout=15).json()
    if inf["code"] != 1: raise Exception("Inference failed")
    item_uid  = inf["data"]["item"]["uid"]
    time_need = inf["data"]["item"]["time_need"]
    push(f"  [05/07] ✅ Job queued! ETA: {time_need}s")
    push(f"  [06/07] ✨ Styling... please wait")
    time.sleep(time_need)
    push(f"  [07/07] 📥 Fetching result...")
    r2 = requests.post("https://sv.aivideo123.site/api/item/get_items",
        headers=headers, json={"page": 0, "page_size": 50}, timeout=15).json()
    result_url = ""
    for item in r2["data"]["items"]:
        if item["uid"] == item_uid:
            result_url = item.get("thumbnail",""); break
    if not result_url: raise Exception("Result not found")
    push(f"  [07/07] ✅ Result URL ready!")
    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  ✨ Downloading final image...", 0)
    img_resp = requests.get(result_url, timeout=20)
    push(f"  🎉 CLOTHESBOT · COMPLETE!", 0)
    return img_resp.content

# ══════════════════════════════════════════════
#  VIDEO API
# ══════════════════════════════════════════════
def _mailtm_create_account():
    domain = requests.get(f"{MAILTM}/domains", timeout=10).json()["hydra:member"][0]["domain"]
    u = ''.join(random.choices(string.ascii_lowercase+string.digits, k=12))
    p = ''.join(random.choices(string.ascii_letters+string.digits, k=14))
    email = f"{u}@{domain}"
    r = requests.post(f"{MAILTM}/accounts", json={"address":email,"password":p}, timeout=10)
    if r.status_code not in (200,201): raise Exception("Tạo email tạm thất bại")
    tok = requests.post(f"{MAILTM}/token", json={"address":email,"password":p}, timeout=10).json()
    if "token" not in tok: raise Exception("Đăng nhập email tạm thất bại")
    return {"email":email,"password":p,"token":tok["token"]}

def _mailtm_poll_pika(token, timeout=120, interval=6):
    seen, deadline = set(), time.time()+timeout
    hdrs = {"Authorization":f"Bearer {token}"}
    while time.time()<deadline:
        for m in requests.get(f"{MAILTM}/messages",headers=hdrs,timeout=10).json().get("hydra:member",[]):
            if m["id"] in seen: continue
            seen.add(m["id"])
            if "pika" in m.get("from",{}).get("address","").lower() or "pika" in m.get("subject","").lower():
                return requests.get(f"{MAILTM}/messages/{m['id']}",headers=hdrs,timeout=10).json()
        time.sleep(interval)
    return None

def _extract_verify_link(msg):
    pat = r'https://login\.pika\.art/auth/v1/verify\?[^\s\]\)\'"<>]+'
    html = msg.get("html","")
    if isinstance(html,list): html="\n".join(html)
    for src in [msg.get("text",""), html]:
        m = re.search(pat, src)
        if m: return m.group(0).replace("&amp;","&")
    return None

def _pika_signup(sess, email, password, username):
    page = sess.get("https://pika.art/signup", timeout=15)
    m = re.search(r'"([0-9a-f]{40})"', page.text)
    ah = m.group(1) if m else "4045d309671c08e4d71fe9aff61638cf00467c081f"
    sess.post("https://pika.art/signup",
        headers={"accept":"text/x-component","next-action":ah,
                 "next-router-state-tree":("%5B%22%22%2C%7B%22children%22%3A%5B%22(entry)%22%2C%7B%22children%22%3A%5B%22signup%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Ctrue%5D"),
                 "origin":"https://pika.art","referer":"https://pika.art/signup"},
        files={"1_name":(None,username),"1_email":(None,email),"1_password":(None,password),"0":(None,'["$K1"]')},
        allow_redirects=False, timeout=20)

def _pika_login(email, password):
    sess = requests.Session()
    sess.headers.update({"user-agent":PIKA_UA,"accept-language":"vi-VN,vi;q=0.9,en;q=0.5"})
    page = sess.get("https://pika.art/login", timeout=15)
    m = re.search(r'"([0-9a-f]{40})"', page.text)
    ah = m.group(1) if m else "409cc0dec0398e3142f0f16c994ca8915680346831"
    resp = sess.post("https://pika.art/login",
        headers={"accept":"text/x-component","next-action":ah,
                 "next-router-state-tree":("%5B%22%22%2C%7B%22children%22%3A%5B%22(entry)%22%2C%7B%22children%22%3A%5B%22login%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D"),
                 "origin":"https://pika.art","referer":"https://pika.art/login"},
        files={"1_email":(None,email),"1_password":(None,password),"1_to":(None,"/"),"0":(None,'["$K1"]')},
        allow_redirects=True, timeout=20)
    sb_cookie = None
    for c in sess.cookies:
        if "sb-login-auth-token" in c.name: sb_cookie=c.value; break
    if not sb_cookie:
        for r_hist in resp.history:
            sc = r_hist.headers.get("set-cookie","")
            if "sb-login-auth-token" in sc:
                for part in sc.split(";"):
                    if "sb-login-auth-token" in part:
                        sb_cookie=part.split("=",1)[-1].strip(); break
            if sb_cookie: break
    if not sb_cookie: return {}
    try:
        raw = sb_cookie[7:] if sb_cookie.startswith("base64-") else sb_cookie
        padded = raw+"="*(-len(raw)%4)
        decoded = json.loads(base64.b64decode(padded).decode())
        return {"access_token":decoded.get("access_token",""),"user_id":decoded.get("user",{}).get("id",""),"sb_cookie":sb_cookie}
    except: return {}

def _detect_mime(b, filename):
    if b[:8]==b'\x89PNG\r\n\x1a\n': return "image/png"
    if b[:3]==b'\xff\xd8\xff': return "image/jpeg"
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(ext,"image/jpeg")

def _pika_generate_job(access_token, user_id, image_bytes, image_filename,
                       prompt="gentle movement", model="2.5", duration=5, resolution="480p"):
    mime = _detect_mime(image_bytes, image_filename)
    options = json.dumps({"frameRate":24,"camera":{},"parameters":{"guidanceScale":12,"motion":1,"negativePrompt":""},"extend":False})
    resp = requests.post("https://api.pika.art/generate/v2",
        headers={"accept":"*/*","authorization":f"Bearer {access_token}","origin":"https://pika.art","referer":"https://pika.art/","user-agent":PIKA_UA},
        files={"resolution":(None,resolution),"promptText":(None,prompt),"image":(image_filename,image_bytes,mime),
               "duration":(None,str(duration)),"model":(None,model),"contentType":(None,"i2v"),"options":(None,options),
               "creditCost":(None,"12"),"userId":(None,user_id)},
        timeout=60)
    data = resp.json()
    if data.get("success")==False: raise Exception(data.get("error","Unknown error"))
    job_id = (data.get("id") or data.get("jobId") or data.get("data",{}).get("id") or data.get("data",{}).get("generation",{}).get("id"))
    if not job_id: raise Exception("Không nhận được Job ID")
    return str(job_id)

def _pika_poll_video(access_token, sb_cookie, job_id, timeout=300, interval=10):
    lib_hash = "4011bb5085d98313ee4cb9f6c1e0e4f1323144af54"
    cookie_str = (sb_cookie if sb_cookie.startswith("sb-login-auth-token=") else f"sb-login-auth-token={sb_cookie}")
    deadline = time.time()+timeout
    while time.time()<deadline:
        try:
            resp = requests.post("https://pika.art/library",
                headers={"accept":"text/x-component","accept-language":"vi-VN,vi;q=0.9,en;q=0.5","content-type":"text/plain;charset=UTF-8",
                         "next-action":lib_hash,"next-router-state-tree":("%5B%22%22%2C%7B%22children%22%3A%5B%22(dashboard)%22%2C%7B%22children%22%3A%5B%22library%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Ctrue%5D"),
                         "origin":"https://pika.art","referer":"https://pika.art/library","user-agent":PIKA_UA,"cookie":cookie_str},
                data=json.dumps([{"ids":[job_id]}]), timeout=20)
            if resp.status_code==200:
                raw = resp.text
                for line in raw.split("\n"):
                    line=line.strip()
                    if not line: continue
                    if re.match(r'^\d+:',line):
                        payload=line.split(":",1)[1]
                        try:
                            obj=json.loads(payload)
                            if obj.get("success") and "data" in obj:
                                for result in obj["data"].get("results",[]):
                                    for video in result.get("videos",[]):
                                        url=(video.get("resultUrl") or video.get("sharingUrl") or video.get("url"))
                                        if url and url.endswith(".mp4"): return url
                                    url=result.get("resultUrl") or result.get("videoUrl")
                                    if url and url.endswith(".mp4"): return url
                        except: pass
                for pat in [r'"resultUrl"\s*:\s*"(https://[^"]+\.mp4)"',r'"sharingUrl"\s*:\s*"(https://[^"]+\.mp4)"']:
                    m=re.search(pat,raw)
                    if m: return m.group(1)
                m=re.search(r'"status"\s*:\s*"([^"]+)"',raw)
                if m and m.group(1) in ("failed","error","cancelled"): raise Exception(f"Job thất bại: {m.group(1)}")
        except Exception as e:
            if "thất bại" in str(e): raise
        time.sleep(interval)
    raise Exception(f"Quá thời gian {timeout}s, video chưa hoàn thành")

def pika_create_account_and_generate(image_bytes, filename, prompt="gentle movement", log_cb=None):
    lines=[]; step_c=[0]
    def push(line, step_inc=1):
        lines.append(line); step_c[0]=min(step_c[0]+step_inc,9)
        if log_cb:
            try: log_cb(list(lines),step_c[0])
            except: pass
    push(f"  ◈ Prompt : {prompt[:30]}",0); push(f"  ◈ Output : 🎬 480p | ⏱ 5 giây",0); push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",0)
    push(f"  [01/06] 📧 Tạo email tạm..."); mt=_mailtm_create_account(); push(f"  [01/06] ✅ Email: {mt['email'][:25]}")
    push(f"  [02/06] 🔧 Khởi tạo phiên xử lý...")
    rnd_name=''.join(random.choices(string.ascii_lowercase,k=8)); pika_pass=''.join(random.choices(string.ascii_letters+string.digits,k=10))+"Aa1!"
    sess=requests.Session(); sess.headers.update({"user-agent":PIKA_UA}); _pika_signup(sess,mt["email"],pika_pass,rnd_name)
    push(f"  [02/06] ✅ Đã gửi yêu cầu đăng ký")
    push(f"  [03/06] 📨 Chờ email xác nhận..."); msg=_mailtm_poll_pika(mt["token"],timeout=120,interval=6)
    if not msg: raise Exception("Không nhận được email xác nhận")
    verify_url=_extract_verify_link(msg)
    if not verify_url: raise Exception("Không tìm thấy link xác nhận")
    vr=requests.Session(); vr.headers.update({"user-agent":PIKA_UA}); vr.get(verify_url,allow_redirects=True,timeout=20)
    push(f"  [03/06] ✅ Xác nhận email OK")
    push(f"  [04/06] 🔐 Xác thực hệ thống..."); lr=_pika_login(mt["email"],pika_pass)
    if not lr.get("access_token"): raise Exception("Xác thực thất bại")
    push(f"  [04/06] ✅ Xác thực thành công!")
    push(f"  [05/06] 🎬 Gửi yêu cầu render..."); job_id=_pika_generate_job(lr["access_token"],lr["user_id"],image_bytes,filename,prompt=prompt)
    push(f"  [05/06] ✅ Job ID: {job_id[:8]}...")
    push(f"  [06/06] ⏳ Đang render (~2-5 phút)..."); time.sleep(20)
    video_url=_pika_poll_video(lr["access_token"],lr["sb_cookie"],job_id,timeout=300,interval=10)
    push(f"  [06/06] ✅ 🎬 Video sẵn sàng!"); push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",0); push(f"  📥 Đang tải video về...",0)
    vresp=requests.get(video_url,timeout=180,stream=True); video_bytes=b"".join(vresp.iter_content(chunk_size=8192))
    push(f"  ✅ {len(video_bytes)//1024} KB — 🎉 Hoàn tất!",0)
    return video_bytes, video_url

# ══════════════════════════════════════════════
#  ADMIN COMMANDS (chỉ @shadowbotnet99)
# ══════════════════════════════════════════════

def is_admin(u) -> bool:
    return (u.username or "").lower() == ADMIN_USERNAME.lower()

async def cmd_addcoins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u):
        await update.message.reply_text("⛔ Bạn không có quyền dùng lệnh này.")
        return
    # /addcoins @username <số xu>
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("❌ Cú pháp: `/addcoins @username <số xu>`", parse_mode="MarkdownV2")
        return
    target = args[0].lstrip("@")
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Số xu phải là số nguyên.")
        return

    ok, new_coin = admin_add_coins(target, amount)
    if ok:
        await update.message.reply_text(
            f"✅ Đã thêm `{amount}` xu cho `@{esc(target)}`\\.\n"
            f"💰 Số dư mới: `{new_coin}` xu",
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(f"❌ Không tìm thấy user `@{esc(target)}`\\.", parse_mode="MarkdownV2")

async def cmd_setpackage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u):
        await update.message.reply_text("⛔ Bạn không có quyền dùng lệnh này.")
        return
    # /setpackage @username free|vip|vip_pro
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("❌ Cú pháp: `/setpackage @username free|vip|vip_pro`", parse_mode="MarkdownV2")
        return
    target  = args[0].lstrip("@")
    package = args[1].lower()
    if package not in ("free", "vip", "vip_pro"):
        await update.message.reply_text("❌ Package hợp lệ: `free`, `vip`, `vip_pro`", parse_mode="MarkdownV2")
        return

    ok = admin_set_package(target, package)
    if ok:
        pkg_label = {"free":"🆓 FREE","vip":"👑 VIP","vip_pro":"💎 VIP PRO"}.get(package, package)
        await update.message.reply_text(
            f"✅ Đã cập nhật gói `@{esc(target)}` → *{pkg_label}*",
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(f"❌ Không tìm thấy user `@{esc(target)}`\\.", parse_mode="MarkdownV2")

async def cmd_userinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u):
        await update.message.reply_text("⛔ Bạn không có quyền dùng lệnh này.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("❌ Cú pháp: `/userinfo @username`", parse_mode="MarkdownV2")
        return
    target = args[0].lstrip("@")
    data   = get_user_by_username(target)
    if not data:
        await update.message.reply_text(f"❌ Không tìm thấy `@{esc(target)}`\\.", parse_mode="MarkdownV2")
        return
    pkg   = pkg_badge(data.get("package","free"))
    badge = rank_badge(data.get("coin",0))
    await update.message.reply_text(
        f"👤 *@{esc(target)}*\n"
        f"🆔 ID: `{data.get('id_user','')}`\n"
        f"💰 Xu: `{data.get('coin',0)}`\n"
        f"🏆 {badge}  ·  {pkg}\n"
        f"🎨 Ảnh: `{data.get('number_create_image',0)}`\n"
        f"🎬 Video: `{data.get('number_create_video',0)}`\n"
        f"📅 Roll call: `{data.get('roll_call',False)}`",
        parse_mode="MarkdownV2"
    )

# ══════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(lambda text, **kw: update.message.reply_text(text, **kw))
        return
    user_db = get_or_create_user(str(u.id), u.username or "")
    full_clear_session(u.id)
    await animated_splash(update.message, u, user_db)


async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user

    if d == "noop": return

    # ── Check join ──
    if d == "check_join":
        if await check_join(ctx.bot, u.id):
            user_db = get_or_create_user(str(u.id), u.username or "")
            full_clear_session(u.id)
            await q.edit_message_text(
                splash_final(u.first_name or "bạn",
                             user_db.get("coin", INIT_COINS),
                             user_db.get("number_create_image", 0),
                             user_db.get("number_create_video", 0),
                             user_db.get("package", "free"),
                             user_db.get("roll_call", False)),
                reply_markup=kb_main(user_db.get("coin", INIT_COINS), user_db.get("package","free"), user_db.get("roll_call", False)),
                parse_mode="MarkdownV2"
            )
        else:
            await q.answer("❌ Bạn chưa join channel! Hãy join rồi thử lại.", show_alert=True)
        return

    # ── Channel gate ──
    if not await check_join(ctx.bot, u.id):
        await q.answer("⚠️ Bạn cần join channel để dùng bot!", show_alert=True)
        return

    user_db = get_or_create_user(str(u.id), u.username or "")
    sess    = get_session(u.id)
    coins   = user_db.get("coin", INIT_COINS)
    package = user_db.get("package", "free")

    # ── PAYMENT callbacks ──
    if d in ("pay_menu","pay_coin_menu","pay_vip_menu") or \
       d.startswith("pay_buy_") or d.startswith("pay_sendphoto_"):
        await handle_payment_callback(d, q, u, user_db, sessions_db)
        return

    # ── Home ──
    if d == "home":
        full_clear_session(u.id)
        user_db = get_or_create_user(str(u.id), u.username or "")
        coins   = user_db.get("coin", INIT_COINS)
        await q.edit_message_text(
            splash_final(u.first_name or "bạn", coins,
                         user_db.get("number_create_image",0),
                         user_db.get("number_create_video",0),
                         user_db.get("package","free"),
                         user_db.get("roll_call", False)),
            reply_markup=kb_main(coins, user_db.get("package","free"), user_db.get("roll_call", False)),
            parse_mode="MarkdownV2"
        ); return

    # ── Balance ──
    if d == "balance":
        await q.edit_message_text(
            msg_balance(u.full_name or "", u.id, coins,
                        user_db.get("number_create_image",0),
                        user_db.get("number_create_video",0),
                        package),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    # ── Stats ──
    if d == "stats":
        await q.edit_message_text(
            msg_stats(u.id, coins,
                      user_db.get("number_create_image",0),
                      user_db.get("number_create_video",0),
                      package),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    # ── Help ──
    if d == "help":
        await q.edit_message_text(msg_help(), reply_markup=kb_back(), parse_mode="MarkdownV2"); return

    # ── Roll Call (Điểm danh) ──
    if d == "rollcall":
        success, new_coin, reward = do_rollcall(str(u.id))
        if success:
            pkg_label = {"free": "🆓 FREE", "vip": "👑 VIP", "vip_pro": "💎 VIP PRE"}.get(package, "FREE")
            await q.edit_message_text(
                f"```\n{BANNER_SUCCESS}\n```\n\n"
                f"📅 *ĐIỂM DANH THÀNH CÔNG\\!*\n\n"
                f"```\n  🏷  Gói:        {pkg_label}\n  🎁 Nhận được:  +{reward} xu\n  💰 Số dư mới:  {new_coin} xu\n```\n\n"
                f"✅ Quay lại lúc 00:00 ngày mai để điểm danh tiếp\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎨 Tạo Ảnh Ngay!", callback_data="img_start"),
                     InlineKeyboardButton("🎬 Tạo Video!",    callback_data="vid_start")],
                    [InlineKeyboardButton("🏠 Menu",          callback_data="home")],
                    [InlineKeyboardButton(f"💰 Số dư: {new_coin} xu", callback_data="balance")],
                ]),
                parse_mode="MarkdownV2"
            )
        else:
            pkg_reward = ROLLCALL_BY_PKG.get(package, 300)
            await q.answer(f"✅ Đã điểm danh hôm nay rồi! (+{pkg_reward} xu mỗi ngày)", show_alert=True)
        return

    # ── Start Image ──
    if d == "img_start":
        if coins < COST_IMAGE:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n  Cần:    {COST_IMAGE} xu\n  Có:     {coins} xu\n  Thiếu:  {COST_IMAGE-coins} xu\n```\n\n"
                f"💳 Mua xu ngay hoặc điểm danh nhận xu miễn phí\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳  Mua Xu →",              callback_data="pay_menu")],
                    [InlineKeyboardButton("📅  Điểm Danh \\(\\+100xu\\)", callback_data="rollcall")],
                    [InlineKeyboardButton("◀️  Quay Về Menu",            callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_photo"
        sess.pop("photo_id", None); sess.pop("photo_name", None)
        await q.edit_message_text(
            f"🎨 ✨ *TẠO ẢNH*\n\n"
            f"```\n  💰 Số dư:   {coins} xu\n  💸 Chi phí: {COST_IMAGE} xu / lần\n  📊 Sau khi: {coins-COST_IMAGE} xu\n```\n\n"
            f"📸 *BƯỚC 1 / 2* — Gửi ảnh bạn muốn chỉnh sửa:",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    # ── Start Video ──
    if d == "vid_start":
        if coins < COST_VIDEO:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n  Cần:    {COST_VIDEO} xu\n  Có:     {coins} xu\n```\n\n💳 Mua xu để tạo video\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳  Mua Xu →",          callback_data="pay_menu")],
                    [InlineKeyboardButton("📅  Điểm Danh",         callback_data="rollcall")],
                    [InlineKeyboardButton("◀️  Quay Về Menu",        callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_video_photo"
        sess.pop("video_photo_id",None); sess.pop("video_photo_bytes",None); sess.pop("video_photo_name",None)
        await q.edit_message_text(
            f"🎬 ✨ *TẠO VIDEO*\n\n"
            f"```\n  💰 Số dư:   {coins} xu\n  💸 Chi phí: {COST_VIDEO} xu / lần\n  🎞️  Output:  480p | 5 giây\n```\n\n"
            f"📸 *BƯỚC 1 / 2* — Gửi ảnh bạn muốn chuyển thành video:",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    # ── Video từ ảnh vừa tạo ──
    if d == "vid_from_last_image":
        last_img  = sess.get("last_image_bytes")
        last_name = sess.get("last_image_name","image.jpg")
        if not last_img:
            await q.edit_message_text(
                "❌ Không tìm thấy ảnh vừa tạo\\. Vui lòng tạo ảnh trước\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎨 ✨ Tạo Ảnh", callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Menu",       callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        if coins < COST_VIDEO:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n```\n  Cần:    {COST_VIDEO} xu\n  Có:     {coins} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Mua Xu",  callback_data="pay_menu")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"]             = "wait_video_prompt"
        sess["video_photo_bytes"] = last_img
        sess["video_photo_name"]  = last_name
        await q.edit_message_text(
            f"🎬 ✨ *TẠO VIDEO TỪ ẢNH VỪA TẠO*\n\n"
            f"```\n  💸 Chi phí: {COST_VIDEO} xu\n  📊 Sau khi: {coins-COST_VIDEO} xu\n  🎞️  Output:  480p | 5 giây\n```\n\n"
            f"✏️ *BƯỚC 2 / 2 — Nhập mô tả chuyển động:*\n\n"
            f"💡 `gentle swaying motion`\n`hair blowing in the wind`\n`slow zoom in, cinematic`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "external_link":
        # u.id
        id_key = KeyManager(str(u.id)).get_key()
        link = f"{WEB_BASE_URL}/getkey?user_id={id_key}"

        sess["state"] = "wait_key"

        await q.edit_message_text(
            "🔑 *NHẬN XU BẰNG KEY*\n\n"
            "```\n"
            "  Bước 1: Vượt link bên dưới\n"
            "  Bước 2: Lấy KEY\n"
            "  Bước 3: Dán KEY vào bot \n"
            "```\n\n"
            "🎁 Phần thưởng: `+20 xu`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Lấy KEY", url=link)],
                [InlineKeyboardButton("❌ Huỷ", callback_data="home")]
            ]),
            parse_mode="MarkdownV2"
        )
        return
# ══════════════════════════════════════════════
#  PHOTO HANDLER
# ══════════════════════════════════════════════
async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(lambda text, **kw: update.message.reply_text(text, **kw))
        return
    sess  = get_session(u.id)
    state = sess.get("state")
    photo = update.message.photo[-1]

    # ── Ảnh chuyển khoản thanh toán ──
    if state == "wait_payment_photo":
        success, label = await handle_payment_photo(photo.file_id, u, sessions_db, bot=update.get_bot())
        if success:
            await update.message.reply_text(
                msg_pending_confirm(label),
                reply_markup=kb_after_pay_confirm(),
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                "❌ Có lỗi xảy ra\\. Vui lòng thử lại hoặc liên hệ admin\\.",
                parse_mode="MarkdownV2"
            )
        return

    if state == "wait_photo":
        sess["photo_id"]   = photo.file_id
        sess["photo_name"] = f"photo_{photo.file_id[:8]}.jpg"
        sess["state"]      = "wait_prompt"
        await update.message.reply_text(
            "✅ *ĐÃ NHẬN ẢNH\\!*\n\n"
            "✏️ *BƯỚC 2 / 2* — Nhập mô tả bạn muốn hệ thống thực hiện:\n\n"
            "💡 `wear a red summer dress`\n`wearing a suit, professional`\n`anime style, colorful outfit`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if state == "wait_video_photo":
        sess["video_photo_id"]   = photo.file_id
        sess["video_photo_name"] = f"video_{photo.file_id[:8]}.jpg"
        sess["state"]            = "wait_video_prompt"
        await update.message.reply_text(
            "✅ *ĐÃ NHẬN ẢNH\\!*\n\n"
            "✏️ *BƯỚC 2 / 2 — Mô tả chuyển động:*\n\n"
            "💡 `gentle swaying motion`\n`hair blowing in the wind`\n`slow zoom in, cinematic`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return



# ══════════════════════════════════════════════
#  TEXT HANDLER
# ══════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(lambda text, **kw: update.message.reply_text(text, **kw))
        return
    sess  = get_session(u.id)
    state = sess.get("state")
    text  = update.message.text.strip()
    user_db = get_or_create_user(str(u.id), u.username or "")
    coins   = user_db.get("coin", INIT_COINS)
    package = user_db.get("package","free")

    # ── Prompt tạo ảnh ──
    if state == "wait_prompt":
        photo_id   = sess.get("photo_id")
        photo_name = sess.get("photo_name","photo.jpg")
        prompt     = text
        if not photo_id:
            await update.message.reply_text("❌ Không tìm thấy ảnh\\. Vui lòng gửi lại ảnh\\!", parse_mode="MarkdownV2")
            clear_session(u.id); return

        ok_spend, new_bal = db_spend_coins(str(u.id), COST_IMAGE)
        if not ok_spend:
            await update.message.reply_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\nCần `{COST_IMAGE}` xu \\| Có `{new_bal}` xu",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Mua Xu",        callback_data="pay_menu")],
                    [InlineKeyboardButton("📅 Điểm Danh",     callback_data="rollcall")],
                    [InlineKeyboardButton("🏠 Menu",          callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        tick_counter = [0]
        msg = await update.message.reply_text(
            render_log_step(0, 9, ["  ⏳ Khởi động CLOTHESBOT...", f"  📝 Prompt: {prompt[:35]}"], "~30-40s", tick=0),
            parse_mode="Markdown"
        )

        _photo_id   = photo_id
        _photo_name = photo_name
        clear_session(u.id)

        import queue as _queue
        log_queue = _queue.Queue()
        def log_cb_q(lines, step=0): log_queue.put((list(lines), step))

        async def updater():
            while True:
                try:
                    lines, step = log_queue.get_nowait()
                    tick_counter[0] += 1
                    try:
                        await msg.edit_text(render_log_step(step, 9, lines, "...", tick=tick_counter[0]), parse_mode="Markdown")
                    except: pass
                except _queue.Empty: pass
                await asyncio.sleep(1.5)

        if package == "free":
            queue_msg = await update.message.reply_text("⏳ Đang kiểm tra hàng chờ\\.\\.\\.", parse_mode="MarkdownV2")
            async def queue_status_cb(status_text, pos):
                try: await queue_msg.edit_text(status_text, parse_mode="MarkdownV2")
                except: pass
            entered = await enter_queue(str(u.id), package, queue_status_cb)
            if not entered:
                await queue_msg.edit_text("❌ Hàng chờ quá tải\\. Vui lòng thử lại sau\\!", parse_mode="MarkdownV2")
                db_add_coins(str(u.id), COST_IMAGE)
                return
            try: await queue_msg.delete()
            except: pass

        loop = asyncio.get_event_loop()
        updater_task = asyncio.ensure_future(updater())

        try:
            photo_file  = await update.get_bot().get_file(_photo_id)
            photo_bytes = await photo_file.download_as_bytearray()
            log_cb_q(["  ✅ Ảnh đã tải xong!","  👗 Đang phân tích trang phục..."], 1)
            result_bytes = await loop.run_in_executor(None, generate_image, bytes(photo_bytes), _photo_name, prompt, log_cb_q)
        except Exception as e:
            updater_task.cancel()
            if package == "free": leave_queue(str(u.id))
            db_add_coins(str(u.id), COST_IMAGE)
            await msg.edit_text(
                f"```\n{BANNER_ERROR}\n```\n\n❌ *XỬ LÝ THẤT BẠI*\n\n"
                f"```\n  Lỗi: {str(e)[:55]}\n  💰 Đã hoàn lại: {COST_IMAGE} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thử Lại", callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="Markdown"
            )
            return

        updater_task.cancel()
        if package == "free": leave_queue(str(u.id))
        inc_image_count(str(u.id))

        fresh_sess = get_session(u.id)
        fresh_sess["last_image_bytes"] = result_bytes
        fresh_sess["last_image_name"]  = _photo_name

        await update.message.reply_photo(
            photo   = result_bytes,
            caption = (
                f"✨ *CLOTHESBOT · KẾT QUẢ TẠO ẢNH*\n\n"
                f"```\n  ✅ Xử lý thành công\n  📝 Prompt: {prompt[:40]}\n  💰 Còn lại: {new_bal} xu\n```\n\n"
                f"👇 *Muốn tạo video từ ảnh này không?*"
            ),
            parse_mode   = "MarkdownV2",
            reply_markup = kb_after_image(new_bal)
        )
        await msg.delete()
        return

    # ── Prompt tạo video ──
    if state == "wait_video_prompt":
        prompt = text
        video_photo_bytes = sess.get("video_photo_bytes")
        video_photo_name  = sess.get("video_photo_name","image.jpg")
        video_photo_id    = sess.get("video_photo_id")

        if not video_photo_bytes and not video_photo_id:
            await update.message.reply_text("❌ Không tìm thấy ảnh\\. Vui lòng thử lại\\!", parse_mode="MarkdownV2")
            clear_session(u.id); return

        ok_spend, new_bal = db_spend_coins(str(u.id), COST_VIDEO)
        if not ok_spend:
            await update.message.reply_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\nCần `{COST_VIDEO}` xu \\| Có `{new_bal}` xu",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Mua Xu",    callback_data="pay_menu")],
                    [InlineKeyboardButton("📅 Điểm Danh", callback_data="rollcall")],
                    [InlineKeyboardButton("🏠 Menu",      callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        tick_counter = [0]
        msg = await update.message.reply_text(
            render_video_log(0, 9, ["  🎬 Khởi động CLOTHESBOT Video...", f"  📝 Prompt: {prompt[:35]}", "  ⚠️  Quá trình này mất 2-5 phút!"], "~2-5 phút", tick=0),
            parse_mode="Markdown"
        )

        _vbytes = video_photo_bytes
        _vname  = video_photo_name
        _vid    = video_photo_id
        clear_session(u.id)

        import queue as _queue
        log_queue = _queue.Queue()
        def log_cb_q(lines, step=0): log_queue.put((list(lines), step))

        async def video_updater():
            while True:
                try:
                    lines, step = log_queue.get_nowait()
                    tick_counter[0] += 1
                    try:
                        await msg.edit_text(render_video_log(step, 9, lines, "đang xử lý...", tick=tick_counter[0]), parse_mode="Markdown")
                    except: pass
                except _queue.Empty: pass
                await asyncio.sleep(3)

        if package == "free":
            queue_msg = await update.message.reply_text("⏳ Đang kiểm tra hàng chờ\\.\\.\\.", parse_mode="MarkdownV2")
            async def queue_status_cb_v(status_text, pos):
                try: await queue_msg.edit_text(status_text, parse_mode="MarkdownV2")
                except: pass
            entered = await enter_queue(str(u.id), package, queue_status_cb_v)
            if not entered:
                await queue_msg.edit_text("❌ Hàng chờ quá tải\\. Vui lòng thử lại sau\\!", parse_mode="MarkdownV2")
                db_add_coins(str(u.id), COST_VIDEO)
                return
            try: await queue_msg.delete()
            except: pass

        loop = asyncio.get_event_loop()
        updater_task = asyncio.ensure_future(video_updater())

        try:
            if not _vbytes and _vid:
                photo_file = await update.get_bot().get_file(_vid)
                raw = await photo_file.download_as_bytearray()
                _vbytes = bytes(raw)
            log_cb_q(["  ✅ Ảnh sẵn sàng!","  🔧 Đang khởi tạo phiên xử lý..."], 1)
            video_bytes, video_url = await loop.run_in_executor(None, pika_create_account_and_generate, _vbytes, _vname, prompt, log_cb_q)
        except Exception as e:
            updater_task.cancel()
            if package == "free": leave_queue(str(u.id))
            db_add_coins(str(u.id), COST_VIDEO)
            log.error(f"Video generate error: {e}")
            await msg.edit_text(
                f"```\n{BANNER_ERROR}\n```\n\n❌ *TẠO VIDEO THẤT BẠI*\n\n"
                f"```\n  Lỗi: {str(e)[:60]}\n  💰 Đã hoàn lại: {COST_VIDEO} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thử Lại", callback_data="vid_start")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="Markdown"
            )
            return

        updater_task.cancel()
        if package == "free": leave_queue(str(u.id))
        inc_video_count(str(u.id))

        await update.message.reply_video(
            video        = video_bytes,
            caption      = (
                f"🎬 ✨ *CLOTHESBOT · VIDEO HOÀN TẤT\\!*\n\n"
                f"```\n  ✅ Render thành công\n  📝 Prompt: {prompt[:40]}\n  🎞️  480p | 5 giây\n  💰 Còn lại: {new_bal} xu\n```"
            ),
            parse_mode       = "MarkdownV2",
            reply_markup     = kb_after_video(new_bal),
            supports_streaming = True,
        )
        await msg.delete()
        return


    if state == "wait_key":
        check_key = KeyManager(str(u.id)).check_key(text.strip())
        if not check_key:
            await update.message.reply_text(
                "❌ KEY không hợp lệ hoặc đã được sử dụng\\. Vui lòng kiểm tra lại\\!",
                parse_mode="MarkdownV2"
            )
            return
        db_add_coins(str(u.id), 300)
        await update.message.reply_text(
            "✅ KEY hợp lệ! Bạn đã được cộng 300 xu.",
            parse_mode="MarkdownV2"
        )

    # ── Default ──
    user_db = get_or_create_user(str(u.id), u.username or "")
    await animated_splash(update.message, u, user_db)


# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════
def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start",      cmd_start))
    application.add_handler(CommandHandler("addcoins",   cmd_addcoins))
    application.add_handler(CommandHandler("setpackage", cmd_setpackage))
    application.add_handler(CommandHandler("userinfo",   cmd_userinfo))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application