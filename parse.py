#!/usr/bin/python3
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
from time import sleep
import methods

headers = {
    'User-Agent': "Mozilla/5.0 (compatible; ssturasp_bot/v0.1.1; https://t.me/ssturasp_bot; l27001@ezdomain.ru)"
}

def parse_groups():
    response = requests.get("https://rasp.sstu.ru/", headers=headers)
    if(response.status_code != 200):
        raise(f"Got unknown HTTP status code: {response.status_code}")

    page = BeautifulSoup(response.text, "html.parser")
    cards = page.find("div", id="raspStructure").findAll("div", class_="card")

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
                mysql.query("INSERT INTO `groups` (`institute`, `form`, `type`, `group_start`, `name`, `id`, `course`) \
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE `institute`=%s, `form`=%s, `type`=%s, `group_start`=%s, `name`=%s, `course`=%s, `last_appearance`=%s",
                    (institute, edu_form, group_type, group_start, group_name, group_id, course, institute, edu_form, group_type, group_start, group_name, course, datetime.now().isoformat()))
    del_date = (date.today() - timedelta(days=2)).isoformat()
    mysql.query("DELETE FROM `groups` WHERE `last_appearance` <= %s", (del_date, ))

def parse_rasp(group):
    response = requests.get(f"https://rasp.sstu.ru/rasp/group/{group}", headers=headers)
    if(response.status_code != 200):
        raise(f"Got unknown HTTP status code: {response.status_code}")

    page = BeautifulSoup(response.text, "html.parser")
    days = page.findAll("div", class_="day")
    for day in days:
        if("day-color-red" in day.get("class") or "day-color-blue" in day.get("class") or "day-header-empty" in day.get("class")): continue
        day_header = day.find("div", class_="day-header").find("div").contents
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
                if(lesson_teacher == ""): lesson_teacher = "Нет данных"
                mysql.query("REPLACE INTO `lessons` (`date`, `weekday`, `time_start`, `time_end`, `teacher`, `lesson_num`, `name`, `type`, `room`, `group_id`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (cur_date, lesson_day[0], lesson_hours[0], lesson_hours[1], lesson_teacher, lesson_num, lesson_name, lesson_type, lesson_room, group))
            lesson_num += 1
    del_date = (date.today() - timedelta(days=2)).isoformat()
    mysql.query("DELETE FROM `lessons` WHERE `date` <= %s", (del_date, ))

def parse_weather():
    response = requests.get("https://api.openweathermap.org/data/2.5/forecast?appid=e07e04a3d6a1cf3000173581aded051e&units=metric&lat=51.530018&lon=46.034683&lang=ru")
    if(response.status_code != 200):
        raise(f"Got unknown HTTP status code: {response.status_code}")
    data = response.json()
    for n in data['list']:
        mysql.query("REPLACE INTO `weather` (`date`, `temp`, `weather`, `weather_main`, `weather_icon`) VALUES (%s, %s, %s, %s, %s)",
            (datetime.fromtimestamp(n['dt']), int(round(n['main']['temp'])), n['weather'][0]['description'].title(), n['weather'][0]['main'], n['weather'][0]['icon']))
    del_date = (date.today() - timedelta(days=2)).isoformat()
    mysql.query("DELETE FROM `weather` WHERE `date` <= %s", (del_date, ))

def notify_tomorrow():
    Tg = methods.Tg()
    groups = mysql.query("SELECT * FROM `groups`", fetchall=True)
    tomorrow = date.today() + timedelta(days=1)
    for group in groups:
        subscribers = mysql.query("SELECT * FROM `group_subs` WHERE `group_id` = %s", (group['id'], ), fetchall=True)
        if(subscribers is None or subscribers == ()):
            continue
        lessons = mysql.query("SELECT * FROM `lessons` WHERE `date` = %s AND `group_id` = %s", (tomorrow.isoformat(), group['id']), fetchall=True)
        if(lessons is None or lessons == ()):
            continue
        for l in range(len(lessons)):
            lessons[l].update({"time_start": datetime.strptime(f"{lessons[l]['date']} {lessons[l]['time_start']}", "%Y-%m-%d %H:%M:%S"),
                "time_end": datetime.strptime(f"{lessons[l]['date']} {lessons[l]['time_end']}", "%Y-%m-%d %H:%M:%S")})
        weather = mysql.query("SELECT `temp`,`weather` FROM `weather` WHERE `date` BETWEEN %s AND %s",
            (f"{lessons[0]['date']} {lessons[0]['time_start'].strftime('%H:%M')}", f"{lessons[-1]['date']} {lessons[-1]['time_end'].strftime('%H:%M')}"))
        if(weather is None):
            weather = {"temp": 0, "weather": "Нет данных"}
        les = "\n".join([f"[{i['lesson_num']}] {i['name']}" for i in lessons])
        msg = f"""🔔 Напоминание о расписании на завтра для *{group['name']}*:
Кол-во пар: {len(lessons)}
Первая пара: {lessons[0]['time_start'].strftime("%H:%M")}
Последняя пара: {lessons[-1]['time_end'].strftime("%H:%M")}
Погода: {weather['weather']} {weather['temp']}°C
Пары:
_{les}_"""
        keyb = Tg.generateInlineKeyb(Tg.makeRows(Tg.makeButton("🗒️ Подробнее", f"date_rasp/{group['id']},{lessons[0]['date']}"),
            Tg.makeButton("❗ Отписаться от рассылки", f"toggle_sub/{group['id']}"), max_=2))
        for sub in subscribers:
            Tg.sendMessage(sub['user_id'], msg, reply_markup=keyb)

if(__name__ == "__main__"):
    mysql = methods.Mysql()
    import sys
    try:
        if(len(sys.argv) == 1):
            parse_groups()
            groups = mysql.query("SELECT id FROM groups", fetchall=True)
            for n in groups:
                try: parse_rasp(n["id"]); sleep(.5)
                except KeyboardInterrupt: exit()
                except: print(f"Error while parsing group with id {n['id']}")
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
    finally:
        mysql.close()
