#!env python3
import requests
import os
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
from time import sleep
from multiprocess import Pool
import methods
from config import openweathermap_key

dir_path = os.path.dirname(os.path.realpath(__file__))
headers = {
    'User-Agent': "Mozilla/5.0 (compatible; ssturasp_bot/v0.1.3; https://t.me/ssturasp_bot; l27001@ezdomain.ru)"
}

def parse_groups():
    attempts = 0
    response = None
    while attempts < 3:
        try:
            response = requests.get("https://rasp.sstu.ru/", headers=headers, timeout=5)
            if(response.status_code != 200): raise RuntimeError(f'Unexpected http code for parse_groups - {response.status_code}')
            break
        except Exception as e:
            sleep(1)
            attempts += 1
    if(response is None):
        print("Can't parse group list")
        exit()
    page = BeautifulSoup(response.text, "html.parser")
    cards = page.find("div", id="raspStructure").findAll("div", class_="card")
    groups = []
    mysql = methods.Mysql(autocommit=False)
    try:
        for card in cards:
            institute = card.find("div", class_="institute").text.strip()
            for div in card.find("div", class_="card-body").findAll("div"):
                if("edu-form" in div.get("class")):
                    edu_form = div.text.strip()
                elif("group-type" in div.get("class")):
                    group_type = div.text.strip()
                elif("groups" in div.get("class")):
                    group_start = div.find("div", class_="group-start").text.strip()
                elif("group" in div.get("class")):
                    a = div.find("a")
                    group_id = int(a.get("href").split("/")[-1])
                    group_name = a.text.strip()
                    course = int(group_name[-2])
                    group = mysql.query("SELECT * FROM `groups` WHERE `name`=%s", (group_name, ))
                    if(not group):
                        db_group_id = mysql.query("INSERT INTO `groups` (`institute`, `form`, `type`, `group_start`, `name`, `sstu_id`, `course`) \
                            VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE `sstu_id`=%s, `institute`=%s, `form`=%s, `type`=%s, `group_start`=%s, `name`=%s, `course`=%s, `last_appearance`=%s",
                            (institute, edu_form, group_type, group_start, group_name, group_id, course, group_id, institute, edu_form, group_type, group_start, group_name, course, datetime.now().isoformat()), lastrow=True)
                    else:
                        if(group['sstu_id']):
                            dgroup = mysql.query("SELECT `id` FROM `groups` WHERE `sstu_id`=%s AND `id`!=%s", (group_id, group['id']))
                            if(dgroup):
                                mysql.query("UPDATE `groups` SET `sstu_id`=NULL WHERE `id`=%s", (dgroup['id'], ))
                        mysql.query("UPDATE `groups` SET `last_appearance`=%s, `sstu_id`=%s WHERE `id`=%s", (datetime.now().isoformat(), group_id, group['id']))
                        db_group_id = group['id']
                    groups.append(db_group_id)
        del_date = (date.today() - timedelta(days=7)).isoformat()
        mysql.query("DELETE FROM `groups` WHERE `last_appearance` <= %s", (del_date, ))
        mysql.query("DELETE FROM `lessons` WHERE `date` <= %s", (del_date, ))
        mysql.commit()
    finally:
        mysql.close()
    return groups

def parse_rasp(group):
    attempts = 0
    response = None
    mysql = methods.Mysql(autocommit=False)
    sstugroup = mysql.query("SELECT sstu_id FROM groups WHERE id=%s", (group, ))
    if(not sstugroup):
        mysql.close()
        return
    while attempts < 3:
        try:
            response = requests.get(f"https://rasp.sstu.ru/rasp/group/{sstugroup['sstu_id']}", headers=headers, timeout=5)
            if(response.status_code != 200): raise RuntimeError(f'Unexpected http code for group #{group} - {response.status_code}')
            break
        except Exception as e:
            sleep(1)
            attempts += 1
    try:
        page = BeautifulSoup(response.text, "html.parser")
        if(page is None):
            return
        days = page.findAll("div", class_="day")
        for day in days:
            if("day-color-red" in day.get("class") or "day-color-blue" in day.get("class") or "day-header-empty" in day.get("class")): continue
            day_header = day.find("div", class_="day-header")
            if("day-header-hour" in day_header.get("class")): continue
            day_header = day_header.find("div").contents
            lesson_day = [day_header[0].text, [int(i) for i in day_header[1].text.split(".")]]
            cur_date = date.today()
            if(lesson_day[1][0] == 1 and cur_date.month == 12):
                cur_date.replace(year=cur_date.year + 1)
            cur_date = cur_date.replace(day=lesson_day[1][0], month=lesson_day[1][1]).isoformat()
            mysql.query("DELETE FROM `lessons` WHERE `date` = %s AND `group_id` = %s",
                    (cur_date, group))
            lesson_num = 1
            for div in day.findAll("div", class_="day-lesson"):
                if("day-lesson-empty" not in div.get("class")):
                    lesson_hours = div.find("div", class_="lesson-hour").text.strip().replace("\u2014", "").split(" - ")
                    lesson_name = div.find("div", class_="lesson-name").text.strip()
                    lesson_type = div.find("div", class_="lesson-type").text.strip()
                    lesson_room = [i.text.strip().replace("_", "") for i in div.findAll("div", class_="lesson-room")]
                    lesson_teacher = [i.text.strip() for i in div.findAll("div", class_="lesson-teacher")]
                    try: lesson_room.remove("")
                    except ValueError: pass
                    lesson_room = " ".join(lesson_room)
                    lesson_teacher = "/".join(lesson_teacher)
                    if(lesson_teacher in ("", "/")): lesson_teacher = "Нет данных"
                    mysql.query("REPLACE INTO `lessons` (`date`, `weekday`, `time_start`, `time_end`, `teacher`, `lesson_num`, `name`, `type`, `room`, `group_id`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (cur_date, lesson_day[0], lesson_hours[0], lesson_hours[1], lesson_teacher, lesson_num, lesson_name, lesson_type, lesson_room, group))
                lesson_num += 1
        mysql.commit()
    finally:
        mysql.close()

def parse_weather():
    if(openweathermap_key == None):
        return 0
    response = requests.get(f"https://api.openweathermap.org/data/2.5/forecast?appid={openweathermap_key}&units=metric&lat=51.530018&lon=46.034683&lang=ru", headers=headers)
    if(response.status_code != 200):
        print(f"Got unknown HTTP status code: {response.status_code}")
        return 0
    data = response.json()
    mysql = methods.Mysql(autocommit=False)
    try:
        for n in data['list']:
            mysql.query("REPLACE INTO `weather` (`date`, `temp`, `weather`, `weather_main`, `weather_icon`) VALUES (%s, %s, %s, %s, %s)",
                (datetime.fromtimestamp(n['dt']), int(round(n['main']['temp'])), n['weather'][0]['description'].title(), n['weather'][0]['main'], n['weather'][0]['icon']))
        del_date = (date.today() - timedelta(days=2)).isoformat()
        mysql.query("DELETE FROM `weather` WHERE `date` <= %s", (del_date, ))
        mysql.commit()
    finally:
        mysql.close()

def notify_tomorrow():
    mysql = methods.Mysql()
    try:
        Tg = methods.Tg()
        groups = mysql.query("SELECT group_id AS id, COUNT(*) AS count FROM `group_subs` WHERE subscribe = 1 GROUP BY group_id ORDER BY count DESC", fetchall=True)
        tomorrow = date.today() + timedelta(days=1)
        for group in groups:
            group = mysql.query("SELECT * FROM `groups` WHERE id = %s", (group['id'], ))
            subscribers = mysql.query("SELECT * FROM `group_subs` g LEFT JOIN `notifies` n ON g.user_id = n.user AND date = CURDATE() WHERE `group_id` = %s AND `subscribe` = 1 AND date IS NULL", (group['id'], ), fetchall=True)
            if(subscribers is None or subscribers == ()):
                continue
            lessons = mysql.query("SELECT * FROM `lessons` WHERE `date` = %s AND `group_id` = %s", (tomorrow.isoformat(), group['id']), fetchall=True)
            if(lessons is None or lessons == ()):
                continue
            for l in range(len(lessons)):
                lessons[l].update({"time_start": datetime.strptime(f"{lessons[l]['date']} {lessons[l]['time_start']}", "%Y-%m-%d %H:%M:%S"),
                    "time_end": datetime.strptime(f"{lessons[l]['date']} {lessons[l]['time_end']}", "%Y-%m-%d %H:%M:%S")})
            weather = mysql.query("SELECT `date`, `temp`, `weather` FROM `weather` WHERE `date` BETWEEN %s AND %s",
                (f"{lessons[0]['date']} {lessons[0]['time_start'].strftime('%H:%M')}", f"{lessons[-1]['date']} {lessons[-1]['time_end'].strftime('%H:%M')}"))
            if(weather == None):
                weather = mysql.query("SELECT `date`, `temp`, `weather` FROM `weather` WHERE date = (SELECT MAX(date) AS date FROM `weather` WHERE date < %s LIMIT 1)", (lessons[0]['time_start'].strftime("%Y-%m-%d %H:%M:%S"), ))
            if(weather == None or weather['date'].strftime("%Y-%m-%d") != lessons[0]['time_start'].strftime("%Y-%m-%d")):
                weather = {"temp": None, "weather": "Нет данных"}
            les = "\n".join([f"[{i['lesson_num']}] {i['name']} {i['type']}" for i in lessons])
            msg = f"""🔔 <u>Напоминание о расписании на завтра для <b>{group['name']}</b></u>:
<b>Кол-во пар</b>: {len(lessons)}
<b>Начало занятий</b>: {lessons[0]['time_start'].strftime("%H:%M")}
<b>Конец занятий</b>: {lessons[-1]['time_end'].strftime("%H:%M")}
<b>Погода</b>: {weather['weather']} {weather['temp']}°C
<b>Пары</b>:
<i>{les}</i>"""
            keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🗒️ Подробнее", f"date_rasp/{group['id']},{lessons[0]['date']}"),
                Tg.makeButton("🌐 Расписание на неделю", web_app={"url": f"https://ssturasp.l27001.net/group/{group['sstu_id']}"}),
                Tg.makeButton("❗ Отписаться от рассылки", f"toggle_sub/{group['id']}"), max_=2))
            for sub in subscribers:
                res = Tg.sendMessage(sub['user_id'], msg, reply_markup=keyb)
                mysql.query("INSERT INTO notifies (`user`, `date`) VALUES (%s, CURDATE())", (sub['user_id'], ))
                if("error_code" in res and res["error_code"] == 403):
                    mysql.query("UPDATE `group_subs` SET `subscribe` = 0 WHERE `user_id` = %s", (sub['user_id'], ))
                sleep(0.04)
    finally:
        mysql.close()

if(__name__ == "__main__"):
    import sys
    if(len(sys.argv) == 1):
        groups = parse_groups()
        with Pool() as p:
            p.map(parse_rasp, groups)
    elif(sys.argv[1] == "weather"):
        parse_weather()
    elif(sys.argv[1] == "groups"):
        parse_groups()
    elif(sys.argv[1] == "group"):
        if(len(sys.argv) < 2 or sys.argv[2].isdigit() == False):
            print("./parse.py group <ID>")
        else:
            parse_rasp(int(sys.argv[2]))
    elif(sys.argv[1] == "notify"):
        notify_tomorrow()
    else:
        print("./parse.py [weather|groups|group|notify]")
