import pymysql, requests, json
from pymysql.err import InterfaceError, OperationalError
import config

class Mysql:

    def __init__(self):
        self.con = Mysql.make_con()

    def query(self,query,variables=(),fetch="one"):
        try:
            cur = self.con.cursor()
            cur.execute(query, variables)
        except (InterfaceError,OperationalError):
            self.con = Mysql.make_con()
            cur = self.con.cursor()
            cur.execute(query, variables)
        if(fetch == "one"):
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
                 cursorclass=pymysql.cursors.DictCursor)

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
        return data.json()

    def sendPhoto(self, chat_id, photo, **kwargs):
        params = {"chat_id":chat_id, "photo":photo}
        params.update(kwargs)
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

    def generateInlineKeyb(self, *args):
        if(type(args[0]) != list):
            args = list(args)
        else:
            args = args[0]
        return json.dumps({"inline_keyboard": [
                args
            ]
        })

    def editMessageText(self, chat, message, text, keyb=""):
        params = {"chat_id": chat, "message_id": message, "text": text, "reply_markup": keyb}
        data = requests.get(f"{self.url}editMessageText", params=params)
        return data.json()

def getUserInfo(user, chat):
    if(chat is not None):
        chat_info = mysql.query("SELECT * FROM users WHERE id = %s", (chat,))
        if(chat_info == None):
            mysql.query("INSERT INTO users (id) VALUES (%s)", (chat,))
            chat_info = mysql.query("SELECT * FROM users WHERE id = %s", (chat,))
    else: chat_info = None
    user_info = mysql.query("SELECT * FROM users WHERE id = %s", (user,))
    if(user_info == None):
        mysql.query("INSERT INTO users (id) VALUES (%s)", (user,))
        user_info = mysql.query("SELECT * FROM users WHERE id = %s", (user,))
    return user_info, chat_info

def setUserState(id_, state=None):
    mysql.query("UPDATE `users` SET state = %s WHERE id = %s", (state, id_))

def sendErrorMessage(to, exception):
    Tg().sendMessage(to, "⚠ Произошла непредвиденная ошибка.\nОбратитесь к @l270011")
    print(exception)