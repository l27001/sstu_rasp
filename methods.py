import pymysql, requests, json
from pymysql.err import InterfaceError, OperationalError
from time import sleep
import config

class Mysql:

    def __init__(self):
        self.con = Mysql.make_con()

    def query(self,query,variables=(),fetchall=False):
        try:
            cur = self.con.cursor()
            cur.execute(query, variables)
        except (InterfaceError,OperationalError):
            self.con = Mysql.make_con()
            cur = self.con.cursor()
            cur.execute(query, variables)
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
                 autocommit=True,
                 cursorclass=pymysql.cursors.DictCursor,
                 write_timeout=5)

    def close(self):
        self.con.close() 

class Tg:

    def __init__(self, token=config.tg_info['access_token']):
        self.url = f"{config.tg_info['url']}bot{token}/"
        self.offset = 0
        self.getMe()

    def getOffset(self):
        return self.offset

    def setOffset(self, offset):
        self.offset = offset

    def getUpdates(self, offset=0, timeout=60):
        data = requests.get(f"{self.url}getUpdates", params={"offset":offset, "timeout":timeout}, timeout=61).json()
        if(len(data['result']) > 0):
            self.offset = data['result'][-1]['update_id']+1
        return data

    def sendMessage(self, chat_id, text, allow_sending_without_reply=True, parse_mode="Markdown", **kwargs):
        params = {"chat_id":chat_id, "text":text, "allow_sending_without_reply":allow_sending_without_reply, "parse_mode":parse_mode}
        params.update(kwargs)
        data = requests.get(f"{self.url}sendMessage", params=params)
        if(data.status_code == 429):
            sleep(1)
            data = requests.get(f"{self.url}sendPhoto", params=params)
        return data.json()

    def sendPhoto(self, chat_id, photo, **kwargs):
        params = {"chat_id":chat_id, "photo":photo}
        params.update(kwargs)
        data = requests.get(f"{self.url}sendPhoto", params=params)
        if(data.status_code == 429):
            sleep(1)
            data = requests.get(f"{self.url}sendPhoto", params=params)
        return data.json()

    def getMe(self):
        data = requests.get(f"{self.url}getMe").json()['result']
        self.id = data['id']
        self.username = data['username']

    def makeButton(self, text, callback_data="", **kwargs):
        res = {"text": text, "callback_data": callback_data}
        res.update(kwargs)
        return res

    def makeRows(self, *args, max_=5, add_list=True):
        if(len(args) > 0 and type(args[0]) == list):
            args = args[0]
        if(len(args) > max_):
            return [args[x:x+max_] for x in range(0, len(args), max_)]
        if(add_list == True):
            return [list(args)]
        return list(args)

    def generateInlineKeyb(self, *args, home=True, empty=False):
        if(empty == True):
            return json.dumps({"inline_keyboard": []})
        s = []
        for n in args:
            s += n
        if(home == True):
            s.append([{"text": "🏠 Меню", "callback_data": "clear_state"}])
        return json.dumps({"inline_keyboard": s})

    def editMessageText(self, chat, message, text, parse_mode="Markdown", **kwargs):
        params = {"chat_id": chat, "message_id": message, "text": text, "parse_mode": parse_mode}
        params.update(kwargs)
        data = requests.get(f"{self.url}editMessageText", params=params)
        if(data.status_code == 429):
            sleep(1)
            data = requests.get(f"{self.url}sendPhoto", params=params)
        return data.json()

    def editOrSend(self, MsgInfo, text, **kwargs):
        if(MsgInfo.callback_data is not None):
            res = self.editMessageText(MsgInfo.from_chat, MsgInfo.msg_id, text, **kwargs)
        if(MsgInfo.callback_data is None or res['ok'] == False):
            res = self.sendMessage(MsgInfo.from_chat, text, **kwargs)
        return res

    def inlineQueryResult(self, type_, id_, **kwargs):
        res = {"type": type_, "id": id_}
        if("reply_markup" in kwargs):
            kwargs.update({"reply_markup": json.loads(kwargs['reply_markup'])})
        res.update(kwargs)
        return res

    def answerInlineQuery(self, id_, results, **kwargs):
        params = {"inline_query_id": id_, "results": json.dumps(results)}
        params.update(kwargs)
        data = requests.get(f"{self.url}answerInlineQuery", params=params)
        return data.json()

def getUserInfo(user):
    user_info = mysql.query("SELECT * FROM users WHERE id = %s", (user,))
    if(user_info == None):
        mysql.query("INSERT INTO users (id) VALUES (%s)", (user,))
        user_info = mysql.query("SELECT * FROM users WHERE id = %s", (user,))
    return user_info

def getUserGroups(user_id):
    return mysql.query("SELECT g.id, gs.subscribe, g.name FROM group_subs gs INNER JOIN groups g ON gs.group_id = g.id WHERE user_id = %s",
        (user_id, ), fetchall=True)

def setUserState(id_, state=None):
    mysql.query("UPDATE `users` SET state = %s WHERE id = %s", (state, id_))

def sendErrorMessage(to, exception):
    t = Tg()
    keyb = t.generateInlineKeyb(t.makeRows(t.makeButton("😡 Поругаться на разраба", url="tg://user?id=731264169")))
    try:
        t.sendMessage(to, "⚠ Произошла непредвиденная ошибка.\nОбратитесь к @l270011", reply_markup=keyb)
    except: pass
    logger.error(exception)