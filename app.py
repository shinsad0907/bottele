from flask import Flask, request, Response, render_template
import asyncio
from supabase import create_client
from telegram import Update, Bot
from telegram.ext import Application
from script.bottele import WEB_BASE_URL, setup_application
import os

from script.create_key import KeyManager

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU")
SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
# API_TOKEN = "69ad89d5a7b0c143fe257cde"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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


@app.route("/getkey")
def getkey():

    id_key = request.args.get("id_key")
    if not id_key:
        return "Missing id_key parameter", 400

    res = supabase.table("external_link")\
        .select("*")\
        .eq("id", id_key)\
        .execute()

    if not res.data:
        return "Key not found", 404

    full_url = res.data[0].get("url_shorten_key")

    if not full_url:
        return "Shortened link not found", 404

    return render_template("getkey.html", link=full_url)

@app.route("/result_key")
def result_key():
    key = request.args.get("key")
    if not key:
        return "Missing key parameter", 400

    return render_template("getkey.html", link=key)

if __name__ == "__main__":
    app.run("index.html", debug=True, port=5000)