import pymysql, requests, json
from pymysql.err import InterfaceError, OperationalError
from time import sleep
from abc import ABC, abstractmethod
import config

class Mysql:

    def __init__(self, autocommit=True):
        self.autocommit = autocommit
        self.con = self.make_con()

    def query(self,query,variables=(),fetchall=False,lastrow=False):
        try:
            cur = self.con.cursor()
            cur.execute(query, variables)
        except (InterfaceError,OperationalError):
            self.con = self.make_con()
            cur = self.con.cursor()
            cur.execute(query, variables)
        if(lastrow == True):
            return cur.lastrowid
        if(fetchall == False):
            data = cur.fetchone()
        else:
            data = cur.fetchall()
        return data

    def make_con(self=None):
        return pymysql.connect(host=config.db['host'],
                 user=config.db['user'],
                 password=config.db['password'],
                 db=config.db['database'],
                 charset='utf8mb4',
                 autocommit=self.autocommit,
                 cursorclass=pymysql.cursors.DictCursor,
                 write_timeout=5)
    
    def commit(self):
        if(self.autocommit):
            return False
        self.con.commit()

    def rollback(self):
        if(self.autocommit):
            return False
        self.con.rollback()
        self.con.close()

    def close(self):
        self.con.close()

    def getUserInfo(self, user):
        user_info = self.query("SELECT * FROM users WHERE id = %s", (user,))
        if(user_info == None):
            self.query("INSERT INTO users (id) VALUES (%s)", (user,))
            user_info = self.query("SELECT * FROM users WHERE id = %s", (user,))
        return user_info

    def getUserGroups(self, user_id):
        res = self.query("SELECT g.sstu_id, g.id, gs.subscribe, g.name FROM group_subs gs INNER JOIN groups g ON gs.group_id = g.id WHERE user_id = %s AND g.sstu_id IS NOT NULL",
            (user_id, ), fetchall=True)
        return res

    def setUserState(self, id_, state=None):
        self.query("UPDATE `users` SET state = %s WHERE id = %s", (state, id_))
        return

class BaseBot(ABC):
    """Базовый класс для ботов (TG / VK и т.п.)"""

    def __init__(self):
        pass

    # -------- ОБЩИЕ УТИЛИТЫ --------
    def makeRows(self, *args, max_=5, add_list=True):
        """
        Разбивает список кнопок на строки.
        Общая логика для Tg/Vk, только max_ можно менять при вызове.
        """
        if len(args) > 0 and type(args[0]) == list:
            args = args[0]

        if len(args) > max_:
            return [args[x:x+max_] for x in range(0, len(args), max_)]

        if add_list:
            return [list(args)]
        return list(args)

    # -------- АБСТРАКТНЫЕ МЕТОДЫ (ИНТЕРФЕЙС) --------
    @abstractmethod
    def sendMessage(self, *args, **kwargs):
        pass

    @abstractmethod
    def makeButton(self, *args, **kwargs):
        pass

    @abstractmethod
    def generateKeyboard(self, *args, **kwargs):
        pass


# ============================================
#   TELEGRAM
# ============================================

class Tg(BaseBot):

    def __init__(self, token=config.tg_info['access_token'], use_proxy=False):
        super().__init__()
        self.url = f"{config.tg_info['url']}bot{token}/"
        self.offset = 0
        self.proxies = {}
        if(use_proxy == True):
            self.proxies = {"http": "socks5://tg-shared:Wyjzsia27h@deluxe.node.l27001.net:3129",
                        "https": "socks5://tg-shared:Wyjzsia27h@deluxe.node.l27001.net:3129"}
        self.getMe()

    # ---- специфично для TG ----
    def getOffset(self):
        return self.offset

    def setOffset(self, offset):
        self.offset = offset

    def getUpdates(self, offset=0, timeout=60):
        data = requests.get(
            f"{self.url}getUpdates",
            params={"offset": offset, "timeout": timeout},
            proxies=self.proxies,
            timeout=timeout+1
        ).json()
        if len(data['result']) > 0:
            self.offset = data['result'][-1]['update_id'] + 1
        return data

    def sendMessage(self, chat_id, text, allow_sending_without_reply=True,
                    parse_mode="HTML", **kwargs):
        params = {
            "chat_id": chat_id,
            "text": text,
            "allow_sending_without_reply": allow_sending_without_reply,
            "parse_mode": parse_mode
        }
        params.update(kwargs)
        data = requests.get(f"{self.url}sendMessage", params=params, proxies=self.proxies)
        while data.status_code == 429:
            sleep(data.json()['parameters']['retry_after'])
            data = requests.get(f"{self.url}sendMessage", params=params, proxies=self.proxies)
        return data.json()

    def sendPhoto(self, chat_id, photo, parse_mode="HTML", **kwargs):
        params = {"chat_id": chat_id, "photo": photo, "parse_mode": parse_mode}
        params.update(kwargs)
        data = requests.get(f"{self.url}sendPhoto", params=params, proxies=self.proxies)
        while data.status_code == 429:
            sleep(data.json()['parameters']['retry_after'])
            data = requests.get(f"{self.url}sendPhoto", params=params, proxies=self.proxies)
        return data.json()

    def getMe(self):
        data = requests.get(f"{self.url}getMe", proxies=self.proxies).json()['result']
        self.id = data['id']
        self.username = data['username']

    # ---- кнопки / клавиатуры (реализация интерфейса BaseBot) ----
    def makeButton(self, text, callback_data="", **kwargs):
        res = {"text": text, "callback_data": callback_data}
        res.update(kwargs)
        return res

    def generateInlineKeyb(self, *args, home=True, empty=False):
        if empty:
            return json.dumps({"inline_keyboard": []})
        s = []
        for n in args:
            s += n
        if home:
            s.append([{"text": "🏠 Меню", "callback_data": "clear_state"}])
        return json.dumps({"inline_keyboard": s})

    def generateKeyboard(self, *args, **kwargs):
        """
        Реализация интерфейса BaseBot: для TG это просто обёртка над inline-клавой.
        kwargs: home=True/False, empty=True/False
        """
        return self.generateInlineKeyb(*args, **kwargs)

    # ---- редактирование сообщений ----
    def editMessageText(self, chat, message, text, parse_mode="HTML", **kwargs):
        params = {
            "chat_id": chat,
            "message_id": message,
            "text": text,
            "parse_mode": parse_mode
        }
        params.update(kwargs)
        data = requests.get(f"{self.url}editMessageText", params=params, proxies=self.proxies)
        while data.status_code == 429:
            sleep(data.json()['parameters']['retry_after'])
            data = requests.get(f"{self.url}editMessageText", params=params, proxies=self.proxies)
        return data.json()

    def editMessageReplyMarkup(self, chat, message, reply_markup, **kwargs):
        params = {
            "chat_id": chat,
            "message_id": message,
            "reply_markup": reply_markup
        }
        params.update(kwargs)
        data = requests.get(f"{self.url}editMessageReplyMarkup", params=params, proxies=self.proxies)
        while data.status_code == 429:
            sleep(data.json()['parameters']['retry_after'])
            data = requests.get(f"{self.url}editMessageReplyMarkup", params=params, proxies=self.proxies)
        return data.json()

    def editOrSend(self, MsgInfo, text, **kwargs):
        res = None
        if MsgInfo.callback_data is not None:
            res = self.editMessageText(MsgInfo.from_chat, MsgInfo.msg_id, text, **kwargs)
        if MsgInfo.callback_data is None or (res and res['ok'] is False):
            if res and res['ok'] is False and MsgInfo.message:
                self.editMessageReplyMarkup(
                    MsgInfo.from_chat,
                    MsgInfo.msg_id,
                    proxies=self.proxies,
                    reply_markup=self.generateInlineKeyb(empty=True)
                )
            res = self.sendMessage(MsgInfo.from_chat, text, **kwargs)
        return res

    # ---- inline mode ----
    def inlineQueryResult(self, type_, id_, **kwargs):
        res = {"type": type_, "id": id_}
        if "reply_markup" in kwargs:
            kwargs.update({"reply_markup": json.loads(kwargs['reply_markup'])})
        res.update(kwargs)
        return res

    def answerInlineQuery(self, id_, results, **kwargs):
        params = {"inline_query_id": id_, "results": json.dumps(results)}
        params.update(kwargs)
        data = requests.get(f"{self.url}answerInlineQuery", params=params, proxies=self.proxies)
        return data.json()


# ============================================
#   VK
# ============================================

class Vk(BaseBot):

    def __init__(self, token=config.vk_info['access_token'], group_id=config.vk_info['group_id']):
        super().__init__()
        self.token = token
        self.group_id = group_id
        self.api_url = "https://api.vk.com/method/"
        self.v = "5.199"

        self.server = None
        self.key = None
        self.ts = None

        self.getLongPollServer()

    # ---- LongPoll ----
    def getLongPollServer(self):
        data = requests.get(
            self.api_url + "groups.getLongPollServer",
            params={"access_token": self.token, "v": self.v, "group_id": self.group_id}
        ).json()["response"]

        self.server = data["server"]
        self.key = data["key"]
        self.ts = data["ts"]

    def getUpdates(self, wait=25):
        params = {"act": "a_check", "key": self.key, "ts": self.ts, "wait": wait}
        data = requests.get(self.server, params=params, timeout=wait+5).json()

        if "ts" in data:
            self.ts = data["ts"]

        return data.get("updates", [])

    # ---- реализация интерфейса BaseBot ----
    def sendMessage(self, peer_id, text, keyboard=None, **kwargs):
        params = {
            "peer_id": peer_id,
            "message": text,
            "random_id": 0,
            "access_token": self.token,
            "v": self.v
        }

        if keyboard:
            params["keyboard"] = keyboard

        params.update(kwargs)

        data = requests.post(self.api_url + "messages.send", params=params)

        # flood control
        while data.status_code == 429 or (
            "error" in data.json() and data.json()["error"]["error_code"] == 6
        ):
            sleep(1)
            data = requests.post(self.api_url + "messages.send", params=params)

        return data.json()

    def makeButton(self, label, color="primary", payload=None):
        res = {"action": {"type": "text", "label": label}}
        if payload is not None:
            res["action"]["payload"] = json.dumps(payload)
        res["color"] = color
        return res

    def generateKeyboard(self, *rows, inline=False, empty=False):
        """
        Генератор клавы VK.
        rows — уже сформированные строки кнопок (makeRows из BaseBot можно юзать).
        """
        if empty:
            return json.dumps({"buttons": [], "inline": inline}, ensure_ascii=False)

        buttons = []
        for row in rows:
            buttons.append(row)

        obj = {
            "one_time": False,
            "inline": inline,
            "buttons": buttons
        }

        return json.dumps(obj, ensure_ascii=False)

    # ---- редактирование / editOrSend ----
    def editMessage(self, peer_id, message_id, text=None, keyboard=None):
        params = {
            "peer_id": peer_id,
            "message_id": message_id,
            "access_token": self.token,
            "v": self.v
        }
        if text is not None:
            params["message"] = text
        if keyboard is not None:
            params["keyboard"] = keyboard

        data = requests.post(self.api_url + "messages.edit", params=params)
        return data.json()

    def editOrSend(self, MsgInfo, text, keyboard=None):
        # если пришёл callback/payload и есть id сообщения — пробуем редактировать
        if getattr(MsgInfo, "payload", None) is not None and getattr(MsgInfo, "msg_id", None) is not None:
            res = self.editMessage(
                peer_id=MsgInfo.peer_id,
                message_id=MsgInfo.msg_id,
                text=text,
                keyboard=keyboard
            )
            if "error" in res:
                return self.sendMessage(MsgInfo.peer_id, text, keyboard)
            return res

        return self.sendMessage(MsgInfo.peer_id, text, keyboard)


# Для удобства (пример структуры)
class VkMsgInfo:
    def __init__(self, peer_id, msg_id=None, payload=None):
        self.peer_id = peer_id
        self.msg_id = msg_id
        self.payload = payload


def sendErrorMessage(logger, to, exception):
    t = Tg()
    keyb = t.generateInlineKeyb(t.makeRows(t.makeButton("😡 Поругаться на разраба", url="tg://user?id=731264169")))
    try:
        t.sendMessage(to, "⚠ Произошла непредвиденная ошибка.\nОбратитесь к @l270011", reply_markup=keyb)
    except: pass
    logger.error(exception, exc_info=True)
