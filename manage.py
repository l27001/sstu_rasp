#!env python
import time
from flask.cli import FlaskGroup

from app import app, bot, db, logger, parser


cli = FlaskGroup(app)


@cli.command("create_db")
def create_db():
    db.create_all()
    db.session.commit()
    logger.info("DB tables created successfully!")


@cli.command("drop_db")
def create_db():
    db.drop_all()
    db.session.commit()
    logger.info("DB tables dropped successfully!")


@cli.command("setup_webhook")
def setup_webhook():
    bot.remove_webhook()
    time.sleep(0.1)
    if(bot.set_webhook(url=f"https://{app.config['WEBSERVER_HOST']}{app.config['URL_PATH']}")):
        logger.info("Webhook created successfully!")
    else:
        logger.warn("Failed to create webhook!")


@cli.command("parse")
def do_parse():
    parser.do_parse()


@cli.command("parse_weather")
def parse_weather():
    parser.parse_weather()


@cli.command("init_scheduler")
def init_scheduler():
    parser.run_scheduler()


if(__name__ == "__main__"):
    cli()
