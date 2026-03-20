from flask import Flask, request, Response, render_template
import asyncio
from supabase import create_client
from telegram import Update, Bot
from telegram.ext import Application
from script.bottele import WEB_BASE_URL, setup_application
import os

from script.create_key import KeyManager
# ← Import thêm hàm IP limit từ database
from script.database import check_and_inc_ip_limit

app = Flask(__name__)
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU")
SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Helper lấy IP thật (qua proxy / Vercel / Render) ─────────────────────────
def get_real_ip() -> str:
    """
    Ưu tiên header X-Forwarded-For (Vercel, Render, Nginx proxy).
    Nếu không có thì dùng remote_addr.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # X-Forwarded-For có thể là "client, proxy1, proxy2" → lấy cái đầu
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"

# ─── Async helper ─────────────────────────────────────────────────────────────
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

async def process_update(data):
    app_bot = setup_application(BOT_TOKEN)
    await app_bot.initialize()
    try:
        update = Update.de_json(data, app_bot.bot)
        await app_bot.process_update(update)
    finally:
        await app_bot.shutdown()

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route(f"/webhook/<token>", methods=["POST"])
def webhook(token):
    if token != BOT_TOKEN:
        return Response("Unauthorized", status=401)
    data = request.get_json(force=True)
    if not data:
        return Response("Bad Request", status=400)
    try:
        run_async(process_update(data))
    except Exception as e:
        print(f"[webhook ERROR] {e}")
    return Response("OK", status=200)


@app.route("/set_webhook")
def set_webhook():
    base_url    = request.host_url.rstrip("/")
    webhook_url = f"{base_url}/webhook/{BOT_TOKEN}"

    async def _set():
        bot = Bot(token=BOT_TOKEN)
        async with bot:
            return await bot.set_webhook(url=webhook_url)

    try:
        ok = run_async(_set())
    except Exception as e:
        return f"Loi: {e}", 500

    if ok:
        return f"OK! Webhook: <code>{webhook_url}</code>"
    return "That bai", 500


@app.route("/webhook_info")
def webhook_info():
    async def _info():
        bot = Bot(token=BOT_TOKEN)
        async with bot:
            return await bot.get_webhook_info()

    try:
        info = run_async(_info())
        return f"<pre>{info.to_json()}</pre>"
    except Exception as e:
        return f"Loi: {e}", 500


# ─── /getkey – kiểm tra IP limit trước khi cho xem link ──────────────────────
@app.route("/getkey")
def getkey():
    id_key = request.args.get("user_id")
    if not id_key:
        return "Missing id_key parameter", 400

    # 1. Lấy IP thật
    user_ip = get_real_ip()

    # 2. Kiểm tra + tăng bộ đếm IP hôm nay
    allowed, count = check_and_inc_ip_limit(user_ip)

    if not allowed:
        # IP đã vượt quá 2 lần hôm nay → trả về trang cảnh báo
        return render_template(
            "ip_limit.html",
            ip=user_ip,
            limit=2,
            count=count,
        ), 429   # 429 Too Many Requests

    # 3. Lấy link từ Supabase
    res = supabase.table("external_link") \
        .select("*") \
        .eq("id", id_key) \
        .execute()

    if not res.data:
        return "Key not found", 404

    full_url = res.data[0].get("url_shorten_key")
    if not full_url:
        return "Shortened link not found", 404

    return render_template("getkey.html", full_url=full_url, ip=user_ip)


@app.route("/result_key")
def result_key():
    key = request.args.get("key")
    if not key:
        return "Missing key parameter", 400
    return render_template("result.html", key=key, ip=get_real_ip())


if __name__ == "__main__":
    app.run(debug=True, port=5000)