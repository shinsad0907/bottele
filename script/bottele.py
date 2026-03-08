import os, logging, uuid, random, string, asyncio, time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app").rstrip("/")
INIT_COINS    = 100000000000000000000000000000000000000
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
#  RAM DB
# ══════════════════════════════════════════════
users_db    = {}
keys_db     = {}
sessions_db = {}

# ══════════════════════════════════════════════
#  BANNERS & VISUAL ASSETS
# ══════════════════════════════════════════════

BANNER_MAIN = """╔═══════════════════════════════════╗
║   ░█████╗░██╗  ██╗███╗░░██╗██████╗ ║
║   ██╔══██╗██║  ██║████╗░██║╚════██╗║
║   ███████║██║  ██║██╔██╗██║░░███╔═╝║
║   ██╔══██║██║  ██║██║╚████║██╔══╝░░║
║   ██║░░██║╚██████╔╝██║░╚███║███████╗║
║   ╚═╝░░╚═╝░╚═════╝░╚═╝░░╚══╝╚══════╝║
╠═══════════════════════════════════╣
║        🤖  AI IMAGE STUDIO  🎨     ║
║   Powered by Advanced Neural Net   ║
╚═══════════════════════════════════╝"""

BANNER_PROCESSING = """┌─────────────────────────────────┐
│  ██████╗ ██████╗  ██████╗  ██████╗ │
│  ██╔══██╗██╔══██╗██╔═══██╗██╔════╝ │
│  ██████╔╝██████╔╝██║   ██║██║      │
│  ██╔═══╝ ██╔══██╗██║   ██║██║      │
│  ██║     ██║  ██║╚██████╔╝╚██████╗ │
│  ╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ │
├─────────────────────────────────┤
│        🧠  NEURAL ENGINE  ⚡      │
└─────────────────────────────────┘"""

BANNER_WALLET = """╔══════════════════════════════╗
║  💎  DIAMOND  WALLET  💎   ║
╠══════════════════════════════╣"""

BANNER_BYPASS = """╔══════════════════════════════╗
║  🔗  EARN  COINS  FAST  💰  ║
╠══════════════════════════════╣"""

BANNER_SUCCESS = """╔══════════════════════════════╗
║  ✅  TRANSACTION  COMPLETE  ║
╠══════════════════════════════╣"""

BANNER_ERROR = """╔══════════════════════════════╗
║  ⚠️   SYSTEM  ALERT  ⚠️    ║
╠══════════════════════════════╣"""

# Spinner frames cho processing log
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
PROGRESS_BLOCKS = ["░░░░░░░░░░","█░░░░░░░░░","██░░░░░░░░","███░░░░░░░","████░░░░░░","█████░░░░░","██████░░░░","███████░░░","████████░░","█████████░","██████████"]

def progress_bar(step: int, total: int = 10) -> str:
    idx = min(int(step / total * 10), 10)
    pct = int(step / total * 100)
    return f"{PROGRESS_BLOCKS[idx]} {pct}%"

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def render_cmd(title: str, lines: list, footer: str = "") -> str:
    body = "\n".join(lines[-18:])
    tail = f"\n{'─'*35}\n{footer}" if footer else ""
    return (
        f"```\n"
        f"{'─'*35}\n"
        f"  {title}\n"
        f"{'─'*35}\n"
        f"{body}{tail}\n"
        f"{'─'*35}"
        f"\n```"
    )

def render_log_step(step: int, total_steps: int, lines: list, eta: str = "") -> str:
    bar = progress_bar(step, total_steps)
    body = "\n".join(lines[-14:])
    eta_line = f"\n  ⏱ ETA: {eta}" if eta else ""
    return (
        f"```\n"
        f"╔══ 🧠 NEURAL PROCESSING ENGINE ══╗\n"
        f"║  {bar}\n"
        f"╠══════════════════════════════════╣\n"
        f"{body}\n"
        f"╚══════════════════════════════════╝"
        f"{eta_line}"
        f"\n```"
    )

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

def coin_bar(coins: int, max_coins: int = 200) -> str:
    filled = min(int(coins / max_coins * 10), 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}]"

def rank_badge(coins: int) -> str:
    if coins >= 500: return "👑 LEGEND"
    if coins >= 200: return "💎 DIAMOND"
    if coins >= 100: return "🥇 GOLD"
    if coins >= 50:  return "🥈 SILVER"
    return "🥉 BRONZE"

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
        raise Exception(f"Firebase error: {r.get('error',{}).get('message', str(r))}")
    r2 = requests.post(
        'https://sv.aivideo123.site/api/user/init_data', headers=API_HDR,
        json={'token': r['idToken'], 'code': '-1', 'login_type': 0, 'current_uid': ''},
        timeout=15
    ).json()
    if r2.get('code') != 1:
        raise Exception(f"init_data error: {r2}")
    return email, r2['data']['session_token']

def generate_image(image_bytes: bytes, filename: str, prompt: str,
                   log_cb=None) -> bytes:
    lines = []
    step_counter = [0]

    def push(line: str, step_inc: int = 1):
        lines.append(line)
        step_counter[0] = min(step_counter[0] + step_inc, 9)
        if log_cb:
            try: log_cb(list(lines), step_counter[0])
            except: pass
        log.info(line)

    push(f"  ◈ Target  : {filename[:22]}", 0)
    push(f"  ◈ Prompt  : {prompt[:28]}...", 0)
    push(f"  ◈ Model   : Neural v3.0", 0)
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
    if up.status_code not in [200, 201, 204]:
        raise Exception(f"Upload failed {up.status_code}")
    push(f"  [04/07] ✅ HTTP {up.status_code} — Upload accepted!")

    push(f"  [05/07] 🧠 Sending to AI neural net...")
    inf = requests.post("https://sv.aivideo123.site/api/item/inference2",
        headers=headers,
        json={"s3_path": s3_key, "mask_path": "", "prompt": prompt, "ai_model_type": 3},
        timeout=15).json()
    if inf["code"] != 1: raise Exception("Inference failed")
    item_uid  = inf["data"]["item"]["uid"]
    time_need = inf["data"]["item"]["time_need"]
    push(f"  [05/07] ✅ Job queued! ETA: {time_need}s")
    push(f"  [06/07] ⚡ Processing... please wait")
    time.sleep(time_need)

    push(f"  [07/07] 📥 Fetching result...")
    r2 = requests.post("https://sv.aivideo123.site/api/item/get_items",
        headers=headers, json={"page": 0, "page_size": 50}, timeout=15).json()
    result_url = ""
    for item in r2["data"]["items"]:
        if item["uid"] == item_uid:
            result_url = item.get("thumbnail", ""); break
    if not result_url: raise Exception("Result not found")
    push(f"  [07/07] ✅ Result URL ready!")

    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  ✨ Downloading final image...", 0)
    img_resp = requests.get(result_url, timeout=20)
    push(f"  🎉 COMPLETE! Sending to you...", 0)
    return img_resp.content

# ══════════════════════════════════════════════
#  KEYBOARDS — Beautiful & Organized
# ══════════════════════════════════════════════
def kb_main(coins: int, username: str = ""):
    badge = rank_badge(coins)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        [InlineKeyboardButton("🎨  Tạo Ảnh AI  ✨",   callback_data="img_start")],
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        [InlineKeyboardButton("💎 Ví Xu",             callback_data="balance"),
         InlineKeyboardButton("🔗 Kiếm Xu",           callback_data="bypass")],
        [InlineKeyboardButton("📊 Thống Kê",          callback_data="stats"),
         InlineKeyboardButton("📖 Hướng Dẫn",         callback_data="help")],
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        [InlineKeyboardButton(f"{badge}  •  💰 {coins} xu", callback_data="balance")],
    ])

def kb_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️  Quay Về Menu", callback_data="home")]
    ])

def kb_cancel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌  Hủy Thao Tác", callback_data="home")]
    ])

def kb_after_image(coins: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Tạo Ảnh Mới",      callback_data="img_start"),
         InlineKeyboardButton("🏠 Menu Chính",        callback_data="home")],
        [InlineKeyboardButton(f"💰 Còn lại: {coins} xu", callback_data="balance")],
    ])

def kb_after_key(coins: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Tạo Ảnh Ngay!",    callback_data="img_start")],
        [InlineKeyboardButton("🔗 Kiếm Thêm Xu",     callback_data="bypass"),
         InlineKeyboardButton("🏠 Menu",              callback_data="home")],
        [InlineKeyboardButton(f"💰 Số dư: {coins} xu", callback_data="balance")],
    ])

# ══════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════
def msg_home(name: str, coins: int, total_images: int, total_bypassed: int) -> str:
    bar = coin_bar(coins)
    badge = rank_badge(coins)
    return (
        f"```\n{BANNER_MAIN}\n```\n\n"
        f"👋 Xin chào, *{esc(name)}*\\!\n\n"
        f"┌─ 📊 *THÔNG TIN TÀI KHOẢN* ─┐\n"
        f"│  {badge}\n"
        f"│  💰 Xu: `{coins}` {bar}\n"
        f"│  🎨 Ảnh đã tạo: `{total_images}`\n"
        f"│  🔗 Lượt kiếm xu: `{total_bypassed}`\n"
        f"└──────────────────────────────┘\n\n"
        f"⚡ Chi phí tạo ảnh: `{COST_IMAGE} xu / lần`\n"
        f"🎁 Thưởng mỗi link: `+{BYPASS_REWARD} xu`\n\n"
        f"👇 *Chọn tính năng bên dưới:*"
    )

def msg_balance(full_name: str, uid: int, coins: int, total_images: int, total_bypassed: int) -> str:
    bar = coin_bar(coins)
    badge = rank_badge(coins)
    spent = total_images * COST_IMAGE
    earned = total_bypassed * BYPASS_REWARD
    return (
        f"```\n{BANNER_WALLET}\n```\n\n"
        f"👤 *{esc(full_name or 'User')}*\n"
        f"🆔 ID: `{uid}`\n\n"
        f"┌─ 💎 *SỐ DƯ* ───────────────┐\n"
        f"│  {badge}\n"
        f"│  💰 Xu hiện có: `{coins} xu`\n"
        f"│  {bar}\n"
        f"└────────────────────────────┘\n\n"
        f"┌─ 📈 *LỊCH SỬ GIAO DỊCH* ──┐\n"
        f"│  🎨 Ảnh đã tạo: `{total_images}` lần\n"
        f"│  💸 Đã chi:     `{spent} xu`\n"
        f"│  🔗 Đã kiếm:   `{total_bypassed}` lần\n"
        f"│  💵 Tổng nhận:  `{earned + INIT_COINS} xu`\n"
        f"└────────────────────────────┘"
    )

def msg_bypass(link: str) -> str:
    return (
        f"```\n{BANNER_BYPASS}\n```\n\n"
        f"🎁 *Phần thưởng:* `+{BYPASS_REWARD} xu` mỗi lần\\!\n\n"
        f"📋 *Hướng dẫn nhanh:*\n"
        f"┌──────────────────────────────┐\n"
        f"│  1️⃣  Bấm nút link bên dưới   │\n"
        f"│  2️⃣  Hoàn thành trên web      │\n"
        f"│  3️⃣  Sao chép mã KEY          │\n"
        f"│  4️⃣  Bấm \"Nhập Key\" → dán vào│\n"
        f"└──────────────────────────────┘\n\n"
        f"⚠️ *Lưu ý:* Mỗi key chỉ dùng *1 lần*\n"
        f"🔑 Key có dạng: `xxxxxxxx\\-xxxx\\-xxxx\\-xxxx\\-xxxxxxxxxxxx`"
    )

def msg_help() -> str:
    return (
        f"📖 *HƯỚNG DẪN SỬ DỤNG*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎨 *TẠO ẢNH AI*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"1\\. Bấm `🎨 Tạo Ảnh AI`\n"
        f"2\\. Gửi ảnh gốc của bạn\n"
        f"3\\. Nhập mô tả \\(prompt\\) bằng tiếng Anh\n"
        f"4\\. Đợi AI xử lý \\(~20\\-40 giây\\)\n"
        f"💰 Chi phí: `{COST_IMAGE} xu` / lần\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *KIẾM XU MIỄN PHÍ*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"1\\. Bấm `🔗 Kiếm Xu`\n"
        f"2\\. Vào link được cấp\n"
        f"3\\. Hoàn thành bước trên web\n"
        f"4\\. Sao chép key → nhập vào bot\n"
        f"🎁 Phần thưởng: `+{BYPASS_REWARD} xu` / lần\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *MẸO HAY*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Prompt tiếng Anh cho kết quả tốt nhất\n"
        f"• Ảnh rõ nét, ánh sáng tốt → AI đẹp hơn\n"
        f"• Ví dụ prompt hay:\n"
        f"  `wear a red summer dress`\n"
        f"  `anime style, colorful outfit`\n"
        f"  `professional suit, business look`"
    )

def msg_stats(uid: int, coins: int, total_images: int, total_bypassed: int) -> str:
    rank = rank_badge(coins)
    efficiency = f"{total_images * COST_IMAGE} xu" if total_images > 0 else "0 xu"
    return (
        f"📊 *THỐNG KÊ CÁ NHÂN*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"🏆 Hạng: *{rank}*\n\n"
        f"┌─ 💰 *COINS* ───────────────┐\n"
        f"│  Hiện có:   `{coins} xu`\n"
        f"│  {coin_bar(coins)}\n"
        f"│  Đã kiếm:   `{total_bypassed * BYPASS_REWARD + INIT_COINS} xu` tổng\n"
        f"│  Đã tiêu:   `{efficiency}`\n"
        f"└────────────────────────────┘\n\n"
        f"┌─ 🎨 *HOẠT ĐỘNG* ───────────┐\n"
        f"│  Ảnh đã tạo:    `{total_images}` lần\n"
        f"│  Link đã dùng:  `{total_bypassed}` lần\n"
        f"└────────────────────────────┘\n\n"
        f"💡 Cần `{max(0, 50 - coins)}` xu để đạt Silver\\!"
        if coins < 50 else
        f"📊 *THỐNG KÊ CÁ NHÂN*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"🏆 Hạng: *{rank}*\n\n"
        f"┌─ 💰 *COINS* ───────────────┐\n"
        f"│  Hiện có:   `{coins} xu`\n"
        f"│  {coin_bar(coins)}\n"
        f"│  Đã kiếm:   `{total_bypassed * BYPASS_REWARD + INIT_COINS} xu` tổng\n"
        f"│  Đã tiêu:   `{efficiency}`\n"
        f"└────────────────────────────┘\n\n"
        f"┌─ 🎨 *HOẠT ĐỘNG* ───────────┐\n"
        f"│  Ảnh đã tạo:    `{total_images}` lần\n"
        f"│  Link đã dùng:  `{total_bypassed}` lần\n"
        f"└────────────────────────────┘"
    )

# ══════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    user = get_user(u.id)
    clear_session(u.id)
    await update.message.reply_text(
        msg_home(
            u.first_name or "bạn",
            user["coins"],
            user.get("total_images", 0),
            user.get("total_bypassed", 0)
        ),
        reply_markup=kb_main(user["coins"], u.first_name or ""),
        parse_mode="MarkdownV2"
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
            msg_home(
                u.first_name or "bạn",
                user["coins"],
                user.get("total_images", 0),
                user.get("total_bypassed", 0)
            ),
            reply_markup=kb_main(user["coins"], u.first_name or ""),
            parse_mode="MarkdownV2"
        ); return

    if d == "balance":
        await q.edit_message_text(
            msg_balance(
                u.full_name or "", u.id, user["coins"],
                user.get("total_images", 0), user.get("total_bypassed", 0)
            ),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    if d == "stats":
        await q.edit_message_text(
            msg_stats(
                u.id, user["coins"],
                user.get("total_images", 0), user.get("total_bypassed", 0)
            ),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    if d == "bypass":
        k    = new_key(u.id)
        link = f"{WEB_BASE_URL}/result/{k}"
        sess["pending_key"] = k
        await q.edit_message_text(
            msg_bypass(link),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐  Bấm Vào Đây Để Lấy Key  🔑", url=link)],
                [InlineKeyboardButton("⌨️  Nhập Key Vào Đây",  callback_data="key_enter")],
                [InlineKeyboardButton("◀️  Quay Lại",          callback_data="home")],
            ]), parse_mode="MarkdownV2"
        ); return

    if d == "key_enter":
        sess["state"] = "key"
        await q.edit_message_text(
            "🔑 *NHẬP KEY*\n\n"
            "```\n"
            "┌──────────────────────────────┐\n"
            "│  Dán key từ trang web vào đây │\n"
            "│  Định dạng UUID v4:            │\n"
            "│  xxxxxxxx-xxxx-xxxx-xxxx-xxx  │\n"
            "└──────────────────────────────┘\n"
            "```\n\n"
            "💬 Gửi key vào chat này:",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "img_start":
        if user["coins"] < COST_IMAGE:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n"
                f"  Cần:    {COST_IMAGE} xu\n"
                f"  Có:     {user['coins']} xu\n"
                f"  Thiếu:  {COST_IMAGE - user['coins']} xu\n"
                f"```\n\n"
                f"🔗 Kiếm xu miễn phí ngay bây giờ\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗  Kiếm Xu Miễn Phí  →",  callback_data="bypass")],
                    [InlineKeyboardButton("◀️  Quay Về Menu",          callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_photo"
        await q.edit_message_text(
            f"🎨 *TẠO ẢNH AI*\n\n"
            f"```\n"
            f"  Số dư:    {user['coins']} xu\n"
            f"  Chi phí:  {COST_IMAGE} xu / lần\n"
            f"  Sau khi:  {user['coins'] - COST_IMAGE} xu\n"
            f"```\n\n"
            f"📸 *BƯỚC 1 / 2*\n"
            f"Gửi ảnh bạn muốn chỉnh sửa:\n\n"
            f"• Ảnh rõ nét, đủ sáng\n"
            f"• Gửi trực tiếp \\(không qua file\\)\n"
            f"• Tối đa 5MB",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "help":
        await q.edit_message_text(
            msg_help(),
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
        "✅ *ĐÃ NHẬN ẢNH\\!*\n\n"
        "```\n"
        "  ████████████████  100%\n"
        "  [✓] Ảnh đã được tải lên\n"
        "  [✓] Kích thước OK\n"
        "  [✓] Định dạng OK\n"
        "```\n\n"
        "✏️ *BƯỚC 2 / 2*\n"
        "Nhập mô tả bạn muốn AI thực hiện:\n\n"
        "💡 *Ví dụ prompt hay:*\n"
        "`wear a red summer dress`\n"
        "`wearing a suit, professional`\n"
        "`anime style, colorful outfit`\n"
        "`beach look, casual clothes`",
        reply_markup=kb_cancel(), parse_mode="MarkdownV2"
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u     = update.effective_user
    sess  = get_session(u.id)
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
                f"```\n{BANNER_SUCCESS}\n```\n\n"
                f"🎉 *NHẬN XU THÀNH CÔNG\\!*\n\n"
                f"```\n"
                f"  ✅ Key hợp lệ\n"
                f"  💎 Nhận được:  +{BYPASS_REWARD} xu\n"
                f"  💰 Số dư mới:  {nb} xu\n"
                f"  🏆 Hạng:       {rank_badge(nb)}\n"
                f"```",
                reply_markup=kb_after_key(nb),
                parse_mode="MarkdownV2"
            )
        elif status == "used":
            await update.message.reply_text(
                f"```\n{BANNER_ERROR}\n```\n\n"
                "⚠️ *KEY ĐÃ ĐƯỢC SỬ DỤNG\\!*\n\n"
                "Key này đã được dùng trước đó\\.\n"
                "Mỗi key chỉ sử dụng được *1 lần*\\.\n\n"
                "👉 Lấy key mới bằng cách bấm Kiếm Xu\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Lấy Key Mới",  callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",         callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                f"```\n{BANNER_ERROR}\n```\n\n"
                "❌ *KEY KHÔNG HỢP LỆ\\!*\n\n"
                "```\n"
                "  ✗ Key không tồn tại trong hệ thống\n"
                "  ✗ Kiểm tra lại nội dung đã sao chép\n"
                "  ✗ Đảm bảo copy đầy đủ, không thiếu ký tự\n"
                "```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Nhập Lại",    callback_data="key_enter")],
                    [InlineKeyboardButton("🔗 Lấy Key Mới", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",        callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        clear_session(u.id); return

    # ── Nhập prompt tạo ảnh ──
    if state == "wait_prompt":
        photo_id   = sess.get("photo_id")
        photo_name = sess.get("photo_name", "photo.jpg")
        prompt     = text

        if not photo_id:
            await update.message.reply_text(
                "❌ Không tìm thấy ảnh\\. Vui lòng gửi lại ảnh\\!",
                parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        ok, new_bal = spend_coins(u.id, COST_IMAGE)
        if not ok:
            await update.message.reply_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n"
                f"Cần `{COST_IMAGE}` xu \\| Có `{new_bal}` xu",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiếm Xu", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        msg = await update.message.reply_text(
            render_log_step(0, 9,
                ["  ⏳ Khởi động hệ thống AI...",
                 f"  📝 Prompt: {prompt[:35]}"],
                "~30-40s"
            ),
            parse_mode="Markdown"
        )
        clear_session(u.id)

        import threading, queue as _queue
        log_queue = _queue.Queue()

        def log_cb_q(lines, step=0):
            log_queue.put((list(lines), step))

        async def updater():
            current_step = [0]
            while True:
                try:
                    lines, step = log_queue.get_nowait()
                    current_step[0] = step
                    try:
                        await msg.edit_text(
                            render_log_step(step, 9, lines, "..."),
                            parse_mode="Markdown"
                        )
                    except: pass
                except _queue.Empty:
                    pass
                await asyncio.sleep(1.8)

        loop = asyncio.get_event_loop()
        updater_task = asyncio.ensure_future(updater())

        try:
            photo_file  = await update.get_bot().get_file(photo_id)
            photo_bytes = await photo_file.download_as_bytearray()
            log_cb_q(["  ✅ Ảnh đã tải xong!", "  🔐 Đang kết nối AI engine..."], 1)

            result_bytes = await loop.run_in_executor(
                None, generate_image,
                bytes(photo_bytes), photo_name, prompt, log_cb_q
            )
        except Exception as e:
            updater_task.cancel()
            add_coins(u.id, COST_IMAGE)
            log.error(f"Generate error: {e}")
            await msg.edit_text(
                f"```\n{BANNER_ERROR}\n```\n\n"
                f"❌ *XỬ LÝ THẤT BẠI*\n\n"
                f"```\n"
                f"  Lỗi: {str(e)[:55]}\n"
                f"  💰 Đã hoàn lại: {COST_IMAGE} xu\n"
                f"```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thử Lại",  callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Menu",     callback_data="home")],
                ]), parse_mode="Markdown"
            )
            return

        updater_task.cancel()

        user = get_user(u.id)
        user["total_images"] = user.get("total_images", 0) + 1

        await update.message.reply_photo(
            photo=result_bytes,
            caption=(
                f"✨ *KẾT QUẢ TẠO ẢNH AI*\n\n"
                f"```\n"
                f"  ✅ Xử lý thành công\n"
                f"  📝 Prompt: {prompt[:40]}\n"
                f"  💰 Còn lại: {new_bal} xu\n"
                f"  🏆 Hạng: {rank_badge(new_bal)}\n"
                f"```"
            ),
            parse_mode="MarkdownV2",
            reply_markup=kb_after_image(new_bal)
        )
        await msg.delete()
        return

    # ── Tin nhắn thường ──
    user = get_user(u.id)
    await update.message.reply_text(
        msg_home(
            u.first_name or "bạn",
            user["coins"],
            user.get("total_images", 0),
            user.get("total_bypassed", 0)
        ),
        reply_markup=kb_main(user["coins"], u.first_name or ""),
        parse_mode="MarkdownV2"
    )

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application
