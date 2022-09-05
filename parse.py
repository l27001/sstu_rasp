#!/usr/bin/python3
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
from time import sleep
import methods

def get_groups():
    response = requests.get("https://rasp.sstu.ru/")
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
                mysql.query("REPLACE INTO groups (`institute`, `form`, `type`, `group-start`, `name`, `id`, `course`) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (institute, edu_form, group_type, group_start, group_name, group_id, course))
                print(f"Found group with id {group_id}")

def get_rasp(group):
    response = requests.get(f"https://rasp.sstu.ru/rasp/group/{group}")
    if(response.status_code != 200):
        raise(f"Got unknown HTTP status code: {response.status_code}")

    page = BeautifulSoup(response.text, "html.parser")
    days = page.findAll("div", class_="day")
    for day in days:
        if("day-color-red" in day.get("class") or "day-color-blue" in day.get("class") or "day-header-empty" in day.get("class")): continue
        day_header = day.find("div", class_="day-header").find("div").contents
        lesson_day = [day_header[0].text, [int(i) for i in day_header[1].text.split(".")]]
        lesson_num = 1
        for div in day.findAll("div", class_="day-lesson"):
            if("day-lesson-empty" not in div.get("class")):
                lesson_hours = div.find("div", class_="lesson-hour").text.strip().replace("\u2014", "").split(" - ")
                lesson_name = div.find("div", class_="lesson-name").text.strip()
                lesson_type = div.find("div", class_="lesson-type").text.strip()
                lesson_room = [i.text.strip() for i in div.findAll("div", class_="lesson-room")]
                lesson_teacher = [i.text.strip() for i in div.findAll("div", class_="lesson-teacher")]
                try: lesson_room.remove("")
                except ValueError: pass
                lesson_room = " ".join(lesson_room)
                lesson_teacher = "/".join(lesson_teacher)
                if(lesson_teacher == ""): lesson_teacher = "Нет данных"
                cur_date = date.today()
                if(lesson_day[1][0] == 1 and cur_date.month == 12):
                    cur_date.replace(year=cur_date.year + 1)
                cur_date = cur_date.replace(day=lesson_day[1][0], month=lesson_day[1][1]).isoformat()
                mysql.query("REPLACE INTO lessons (`date`, `weekday`, `time_start`, `time_end`, `teacher`, `lesson_num`, `name`, `type`, `room`, `group_id`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (cur_date, lesson_day[0], lesson_hours[0], lesson_hours[1], lesson_teacher, lesson_num, lesson_name, lesson_type, lesson_room, group))
            lesson_num += 1

if(__name__ == "__main__"):
    mysql = methods.Mysql()
    try:
        get_groups()
        groups = mysql.query("SELECT id FROM groups", fetch="all")
        for n in groups:
            try: get_rasp(n["id"]); sleep(.5)
            except KeyboardInterrupt: exit()
            except: print(f"Error while parsing group with id {n['id']}")
        mysql.query("DELETE FROM lessons WHERE date <= %s", (del_date, ))
    finally:
        mysql.close()