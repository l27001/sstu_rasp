from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telebot.util import quick_markup

from config import WEBSERVER_HOST
from app import bot, db
from app.telebot_misc.callback_filter import split_inline_query
from app.telebot_misc.decorators import handle_error


@bot.message_handler(commands=['help', 'start', 'menu'])
@bot.message_handler(text=['🏠 Меню'])
@handle_error
def send_welcome(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(KeyboardButton("🔍 Найти группу"),
               KeyboardButton("❓ Ничего не понимаю"),
               KeyboardButton("📝 Мои группы"),
               KeyboardButton("🗒️ Расписание"))
    bot.reply_to(message, """👋 <b>Привет, я бот отслеживающий расписание СГТУ!</b>
Бота написал <a href="tg://user?id=731264169">L27001</a>, соотвественно со всем вопросами/багами/предложениями к нему.
\nДля просмотра расписания своей группы сначала необходимо привязать группу к аккаунту ТГ. Сделать это можно с помощью кнопок ниже.
\n<s>Этот текст всё-равно никто не читает :(</s>""", reply_markup=markup)


@bot.message_handler(text=['❓ Ничего не понимаю'])
@handle_error
def help(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    markup = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(KeyboardButton("🔍 Найти группу"),
               KeyboardButton("🏠 Меню"))
    bot.reply_to(message, """ℹ️ Этот бот парсит расписание с сайта https://rasp.sstu.ru в свою базу каждые N часов.
Затем вы можете узнать когда начинается первая пара, когда кончается последняя, сколько всего пар/какие и тд и тп. Всё это доступно прямо из мессенджера! Здорово правда?
В дополнение, вы можете <u>подписаться на рассылку</u>, чтобы бот сам присылал вам расписание в <u><b>19:00</b></u> по Саратовскому времени (+04 GMT).
\n<u><b>‼️ ВНИМАНИЕ</b>
Автор хоть и старается, но никак не может гарантировать точность/правильность предоставляемой информации! Учтите это.</u>""", reply_markup=markup)


@bot.message_handler(text=['🔍 Найти группу'])
@handle_error
def find_method(message):
    markup = quick_markup({"🤩 Выбор на сайте": {"web_app": WebAppInfo(f"https://{WEBSERVER_HOST}/select_group")},
                           "🔍 Поиск по параметрам": {"callback_data": "pre_find_abbr"}}, row_width=1)
    bot.reply_to(message, "🤔 Как будем искать?", reply_markup=markup)
