import logging
import telebot
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from telebot.storage import StatePickleStorage, StateRedisStorage
from telebot.custom_filters import StateFilter  


app = Flask(__name__, static_folder="static/")
gunicorn_error_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_error_logger.handlers
app.logger.setLevel(logging.DEBUG)
app.config.from_object('config')


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) | [%(levelname)s] - %(name)s \"%(message)s\"")
handler.setFormatter(formatter)
logger.addHandler(handler)


telebot.logger.setLevel(logging.INFO)
if(app.config['REDISSERVER'] is not None):
    state_storage = StateRedisStorage(host=app.config['REDISSERVER'], prefix="ssturasp_")
else:
    state_storage = StatePickleStorage()
bot = telebot.TeleBot(app.config['TG_TOKEN'],
                      state_storage=state_storage,
                      parse_mode='HTML',
                      num_threads=1,
                      allow_sending_without_reply=True)
bot.add_custom_filter(StateFilter(bot))


db = SQLAlchemy()
db.init_app(app)


from app import views, models, handlers