"""
Chạy bot bằng polling — dùng cho Railway/VPS, KHÔNG dùng cho Vercel
"""
import logging
import os
from script.bottele import setup_application

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU")

if __name__ == "__main__":
    app = setup_application(BOT_TOKEN)
    print("🤖 Bot dang chay (polling)...")
    app.run_polling(drop_pending_updates=True)