from telebot.types import Message, CallbackQuery

from app import bot, logger

def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            text = "⚠️ Произошла непредвиденная ошибка.\nОбратитесь к @l270011"
            if(type(args[0]) == Message):
                bot.send_message(args[0].chat.id, text)
            elif(type(args[0]) == CallbackQuery):
                bot.send_message(args[0].message.chat.id, text)
            else:
                bot.send_message(args[0].from_user.id, text)
    return wrapper
