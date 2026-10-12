#!env python3
import hashlib
import hmac
import json
import os
from datetime import date, datetime, timedelta
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


class AuthRequest(BaseModel):
    auth: str = Form()


class GroupAction(AuthRequest):
    id: int = Form(gt=0)


api = fastapi.FastAPI(docs_url=None, redoc_url=None)
api.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@api.get("/", include_in_schema=False)
@api.get("/my", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE_DIR, "templates", "index.html"))


@api.get("/group/{group_id}", include_in_schema=False)
def group_page(group_id: int):
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


def authenticated_user(response, auth_value, database):
    auth = validate_data(auth_value)
    if(auth is None):
        response.status_code = 401
        return None
    user_id = auth['user']['id']
    database.getUserInfo(user_id)
    return user_id


def format_time(value):
    if(isinstance(value, timedelta)):
        total_minutes = int(value.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours % 24:02d}:{minutes:02d}"
    if(hasattr(value, "strftime")):
        return value.strftime("%H:%M")
    return str(value)[:5]


def serialize_schedule(rows):
    days = []
    current = None
    for row in rows:
        day_key = row['date'].isoformat()
        if(current is None or current['date'] != day_key):
            current = {
                "date": day_key,
                "weekday": row['weekday'],
                "lessons": []
            }
            days.append(current)
        current['lessons'].append({
            "number": row['lesson_num'],
            "start": format_time(row['time_start']),
            "end": format_time(row['time_end']),
            "name": row['name'],
            "type": row['type'],
            "room": row['room'],
            "room_token": row.get('room_token'),
            "teacher": row['teacher'],
            "teacher_token": row.get('teacher_token'),
            "group": row.get('group_name')
        })
    return days


def add_weather(database, days):
    for day in days:
        if(not day['lessons']):
            continue
        weather = database.query(
            "SELECT `temp`, `weather` FROM `weather` WHERE DATE(`date`) = %s "
            "ORDER BY ABS(TIME_TO_SEC(TIME(`date`)) - TIME_TO_SEC(%s)) LIMIT 1",
            (day['date'], day['lessons'][0]['start'])
        )
        if(weather is not None):
            day['weather'] = weather
    return days


@api.post("/me/groups")
@api.post("/api/me/groups", include_in_schema=False)
@database
def my_groups(response: Response, body: AuthRequest, database=None):
    user_id = authenticated_user(response, body.auth, database)
    if(user_id is None):
        return {"status": "fail", "message": "Откройте приложение через Telegram-бота"}
    result = database.query(
        "SELECT g.`sstu_id` AS `id`, g.`name`, g.`form`, g.`type`, g.`course`, g.`institute`, "
        "gs.`subscribe`, g.`last_appearance` FROM `group_subs` gs "
        "INNER JOIN `groups` g ON g.`id` = gs.`group_id` "
        "WHERE gs.`user_id` = %s AND g.`sstu_id` IS NOT NULL ORDER BY g.`name`",
        (user_id, ), fetchall=True
    )
    for group in result:
        group['subscribe'] = bool(group['subscribe'])
        group['last_appearance'] = group['last_appearance'].isoformat()
    return {"status": "success", "groups": result}


@api.post("/group/remove")
@api.post("/api/group/remove", include_in_schema=False)
@database
def remove_group(response: Response, body: GroupAction, database=None):
    user_id = authenticated_user(response, body.auth, database)
    if(user_id is None):
        return {"status": "fail", "message": "Необходима авторизация Telegram"}
    group = database.query("SELECT `id` FROM `groups` WHERE `sstu_id` = %s", (body.id, ))
    if(group is None):
        response.status_code = 404
        return {"status": "fail", "message": "Группа не найдена"}
    subscription = database.query(
        "SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (user_id, group['id'])
    )
    if(subscription is None):
        response.status_code = 404
        return {"status": "fail", "message": "Группа уже удалена"}
    database.query(
        "DELETE FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (user_id, group['id'])
    )
    return {"status": "success", "message": "Группа удалена"}


@api.post("/group/toggle-notifications")
@api.post("/api/group/toggle-notifications", include_in_schema=False)
@database
def toggle_notifications(response: Response, body: GroupAction, database=None):
    user_id = authenticated_user(response, body.auth, database)
    if(user_id is None):
        return {"status": "fail", "message": "Необходима авторизация Telegram"}
    database.query(
        "UPDATE `group_subs` gs INNER JOIN `groups` g ON g.`id` = gs.`group_id` "
        "SET gs.`subscribe` = !gs.`subscribe` WHERE gs.`user_id` = %s AND g.`sstu_id` = %s",
        (user_id, body.id)
    )
    state = database.query(
        "SELECT gs.`subscribe` FROM `group_subs` gs INNER JOIN `groups` g ON g.`id` = gs.`group_id` "
        "WHERE gs.`user_id` = %s AND g.`sstu_id` = %s",
        (user_id, body.id)
    )
    if(state is None):
        response.status_code = 404
        return {"status": "fail", "message": "Сначала добавьте группу"}
    enabled = bool(state['subscribe'])
    return {
        "status": "success",
        "subscribe": enabled,
        "message": "Рассылка включена" if enabled else "Рассылка отключена"
    }


@api.get("/group/{group_id}/schedule")
@api.get("/api/group/{group_id}/schedule", include_in_schema=False)
@database
def group_schedule(group_id: int, response: Response, database=None):
    group = database.query(
        "SELECT `id`, `sstu_id`, `name`, `form`, `type`, `course`, `institute`, `last_appearance` "
        "FROM `groups` WHERE `sstu_id` = %s",
        (group_id, )
    )
    if(group is None):
        response.status_code = 404
        return {"status": "fail", "message": "Группа не найдена"}
    rows = database.query(
        "SELECT `date`, `weekday`, `lesson_num`, `time_start`, `time_end`, `name`, `type`, `room`, `teacher`, "
        "MD5(LOWER(`room`)) AS `room_token`, MD5(LOWER(`teacher`)) AS `teacher_token` "
        "FROM `lessons` WHERE `group_id` = %s AND `date` >= %s ORDER BY `date`, `lesson_num`",
        (group['id'], date.today().isoformat()), fetchall=True
    )
    group['id'] = group['sstu_id']
    del(group['sstu_id'])
    group['last_appearance'] = group['last_appearance'].isoformat()
    days = add_weather(database, serialize_schedule(rows))
    return {"status": "success", "group": group, "days": days}


def entity_field(kind):
    return {"room": "room", "teacher": "teacher"}.get(kind)


@api.get("/entities")
@api.get("/api/entities", include_in_schema=False)
@database
def entities(kind: str, q: str = "", database=None):
    field = entity_field(kind)
    query = q.strip()
    if(field is None or len(query) < 2):
        return {"entities": []}
    result = database.query(
        f"SELECT `{field}` AS `value`, MD5(LOWER(`{field}`)) AS `token`, MIN(`date`) AS `next_date` "
        f"FROM `lessons` WHERE `date` >= %s AND `{field}` LIKE %s AND `{field}` NOT IN ('', 'Нет данных') "
        f"GROUP BY `{field}` ORDER BY `next_date`, `{field}` LIMIT 30",
        (date.today().isoformat(), "%"+query+"%"), fetchall=True
    )
    for item in result:
        item['next_date'] = item['next_date'].isoformat()
    return {"entities": result}


@api.get("/entity/{kind}/{token}/schedule")
@api.get("/api/entity/{kind}/{token}/schedule", include_in_schema=False)
@database
def entity_schedule(kind: str, token: str, response: Response, database=None):
    field = entity_field(kind)
    if(field is None or len(token) != 32):
        response.status_code = 400
        return {"status": "fail", "message": "Некорректный тип поиска"}
    entity = database.query(
        f"SELECT `{field}` AS `value` FROM `lessons` "
        f"WHERE MD5(LOWER(`{field}`)) = %s AND `date` >= %s LIMIT 1",
        (token, date.today().isoformat())
    )
    if(entity is None):
        response.status_code = 404
        return {"status": "fail", "message": "Актуальное расписание не найдено"}
    rows = database.query(
        f"SELECT l.`date`, l.`weekday`, l.`lesson_num`, l.`time_start`, l.`time_end`, l.`name`, "
        f"l.`type`, l.`room`, l.`teacher`, MD5(LOWER(l.`room`)) AS `room_token`, "
        f"MD5(LOWER(l.`teacher`)) AS `teacher_token`, g.`name` AS `group_name` FROM `lessons` l "
        f"INNER JOIN `groups` g ON g.`id` = l.`group_id` "
        f"WHERE MD5(LOWER(l.`{field}`)) = %s AND l.`date` >= %s "
        f"ORDER BY l.`date`, l.`lesson_num`, g.`name`",
        (token, date.today().isoformat()), fetchall=True
    )
    days = add_weather(database, serialize_schedule(rows))
    return {"status": "success", "kind": kind, "value": entity['value'], "days": days}


@api.get("/stats")
@api.get("/api/stats", include_in_schema=False)
@database
def stats(database=None):
    return {
        "groups": database.query("SELECT COUNT(*) AS count FROM `groups` WHERE `sstu_id` IS NOT NULL")['count'],
        "lessons": database.query("SELECT COUNT(*) AS count FROM `lessons` WHERE `date` >= CURDATE()")['count'],
        "users": database.query("SELECT COUNT(*) AS count FROM `users`")['count'],
        "updated": database.query("SELECT MAX(`last_appearance`) AS value FROM `groups`")['value'].isoformat()
    }


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
        host="0.0.0.0",
        port=8124
    )
