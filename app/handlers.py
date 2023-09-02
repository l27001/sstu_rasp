from app import bot, db


@bot.message_handler(commands=['help', 'start', 'menu'])
def send_welcome(message):
    bot.reply_to(message, "Оно живое!")
