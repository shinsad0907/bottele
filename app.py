from flask import Flask, render_template, request, Response
from script.create_key import KeyManager
import asyncio
from telegram import Update, Bot
from telegram.ext import Application

# Import logic bot
from script.bottele import setup_application

app = Flask(__name__)
manager = KeyManager()

BOT_TOKEN = "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU"


def get_ip() -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    return ip


# ══════════════════════════════════════════════
#  HELPER: chạy async an toàn trên mọi môi trường
# ══════════════════════════════════════════════

def run_async(coro):
    """
    Chạy coroutine an toàn trên cả Vercel lẫn local.
    Vercel serverless: mỗi request là process riêng, không có running loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ══════════════════════════════════════════════
#  XỬ LÝ WEBHOOK — tạo Application mới mỗi request
#  (bắt buộc với serverless — KHÔNG dùng singleton)
# ══════════════════════════════════════════════

async def process_telegram_update(data: dict):
    """Khởi tạo, xử lý update, rồi shutdown gọn."""
    application: Application = setup_application(BOT_TOKEN)
    await application.initialize()
    try:
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    finally:
        await application.shutdown()


# ══════════════════════════════════════════════
#  WEB ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/getkey")
def getkey():
    ip = get_ip()
    base_url = request.host_url.rstrip("/")
    result   = manager.get_or_create_key(user=ip, ip=ip, full_url=base_url)
    link_key = result["link_key"]
    raw_key  = result["raw_key"]

    print(f"\n{'='*60}")
    print(f"  IP           : {ip}")
    print(f"  UUID Key     : {raw_key}")
    print(f"  Link rut gon : {link_key}")
    print(f"  Status       : {'Tao moi' if result['created'] else 'Lay lai cu'}")
    print(f"{'='*60}\n")

    return render_template("getkey.html", ip=ip, link_key=raw_key, full_url=link_key)


@app.route("/result/<raw_key>")
def result(raw_key: str):
    ip = get_ip()
    return render_template("result.html", ip=ip, key=raw_key)


# ══════════════════════════════════════════════
#  TELEGRAM WEBHOOK
# ══════════════════════════════════════════════

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Telegram gọi vào đây mỗi khi có tin nhắn/callback."""
    data = request.get_json(force=True)
    if not data:
        return Response("Bad Request", status=400)

    try:
        run_async(process_telegram_update(data))
    except Exception as e:
        # Vẫn trả 200 để Telegram không retry liên tục
        print(f"[webhook ERROR] {type(e).__name__}: {e}")

    return Response("OK", status=200)


@app.route("/set_webhook")
def set_webhook():
    """Gọi route này 1 lần để đăng ký webhook với Telegram."""
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
        return (f"Webhook set thanh cong!<br><code>{webhook_url}</code>")
    return "Set webhook that bai", 500


@app.route("/webhook_info")
def webhook_info():
    """Kiểm tra trạng thái webhook hiện tại."""
    async def _info():
        bot = Bot(token=BOT_TOKEN)
        async with bot:
            return await bot.get_webhook_info()

    try:
        info = run_async(_info())
    except Exception as e:
        return f"Loi: {e}", 500

    return f"<pre>{info.to_json()}</pre>"


if __name__ == "__main__":
    app.run(debug=True, port=5000)