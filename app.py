from flask import Flask, request, Response
import asyncio
from telegram import Update, Bot
from telegram.ext import Application
from script.bottele import setup_application
import os

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU")

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

@app.route("/")
def index():
    return "Bot dang chay!"

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
    base_url = request.host_url.rstrip("/")
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

if __name__ == "__main__":
    app.run(debug=True, port=5000)