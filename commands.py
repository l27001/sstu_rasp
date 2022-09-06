from methods import getUserInfo, setUserState, sendErrorMessage

class MsgInfo(): pass

def execute_command(data):
    print(data)
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
        MsgInfo.user_info, MsgInfo.chat_info = getUserInfo(MsgInfo.from_user, MsgInfo.from_chat)
    elif('callback_query' in data): # возможно объединить?
        MsgInfo.from_user = data['callback_query']['message']['from']['id']
        MsgInfo.from_chat = data['callback_query']['message']['chat']['id']
        MsgInfo.is_chat = MsgInfo.from_chat < 0
        MsgInfo.text = None
        MsgInfo.msg_id = data['callback_query']['message']['message_id']
        MsgInfo.callback_data = data['callback_query']['data'].split("/")
        MsgInfo.callback_data[1] = MsgInfo.callback_data[1].split(",")
        MsgInfo.user_info, MsgInfo.chat_info = getUserInfo(MsgInfo.from_user, MsgInfo.from_chat)
        try:
            return inlines[MsgInfo.callback_data[0]](MsgInfo)
        except Exception as e:
            sendErrorMessage(MsgInfo.from_chat, e)
            return None
    # elif('inline_query' in data):
    #     MsgInfo.from_user = data['inline_query']['from']['id']
    #     MsgInfo.from_chat = None
    #     MsgInfo.is_chat = None
    #     MsgInfo.user_info, MsgInfo.chat_info = getUserInfo(MsgInfo.from_user, None)
    #     return Tg.answerInlineQuery()
    if(MsgInfo.is_chat == True):
        MsgInfo.text[0] = MsgInfo.text[0].split("@")
        if(len(MsgInfo.text[0]) > 1):
            if(MsgInfo.text[0][1] != Tg.username): # Фильтруем команды по тегу бота
                return None                     # Пример: /status@first_bot и /status@second_bot
        MsgInfo.text[0] = MsgInfo.text[0][0] # убираем тег из команды
    if(MsgInfo.user_info['state'] != None and MsgInfo.text[0][0] != "/"):
        try:
            return states[MsgInfo.user_info['state']](MsgInfo)
        except Exception as e:
            sendErrorMessage(MsgInfo.from_chat, e)
            return None
    cmd = MsgInfo.text[0].lower()
    del(MsgInfo.text[0])
    if(cmds.get(cmd) == None):
        if(MsgInfo.is_chat == False):
            Tg.sendMessage(MsgInfo.from_chat, "👎🏻 Не понял", reply_to_message_id=MsgInfo.msg_id)
        return None
    try:
        cmds[cmd](MsgInfo)
    except Exception as e:
        sendErrorMessage(MsgInfo.from_chat, e)
        return None

### Обычные команды
def start(MsgInfo):
    Tg.sendMessage(MsgInfo.from_chat, "Привет! Для начала давай найдём твою группу:",
        reply_markup=Tg.generateInlineKeyb(Tg.makeButton("Поиск по аббревиатуре", "pre_find_abbr"), Tg.makeButton("test2", "T2")))

def test(MsgInfo):
    Tg.sendMessage(MsgInfo.from_chat, "sstu_rasp bot by @l270011")

def info(MsgInfo):
    txt = f"ℹ️ Информация\nID: {MsgInfo.from_user}\nЧат: {MsgInfo.is_chat}/{MsgInfo.from_chat}\nГруппа: {MsgInfo.user_info['group_id']}"
    Tg.sendMessage(MsgInfo.from_chat, txt)

def subscribe(MsgInfo):
    if(MsgInfo.is_chat):
        if(MsgInfo.chat_info['subscribe'] == 1):
            mysql.query("UPDATE tg_infoscribe SET subscribe=0 WHERE id = %s", (MsgInfo.from_chat,))
            txt = "✅ Вы успешно *отписали беседу* от уведомлений о трансляциях"
        else:
            mysql.query("UPDATE tg_infoscribe SET subscribe=1 WHERE id = %s", (MsgInfo.from_chat,))
            txt = "✅ Вы успешно *подписали беседу* на уведомления о трансляциях"
    else:
        if(MsgInfo.user_info['subscribe'] == 1):
            mysql.query("UPDATE tg_infoscribe SET subscribe=0 WHERE id = %s", (MsgInfo.from_user,))
            txt = "✅ Вы успешно *отписались* от уведомлений о трансляциях"
        else:
            mysql.query("UPDATE tg_infoscribe SET subscribe=1 WHERE id = %s", (MsgInfo.from_user,))
            txt = "✅ Вы успешно *подписались* на уведомления о трансляциях"
    Tg.sendMessage(MsgInfo.from_chat, txt)

### Действия inline клавиатур/сообщений с состоянием
def pre_find_abbr(MsgInfo):
    setUserState(MsgInfo.from_chat, "sa")
    Tg.editMessageText(MsgInfo.from_chat, MsgInfo.msg_id, "Отправьте аббревиатуру вашего направления (Прим: ИФСТ, СЗС, АРХТ)")

def select_abbr_name(MsgInfo):
    types = mysql.query("SELECT DISTINCT `type` FROM `groups` WHERE `group-start` = %s", (MsgInfo.text, ), fetch="all")
    if(len(types) == 0):
        Tg.sendMessage(MsgInfo.from_chat, "⚠ Групп с такой аббревиатурой не найдено. Попробуйте ещё раз.")
    else:
        buttons = [Tg.makeButton(i['type'], "sa_c/"+i['type']) for i in types]
        Tg.sendMessage(MsgInfo.from_chat, "Выберите тип обучения:", reply_markup=Tg.generateInlineKeyb(buttons))

def select_course(MsgInfo):
    pass

### Список команд
cmds = {'/start':start,
        '/test':test,
        '/info':info,
        '/subscribe':subscribe,'/unsubscribe':subscribe
}

### Список inline действий
inlines = {
        'pre_find_abbr':pre_find_abbr,
        'sa_c':select_course
}

### Список состояний
states = {
        'sa':select_abbr_name
}

# sa = select_abbr