#!env python3
import fastapi, uvicorn, hashlib, hmac, json
from fastapi import Form, Response
from pydantic import BaseModel
from functools import wraps
from urllib.parse import unquote
import config, methods

def validate_data(check_string):
    if(check_string == ""): return None
    check_string = sorted([i for i in unquote(check_string).split("&")])
    data = {}
    for n in check_string:
        if(n.startswith("hash=")): hash = n.split("=", 1)[-1]
        data.update({n.split("=")[0]: n.split("=", 1)[1]})
    check_string.remove("hash="+hash)
    check_string = "\n".join(check_string)
    secret_key = hmac.new("WebAppData".encode(), config.tg_info['access_token'].encode(), hashlib.sha256).digest()
    check = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if(check == hash):
        data['user'] = json.loads(data['user'])
        return data
    return None

def database(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs.update({"database": methods.Mysql()})
        r = func(*args, **kwargs)
        kwargs['database'].close()
        return r
    return wrapper

class Subscribe(BaseModel):
    id: int = Form(gt=0)
    auth: str = Form()

api = fastapi.FastAPI(docs=None, redoc_url=None, root_path="/api")

@api.post("/subscribe")
@database
def subscribe(response: Response, sub: Subscribe, database = None):
    auth = validate_data(sub.auth)
    if(auth is None):
        response.status_code = 400
        return {"status": "fail", "message": "Invalid initData"}
    group = database.query("SELECT `id`, `name` FROM `groups` WHERE `sstu_id` = %s", (sub.id, ))
    if(group is None):
        response.status_code = 404
        return {"status": "fail", "message": "Группа не найдена в базе. Обратитесь к разработчику"}
    already_in = database.query("SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s", (auth['user']['id'], group['id']))
    if(already_in is not None):
        return {"status": "fail", "message": "Эта группа уже выбрана вами!"}
    count = database.query("SELECT COUNT(*) AS count FROM `group_subs` WHERE `user_id` = %s", (auth['user']['id'], ))['count']
    if(count > 5):
        return {"status": "fail", "message": "Вы достигли лимита групп!"}
    database.query("INSERT INTO `group_subs` (`user_id`, `group_id`) VALUES (%s, %s)", (auth['user']['id'], group['id']))
    Tg = methods.Tg()
    Tg.sendMessage(auth['user']['id'], f"🟢 Группа {group['name']} была отмечена как ваша!",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"),
            Tg.makeButton(f"❗ Подписаться на рассылку", f"toggle_sub/{group['id']}"),
            Tg.makeButton(f"⁉️ Что за рассылка?", "about"), Tg.makeButton("🗓️ Расписание группы", f"get_rasp/{group['id']}"), max_=1)))
    response.status_code = 201
    return {"status": "success", "message": "Успех!"}

uvicorn.run(
    api,
    host="::",
    port=8124,
    root_path="/api"
)
