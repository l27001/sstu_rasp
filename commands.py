from time import sleep
from methods import Mysql, sendErrorMessage
from datetime import date, timedelta, datetime
from html import escape

class MsgInfoClass(): pass

def execute_command(logger, Tg, data):
    MsgInfo = MsgInfoClass()
    mysql = Mysql()
    if('my_chat_member' in data):
        mysql.close()
        return None
    elif('message' in data):
        data = data['message']
        if('text' not in data): # исключение/добавление участника приходит с элементом message
            mysql.close()   # но без text в нём. Игнорируем такие события
            return None
        MsgInfo.from_user = data['from']['id']
        MsgInfo.from_chat = data['chat']['id']
        MsgInfo.is_chat = MsgInfo.from_chat < 0
        MsgInfo.text = data['text'].split()
        MsgInfo.msg_id = data['message_id']
        # Состояния сохраняются по идентификатору чата (в личке он равен user id).
        MsgInfo.user_info = mysql.getUserInfo(MsgInfo.from_chat)
        MsgInfo.callback_data = None
        if(MsgInfo.is_chat == True and "reply_to_message" not in data):
            MsgInfo.text[0] = MsgInfo.text[0].split("@")
            if(len(MsgInfo.text[0]) > 1):
                if(MsgInfo.text[0][1] != Tg.username): # Фильтруем команды по тегу бота
                    mysql.close()   # Пример: /status@first_bot и /status@second_bot
                    return None
            MsgInfo.text[0] = MsgInfo.text[0][0] # убираем тег из команды
        if((MsgInfo.user_info['state'] != None or MsgInfo.is_chat == True) and MsgInfo.text[0][0] != "/"):
            try:
                res = states[MsgInfo.user_info['state']](logger, mysql, Tg, MsgInfo)
                mysql.close()
                return res
            except KeyError:
                mysql.close()
                return Tg.sendMessage(MsgInfo.from_chat, "⚠ Ожидается другое действие", reply_markup=Tg.generateInlineKeyb())
            except Exception as e:
                mysql.close()
                sendErrorMessage(logger, MsgInfo.from_chat, e)
                return None
        cmd = MsgInfo.text[0].lower()
        del(MsgInfo.text[0])
        if(cmds.get(cmd) == None):
            mysql.close()
            if(MsgInfo.is_chat == False):
                Tg.sendMessage(MsgInfo.from_chat, "👎🏻 Неизвестная команда", reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔍 Найти группу", "start_find"), Tg.makeButton("🔎 Найти аудиторию/преподавателя", "schedule_search"), Tg.makeButton("📝 Мои группы", "mg"), max_=1)), reply_to_message_id=MsgInfo.msg_id)
            return None
        try:
            cmds[cmd](logger, mysql, Tg, MsgInfo)
        except Exception as e:
            mysql.close()
            sendErrorMessage(logger, MsgInfo.from_chat, e)
            return None
    elif('callback_query' in data): # возможно объединить?
        if('message' in data['callback_query']):
            MsgInfo.message = data['callback_query']['message']
            MsgInfo.from_user = data['callback_query']['from']['id']
            MsgInfo.from_chat = data['callback_query']['message']['chat']['id']
            if('text' in data['callback_query']['message']):
                MsgInfo.text = data['callback_query']['message']['text']
            else:
                MsgInfo.text = None
            if('caption' in data['callback_query']['message']):
                MsgInfo.text = data['callback_query']['message']['caption']
            else:
                MsgInfo.text = None
            MsgInfo.msg_id = data['callback_query']['message']['message_id']
        else:
            MsgInfo.from_user = data['callback_query']['from']['id']
            MsgInfo.from_chat = MsgInfo.from_user
            MsgInfo.message = None
            MsgInfo.msg_id = 0
            MsgInfo.text = None
        MsgInfo.is_chat = MsgInfo.from_chat < 0
        MsgInfo.callback_data = data['callback_query']['data'].split("/")
        if(len(MsgInfo.callback_data) > 1):
            MsgInfo.callback_data[1] = MsgInfo.callback_data[1].split(",")
        MsgInfo.user_info = mysql.getUserInfo(MsgInfo.from_chat)
        try:
            res = inlines[MsgInfo.callback_data[0]](logger, mysql, Tg, MsgInfo)
            mysql.close()
            return res
        except Exception as e:
            mysql.close()
            sendErrorMessage(logger, MsgInfo.from_chat, e)
            return None
    elif('inline_query' in data):
        MsgInfo.from_user = data['inline_query']['from']['id']
        MsgInfo.is_chat = True
        MsgInfo.query = data['inline_query']['query']
        MsgInfo.query_id = data['inline_query']['id']
        res = mysql.query("SELECT `id`, `name` FROM `groups` WHERE `name` LIKE %s LIMIT 10",
            ("%"+MsgInfo.query.replace(" ", "%")+"%", ), fetchall=True)
        answers = []
        mysql.close()
        if(res is None or res == ()):
            answers = []
        else:
            for i in res:
                MsgInfo.callback_data = [None, [i['id']]]
                msg, _ = get_rasp(logger, mysql, Tg, MsgInfo)
                answers.append(Tg.inlineQueryResult("article", i['id'], title=i['name'],
                    input_message_content={"message_text": msg, "parse_mode": "HTML"}))
        Tg.answerInlineQuery(MsgInfo.query_id, answers, cache_time=3600, switch_pm_parameter="1", switch_pm_text="🏠 Перейти к боту")

###
def menu(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, None)
    menu_text = """👋 <b>Привет, я бот отслеживающий расписание СГТУ!</b>
Бота написал @l27001, соотвественно со всем вопросами/багами/предложениями к нему.
\nДля просмотра расписания своей группы сначала необходимо привязать группу к аккаунту ТГ. Сделать это можно с помощью кнопок ниже.
\n<s>Этот текст всё-равно никто не читает :(</s>"""
    menu_keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔍 Найти группу", "start_find"),
        Tg.makeButton("🔎 Аудитории и преподаватели", "schedule_search"),
        Tg.makeButton("❓ Ничего не понимаю", "about"),
        Tg.makeButton("📝 Мои группы", "mg"),
        Tg.makeButton("🗒️ Расписание", "rasp"), max_=2), home=False)
    Tg.editOrSend(MsgInfo, menu_text, reply_markup=menu_keyb)

def about(logger, mysql, Tg, MsgInfo):
    text = """ℹ️ Этот бот парсит расписание с сайта https://rasp.sstu.ru в свою базу каждые 6 часов.
Затем вы можете узнать когда начинается первая пара, когда кончается последняя, сколько всего пар/какие и тд и тп. Всё это доступно прямо из мессенджера! Здорово правда?
В дополнение, вы можете <u>подписаться на рассылку</u>, чтобы бот сам присылал вам расписание в <u><b>19:00</b></u> по Саратовскому времени (+04 GMT).
\n<u><b>‼️ ВНИМАНИЕ</b>
Автор хоть и старается, но никак не может гарантировать точность/правильность предоставляемой информации! Учтите это.</u>"""
    if(len(MsgInfo.callback_data) > 1):
        button = Tg.makeRows(Tg.makeButton("🔙 Вернуться", f"chk_grp/{MsgInfo.callback_data[1][0]}"))
    else: button = ""
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb(button))

def start_find(logger, mysql, Tg, MsgInfo):
    rows = Tg.makeRows(Tg.makeButton("🌟 [NEW] 🌟 Выбор на сайте", web_app={"url": "https://ssturasp.l27001.net"}))
    rows += Tg.makeRows(Tg.makeButton("🔍 Поиск по параметрам", "pre_find_abbr"))
    Tg.editOrSend(MsgInfo, "🤔 Как будем искать?:",
        reply_markup=Tg.generateInlineKeyb(rows))

def schedule_search(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, None)
    rows = Tg.makeRows(
        Tg.makeButton("🚪 По аудитории", "search_room"),
        Tg.makeButton("👨‍🏫 По преподавателю", "search_teacher"),
        max_=1
    )
    Tg.editOrSend(MsgInfo, "🔎 Что будем искать?",
        reply_markup=Tg.generateInlineKeyb(rows))

def prompt_room_search(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, "search_room")
    Tg.editOrSend(MsgInfo, "🚪 Введите номер или часть названия аудитории.\nНапример: <code>1/202</code>",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 К выбору поиска", "schedule_search"))))

def prompt_teacher_search(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, "search_teacher")
    Tg.editOrSend(MsgInfo, "👨‍🏫 Введите фамилию или часть ФИО преподавателя.",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 К выбору поиска", "schedule_search"))))

def search_lessons(logger, mysql, Tg, MsgInfo, field, title, callback):
    query = " ".join(MsgInfo.text).strip()
    if(len(query) < 2):
        return Tg.editOrSend(MsgInfo, "⚠ Введите не менее двух символов для поиска.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 К выбору поиска", "schedule_search"))))

    # field и callback передаются только из обработчиков ниже, не из пользовательского ввода.
    results = mysql.query(
        f"SELECT `{field}` AS `value`, MD5(LOWER(`{field}`)) AS `token`, MIN(`date`) AS `next_date` "
        f"FROM `lessons` WHERE `date` >= %s AND `{field}` LIKE %s AND `{field}` NOT IN ('', 'Нет данных') "
        f"GROUP BY `{field}` ORDER BY `next_date`, `{field}` LIMIT 20",
        (date.today().isoformat(), "%"+query+"%"), fetchall=True
    )
    if(not results):
        return Tg.editOrSend(MsgInfo, f"⚠ {title} не найдены. Попробуйте изменить запрос.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 К выбору поиска", "schedule_search"))))

    buttons = [Tg.makeButton(i['value'][:60], f"{callback}/{i['token']}") for i in results]
    text = f"🔎 Найдено вариантов: {len(results)}. Выберите нужный:"
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb(
        Tg.makeRows(buttons, max_=1),
        Tg.makeRows(Tg.makeButton("🔙 Другой тип поиска", "schedule_search"))
    ))

def search_rooms(logger, mysql, Tg, MsgInfo):
    return search_lessons(logger, mysql, Tg, MsgInfo, "room", "Аудитории", "room_rasp")

def search_teachers(logger, mysql, Tg, MsgInfo):
    return search_lessons(logger, mysql, Tg, MsgInfo, "teacher", "Преподаватели", "teacher_rasp")

def format_lesson_time(value):
    if(isinstance(value, timedelta)):
        total_minutes = int(value.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours % 24:02d}:{minutes:02d}"
    if(hasattr(value, "strftime")):
        return value.strftime("%H:%M")
    return str(value)[:5]

def entity_rasp(logger, mysql, Tg, MsgInfo, field, icon, search_callback):
    token = MsgInfo.callback_data[1][0]
    try:
        offset = max(0, int(MsgInfo.callback_data[1][1]))
    except (IndexError, ValueError):
        offset = 0

    entity = mysql.query(
        f"SELECT `{field}` AS `value` FROM `lessons` WHERE MD5(LOWER(`{field}`)) = %s AND `date` >= %s LIMIT 1",
        (token, date.today().isoformat())
    )
    if(not entity):
        return Tg.editOrSend(MsgInfo, "⚠ Актуальное расписание для выбранного варианта не найдено.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔎 Новый поиск", search_callback))))

    days = mysql.query(
        f"SELECT DISTINCT `date`, `weekday` FROM `lessons` WHERE MD5(LOWER(`{field}`)) = %s AND `date` >= %s "
        "ORDER BY `date` LIMIT %s,1",
        (token, date.today().isoformat(), offset), fetchall=True
    )
    if(not days):
        return Tg.editOrSend(MsgInfo, "⚠ Ближайших занятий не найдено.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔎 Новый поиск", search_callback))))

    selected_day = days[0]
    lessons = mysql.query(
        f"SELECT l.`time_start`, l.`time_end`, l.`name`, l.`type`, l.`room`, l.`teacher`, g.`name` AS `group_name` "
        f"FROM `lessons` l INNER JOIN `groups` g ON g.`id` = l.`group_id` "
        f"WHERE MD5(LOWER(l.`{field}`)) = %s AND l.`date` = %s ORDER BY l.`time_start`, g.`name`",
        (token, selected_day['date'].isoformat()), fetchall=True
    )
    lesson_text = []
    for lesson in lessons:
        details = [
            f"<b>{format_lesson_time(lesson['time_start'])}–{format_lesson_time(lesson['time_end'])}</b> — {escape(str(lesson['name']))} {escape(str(lesson['type']))}",
            f"Группа: {escape(str(lesson['group_name']))}"
        ]
        if(field != "room"):
            details.append(f"Аудитория: {escape(str(lesson['room']))}")
        if(field != "teacher"):
            details.append(f"Преподаватель: {escape(str(lesson['teacher']))}")
        lesson_text.append("\n".join(details))

    has_next = mysql.query(
        f"SELECT 1 FROM `lessons` WHERE MD5(LOWER(`{field}`)) = %s AND `date` > %s LIMIT 1",
        (token, selected_day['date'].isoformat())
    ) is not None
    navigation = []
    if(offset > 0):
        navigation.append(Tg.makeButton("⬅️ Предыдущий день", f"{MsgInfo.callback_data[0]}/{token},{offset-1}"))
    if(has_next):
        navigation.append(Tg.makeButton("➡️ Следующий день", f"{MsgInfo.callback_data[0]}/{token},{offset+1}"))

    text = (f"{icon} <b>{escape(str(entity['value']))}</b>\n"
        f"📆 {selected_day['date'].strftime('%d.%m.%Y')} ({escape(str(selected_day['weekday']))})\n"
        "---------------------\n" + "\n---------------------\n".join(lesson_text))
    buttons = Tg.makeRows(navigation, max_=2)
    buttons += Tg.makeRows(Tg.makeButton("🔎 Новый поиск", search_callback))
    Tg.editOrSend(MsgInfo, text, reply_markup=Tg.generateInlineKeyb(buttons))

def room_rasp(logger, mysql, Tg, MsgInfo):
    return entity_rasp(logger, mysql, Tg, MsgInfo, "room", "🚪", "search_room")

def teacher_rasp(logger, mysql, Tg, MsgInfo):
    return entity_rasp(logger, mysql, Tg, MsgInfo, "teacher", "👨‍🏫", "search_teacher")

def info(logger, mysql, Tg, MsgInfo):
    txt = f"ℹ️ Информация\nID: {MsgInfo.from_user}\nЧат: {MsgInfo.is_chat}/{MsgInfo.from_chat}"
    Tg.editOrSend(MsgInfo, txt)

def pre_find_abbr(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, "sa")
    text = "ℹ️ Напишите вашу специальность (Прим: ИВЧТ, СТЗС, ИБС)\n<b>Без префиксов (<i>б, б1, м, м1, с, с1 и тд.</i>) и суффиксов курса/группы (<i>11, 21, 23 и тд.</i>) </b>\n<b>НЕ название института (СЭИ, ИНПиТ и тд.)</b>\n\n<b>Пример: </b>Если у вас группа <i>б1-ТПЭН-21</i> напишите <i>ТПЭН</i>!"
    if(MsgInfo.is_chat == True):
        text += "\n<i>P.S. В беседе необходимо ответить на сообщение чтобы бот его увидел!</i>"
    if(MsgInfo.callback_data is not None):
        Tg.editMessageText(MsgInfo.from_chat, MsgInfo.msg_id, MsgInfo.message['text'], reply_markup=Tg.generateInlineKeyb(empty=True))
    Tg.sendPhoto(MsgInfo.from_chat, "https://l27001.net/ssturasphint.jpg", caption=text, reply_markup=Tg.generateInlineKeyb())

def select_abbr_name(logger, mysql, Tg, MsgInfo):
    types = mysql.query("SELECT DISTINCT `type` FROM `groups` WHERE (`group_start` = %s OR `name` = %s) AND `sstu_id` IS NOT NULL", (MsgInfo.text[0], MsgInfo.text[0]), fetchall=True)
    if(len(types) == 0):
        Tg.editOrSend(MsgInfo, "⚠ Групп с такой аббревиатурой не найдено. Попробуйте ещё раз.\nЧтобы вернуться в меню, используйте /menu")
    else:
        rows = Tg.makeRows([Tg.makeButton(i['type'], f"sa_c/{MsgInfo.text[0]},{i['type']}") for i in types], max_=2)
        Tg.editOrSend(MsgInfo, "ℹ️ Выберите тип обучения:", reply_markup=Tg.generateInlineKeyb(rows))

def select_course(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, f"{MsgInfo.callback_data[0]}/{','.join(MsgInfo.callback_data[1])}")
    courses = mysql.query("SELECT DISTINCT `course` FROM `groups` WHERE (`group_start` = %s OR `name` = %s) AND `type` = %s AND `sstu_id` IS NOT NULL ORDER BY `course`",
        (MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][1]), fetchall=True)
    rows = Tg.makeRows([Tg.makeButton(i['course'], f"sa_c1/{','.join(MsgInfo.callback_data[1])},{i['course']}") for i in courses])
    Tg.editOrSend(MsgInfo, "ℹ️ Выберите курс:", reply_markup=Tg.generateInlineKeyb(rows))

def select_group(logger, mysql, Tg, MsgInfo):
    mysql.setUserState(MsgInfo.from_chat, f"{MsgInfo.callback_data[0]}/{','.join(MsgInfo.callback_data[1])}")
    groups = mysql.query("SELECT `id`,`name` FROM `groups` WHERE (`group_start` = %s OR `name` = %s) AND `type` = %s AND `course` = %s AND `sstu_id` IS NOT NULL ORDER BY `name`",
        (MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][0], MsgInfo.callback_data[1][1], MsgInfo.callback_data[1][2]), fetchall=True)
    rows = Tg.makeRows([Tg.makeButton(i['name'], f"cg/{i['id']}") for i in groups], max_=2)
    Tg.editOrSend(MsgInfo, "Наконец, выберите свою группу:",
        reply_markup=Tg.generateInlineKeyb(rows, Tg.makeRows(Tg.makeButton("🔙 Искать заново", "pre_find_abbr"))))

def confirm_group(logger, mysql, Tg, MsgInfo): # вынести выбор группы в отдельную функцию
    mysql.setUserState(MsgInfo.from_chat, None)
    count = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `user_id` = %s", (MsgInfo.from_chat, ))['COUNT(*)']
    already_in = mysql.query("SELECT `user_id` FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s",
        (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    if(already_in is not None):
        return Tg.editOrSend(MsgInfo, "🔴 Эта группа уже выбрана вами!",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Искать заново", "pre_find_abbr"))))
    if(count >= 5):
        return Tg.editOrSend(MsgInfo, "🔴 Вы достигли лимита групп!", reply_markup=Tg.generateInlineKeyb())
    mysql.query("INSERT INTO `group_subs` (`user_id`, `group_id`) VALUES (%s, %s)", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    Tg.editOrSend(MsgInfo, "🟢 Группа была отмечена как ваша!",
        reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"),
            Tg.makeButton("❗ Подписаться на рассылку", f"toggle_sub/{MsgInfo.callback_data[1][0]}"),
            Tg.makeButton("⁉️ Что за рассылка?", "about"), Tg.makeButton("🗓️ Расписание группы", f"get_rasp/{MsgInfo.callback_data[1][0]}"), max_=1)))

def my_groups(logger, mysql, Tg, MsgInfo):
    groups = mysql.getUserGroups(MsgInfo.from_chat)
    msg = []; buttons = []
    for g in groups:
        if(g['subscribe'] == False):
            sub = "<i>Не подписаны</i>"
        else: sub = "<i>Подписаны</i>"
        msg.append(f"ID - <code>{g['sstu_id']}</code> | {g['name']} | {sub}")
        buttons.append(Tg.makeButton(g['name'], f"chk_grp/{g['id']}"))
    if(groups is None or groups == ()):
        msg = ["<b>Нет групп</b>"]
        buttons.append(Tg.makeButton("🔍 Найти группу", "start_find"))
    msg = "📝 Ваши группы:\n"+"\n".join(msg)
    keyb = Tg.generateInlineKeyb(Tg.makeRows(buttons, max_=2))
    Tg.editOrSend(MsgInfo, msg, reply_markup=keyb)

def check_group(logger, mysql, Tg, MsgInfo):
    group = mysql.query("SELECT gg.*, gs.* FROM `groups` gg INNER JOIN `group_subs` gs ON gs.group_id = gg.id AND gs.user_id = %s WHERE `id` = %s", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    if(group is None or group == ()):
        return Tg.editOrSend(MsgInfo, "⚠ Не удалось получить информацию о группе. Вернитесь в меню", reply_markup=Tg.generateInlineKeyb())
    count = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `group_id` = %s", (group['id'], ))
    if(group['subscribe'] == False):
        sub = "<i>Не подписаны</i>"
        toggle = "Подписаться на рассылку"
    else:
        sub = "<i>Подписаны</i>"
        toggle = "Отписаться от рассылки"
    msg = f"""📙 Группа <b>{group['name']}</b>
- <b>ID</b>: <code>{group['id']}</code>
- <b>Форма</b>: {group['form']}
- <b>Тип</b>: {group['type']}
- <b>Рассылка</b>: {sub}
- <b>Институт</b>: {group['institute']}
- <b>Человек в группе</b> (согласно локальной базе): {count['COUNT(*)']}"""
    rows = Tg.makeRows(Tg.makeButton("🗑️ Удалить группу", f"del_grp/{group['id']}"),
        Tg.makeButton(f"❗ {toggle}", f"toggle_sub/{group['id']}"),
        Tg.makeButton(f"⁉️ Что за рассылка?", f"about/{group['id']}"),
        Tg.makeButton("🔙 Вернуться к списку групп", "mg"),
        Tg.makeButton("🗒️ Расписание группы", f"get_rasp/{group['id']}"), max_=2)
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(rows))

def del_group(logger, mysql, Tg, MsgInfo):
    mysql.query("DELETE FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Вернуться к списку групп", "mg"), max_=2))
    Tg.editOrSend(MsgInfo, "🟢 Группа была откреплена от этого профиля!", reply_markup=keyb)

def toggle_subscribtion(logger, mysql, Tg, MsgInfo):
    group = mysql.query("SELECT gg.*, gs.* FROM `groups` gg INNER JOIN `group_subs` gs ON gs.group_id = gg.id AND gs.user_id = %s WHERE `id` = %s", (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    mysql.query("UPDATE `group_subs` SET `subscribe` = !subscribe WHERE `user_id` = %s AND `group_id` = %s",
        (MsgInfo.from_chat, MsgInfo.callback_data[1][0]))
    if(group['subscribe'] == 0):
        text = f"🟢 Вы успешно <u>подписались</u> на рассылку расписания группы <b>{group['name']}</b>!"
        toggle = "Отписаться снова"
    else:
        text = f"🟢 Вы успешно <u>отписались</u> от рассылки расписания группы <b>{group['name']}</b>!"
        toggle = "Подписаться снова"
    keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔙 Вернуться к группе", f"chk_grp/{MsgInfo.callback_data[1][0]}"), Tg.makeButton(f"❗ {toggle}", f"toggle_sub/{MsgInfo.callback_data[1][0]}"), max_=1))
    Tg.editOrSend(MsgInfo, text, reply_markup=keyb)

def rasp(logger, mysql, Tg, MsgInfo):
    groups = mysql.getUserGroups(MsgInfo.from_chat)
    buttons = []
    msg = "🔘 Выберите группу расписание которой вы хотите увидеть:"
    for g in groups:
        buttons.append(Tg.makeButton(g['name'], f"get_rasp/{g['id']}"))
    if(groups is None or groups == ()):
        msg = "<b>Нет групп</b>"
        buttons.append(Tg.makeButton("🔍 Найти группу", "start_find"))
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(Tg.makeRows(buttons, max_=2)))

def get_rasp(logger, mysql, Tg, MsgInfo):
    days_in_msg = 2
    group = mysql.query("SELECT * FROM `groups` WHERE `id` = %s", (MsgInfo.callback_data[1][0], ))
    if(group is None):
        if(MsgInfo.callback_data[0] == None):
            return "⚠ Не удалось получить информацию о группе.", Tg.generateInlineKeyb(empty=True)
        return Tg.editOrSend(MsgInfo, "⚠ Не удалось получить информацию о группе.",
            reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("📝 Мои группы", "mg"), Tg.makeButton("🔙 Расписание", "rasp"))))
    if(len(MsgInfo.callback_data[1]) > 1):
        offset = int(MsgInfo.callback_data[1][1])
    else:
        offset = 0
    days = mysql.query("SELECT DISTINCT `date` FROM lessons WHERE `group_id` = %s AND `date` >= %s ORDER BY `date` LIMIT %s,%s", (MsgInfo.callback_data[1][0], date.today().isoformat(), offset, days_in_msg), fetchall=True)
    if(days is None or days == ()):
        if(MsgInfo.callback_data[0] == None):
            return "⚠ Похоже, расписания на ближайшие дни нет", Tg.generateInlineKeyb(empty=True)
        return Tg.editOrSend(MsgInfo, f"⚠ Похоже, расписания на ближайшие дни для группы <b>{group['name']}</b> нет\n\n<i>Акутально на {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>",
                reply_markup=Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🔄 Обновить", MsgInfo.callback_data[0] + "/" + ','.join(MsgInfo.callback_data[1])),
                            Tg.makeButton("🗒️ Меню расписания", "rasp"),
                            Tg.makeButton("🌐 Расписание на неделю", web_app={"url": f"https://rasp.sstu.ru/rasp/group/{group['sstu_id']}"}), max_=1)))
    prev_available = offset > 0
    next_available = bool(mysql.query("SELECT DISTINCT `date` FROM lessons WHERE `group_id` = %s AND `date` > %s ORDER BY `date` LIMIT 1", (MsgInfo.callback_data[1][0], days[-1]['date'])))
    buttons = []; msg = []
    for i in range(len(days)):
        day = mysql.query("SELECT `date`, `type`, `name`, `weekday`, `lesson_num`, `time_start`, `time_end` FROM lessons WHERE `group_id` = %s AND `date` = %s ORDER BY `lesson_num`",
            (group['id'], days[i]['date'].isoformat()), fetchall=True)
        if(day is None or day == ()): continue
        if(day[-1]['date'].strftime('%d.%m') == datetime.now().strftime('%d.%m') and day[-1]['time_end'] < timedelta(hours=datetime.now().hour, minutes=datetime.now().minute)): continue
        les = "\n".join([f"[{l['lesson_num']}] {l['name']} {l['type']}" for l in day])
        day = {'info': {'date': day[0]['date'], 'weekday': day[0]['weekday'], 'count': len(day),
                'time_start': datetime.strptime(f"{day[0]['date']} {day[0]['time_start']}", "%Y-%m-%d %H:%M:%S"),
                'time_end': datetime.strptime(f"{day[-1]['date']} {day[-1]['time_end']}", "%Y-%m-%d %H:%M:%S")}}
        if(day['info']['date'].strftime('%d.%m') != datetime.today().strftime('%d.%m')):
            buttons.append(Tg.makeButton(f"📆 {day['info']['date'].strftime('%d.%m')} ({day['info']['weekday']})", f"date_rasp/{group['id']},{day['info']['date'].strftime('%Y-%m-%d')}"))
        else:
            buttons.append(Tg.makeButton(f"📆 {day['info']['date'].strftime('%d.%m')} (Сегодня)", f"date_rasp/{group['id']},{day['info']['date'].strftime('%Y-%m-%d')}"))
        if(len(msg) >= 2): continue
        weather = mysql.query("SELECT `date`, `temp`, `weather` FROM `weather` WHERE `date` BETWEEN %s AND %s LIMIT 1",
            (day['info']['time_start'].strftime('%Y-%m-%d %H:%M:%S'), day['info']['time_end'].strftime('%Y-%m-%d %H:%M:%S')))
        if(weather == None):
            weather = mysql.query("SELECT `date`, `temp`, `weather` FROM `weather` WHERE date = (SELECT MAX(date) AS date FROM `weather` WHERE date < %s LIMIT 1)", (day['info']['time_start'].strftime("%Y-%m-%d %H:%M:%S"), ))
        if(weather == None or weather['date'].strftime("%Y-%m-%d") != day['info']['time_start'].strftime("%Y-%m-%d")):
            weather = {"temp": None, "weather": "Нет данных"}
        day.update({'weather': weather})
        msg.append(f"""<b>- День: <u>{day['info']['weekday']} {day['info']['date']}</u></b>
- <b>Кол-во пар</b>: {day['info']['count']}
- <b>Начало занятий</b>: {day['info']['time_start'].strftime("%H:%M")}
- <b>Конец занятий</b>: {day['info']['time_end'].strftime("%H:%M")}
- <b>Погода</b>: {day['weather']['weather']} {day['weather']['temp']}°C
- <b>Пары</b>:
<i>{les}</i>
""")
    last_upd = group['last_appearance'].strftime("%Y-%m-%d %H:%M")
    buttons = Tg.makeRows(buttons, max_=2)
    prev_next_buttons = []
    if(prev_available):
        prev_next_buttons.append(Tg.makeButton("⬅️ Предыдущие дни", f"get_rasp/{group['id']},{offset-days_in_msg}"))
    if(next_available):
        prev_next_buttons.append(Tg.makeButton("➡️ Следующие дни", f"get_rasp/{group['id']},{offset+days_in_msg}"))
    buttons += Tg.makeRows(prev_next_buttons, max_=2)
    msg = f"🗓️ Общая информация для <b>{group['name']}</b>\n---------------------\n" + "---------------------\n".join(msg)
    msg += f"---------------------\n- Последнее обновление: {last_upd}"
    if(mysql.query("SELECT * FROM `group_subs` WHERE `user_id` = %s AND `group_id` = %s AND `subscribe` = 0", (MsgInfo.from_user, group['id'])) is not None):
        msg += "\n<b>Вы не подписаны на рассылку этой группы!</b>"
        buttons += Tg.makeRows(Tg.makeButton("❗ Подписаться на рассылку", f"toggle_sub/{group['id']}"))
    buttons += Tg.makeRows(Tg.makeButton("🌐 Расписание на неделю", web_app={"url": f"https://rasp.sstu.ru/rasp/group/{group['sstu_id']}"})) + Tg.makeRows(Tg.makeButton("📙 Группа", f"chk_grp/{group['id']}"), Tg.makeButton("🗒️ Группы", "rasp"), Tg.makeButton("🏠 Меню", "clear_state"))
    if(MsgInfo.callback_data[0] == None):
        return msg, Tg.generateInlineKeyb(buttons)
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(buttons, home=False))

def date_rasp(logger, mysql, Tg, MsgInfo):
    rasp = mysql.query("SELECT l.*, g.sstu_id, g.last_appearance, g.name AS gname FROM `lessons` l INNER JOIN `groups` g ON l.group_id = g.id WHERE `date` = %s AND `group_id` = %s ORDER BY `lesson_num`",
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
            flag = "<b><u>Текущая пара</u></b>\n"
        elif(i > 0 and rasp[i-1]['time_end'] <= now <= rasp[i]['time_start']):
            flag = "<b><u>Следующая пара</u></b>\n"
        msg.append(f"""{flag}<b>№ пары</b>: {rasp[i]['lesson_num']}
<b>Предмет</b>: {rasp[i]['name']}/{rasp[i]['type']}
<b>Время</b>: {rasp[i]['time_start'].strftime("%H:%M")} - {rasp[i]['time_end'].strftime("%H:%M")}
<b>Аудитория</b>: {rasp[i]['room']}
<b>Преподаватель</b>: {rasp[i]['teacher']}""")
    last_upd = rasp[0]['last_appearance'].strftime("%Y-%m-%d %H:%M")
    msg = f"🗓️ <b>{rasp[0]['gname']} | {MsgInfo.callback_data[1][1]} | {rasp[0]['weekday']}</b>\n---------------------\n"+"\n---------------------\n".join(msg)
    msg += f"\n---------------------\nПоследнее обновление: {last_upd}"
    buttons = Tg.makeRows(Tg.makeButton("🔙 Вернуться", f"get_rasp/{MsgInfo.callback_data[1][0]}"))
    group = mysql.query("SELECT sstu_id FROM `groups` WHERE `id` = %s", (MsgInfo.callback_data[1][0], ))
    next_prev_days = []
    next_day = mysql.query("SELECT `date`, `weekday` FROM lessons WHERE `date` > %s AND `group_id` = %s ORDER BY `date` ASC LIMIT 1", (MsgInfo.callback_data[1][1], MsgInfo.callback_data[1][0]))
    prev_day = mysql.query("SELECT `date`, `weekday` FROM lessons WHERE `date` < %s AND `group_id` = %s ORDER BY `date` DESC LIMIT 1", (MsgInfo.callback_data[1][1], MsgInfo.callback_data[1][0]))
    if(prev_day):
        next_prev_days.append(Tg.makeButton(f"⬅️ {prev_day['date'].strftime('%d.%m')} ({prev_day['weekday']})", f"date_rasp/{MsgInfo.callback_data[1][0]},{prev_day['date'].strftime('%Y-%m-%d')}"))
    if(next_day):
        next_prev_days.append(Tg.makeButton(f"➡️ {next_day['date'].strftime('%d.%m')} ({next_day['weekday']})", f"date_rasp/{MsgInfo.callback_data[1][0]},{next_day['date'].strftime('%Y-%m-%d')}"))
    buttons += Tg.makeRows(next_prev_days)
    buttons += Tg.makeRows(Tg.makeButton("🌐 Расписание на неделю", web_app={"url": f"https://rasp.sstu.ru/rasp/group/{group['sstu_id']}"}))
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb(buttons))

def stats(logger, mysql, Tg, MsgInfo):
    date = mysql.query("SELECT `last_appearance` FROM `groups` ORDER BY `last_appearance` DESC")['last_appearance']
    groups = mysql.query("SELECT COUNT(*) FROM `groups`")["COUNT(*)"]
    lessons = mysql.query("SELECT COUNT(*) FROM `lessons`")["COUNT(*)"]
    users = mysql.query("SELECT COUNT(*) FROM `users`")["COUNT(*)"]
    subs = mysql.query("SELECT COUNT(*) FROM `group_subs`")["COUNT(*)"]
    notifies = mysql.query("SELECT COUNT(*) FROM `group_subs` WHERE `subscribe` = 1")["COUNT(*)"]
    weather = mysql.query("SELECT `date` FROM `weather` WHERE `date` LIKE %s", (((datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d"))+"%",))
    if(weather is not None):
        weather = "Есть данные"
    else:
        weather = "Нет данных"
    msg = f"""ℹ️ <b>Статистика:</b>
<b>Последнее обновление</b>: {date}
<b>Кол-во групп</b>: {groups}
<b>Кол-во пар</b>: {lessons}
<b>Кол-во пользователей</b>: {users}
<b>Кол-во подписок/с уведомлениями</b>: {subs}/{notifies}
<b>Погода на завтра</b>: {weather}"""
    Tg.editOrSend(MsgInfo, msg, reply_markup=Tg.generateInlineKeyb())

### Список команд
cmds = {'/start':menu,
        '/menu':menu,
        '/info':info,
        '/find':start_find,
        '/search':schedule_search,
        '/room':prompt_room_search,
        '/teacher':prompt_teacher_search,
        '/groups':my_groups,
        '/rasp':rasp,
        '/stats':stats
}

### Список inline действий
inlines = {
        'start_find':start_find,
        'schedule_search':schedule_search,
        'search_room':prompt_room_search,
        'search_teacher':prompt_teacher_search,
        'room_rasp':room_rasp,
        'teacher_rasp':teacher_rasp,
        'clear_state':menu,
        'about':about,
        'pre_find_abbr':pre_find_abbr,
        'sa_c':select_course,
        'sa_c1':select_group,
        'cg':confirm_group,
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
        'search_room':search_rooms,
        'search_teacher':search_teachers
}
