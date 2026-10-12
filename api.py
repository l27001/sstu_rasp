#!env python3
import hashlib
import hmac
import json
import os
from functools import wraps
from urllib.parse import parse_qsl

import fastapi
import uvicorn
from fastapi import Form, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import methods


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def validate_data(init_data):
    if(not init_data):
        return None

    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = data.pop("hash")
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret_key = hmac.new(
            b"WebAppData",
            config.tg_info['access_token'].encode(),
            hashlib.sha256
        ).digest()
        expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if(not hmac.compare_digest(expected_hash, received_hash)):
            return None
        data['user'] = json.loads(data['user'])
        return data
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def database(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        database_connection = methods.Mysql()
        kwargs.update({"database": database_connection})
        try:
            return func(*args, **kwargs)
        finally:
            database_connection.close()
    return wrapper


class Subscribe(BaseModel):
    id: int = Form(gt=0)
    auth: str = Form()


api = fastapi.FastAPI(docs_url=None, redoc_url=None)
api.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@api.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE_DIR, "templates", "index.html"))


@api.get("/groups")
@api.get("/api/groups", include_in_schema=False)
@database
def groups(database=None):
    result = database.query(
        "SELECT `sstu_id` AS `id`, `name`, `form`, `type`, `course`, `institute`, `last_appearance` "
        "FROM `groups` WHERE `sstu_id` IS NOT NULL ORDER BY `institute`, `name`",
        fetchall=True
    )
    for group in result:
        group['last_appearance'] = group['last_appearance'].isoformat()
    return {"groups": result}


@api.post("/subscribe")
@api.post("/api/subscribe", include_in_schema=False)
@database
def subscribe(response: Response, sub: Subscribe, database=None):
    auth = validate_data(sub.auth)
    if(auth is None):
        response.status_code = 400
        return {"status": "fail", "message": "Откройте выбор групп через Telegram-бота"}

    group = database.query("SELECT `id`, `name` FROM `groups` WHERE `sstu_id` = %s", (sub.id, ))
    if(group is None):
        response.status_code = 404
        return {"status": "fail", "message": "Группа не найдена в базе. Обратитесь к разработчику"}

    user_id = auth['user']['id']
    database.getUserInfo(user_id)
    already_in = database.query(
        "SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (user_id, group['id'])
    )
    if(already_in is not None):
        return {"status": "fail", "message": "Эта группа уже выбрана вами!"}

    count = database.query(
        "SELECT COUNT(*) AS count FROM `group_subs` WHERE `user_id` = %s",
        (user_id, )
    )['count']
    if(count >= 5):
        return {"status": "fail", "message": "Вы достигли лимита групп!"}

    database.query(
        "INSERT INTO `group_subs` (`user_id`, `group_id`) VALUES (%s, %s)",
        (user_id, group['id'])
    )
    Tg = methods.Tg()
    Tg.sendMessage(user_id, f"🟢 Группа {group['name']} была отмечена как ваша!",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"),
            Tg.makeButton("❗ Подписаться на рассылку", f"toggle_sub/{group['id']}"),
            Tg.makeButton("⁉️ Что за рассылка?", "about"),
            Tg.makeButton("🗓️ Расписание группы", f"get_rasp/{group['id']}"), max_=1)))
    response.status_code = 201
    return {"status": "success", "message": f"Группа {group['name']} добавлена"}


if(__name__ == "__main__"):
    uvicorn.run(
        api,
        host="::",
        port=8124
    )
