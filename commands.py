class Commands:

    def __init__(self, data):
        print(data)
        if('my_chat_member' in data):
            return None
        elif('message' in data):
            data = data['message']
            if('text' not in data): # исключение/добавление участника приходит с элементом message
                return None         # но без text в нём. Игнорируем такие события
            self.from_user = data['from']['id']
            self.from_chat = data['chat']['id']
            if(self.from_chat < 0): self.is_chat = True
            else: self.is_chat = False
            self.text = data['text'].split()
            self.msg_id = data['message_id']
        elif('callback_query' in data): # возможно объединить?
            self.from_user = data['callback_query']['message']['from']['id']
            self.from_chat = data['callback_query']['message']['chat']['id']
            if(self.from_chat < 0): self.is_chat = True
            else: self.is_chat = False
            self.text = None
            self.msg_id = data['callback_query']['message']['message_id']
            self.callback_data = data['callback_query']['data']
            Tg.editMessageText(self.from_chat, self.msg_id, "Изменяю сообщение", Tg.generateInlineKeyb(Tg.makeButton("Кнопка1", "K1"), Tg.makeButton("Кнопка2", "K2")))
            return None
        if(self.is_chat):
            self.chat_sub = mysql.query("SELECT * FROM users WHERE id = %s", (self.from_chat,))
            if(self.chat_sub == None):
                mysql.query("INSERT INTO users (id) VALUES (%s)", (self.from_chat,))
                self.chat_sub = mysql.query("SELECT * FROM users WHERE id = %s", (self.from_chat,))
            self.text[0] = self.text[0].split("@")
            if(len(self.text[0]) > 1):
                if(self.text[0][1] != Tg.username): # Фильтруем команды по тегу бота
                    return None                     # Пример: /status@first_bot и /status@second_bot
            self.text[0] = self.text[0][0] # убираем тег из команды
        else: self.chat_sub = None
        self.user_sub = mysql.query("SELECT * FROM users WHERE id = %s", (self.from_user,))
        if(self.user_sub == None):
            mysql.query("INSERT INTO users (id) VALUES (%s)", (self.from_user,))
            self.user_sub = mysql.query("SELECT * FROM users WHERE id = %s", (self.from_user,))
        cmd = self.text[0].lower()
        del(self.text[0])
        if(cmds.get(cmd) == None):
            if(self.is_chat == False):
                Tg.sendMessage(self.from_chat, "👎🏻 Не понял", reply_to_message_id=self.msg_id)
            return None
        try:
            cmds[cmd](self)
        except Exception as e:
            Tg.sendMessage(self.from_chat, "⚠ Произошла непредвиденная ошибка.\nОбратитесь к @l270011", reply_to_message_id=self.msg_id)
            print(e)

    def start(self):
        Tg.sendMessage(self.from_chat, "Привет! Для начала давай найдём твою группу:",
            reply_markup=Tg.generateInlineKeyb(Tg.makeButton("test", "T1"), Tg.makeButton("test2", "T2")), reply_to_message_id=self.msg_id)

    def test(self):
        Tg.sendMessage(self.from_chat, "TG bot by @l270011", reply_to_message_id=self.msg_id)

    def info(self):
        if(self.is_chat):
            if(self.chat_sub['subscribe'] == 1):
                rassb = f"Chat-ID: {self.from_chat}\nПодписка чата: *Активна*\n"
            else:
                rassb = f"Chat-ID: {self.from_chat}\nПодписка чата: *Неактивна*\n"
        else: rassb = ""
        if(self.user_sub['subscribe'] == 1):
            rass = "Активна"
        else:
            rass = "Неактивна"
        txt = f"ℹ️ Информация\nID: {self.from_user}\nПодписка: *{rass}*\n{rassb}"
        Tg.sendMessage(self.from_chat, txt, reply_to_message_id=self.msg_id)

    def subscribe(self):
        if(self.is_chat):
            if(self.chat_sub['subscribe'] == 1):
                mysql.query("UPDATE tg_subscribe SET subscribe=0 WHERE id = %s", (self.from_chat,))
                txt = "✅ Вы успешно *отписали беседу* от уведомлений о трансляциях"
            else:
                mysql.query("UPDATE tg_subscribe SET subscribe=1 WHERE id = %s", (self.from_chat,))
                txt = "✅ Вы успешно *подписали беседу* на уведомления о трансляциях"
        else:
            if(self.user_sub['subscribe'] == 1):
                mysql.query("UPDATE tg_subscribe SET subscribe=0 WHERE id = %s", (self.from_user,))
                txt = "✅ Вы успешно *отписались* от уведомлений о трансляциях"
            else:
                mysql.query("UPDATE tg_subscribe SET subscribe=1 WHERE id = %s", (self.from_user,))
                txt = "✅ Вы успешно *подписались* на уведомления о трансляциях"
        Tg.sendMessage(self.from_chat, txt, reply_to_message_id=self.msg_id)

cmds = {'/start':Commands.start,
        '/test':Commands.test,
        '/info':Commands.info,
        '/subscribe':Commands.subscribe,'/unsubscribe':Commands.subscribe
        }
