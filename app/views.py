from flask import request, abort, redirect
from telebot.types import Update

from app import app, models, db, bot, logger


@app.route('/', methods=['GET'])
def index():
    return redirect(f"https://t.me/{bot.user.username}")


# Process webhook calls
@app.route(app.config['URL_PATH'], methods=['POST'])
def webhook():
    if(request.headers.get('content-type') == 'application/json'):
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'ok'
    abort(403)
