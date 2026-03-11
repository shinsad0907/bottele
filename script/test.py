import requests
import telebot

TOKEN  = "8505349957:AAECbVyageqjiFttrODr0eHHcERkah-4MMU"
CHANNEL  = "@ClothessAI"

bot = telebot.TeleBot(TOKEN)

def check_join(user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    params = {
        "chat_id": CHANNEL,
        "user_id": user_id
    }

    r = requests.get(url, params=params).json()

    if r["ok"]:
        status = r["result"]["status"]
        return status in ["member", "administrator", "creator"]

    return False


@bot.message_handler(commands=['create'])
def create_image(message):
    user_id = message.from_user.id

    if not check_join(user_id):
        bot.reply_to(
            message,
            "❌ Bạn cần tham gia channel trước\nhttps://t.me/tenchannel"
        )
        return

    bot.reply_to(message, "🎨 Đang tạo ảnh AI cho bạn...")

    # code tạo ảnh của bạn ở đây


bot.infinity_polling()