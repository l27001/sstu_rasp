from methods import getUserInfo, getUserGroups, setUserState, sendErrorMessage
from datetime import date, timedelta, datetime

class MsgInfo(): pass

def execute_command(data):
    msg_info = MsgInfo()
    if('my_chat_member' in data):
        return None
    elif('message' in data):
        data = data['message']
        if('text' not in data): # исключение/добавление участника приходит с элементом message
            return None         # но без text в нём. Игнорируем такие события
        MsgInfo.from_user = data['from']['id']
        MsgInfo.from_chat = data['chat']['id']
        MsgInfo.is_chat = MsgInfo.from_chat < 0
        MsgInfo.text = data['text'].split()
        MsgInfo.msg_id = data['message_id']
        MsgInfo.user_info = getUserInfo(MsgInfo.from_user)
        MsgInfo.callback_data = None
        if(MsgInfo.is_chat == True and "reply_to_message" not in data):
            MsgInfo.text[0] = MsgInfo.text[0].split("@")
            if(len(MsgInfo.text[0]) > 1):
                if(MsgInfo.text[0][1] != Tg.username): # Фильтруем команды по тегу бота
                    return None                     # Пример: /status@first_bot и /status@second_bot
            MsgInfo.text[0] = MsgInfo.text[0][0] # убираем тег из команды
        if((MsgInfo.user_info['state'] != None or MsgInfo.is_chat == True) and MsgInfo.text[0][0] != "/"):
            try:
                return states[MsgInfo.user_info['state']](MsgInfo)
            except KeyError:
                return Tg.sendMessage(MsgInfo.from_chat, "⚠ Ожидается другое действие", reply_markup=Tg.generateInlineKeyb())
            except Exception as e:
                sendErrorMessage(MsgInfo.from_chat, e)
                return None
        cmd = MsgInfo.text[0].lower()
        del(MsgInfo.text[0])
        if(cmds.get(cmd) == None):
            if(MsgInfo.is_chat == False):
                Tg.sendMessage(MsgInfo.from_chat, "👎🏻 Не понял", reply_markup=Tg.generateInlineKeyb(), reply_to_message_id=MsgInfo.msg_id)
            return None
        try:
            cmds[cmd](MsgInfo)
        except Exception as e:
            sendErrorMessage(MsgInfo.from_chat, e)
            return None
    elif('callback_query' in data): # возможно объединить?
        if('message' in data['callback_query']):
            MsgInfo.from_user = data['callback_query']['message']['from']['id']
            MsgInfo.from_chat = data['callback_query']['message']['chat']['id']
            MsgInfo.text = data['callback_query']['message']['text']
            MsgInfo.msg_id = data['callback_query']['message']['message_id']
        else:
            MsgInfo.from_user = data['callback_query']['from']['id']
            MsgInfo.from_chat = MsgInfo.from_user
            MsgInfo.msg_id = 0
            MsgInfo.text = None
        MsgInfo.is_chat = MsgInfo.from_chat < 0
        MsgInfo.callback_data = data['callback_query']['data'].split("/")
        if(len(MsgInfo.callback_data) > 1):
            MsgInfo.callback_data[1] = MsgInfo.callback_data[1].split(",")
        MsgInfo.user_info = getUserInfo(MsgInfo.from_chat)
        try:
            return inlines[MsgInfo.callback_data[0]](MsgInfo)
        except Exception as e:
            sendErrorMessage(MsgInfo.from_chat, e)
            return None
    elif('inline_query' in data):
        MsgInfo.from_user = data['inline_query']['from']['id']
        MsgInfo.is_chat = True
        MsgInfo.query = data['inline_query']['query']
        MsgInfo.query_id = data['inline_query']['id']
        res = mysql.query("SELECT `id`, `name` FROM `groups` WHERE `name` LIKE %s LIMIT 10",
            ("%"+MsgInfo.query.replace(" ", "%")+"%", ), fetchall=True)
        answers = []
        if(res is None or res == ()):
            answers = []
        else:
            for i in res:
                MsgInfo.callback_data = [None, [i['id']]]
                msg, _ = get_rasp(MsgInfo)
                answers.append(Tg.inlineQueryResult("article", i['id'], title=i['name'],
                    input_message_content={"message_text": msg, "parse_mode": "Markdown"}))
        Tg.answerInlineQuery(MsgInfo.query_id, answers, cache_time=3600, switch_pm_parameter="1", switch_pm_text="🏠 Перейти к боту")

###
def menu(MsgInfo):
    setUserState(MsgInfo.from_chat, None)
    menu_text = """👋 Привет, я бот отслеживающий расписание СГТУ!
<s>Идеи Щавеля не будут забыты!</s> Бота написал <a href="tg://user?id=731264169">вот он</a>, соотвественно за вопросами/с багами/предложениями к нему.
\nДля просмотра расписания своей группы сначала необходимо привязать группу к аккаунту ТГ. Сделать это можно с помощью кнопок ниже.
\nПроект является <b><u>BETA</u></b> версией, стабильность не гарантируется!"""
    menu_keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔍 Найти группу", "start_find"),
        Tg.makeButton("❓ Ничего не понимаю", "about"),
        Tg.makeButton("📝 Мои группы", "mg"),
        Tg.makeButton("🗒️ Расписание", "rasp"), max_=2), home=False)
    Tg.editOrSend(MsgInfo, menu_text, reply_markup=menu_keyb, parse_mode="HTML")

def about(MsgInfo):
    text = """ℹ️ Этот бот проверяет сайт https://rasp.sstu.ru каждые N минут (часов, дней...) и парсит расписание в свою базу.
Затем вы можете узнать когда у тебя первая пара, когда последняя, сколько всего пар/какие и тд и тп. Всё это доступно прямо из мессенджера! Здорово правда?
В дополнение, ты можешь подписаться на рассылку, чтобы бот сам присылал тебе расписание в определённое время (19:00)!
\n<u><b>‼️ ВНИМАНИЕ</b>
Автор хоть и старается, но никак не может гарантировать точность/правильность предоставляемой информации! Учтите это.</u>"""
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb(), parse_mode="HTML")

def start_find(MsgInfo):
    rows = Tg.makeRows(Tg.makeButton("🔍 Поиск по параметрам", "pre_find_abbr"), Tg.makeButton("❕ Я знаю ID группы", "find_by_id"))
    Tg.editOrSend(MsgInfo, "🤔 Как будем искать?:",
        reply_markup=Tg.generateInlineKeyb(rows))

def info(MsgInfo):
    txt = f"ℹ️ Информация\nID: {MsgInfo.from_user}\nЧат: {MsgInfo.is_chat}/{MsgInfo.from_chat}"
    Tg.editOrSend(MsgInfo, txt)

def pre_find_abbr(MsgInfo):
    setUserState(MsgInfo.from_chat, "sa")
    text = "ℹ️ Отправь аббревиатуру твоего направления (Прим: ИФСТ, СЗС, АРХТ)"
    if(MsgInfo.is_chat == True):
        text += "\n_P.S. В беседе необходимо ответить на сообщение чтобы бот его увидел!_"
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb())

def find_by_id(MsgInfo):
    setUserState(MsgInfo.from_chat, "fid")
    rows = Tg.makeRows(Tg.makeButton("❔ Где взять ID группы?", "where_id"))
    text = "📧 Отправь ID группы"
    if(MsgInfo.is_chat == True):
        text += "\n_P.S. В беседе необходимо ответить на сообщение чтобы бот его увидел!_"
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb(rows))

def select_by_id(MsgInfo): # вынести выбор группы в отдельную функцию
    rows = Tg.makeRows(Tg.makeButton("❔ Сложно? Жми", "pre_find_abbr"))
    try:
        id_ = int(MsgInfo.text[0])
        if(id_ < 1): raise
    except: return Tg.editOrSend(MsgInfo, "⚠ Некорректный ID группы", reply_markup=Tg.generateInlineKeyb(rows))
    grp_name = mysql.query("SELECT `name` FROM `groups` WHERE `id` = %s", (id_, ))
    if(grp_name is None or grp_name == ()):
        return Tg.editOrSend(MsgInfo, "🔴 Группа не существует", reply_markup=Tg.generateInlineKeyb(rows))
    else: grp_name = grp_name['name']
    count = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `user_id` = %s", (MsgInfo.from_chat, ))['COUNT(*)']
    if(count >= 5):
        return Tg.editOrSend(MsgInfo, "🔴 Ты достиг лимита групп!",
            reply_markup=Tg.generateInlineKeyb())
    already_in = mysql.query("SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (MsgInfo.from_chat, id_))
    if(already_in is not None):
        return Tg.editOrSend(MsgInfo, "🔴 Эта группа уже выбрана тобой!",
            reply_markup=Tg.generateInlineKeyb(rows))
    setUserState(MsgInfo.from_chat, None)
    mysql.query("INSERT INTO `group_subs` (`user_id`, `group_id`) VALUES (%s, %s)", (MsgInfo.from_chat, id_))
    Tg.editOrSend(MsgInfo, f"🟢 Группа {grp_name} была отмечена как твоя!",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"),
            Tg.makeButton(f"❗ Подписаться на рассылку", f"toggle_sub/{id_}"),
            Tg.makeButton(f"⁉️ Что за рассылка?", "about"), max_=1)))

def where_id(MsgInfo):
    rows = Tg.makeRows(Tg.makeButton("❔ Сложно? Жми", "pre_find_abbr"))
    Tg.editOrSend(MsgInfo, MsgInfo.text+"\n\n❔ ID группы можно спросить у однокурсника, который уже выбрал группу,\
либо посмотреть на сайте https://rasp.sstu.ru\n Открыв расписание своей группы ты увидишь в адресной строке \
URL: `https://rasp.sstu.ru/rasp/group/130` где `130` номер группы.", reply_markup=Tg.generateInlineKeyb(rows))

def select_abbr_name(MsgInfo):
    types = mysql.query("SELECT DISTINCT `type` FROM `groups` WHERE `group_start` = %s", (MsgInfo.text[0], ), fetchall=True)
    if(len(types) == 0):
        Tg.editOrSend(MsgInfo, "⚠ Групп с такой аббревиатурой не найдено. Попробуй ещё раз.")
    else:
        rows = Tg.makeRows([Tg.makeButton(i['type'], f"sa_c/{MsgInfo.text[0]},{i['type']}") for i in types], max_=2)
        Tg.editOrSend(MsgInfo, "ℹ️ Выбери тип обучения:", reply_markup=Tg.generateInlineKeyb(rows))

def select_course(MsgInfo):
    setUserState(MsgInfo.from_chat, f"{MsgInfo.callback_data[0]}/{','.join(MsgInfo.callback_data[1])}")
    courses = mysql.query("SELECT DISTINCT `course` FROM `groups` WHERE `group_start` = %s AND `type` = %s ORDER BY `course`",
        (MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][1]), fetchall=True)
    rows = Tg.makeRows([Tg.makeButton(i['course'], f"sa_c1/{','.join(MsgInfo.callback_data[1])},{i['course']}") for i in courses])
    Tg.editOrSend(MsgInfo, "ℹ️ Выбери курс:", reply_markup=Tg.generateInlineKeyb(rows))

def select_group(MsgInfo):
    setUserState(MsgInfo.from_chat, f"{MsgInfo.callback_data[0]}/{','.join(MsgInfo.callback_data[1])}")
    groups = mysql.query("SELECT `id`,`name` FROM `groups` WHERE `group_start` = %s AND `type` = %s AND `course` = %s ORDER BY `name`",
        (MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][1], MsgInfo.callback_data[1][2]), fetchall=True)
    rows = Tg.makeRows([Tg.makeButton(i['name'], f"cg/{i['id']}") for i in groups], max_=2)
    Tg.editOrSend(MsgInfo, "Наконец, выбери свою группу:",
        reply_markup=Tg.generateInlineKeyb(rows, Tg.makeRows(Tg.makeButton("🔙 Искать заново", "pre_find_abbr"))))

def confirm_group(MsgInfo): # вынести выбор группы в отдельную функцию
    setUserState(MsgInfo.from_chat, None)
    count = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `user_id` = %s", (MsgInfo.from_chat, ))['COUNT(*)']
    if(count >= 5):
        return Tg.editOrSend(MsgInfo, "🔴 Ты достиг лимита групп!", reply_markup=Tg.generateInlineKeyb())
    already_in = mysql.query("SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    if(already_in is not None):
        return Tg.editOrSend(MsgInfo, "🔴 Эта группа уже выбрана тобой!",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Искать заново", "pre_find_abbr"))))
    mysql.query("INSERT INTO `group_subs` (`user_id`, `group_id`) VALUES (%s, %s)", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    Tg.editOrSend(MsgInfo, "🟢 Группа была отмечена как твоя!",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"),
            Tg.makeButton(f"❗ Подписаться на рассылку", f"toggle_sub/{MsgInfo.callback_data[1][0]}"),
            Tg.makeButton(f"⁉️ Что за рассылка?", "about"), max_=1)))

def my_groups(MsgInfo):
    groups = getUserGroups(MsgInfo.from_chat)
    msg = []; buttons = []
    for g in groups:
        if(g['subscribe'] == False):
            sub = "_Не подписан_"
        else: sub = "_Подписан_"
        msg.append(f"ID - `{g['id']}` | {g['name']} | {sub}")
        buttons.append(Tg.makeButton(g['name'], f"chk_grp/{g['id']}"))
    if(groups is None or groups == ()):
        msg = ["*Нет групп*"]
        buttons.append(Tg.makeButton("🔍 Найти группу", "start_find"))
    msg = "📝 Твои группы:\n"+"\n".join(msg)
    keyb = Tg.generateInlineKeyb(Tg.makeRows(buttons, max_=2))
    Tg.editOrSend(MsgInfo, msg, reply_markup=keyb)

def check_group(MsgInfo):
    group = mysql.query("SELECT gg.*, gs.* FROM `groups` gg INNER JOIN `group_subs` gs ON gs.group_id = gg.id WHERE `id` = %s", (MsgInfo.callback_data[1][0], ))
    if(group is None or group == ()):
        return Tg.editOrSend(MsgInfo, "⚠ Не удалось получить информацию о группе. Вернитесь в меню", reply_markup=Tg.generateInlineKeyb())
    count = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `group_id` = %s", (group['id'], ))
    if(group['subscribe'] == False):
        sub = "_Не подписан_"
        toggle = "Подписаться на рассылку"
    else:
        sub = "_Подписан_"
        toggle = "Отписаться от рассылки"
    msg = f"""📙 Группа {group['name']}
- ID: `{group['id']}`
- Форма: {group['form']}
- Тип: {group['type']}
- Рассылка: {sub}
- Институт: {group['institute']}
- Человек в группе (согласно локальной базе): {count['COUNT(*)']}"""
    rows = Tg.makeRows(Tg.makeButton("🗑️ Удалить группу", f"del_grp/{group['id']}"),
        Tg.makeButton(f"❗ {toggle}", f"toggle_sub/{group['id']}"),
        Tg.makeButton(f"⁉️ Что за рассылка?", "about"),
        Tg.makeButton("🔙 Вернуться к списку групп", "mg"),
        Tg.makeButton("🗒️ Расписание группы", f"get_rasp/{group['id']}"), max_=2)
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(rows))

def del_group(MsgInfo):
    mysql.query("DELETE FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Вернуться к списку групп", "mg"), max_=2))
    Tg.editOrSend(MsgInfo, "🟢 Группа была откреплена от этого профиля!", reply_markup=keyb)

def toggle_subscribtion(MsgInfo):
    mysql.query("UPDATE `group_subs` SET `subscribe` = !subscribe WHERE `user_id` = %s AND `group_id` = %s",
        (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Вернуться к группе", f"chk_grp/{MsgInfo.callback_data[1][0]}")))
    Tg.editOrSend(MsgInfo, "🟢 Параметры подписки изменены!", reply_markup=keyb)

def rasp(MsgInfo):
    groups = getUserGroups(MsgInfo.from_chat)
    buttons = []
    msg = "🔘 Выбери группу расписание которой ты хочешь увидеть:"
    for g in groups:
        buttons.append(Tg.makeButton(g['name'], f"get_rasp/{g['id']}"))
    if(groups is None or groups == ()):
        msg = "*Нет групп*"
        buttons.append(Tg.makeButton("🔍 Найти группу", "start_find"))
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(Tg.makeRows(buttons, max_=2)))

def get_rasp(MsgInfo):
    group = mysql.query("SELECT * FROM `groups` WHERE `id` = %s", (MsgInfo.callback_data[1][0], ))
    if(group is None):
        if(MsgInfo.callback_data[0] == None):
            return "⚠ Не удалось получить информацию о группе.", Tg.generateInlineKeyb(empty=True)
        return Tg.editOrSend(MsgInfo, "⚠ Не удалось получить информацию о группе.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"), Tg.makeButton("🔙 Вернуться", "rasp"))))
    i = 0; buttons = []; msg = []
    while len(msg) < 6:
        if(i > 8):
            if(len(msg) == 0):
                if(MsgInfo.callback_data[0] == None):
                    return "⚠ Похоже, расписания на ближайшие дни нет", Tg.generateInlineKeyb(empty=True)
                return Tg.editOrSend(MsgInfo, "⚠ Похоже, расписания на ближайшие дни нет",
                    reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🗒️ Меню расписания", "rasp"))))
            else:
                break
        day = mysql.query("SELECT `date`, `type`, `name`, `weekday`, `lesson_num`, `time_start`, `time_end` FROM lessons WHERE `group_id` = %s AND `date` = %s ORDER BY `lesson_num`",
            (group['id'], (date.today()+timedelta(days=i)).isoformat()), fetchall=True)
        i += 1
        if(day is None or day == ()): continue
        les = "\n".join([f"[{l['lesson_num']}] {l['name']} {l['type']}" for l in day])
        day = {'info': {'date': day[0]['date'], 'weekday': day[0]['weekday'], 'count': len(day),
                'time_start': datetime.strptime(f"{day[0]['date']} {day[0]['time_start']}", "%Y-%m-%d %H:%M:%S"),
                'time_end': datetime.strptime(f"{day[-1]['date']} {day[-1]['time_end']}", "%Y-%m-%d %H:%M:%S")}}
        buttons.append(Tg.makeButton(f"➡️ {day['info']['date'].strftime('%d.%m')} ({day['info']['weekday']})", f"date_rasp/{group['id']},{day['info']['date'].strftime('%Y-%m-%d')}"))
        if(len(msg) >= 2): continue
        weather = mysql.query("SELECT `temp`,`weather` FROM `weather` WHERE `date` BETWEEN %s AND %s",
            (day['info']['time_start'].strftime('%Y-%m-%d %H:%M:%S'), day['info']['time_end'].strftime('%Y-%m-%d %H:%M:%S')))
        if(weather == None):
            weather = {"temp": 0, "weather": "Нет данных"}
        day.update({'weather': weather})
        msg.append(f"""- День: *{day['info']['weekday']} {day['info']['date']}*
- Кол-во пар: {day['info']['count']}
- Первая пара: {day['info']['time_start'].strftime("%H:%M")}
- Последняя пара: {day['info']['time_end'].strftime("%H:%M")}
- Погода: {day['weather']['weather']} {day['weather']['temp']}°C
- Пары:
_{les}_
""")
    last_upd = group['last_appearance'].strftime("%Y-%m-%d %H:%M")
    buttons = Tg.makeRows(buttons, max_=2) + Tg.makeRows(Tg.makeButton("🌐 Расписание на неделю", web_app={"url": f"https://rasp.sstu.ru/rasp/group/{group['id']}"})) + Tg.makeRows(Tg.makeButton("🔙 Вернуться", "rasp"), Tg.makeButton("🏠 Меню", "clear_state"))
    msg = f"🗓️ Общая информация для *{group['name']}*\n---------------------\n" + "---------------------\n".join(msg)
    msg += f"---------------------\n- Последнее обновление: {last_upd}"
    if(MsgInfo.callback_data[0] == None):
        return msg, Tg.generateInlineKeyb(buttons)
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(buttons, home=False))

def date_rasp(MsgInfo):
    rasp = mysql.query("SELECT l.*, g.last_appearance, g.name AS gname FROM `lessons` l INNER JOIN `groups` g ON l.group_id = g.id WHERE `date` = %s AND `group_id` = %s ORDER BY `lesson_num`",
        (MsgInfo.callback_data[1][1], MsgInfo.callback_data[1][0]), fetchall=True)
    if(rasp is None or rasp == ()):
        return Tg.editOrSend(MsgInfo, "⚠ Не удалось получить информацию о расписании.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"), Tg.makeButton("🔙 Вернуться", "rasp"))))
    msg = []
    now = datetime.now()
    for i in range(len(rasp)):
        flag = ""
        rasp[i].update({"time_start": datetime.strptime(f"{rasp[i]['date']} {rasp[i]['time_start']}", "%Y-%m-%d %H:%M:%S"),
        "time_end": datetime.strptime(f"{rasp[i]['date']} {rasp[i]['time_end']}", "%Y-%m-%d %H:%M:%S")})
        if(rasp[i]['time_start'] < now < rasp[i]['time_end']):
            flag = "*Текущая пара*\n"
        elif(i > 0 and rasp[i-1]['time_end'] <= now <= rasp[i]['time_start']):
            flag = "*Следующая пара*\n"
        msg.append(f"""{flag}Предмет: {rasp[i]['name']}/{rasp[i]['type']}
Время: {rasp[i]['time_start'].strftime("%H:%M")} - {rasp[i]['time_end'].strftime("%H:%M")}
Аудитория: {rasp[i]['room']}
Преподаватель: {rasp[i]['teacher']}""")
    last_upd = rasp[0]['last_appearance'].strftime("%Y-%m-%d %H:%M")
    msg = f"🗓️ *{rasp[0]['gname']} {MsgInfo.callback_data[1][1]} {rasp[0]['weekday']}*\n---------------------\n"+"\n---------------------\n".join(msg)
    msg += f"\n---------------------\nПоследнее обновление: {last_upd}"
    buttons = Tg.makeRows(Tg.makeButton("🗒️ Меню расписания", "rasp"), Tg.makeButton("🔙 Вернуться", f"get_rasp/{MsgInfo.callback_data[1][0]}"))
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(buttons))

### Список команд
cmds = {'/start':menu,
        '/menu':menu,
        '/info':info,
        '/find':start_find,
        '/groups':my_groups,
        '/rasp':rasp,
}

### Список inline действий
inlines = {
        'start_find':start_find,
        'clear_state':menu,
        'about':about,
        'pre_find_abbr':pre_find_abbr,
        'find_by_id':find_by_id,
        'sa_c':select_course,
        'sa_c1':select_group,
        'cg':confirm_group,
        'where_id':where_id,
        'mg':my_groups,
        'chk_grp':check_group,
        'del_grp':del_group,
        'toggle_sub':toggle_subscribtion,
        'rasp':rasp,
        'get_rasp':get_rasp,
        'date_rasp':date_rasp
}

### Список состояний
states = {
        'sa':select_abbr_name,
        'fid':select_by_id
}

###
# sa = select_abbr
# cg = confirm group
# mg = my groups
# fid = find by id
