import os, logging, uuid, random, string, asyncio, time
import requests, re, json, base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

log = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

WEB_BASE_URL  = os.environ.get("WEB_BASE_URL", "https://bottele-three.vercel.app").rstrip("/")
INIT_COINS    = 1000000000000000000000
BYPASS_REWARD = 20
COST_IMAGE    = 10
COST_VIDEO    = 20

# ══════════════════════════════════════════════
#  CHANNEL GATE — Bắt buộc join trước khi dùng
# ══════════════════════════════════════════════
REQUIRED_CHANNEL     = "@ClothessAI"
REQUIRED_CHANNEL_URL = "https://t.me/ClothessAI"

async def check_join(bot_instance, user_id: int) -> bool:
    """Kiểm tra user đã join channel chưa. Trả về True nếu đã join."""
    try:
        member = await bot_instance.get_chat_member(
            chat_id=REQUIRED_CHANNEL,
            user_id=user_id
        )
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        log.warning(f"check_join error for {user_id}: {e}")
        return False

async def send_join_prompt(reply_fn):
    """Gửi thông báo yêu cầu join channel."""
    text = (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║  🔒  CLOTHESBOT  ·  YÊU CẦU  🔒     ║\n"
        "╠══════════════════════════════════════╣\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        "⚠️ *BẠN CHƯA THAM GIA CHANNEL\\!*\n\n"
        "Để sử dụng bot, bạn cần:\n\n"
        "┌──────────────────────────────┐\n"
        "│  1️⃣  Bấm nút bên dưới         │\n"
        "│  2️⃣  Join channel              │\n"
        "│  3️⃣  Quay lại bấm /start       │\n"
        "└──────────────────────────────┘\n\n"
        "✅ Hoàn toàn *MIỄN PHÍ* để tham gia\\!"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👗 Tham Gia Channel Ngay!", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Đã Join → Bắt Đầu",     callback_data="check_join")],
    ])
    await reply_fn(text, reply_markup=kb, parse_mode="MarkdownV2")

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
#  RAM DB
# ══════════════════════════════════════════════
users_db    = {}
keys_db     = {}
sessions_db = {}

# ══════════════════════════════════════════════
#  SPLASH ANIMATION FRAMES  —  CLOTHESBOT
# ══════════════════════════════════════════════

# Frame 1 — tối / khởi động
SPLASH_F1 = """```
╔══════════════════════════════════════╗
║                                      ║
║   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ║
║   ░                               ░  ║
║   ░   C L O T H E S B O T         ░  ║
║   ░                               ░  ║
║   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ║
║                                      ║
║       [ ĐANG KHỞI ĐỘNG... ]          ║
║                                      ║
╚══════════════════════════════════════╝
```"""

# Frame 2 — sáng dần / icon xuất hiện
SPLASH_F2 = """```
╔══════════════════════════════════════╗
║  👗                              👗  ║
║                                      ║
║  ✨  C L O T H E S B O T  ✨        ║
║       🎨  STUDIO · TOOLS  🎨        ║
║                                      ║
║  👗                              👗  ║
║  ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░▓▓  ║
║       ⚡  LOADING  ⚡               ║
╚══════════════════════════════════════╝
```"""

# Frame 3 — full ASCII rực rỡ
SPLASH_F3 = """```
╔══════════════════════════════════════╗
║ 🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥 ║
║                                      ║
║  ██████╗██╗      ██████╗ ████████╗  ║
║ ██╔════╝██║     ██╔═══██╗╚══██╔══╝  ║
║ ██║     ██║     ██║   ██║   ██║     ║
║ ██║     ██║     ██║   ██║   ██║     ║
║ ╚██████╗███████╗╚██████╔╝   ██║     ║
║  ╚═════╝╚══════╝ ╚═════╝    ╚═╝     ║
║                                      ║
║   👗 H E S B O T  ·  STUDIO 👗      ║
║                                      ║
║ ✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨🔥✨ ║
╚══════════════════════════════════════╝
```"""

# Frame 4 — màn hình chính
def splash_final(name: str, coins: int, total_images: int,
                 total_bypassed: int, total_videos: int = 0) -> str:
    bar   = coin_bar(coins)
    badge = rank_badge(coins)
    return (
        "```\n"
        "╔══════════════════════════════════════╗\n"
        "║ 👗✨━━━━━━━━━━━━━━━━━━━━━━━━━━✨👗 ║\n"
        "║                                      ║\n"
        "║    ██████╗██╗      ██████╗ ████████╗ ║\n"
        "║   ██╔════╝██║     ██╔═══██╗╚══██╔══╝ ║\n"
        "║   ██║     ██║     ██║   ██║   ██║    ║\n"
        "║   ╚██████╗███████╗╚██████╔╝   ██║    ║\n"
        "║    ╚═════╝╚══════╝ ╚═════╝    ╚═╝    ║\n"
        "║                                      ║\n"
        "║    👗  H E S B O T  ·  STUDIO  👗    ║\n"
        "║                                      ║\n"
        "║ 👗✨━━━━━━━━━━━━━━━━━━━━━━━━━━✨👗 ║\n"
        "╚══════════════════════════════════════╝\n"
        "```\n\n"
        f"👋 Xin chào, *{esc(name)}*\\!\n\n"
        f"┌─ 📊 *THÔNG TIN TÀI KHOẢN* ──┐\n"
        f"│  {badge}\n"
        f"│  💰 Xu: `{coins}` {bar}\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}`\n"
        f"│  🎬 Video đã tạo: `{total_videos}`\n"
        f"│  🔗 Lượt kiếm xu: `{total_bypassed}`\n"
        f"└────────────────────────────────┘\n\n"
        f"⚡ Chi phí tạo ảnh: `{COST_IMAGE} xu / lần`\n"
        f"🎬 Chi phí tạo video: `{COST_VIDEO} xu / lần`\n"
        f"🎁 Thưởng mỗi link: `+{BYPASS_REWARD} xu`\n\n"
        f"👇 *Chọn tính năng bên dưới:*"
    )

# ══════════════════════════════════════════════
#  ANIMATED LOADING  —  icon xoay + progress
# ══════════════════════════════════════════════
IMG_ICONS = ["👗", "✨", "🎨", "💫", "🌀", "⚡", "🔮", "🧵"]
VID_ICONS = ["🎬", "👗", "✨", "🌀", "🎞️", "💫", "⚡", "🎥"]

# Spinner dots
SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

PROGRESS_BLOCKS = [
    "░░░░░░░░░░", "█░░░░░░░░░", "██░░░░░░░░", "███░░░░░░░",
    "████░░░░░░", "█████░░░░░", "██████░░░░", "███████░░░",
    "████████░░", "█████████░", "██████████"
]

def progress_bar(step: int, total: int = 10) -> str:
    idx = min(int(step / total * 10), 10)
    pct = int(step / total * 100)
    return f"{PROGRESS_BLOCKS[idx]} {pct}%"

def render_log_step(step: int, total_steps: int, lines: list,
                    eta: str = "", tick: int = 0) -> str:
    bar    = progress_bar(step, total_steps)
    icon   = IMG_ICONS[tick % len(IMG_ICONS)]
    spin   = SPINNER[tick % len(SPINNER)]
    body   = "\n".join(lines[-12:])
    eta_line = f"\n  {spin} ETA: {eta}" if eta else ""
    return (
        f"```\n"
        f"╔══ {icon} CLOTHESBOT · PROCESSING {icon} ══╗\n"
        f"║  {bar}\n"
        f"╠══════════════════════════════════════╣\n"
        f"{body}\n"
        f"╚══════════════════════════════════════╝"
        f"{eta_line}"
        f"\n```"
    )

def render_video_log(step: int, total_steps: int, lines: list,
                     eta: str = "", tick: int = 0) -> str:
    bar    = progress_bar(step, total_steps)
    icon   = VID_ICONS[tick % len(VID_ICONS)]
    spin   = SPINNER[tick % len(SPINNER)]
    body   = "\n".join(lines[-12:])
    eta_line = f"\n  {spin} ETA: {eta}" if eta else ""
    return (
        f"```\n"
        f"╔══ {icon} CLOTHESBOT · RENDERING {icon} ══╗\n"
        f"║  {bar}\n"
        f"╠══════════════════════════════════════╣\n"
        f"{body}\n"
        f"╚══════════════════════════════════════╝"
        f"{eta_line}"
        f"\n```"
    )

# ══════════════════════════════════════════════
#  BANNERS  (static)
# ══════════════════════════════════════════════
BANNER_WALLET = """╔══════════════════════════════════════╗
║  💎  CLOTHESBOT  ·  WALLET  💎      ║
╠══════════════════════════════════════╣"""

BANNER_BYPASS = """╔══════════════════════════════════════╗
║  🔗  CLOTHESBOT  ·  EARN COINS  💰  ║
╠══════════════════════════════════════╣"""

BANNER_SUCCESS = """╔══════════════════════════════════════╗
║  ✅  CLOTHESBOT  ·  SUCCESS  ✅     ║
╠══════════════════════════════════════╣"""

BANNER_ERROR = """╔══════════════════════════════════════╗
║  ⚠️   CLOTHESBOT  ·  ERROR   ⚠️    ║
╠══════════════════════════════════════╣"""

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {"uid": uid, "coins": INIT_COINS,
                         "total_bypassed": 0, "total_images": 0, "total_videos": 0}
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
    """Xóa state/flow nhưng GIỮ LẠI last_image_bytes và last_image_name."""
    uid = str(uid)
    preserved = {}
    if uid in sessions_db:
        for key in ("last_image_bytes", "last_image_name"):
            if key in sessions_db[uid]:
                preserved[key] = sessions_db[uid][key]
    sessions_db[uid] = preserved

def full_clear_session(uid):
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
#  ANIMATED SPLASH
# ══════════════════════════════════════════════
async def animated_splash(message_obj, u, user):
    """3 frame động → màn hình chính."""
    m = await message_obj.reply_text(SPLASH_F1, parse_mode="Markdown")
    await asyncio.sleep(0.55)

    try: await m.edit_text(SPLASH_F2, parse_mode="Markdown")
    except: pass
    await asyncio.sleep(0.55)

    try: await m.edit_text(SPLASH_F3, parse_mode="Markdown")
    except: pass
    await asyncio.sleep(0.65)

    final_text = splash_final(
        u.first_name or "bạn",
        user["coins"],
        user.get("total_images", 0),
        user.get("total_bypassed", 0),
        user.get("total_videos", 0),
    )
    try:
        await m.edit_text(
            final_text,
            reply_markup=kb_main(user["coins"]),
            parse_mode="MarkdownV2"
        )
    except: pass
    return m

# ══════════════════════════════════════════════
#  VIDEO API  (internal)
# ══════════════════════════════════════════════
def _mailtm_create_account():
    domain = requests.get(f"{MAILTM}/domains", timeout=10).json()["hydra:member"][0]["domain"]
    u = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    p = ''.join(random.choices(string.ascii_letters  + string.digits, k=14))
    email = f"{u}@{domain}"
    r = requests.post(f"{MAILTM}/accounts",
                      json={"address": email, "password": p}, timeout=10)
    if r.status_code not in (200, 201):
        raise Exception("Tạo email tạm thất bại")
    tok = requests.post(f"{MAILTM}/token",
                        json={"address": email, "password": p}, timeout=10).json()
    if "token" not in tok:
        raise Exception("Đăng nhập email tạm thất bại")
    return {"email": email, "password": p, "token": tok["token"]}


def _mailtm_poll_pika(token, timeout=120, interval=6):
    seen, deadline = set(), time.time() + timeout
    hdrs = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        for m in requests.get(f"{MAILTM}/messages", headers=hdrs, timeout=10).json().get("hydra:member", []):
            if m["id"] in seen: continue
            seen.add(m["id"])
            if "pika" in m.get("from", {}).get("address", "").lower() or \
               "pika" in m.get("subject", "").lower():
                return requests.get(f"{MAILTM}/messages/{m['id']}", headers=hdrs, timeout=10).json()
        time.sleep(interval)
    return None


def _extract_verify_link(msg):
    pat = r'https://login\.pika\.art/auth/v1/verify\?[^\s\]\)\'"<>]+'
    html = msg.get("html", "")
    if isinstance(html, list): html = "\n".join(html)
    for src in [msg.get("text", ""), html]:
        m = re.search(pat, src)
        if m: return m.group(0).replace("&amp;", "&")
    return None


def _pika_signup(sess, email, password, username):
    page = sess.get("https://pika.art/signup", timeout=15)
    m = re.search(r'"([0-9a-f]{40})"', page.text)
    ah = m.group(1) if m else "4045d309671c08e4d71fe9aff61638cf00467c081f"
    sess.post("https://pika.art/signup",
        headers={
            "accept": "text/x-component", "next-action": ah,
            "next-router-state-tree": (
                "%5B%22%22%2C%7B%22children%22%3A%5B%22(entry)%22%2C%7B%22children%22%3A%5B"
                "%22signup%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull"
                "%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2C"
                "null%2Cnull%2Ctrue%5D"),
            "origin": "https://pika.art", "referer": "https://pika.art/signup",
        },
        files={"1_name": (None, username), "1_email": (None, email),
               "1_password": (None, password), "0": (None, '["$K1"]')},
        allow_redirects=False, timeout=20)


def _pika_login(email, password):
    sess = requests.Session()
    sess.headers.update({"user-agent": PIKA_UA, "accept-language": "vi-VN,vi;q=0.9,en;q=0.5"})
    page = sess.get("https://pika.art/login", timeout=15)
    m = re.search(r'"([0-9a-f]{40})"', page.text)
    ah = m.group(1) if m else "409cc0dec0398e3142f0f16c994ca8915680346831"
    resp = sess.post("https://pika.art/login",
        headers={
            "accept": "text/x-component", "next-action": ah,
            "next-router-state-tree": (
                "%5B%22%22%2C%7B%22children%22%3A%5B%22(entry)%22%2C%7B%22children%22%3A%5B"
                "%22login%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull"
                "%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D"),
            "origin": "https://pika.art", "referer": "https://pika.art/login",
        },
        files={"1_email": (None, email), "1_password": (None, password),
               "1_to": (None, "/"), "0": (None, '["$K1"]')},
        allow_redirects=True, timeout=20)

    sb_cookie = None
    for c in sess.cookies:
        if "sb-login-auth-token" in c.name:
            sb_cookie = c.value
            break
    if not sb_cookie:
        for r_hist in resp.history:
            sc = r_hist.headers.get("set-cookie", "")
            if "sb-login-auth-token" in sc:
                for part in sc.split(";"):
                    if "sb-login-auth-token" in part:
                        sb_cookie = part.split("=", 1)[-1].strip()
                        break
            if sb_cookie: break

    if not sb_cookie:
        return {}
    try:
        raw = sb_cookie[7:] if sb_cookie.startswith("base64-") else sb_cookie
        padded = raw + "=" * (-len(raw) % 4)
        decoded = json.loads(base64.b64decode(padded).decode())
        return {
            "access_token": decoded.get("access_token", ""),
            "user_id":      decoded.get("user", {}).get("id", ""),
            "sb_cookie":    sb_cookie,
        }
    except:
        return {}


def _detect_mime(b, filename):
    if b[:8] == b'\x89PNG\r\n\x1a\n': return "image/png"
    if b[:3] == b'\xff\xd8\xff':       return "image/jpeg"
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")


def _pika_generate_job(access_token, user_id, image_bytes, image_filename,
                       prompt="gentle movement", model="2.5", duration=5, resolution="480p"):
    mime = _detect_mime(image_bytes, image_filename)
    options = json.dumps({
        "frameRate": 24, "camera": {},
        "parameters": {"guidanceScale": 12, "motion": 1, "negativePrompt": ""},
        "extend": False,
    })
    resp = requests.post(
        "https://api.pika.art/generate/v2",
        headers={
            "accept": "*/*",
            "authorization": f"Bearer {access_token}",
            "origin": "https://pika.art", "referer": "https://pika.art/",
            "user-agent": PIKA_UA,
        },
        files={
            "resolution": (None, resolution), "promptText": (None, prompt),
            "image":      (image_filename, image_bytes, mime),
            "duration":   (None, str(duration)), "model": (None, model),
            "contentType": (None, "i2v"), "options": (None, options),
            "creditCost": (None, "12"), "userId": (None, user_id),
        },
        timeout=60,
    )
    data = resp.json()
    if data.get("success") == False:
        raise Exception(data.get("error", "Unknown error"))
    job_id = (data.get("id") or data.get("jobId") or
              data.get("data", {}).get("id") or
              data.get("data", {}).get("generation", {}).get("id"))
    if not job_id:
        raise Exception("Không nhận được Job ID")
    return str(job_id)


def _pika_poll_video(access_token, sb_cookie, job_id, timeout=300, interval=10):
    lib_hash = "4011bb5085d98313ee4cb9f6c1e0e4f1323144af54"
    cookie_str = (sb_cookie if sb_cookie.startswith("sb-login-auth-token=")
                  else f"sb-login-auth-token={sb_cookie}")
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            resp = requests.post(
                "https://pika.art/library",
                headers={
                    "accept": "text/x-component",
                    "accept-language": "vi-VN,vi;q=0.9,en;q=0.5",
                    "content-type": "text/plain;charset=UTF-8",
                    "next-action": lib_hash,
                    "next-router-state-tree": (
                        "%5B%22%22%2C%7B%22children%22%3A%5B%22(dashboard)%22%2C%7B%22children"
                        "%22%3A%5B%22library%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D"
                        "%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull"
                        "%2Cfalse%5D%7D%2Cnull%2Cnull%2Ctrue%5D"
                    ),
                    "origin": "https://pika.art",
                    "referer": "https://pika.art/library",
                    "user-agent": PIKA_UA,
                    "cookie": cookie_str,
                },
                data=json.dumps([{"ids": [job_id]}]),
                timeout=20,
            )
            if resp.status_code == 200:
                raw = resp.text
                for line in raw.split("\n"):
                    line = line.strip()
                    if not line: continue
                    if re.match(r'^\d+:', line):
                        payload = line.split(":", 1)[1]
                        try:
                            obj = json.loads(payload)
                            if obj.get("success") and "data" in obj:
                                for result in obj["data"].get("results", []):
                                    for video in result.get("videos", []):
                                        url = (video.get("resultUrl") or
                                               video.get("sharingUrl") or
                                               video.get("url"))
                                        if url and url.endswith(".mp4"):
                                            return url
                                    url = result.get("resultUrl") or result.get("videoUrl")
                                    if url and url.endswith(".mp4"):
                                        return url
                        except:
                            pass
                for pat in [r'"resultUrl"\s*:\s*"(https://[^"]+\.mp4)"',
                             r'"sharingUrl"\s*:\s*"(https://[^"]+\.mp4)"']:
                    m = re.search(pat, raw)
                    if m: return m.group(1)
                m = re.search(r'"status"\s*:\s*"([^"]+)"', raw)
                if m and m.group(1) in ("failed", "error", "cancelled"):
                    raise Exception(f"Job thất bại: {m.group(1)}")
        except Exception as e:
            if "thất bại" in str(e):
                raise
        time.sleep(interval)

    raise Exception(f"Quá thời gian {timeout}s, video chưa hoàn thành")


def pika_create_account_and_generate(image_bytes: bytes, filename: str,
                                     prompt: str = "gentle movement",
                                     log_cb=None):
    lines = []
    step_c = [0]

    def push(line, step_inc=1):
        lines.append(line)
        step_c[0] = min(step_c[0] + step_inc, 9)
        if log_cb:
            try: log_cb(list(lines), step_c[0])
            except: pass

    push(f"  ◈ Prompt : {prompt[:30]}", 0)
    push(f"  ◈ Output : 🎬 480p | ⏱ 5 giây", 0)
    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  [01/06] 📧 Tạo email tạm...")
    mt = _mailtm_create_account()
    push(f"  [01/06] ✅ Email: {mt['email'][:25]}")

    push(f"  [02/06] 🔧 Khởi tạo phiên xử lý...")
    rnd_name  = ''.join(random.choices(string.ascii_lowercase, k=8))
    pika_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + "Aa1!"
    sess = requests.Session()
    sess.headers.update({"user-agent": PIKA_UA})
    _pika_signup(sess, mt["email"], pika_pass, rnd_name)
    push(f"  [02/06] ✅ Đã gửi yêu cầu đăng ký")

    push(f"  [03/06] 📨 Chờ email xác nhận...")
    msg = _mailtm_poll_pika(mt["token"], timeout=120, interval=6)
    if not msg:
        raise Exception("Không nhận được email xác nhận")
    verify_url = _extract_verify_link(msg)
    if not verify_url:
        raise Exception("Không tìm thấy link xác nhận")
    vr = requests.Session()
    vr.headers.update({"user-agent": PIKA_UA})
    vr.get(verify_url, allow_redirects=True, timeout=20)
    push(f"  [03/06] ✅ Xác nhận email OK")

    push(f"  [04/06] 🔐 Xác thực hệ thống...")
    lr = _pika_login(mt["email"], pika_pass)
    if not lr.get("access_token"):
        raise Exception("Xác thực thất bại")
    push(f"  [04/06] ✅ Xác thực thành công!")

    push(f"  [05/06] 🎬 Gửi yêu cầu render...")
    job_id = _pika_generate_job(
        lr["access_token"], lr["user_id"],
        image_bytes, filename, prompt=prompt
    )
    push(f"  [05/06] ✅ Job ID: {job_id[:8]}...")

    push(f"  [06/06] ⏳ Đang render (~2-5 phút)...")
    time.sleep(20)
    video_url = _pika_poll_video(
        lr["access_token"], lr["sb_cookie"], job_id,
        timeout=300, interval=10
    )
    push(f"  [06/06] ✅ 🎬 Video sẵn sàng!")
    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  📥 Đang tải video về...", 0)
    vresp = requests.get(video_url, timeout=180, stream=True)
    video_bytes = b"".join(vresp.iter_content(chunk_size=8192))
    push(f"  ✅ {len(video_bytes)//1024} KB — 🎉 Hoàn tất!", 0)
    return video_bytes, video_url

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
        json={'returnSecureToken': True, 'email': email, 'password': email,
              'clientType': 'CLIENT_TYPE_WEB'},
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
    push(f"  ◈ 👗 CLOTHESBOT Engine Ready", 0)
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
            result_url = item.get("thumbnail", ""); break
    if not result_url: raise Exception("Result not found")
    push(f"  [07/07] ✅ Result URL ready!")

    push(f"  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", 0)
    push(f"  ✨ Downloading final image...", 0)
    img_resp = requests.get(result_url, timeout=20)
    push(f"  🎉 CLOTHESBOT · COMPLETE!", 0)
    return img_resp.content

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════
def kb_main(coins: int):
    badge = rank_badge(coins)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton("🎨 ✨  TẠO ẢNH  ✨ 🎨",     callback_data="img_start")],
        [InlineKeyboardButton("🎬 ✨  TẠO VIDEO  ✨ 🎬",    callback_data="vid_start")],
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton("💎 Ví Xu",                   callback_data="balance"),
         InlineKeyboardButton("🔗 Kiếm Xu",                 callback_data="bypass")],
        [InlineKeyboardButton("📊 Thống Kê",                callback_data="stats"),
         InlineKeyboardButton("📖 Hướng Dẫn",               callback_data="help")],
        [InlineKeyboardButton("👗✨━━━━━━━━━━━━━━━━━━✨👗", callback_data="noop")],
        [InlineKeyboardButton(f"{badge}  •  💰 {coins} xu",  callback_data="balance")],
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
        [InlineKeyboardButton("🎬 ✨ Tạo Video Từ Ảnh Này!", callback_data="vid_from_last_image")],
        [InlineKeyboardButton("🎨 Tạo Ảnh Mới",             callback_data="img_start"),
         InlineKeyboardButton("🏠 Menu Chính",               callback_data="home")],
        [InlineKeyboardButton(f"💰 Còn lại: {coins} xu",     callback_data="balance")],
    ])

def kb_after_video(coins: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Tạo Video Mới",            callback_data="vid_start"),
         InlineKeyboardButton("🎨 Tạo Ảnh Mới",             callback_data="img_start")],
        [InlineKeyboardButton("🏠 Menu Chính",               callback_data="home")],
        [InlineKeyboardButton(f"💰 Còn lại: {coins} xu",     callback_data="balance")],
    ])

def kb_after_key(coins: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Tạo Ảnh Ngay!",           callback_data="img_start"),
         InlineKeyboardButton("🎬 Tạo Video Ngay!",          callback_data="vid_start")],
        [InlineKeyboardButton("🔗 Kiếm Thêm Xu",             callback_data="bypass"),
         InlineKeyboardButton("🏠 Menu",                     callback_data="home")],
        [InlineKeyboardButton(f"💰 Số dư: {coins} xu",       callback_data="balance")],
    ])

# ══════════════════════════════════════════════
#  MESSAGE BUILDERS
# ══════════════════════════════════════════════
def msg_balance(full_name: str, uid: int, coins: int, total_images: int,
                total_bypassed: int, total_videos: int = 0) -> str:
    bar = coin_bar(coins)
    badge = rank_badge(coins)
    spent = total_images * COST_IMAGE + total_videos * COST_VIDEO
    earned = total_bypassed * BYPASS_REWARD
    return (
        f"```\n{BANNER_WALLET}\n```\n\n"
        f"👤 *{esc(full_name or 'User')}*\n"
        f"🆔 ID: `{uid}`\n\n"
        f"┌─ 💎 *SỐ DƯ* ────────────────┐\n"
        f"│  {badge}\n"
        f"│  💰 Xu hiện có: `{coins} xu`\n"
        f"│  {bar}\n"
        f"└──────────────────────────────┘\n\n"
        f"┌─ 📈 *LỊCH SỬ GIAO DỊCH* ────┐\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}` lần\n"
        f"│  🎬 Video đã tạo: `{total_videos}` lần\n"
        f"│  💸 Đã chi:       `{spent} xu`\n"
        f"│  🔗 Đã kiếm:     `{total_bypassed}` lần\n"
        f"│  💵 Tổng nhận:    `{earned + INIT_COINS} xu`\n"
        f"└──────────────────────────────┘"
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
        f"📖 *CLOTHESBOT · HƯỚNG DẪN*\n\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"🎨 ✨ *TẠO ẢNH*\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"1\\. Bấm `🎨 ✨ Tạo Ảnh`\n"
        f"2\\. Gửi ảnh gốc của bạn\n"
        f"3\\. Nhập mô tả \\(prompt\\) bằng tiếng Anh\n"
        f"4\\. Đợi hệ thống xử lý \\(~20\\-40 giây\\)\n"
        f"💰 Chi phí: `{COST_IMAGE} xu` / lần\n\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"🎬 ✨ *TẠO VIDEO*\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"1\\. Bấm `🎬 ✨ Tạo Video` hoặc sau khi tạo ảnh\n"
        f"2\\. Gửi ảnh muốn chuyển thành video\n"
        f"3\\. Nhập mô tả chuyển động bằng tiếng Anh\n"
        f"4\\. Đợi render \\(~2\\-5 phút\\)\n"
        f"💰 Chi phí: `{COST_VIDEO} xu` / lần\n\n"
        f"💡 Ví dụ prompt:\n"
        f"  `gentle swaying motion`\n"
        f"  `hair blowing in the wind`\n"
        f"  `slow zoom in`\n\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"🔗 *KIẾM XU MIỄN PHÍ*\n"
        f"👗✨━━━━━━━━━━━━━━━━━━━━━✨👗\n"
        f"1\\. Bấm `🔗 Kiếm Xu`\n"
        f"2\\. Vào link được cấp\n"
        f"3\\. Hoàn thành bước trên web\n"
        f"4\\. Sao chép key → nhập vào bot\n"
        f"🎁 Phần thưởng: `+{BYPASS_REWARD} xu` / lần"
    )

def msg_stats(uid: int, coins: int, total_images: int, total_bypassed: int,
              total_videos: int = 0) -> str:
    rank = rank_badge(coins)
    spent = total_images * COST_IMAGE + total_videos * COST_VIDEO
    return (
        f"📊 *CLOTHESBOT · THỐNG KÊ*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"🏆 Hạng: *{rank}*\n\n"
        f"┌─ 💰 *COINS* ─────────────────┐\n"
        f"│  Hiện có:   `{coins} xu`\n"
        f"│  {coin_bar(coins)}\n"
        f"│  Đã kiếm:   `{total_bypassed * BYPASS_REWARD + INIT_COINS} xu` tổng\n"
        f"│  Đã tiêu:   `{spent} xu`\n"
        f"└──────────────────────────────┘\n\n"
        f"┌─ 👗 *HOẠT ĐỘNG* ─────────────┐\n"
        f"│  🎨 Ảnh đã tạo:   `{total_images}` lần\n"
        f"│  🎬 Video đã tạo: `{total_videos}` lần\n"
        f"│  🔗 Link đã dùng: `{total_bypassed}` lần\n"
        f"└──────────────────────────────┘"
    )

# ══════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    # ── CHANNEL GATE ──
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(
            lambda text, **kw: update.message.reply_text(text, **kw)
        )
        return
    # ─────────────────
    user = get_user(u.id)
    full_clear_session(u.id)
    await animated_splash(update.message, u, user)

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    d    = q.data
    u    = q.from_user
    user = get_user(u.id)
    sess = get_session(u.id)

    if d == "noop": return

    # ── Check join (nút "Đã Join → Bắt Đầu") ──
    if d == "check_join":
        if await check_join(ctx.bot, u.id):
            user = get_user(u.id)
            full_clear_session(u.id)
            final_text = splash_final(
                u.first_name or "bạn", user["coins"],
                user.get("total_images", 0), user.get("total_bypassed", 0),
                user.get("total_videos", 0),
            )
            await q.edit_message_text(
                final_text,
                reply_markup=kb_main(user["coins"]),
                parse_mode="MarkdownV2"
            )
        else:
            await q.answer(
                "❌ Bạn chưa join channel! Hãy join rồi thử lại.",
                show_alert=True
            )
        return

    # ── Kiểm tra channel cho mọi hành động khác ──
    if not await check_join(ctx.bot, u.id):
        await q.answer("⚠️ Bạn cần join channel để dùng bot!", show_alert=True)
        await q.edit_message_text(
            "```\n"
            "╔══════════════════════════════════════╗\n"
            "║  🔒  CLOTHESBOT  ·  YÊU CẦU  🔒     ║\n"
            "╠══════════════════════════════════════╣\n"
            "╚══════════════════════════════════════╝\n"
            "```\n\n"
            "⚠️ *BẠN CHƯA THAM GIA CHANNEL\\!*\n\n"
            "Vui lòng join channel để tiếp tục sử dụng bot\\.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👗 Tham Gia Channel Ngay!", url=REQUIRED_CHANNEL_URL)],
                [InlineKeyboardButton("✅ Đã Join → Tiếp Tục",    callback_data="check_join")],
            ]),
            parse_mode="MarkdownV2"
        )
        return
    # ─────────────────────────────────────────────

    # ── Home ──
    if d == "home":
        full_clear_session(u.id)
        user = get_user(u.id)
        await q.edit_message_text(
            splash_final(
                u.first_name or "bạn", user["coins"],
                user.get("total_images", 0), user.get("total_bypassed", 0),
                user.get("total_videos", 0),
            ),
            reply_markup=kb_main(user["coins"]),
            parse_mode="MarkdownV2"
        ); return

    # ── Balance ──
    if d == "balance":
        await q.edit_message_text(
            msg_balance(u.full_name or "", u.id, user["coins"],
                        user.get("total_images", 0), user.get("total_bypassed", 0),
                        user.get("total_videos", 0)),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    # ── Stats ──
    if d == "stats":
        await q.edit_message_text(
            msg_stats(u.id, user["coins"],
                      user.get("total_images", 0), user.get("total_bypassed", 0),
                      user.get("total_videos", 0)),
            reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

    # ── Bypass ──
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

    # ── Start Image ──
    if d == "img_start":
        if user["coins"] < COST_IMAGE:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n  Cần:    {COST_IMAGE} xu\n  Có:     {user['coins']} xu\n  Thiếu:  {COST_IMAGE - user['coins']} xu\n```\n\n"
                f"🔗 Kiếm xu miễn phí ngay\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗  Kiếm Xu Miễn Phí  →",  callback_data="bypass")],
                    [InlineKeyboardButton("◀️  Quay Về Menu",          callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_photo"
        sess.pop("photo_id", None)
        sess.pop("photo_name", None)
        await q.edit_message_text(
            f"🎨 ✨ *TẠO ẢNH*\n\n"
            f"```\n  💰 Số dư:   {user['coins']} xu\n  💸 Chi phí: {COST_IMAGE} xu / lần\n  📊 Sau khi: {user['coins'] - COST_IMAGE} xu\n```\n\n"
            f"📸 *BƯỚC 1 / 2*\n"
            f"Gửi ảnh bạn muốn chỉnh sửa:\n\n"
            f"• Ảnh rõ nét, đủ sáng\n• Gửi trực tiếp \\(không qua file\\)\n• Tối đa 5MB",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    # ── Start Video ──
    if d == "vid_start":
        if user["coins"] < COST_VIDEO:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n  Cần:    {COST_VIDEO} xu\n  Có:     {user['coins']} xu\n  Thiếu:  {COST_VIDEO - user['coins']} xu\n```\n\n"
                f"🔗 Kiếm xu miễn phí để tạo video\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗  Kiếm Xu Miễn Phí  →",  callback_data="bypass")],
                    [InlineKeyboardButton("◀️  Quay Về Menu",          callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"] = "wait_video_photo"
        sess.pop("video_photo_id",    None)
        sess.pop("video_photo_bytes", None)
        sess.pop("video_photo_name",  None)
        await q.edit_message_text(
            f"🎬 ✨ *TẠO VIDEO*\n\n"
            f"```\n  💰 Số dư:   {user['coins']} xu\n  💸 Chi phí: {COST_VIDEO} xu / lần\n  🎞️  Output:  480p | 5 giây\n```\n\n"
            f"📸 *BƯỚC 1 / 2*\n"
            f"Gửi ảnh bạn muốn chuyển thành video:\n\n"
            f"• Ảnh rõ nét, đủ sáng\n"
            f"• Gửi trực tiếp \\(không qua file\\)\n"
            f"• Hoạt động tốt nhất với ảnh người hoặc cảnh vật",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    # ── Video từ ảnh vừa tạo ──
    if d == "vid_from_last_image":
        last_img  = sess.get("last_image_bytes")
        last_name = sess.get("last_image_name", "image.jpg")
        if not last_img:
            await q.edit_message_text(
                "❌ Không tìm thấy ảnh vừa tạo\\. Vui lòng tạo ảnh trước\\!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎨 ✨ Tạo Ảnh",  callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Menu",        callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        if user["coins"] < COST_VIDEO:
            await q.edit_message_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\n\n"
                f"```\n  Cần:    {COST_VIDEO} xu\n  Có:     {user['coins']} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiếm Xu",  callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",     callback_data="home")],
                ]), parse_mode="MarkdownV2"
            ); return
        sess["state"]             = "wait_video_prompt"
        sess["video_photo_bytes"] = last_img
        sess["video_photo_name"]  = last_name
        await q.edit_message_text(
            f"🎬 ✨ *TẠO VIDEO TỪ ẢNH VỪA TẠO*\n\n"
            f"```\n  💸 Chi phí: {COST_VIDEO} xu\n  📊 Sau khi: {user['coins'] - COST_VIDEO} xu\n  🎞️  Output:  480p | 5 giây\n```\n\n"
            f"✏️ *BƯỚC 2 / 2 — Nhập mô tả chuyển động:*\n\n"
            f"💡 Ví dụ:\n"
            f"`gentle swaying motion`\n"
            f"`hair blowing in the wind`\n"
            f"`slow zoom in, cinematic`\n"
            f"`walking forward slowly`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        ); return

    if d == "help":
        await q.edit_message_text(
            msg_help(), reply_markup=kb_back(), parse_mode="MarkdownV2"
        ); return

# ══════════════════════════════════════════════
#  PHOTO HANDLER
# ══════════════════════════════════════════════
async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u     = update.effective_user
    # ── CHANNEL GATE ──
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(
            lambda text, **kw: update.message.reply_text(text, **kw)
        )
        return
    # ─────────────────
    sess  = get_session(u.id)
    state = sess.get("state")
    photo = update.message.photo[-1]

    if state == "wait_photo":
        sess["photo_id"]   = photo.file_id
        sess["photo_name"] = f"photo_{photo.file_id[:8]}.jpg"
        sess["state"]      = "wait_prompt"
        await update.message.reply_text(
            "✅ *ĐÃ NHẬN ẢNH\\!*\n\n"
            "```\n  [✓] Ảnh đã tải lên\n  [✓] Kích thước OK\n  [✓] Định dạng OK\n```\n\n"
            "✏️ *BƯỚC 2 / 2*\n"
            "Nhập mô tả bạn muốn hệ thống thực hiện:\n\n"
            "💡 *Ví dụ prompt:*\n"
            "`wear a red summer dress`\n"
            "`wearing a suit, professional`\n"
            "`anime style, colorful outfit`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        )
        return

    if state == "wait_video_photo":
        sess["video_photo_id"]   = photo.file_id
        sess["video_photo_name"] = f"video_{photo.file_id[:8]}.jpg"
        sess["state"]            = "wait_video_prompt"
        await update.message.reply_text(
            "✅ *ĐÃ NHẬN ẢNH\\!*\n\n"
            "```\n  [✓] Ảnh đã tải lên\n  [✓] Sẵn sàng tạo video\n```\n\n"
            "✏️ *BƯỚC 2 / 2 — Mô tả chuyển động:*\n\n"
            "💡 *Ví dụ prompt:*\n"
            "`gentle swaying motion`\n"
            "`hair blowing in the wind`\n"
            "`slow zoom in, cinematic`\n"
            "`walking forward slowly`\n"
            "`water rippling gently`",
            reply_markup=kb_cancel(), parse_mode="MarkdownV2"
        )
        return

# ══════════════════════════════════════════════
#  TEXT HANDLER
# ══════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u     = update.effective_user
    # ── CHANNEL GATE ──
    if not await check_join(ctx.bot, u.id):
        await send_join_prompt(
            lambda text, **kw: update.message.reply_text(text, **kw)
        )
        return
    # ─────────────────
    sess  = get_session(u.id)
    state = sess.get("state")
    text  = update.message.text.strip()

    # ── Key bypass ──
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
                f"```\n  ✅ Key hợp lệ\n  💎 Nhận được:  +{BYPASS_REWARD} xu\n  💰 Số dư mới:  {nb} xu\n  🏆 Hạng:       {rank_badge(nb)}\n```",
                reply_markup=kb_after_key(nb), parse_mode="MarkdownV2"
            )
        elif status == "used":
            await update.message.reply_text(
                f"```\n{BANNER_ERROR}\n```\n\n"
                "⚠️ *KEY ĐÃ ĐƯỢC SỬ DỤNG\\!*\n\nKey này đã dùng trước đó\\. Mỗi key chỉ *1 lần*\\.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Lấy Key Mới",  callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",         callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                f"```\n{BANNER_ERROR}\n```\n\n"
                "❌ *KEY KHÔNG HỢP LỆ\\!*\n\n"
                "```\n  ✗ Key không tồn tại\n  ✗ Kiểm tra lại nội dung\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Nhập Lại",    callback_data="key_enter")],
                    [InlineKeyboardButton("🔗 Lấy Key Mới", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",        callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
        clear_session(u.id); return

    # ── Prompt tạo ảnh ──
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

        ok_spend, new_bal = spend_coins(u.id, COST_IMAGE)
        if not ok_spend:
            await update.message.reply_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\nCần `{COST_IMAGE}` xu \\| Có `{new_bal}` xu",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiếm Xu", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        tick_counter = [0]
        msg = await update.message.reply_text(
            render_log_step(0, 9,
                ["  ⏳ Khởi động CLOTHESBOT...",
                 f"  📝 Prompt: {prompt[:35]}"],
                "~30-40s", tick=0),
            parse_mode="Markdown"
        )

        _photo_id   = photo_id
        _photo_name = photo_name
        clear_session(u.id)

        import queue as _queue
        log_queue = _queue.Queue()

        def log_cb_q(lines, step=0):
            log_queue.put((list(lines), step))

        async def updater():
            while True:
                try:
                    lines, step = log_queue.get_nowait()
                    tick_counter[0] += 1
                    try:
                        await msg.edit_text(
                            render_log_step(step, 9, lines, "...", tick=tick_counter[0]),
                            parse_mode="Markdown"
                        )
                    except: pass
                except _queue.Empty:
                    pass
                await asyncio.sleep(1.5)

        loop = asyncio.get_event_loop()
        updater_task = asyncio.ensure_future(updater())

        try:
            photo_file  = await update.get_bot().get_file(_photo_id)
            photo_bytes = await photo_file.download_as_bytearray()
            log_cb_q(["  ✅ Ảnh đã tải xong!", "  👗 Đang phân tích trang phục..."], 1)

            result_bytes = await loop.run_in_executor(
                None, generate_image, bytes(photo_bytes), _photo_name, prompt, log_cb_q
            )
        except Exception as e:
            updater_task.cancel()
            add_coins(u.id, COST_IMAGE)
            await msg.edit_text(
                f"```\n{BANNER_ERROR}\n```\n\n❌ *XỬ LÝ THẤT BẠI*\n\n"
                f"```\n  Lỗi: {str(e)[:55]}\n  💰 Đã hoàn lại: {COST_IMAGE} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thử Lại",  callback_data="img_start")],
                    [InlineKeyboardButton("🏠 Menu",     callback_data="home")],
                ]), parse_mode="Markdown"
            )
            return

        updater_task.cancel()
        user = get_user(u.id)
        user["total_images"] = user.get("total_images", 0) + 1

        fresh_sess = get_session(u.id)
        fresh_sess["last_image_bytes"] = result_bytes
        fresh_sess["last_image_name"]  = _photo_name

        await update.message.reply_photo(
            photo=result_bytes,
            caption=(
                f"✨ *CLOTHESBOT · KẾT QUẢ TẠO ẢNH*\n\n"
                f"```\n  ✅ Xử lý thành công\n  📝 Prompt: {prompt[:40]}\n  💰 Còn lại: {new_bal} xu\n  🏆 Hạng: {rank_badge(new_bal)}\n```\n\n"
                f"👇 *Muốn tạo video từ ảnh này không?*"
            ),
            parse_mode="MarkdownV2",
            reply_markup=kb_after_image(new_bal)
        )
        await msg.delete()
        return

    # ── Prompt tạo video ──
    if state == "wait_video_prompt":
        prompt = text

        video_photo_bytes = sess.get("video_photo_bytes")
        video_photo_name  = sess.get("video_photo_name", "image.jpg")
        video_photo_id    = sess.get("video_photo_id")

        if not video_photo_bytes and not video_photo_id:
            await update.message.reply_text(
                "❌ Không tìm thấy ảnh\\. Vui lòng thử lại\\!",
                parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        ok_spend, new_bal = spend_coins(u.id, COST_VIDEO)
        if not ok_spend:
            await update.message.reply_text(
                f"⚠️ *KHÔNG ĐỦ XU\\!*\nCần `{COST_VIDEO}` xu \\| Có `{new_bal}` xu",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Kiếm Xu", callback_data="bypass")],
                    [InlineKeyboardButton("🏠 Menu",    callback_data="home")],
                ]), parse_mode="MarkdownV2"
            )
            clear_session(u.id); return

        tick_counter = [0]
        msg = await update.message.reply_text(
            render_video_log(0, 9,
                ["  🎬 Khởi động CLOTHESBOT Video...",
                 f"  📝 Prompt: {prompt[:35]}",
                 "  ⚠️  Quá trình này mất 2-5 phút, vui lòng chờ!"],
                "~2-5 phút", tick=0
            ),
            parse_mode="Markdown"
        )

        _vbytes = video_photo_bytes
        _vname  = video_photo_name
        _vid    = video_photo_id
        clear_session(u.id)

        import queue as _queue
        log_queue = _queue.Queue()

        def log_cb_q(lines, step=0):
            log_queue.put((list(lines), step))

        async def video_updater():
            while True:
                try:
                    lines, step = log_queue.get_nowait()
                    tick_counter[0] += 1
                    try:
                        await msg.edit_text(
                            render_video_log(step, 9, lines, "đang xử lý...", tick=tick_counter[0]),
                            parse_mode="Markdown"
                        )
                    except: pass
                except _queue.Empty:
                    pass
                await asyncio.sleep(3)

        loop = asyncio.get_event_loop()
        updater_task = asyncio.ensure_future(video_updater())

        try:
            if not _vbytes and _vid:
                photo_file = await update.get_bot().get_file(_vid)
                raw = await photo_file.download_as_bytearray()
                _vbytes = bytes(raw)

            log_cb_q(["  ✅ Ảnh sẵn sàng!", "  🔧 Đang khởi tạo phiên xử lý..."], 1)

            video_bytes, video_url = await loop.run_in_executor(
                None, pika_create_account_and_generate,
                _vbytes, _vname, prompt, log_cb_q
            )
        except Exception as e:
            updater_task.cancel()
            add_coins(u.id, COST_VIDEO)
            log.error(f"Video generate error: {e}")
            await msg.edit_text(
                f"```\n{BANNER_ERROR}\n```\n\n❌ *TẠO VIDEO THẤT BẠI*\n\n"
                f"```\n  Lỗi: {str(e)[:60]}\n  💰 Đã hoàn lại: {COST_VIDEO} xu\n```",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Thử Lại",  callback_data="vid_start")],
                    [InlineKeyboardButton("🏠 Menu",     callback_data="home")],
                ]), parse_mode="Markdown"
            )
            return

        updater_task.cancel()
        user = get_user(u.id)
        user["total_videos"] = user.get("total_videos", 0) + 1

        await update.message.reply_video(
            video=video_bytes,
            caption=(
                f"🎬 ✨ *CLOTHESBOT · VIDEO HOÀN TẤT\\!*\n\n"
                f"```\n  ✅ Render thành công\n  📝 Prompt: {prompt[:40]}\n  🎞️  480p | 5 giây\n  💰 Còn lại: {new_bal} xu\n  🏆 Hạng: {rank_badge(new_bal)}\n```"
            ),
            parse_mode="MarkdownV2",
            reply_markup=kb_after_video(new_bal),
            supports_streaming=True,
        )
        await msg.delete()
        return

    # ── Tin nhắn thường → splash lại ──
    user = get_user(u.id)
    await animated_splash(update.message, u, user)

def setup_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(btn))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application
