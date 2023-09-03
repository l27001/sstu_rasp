#!env python
import requests
import os
from pytz import timezone
from apscheduler.schedulers.background import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
from time import sleep
from multiprocessing import Pool
from telebot.util import quick_markup
from sqlalchemy import or_, and_

import config
from app import bot, db, models, logger

dir_path = os.path.dirname(os.path.realpath(__file__))
headers = {
    'User-Agent': "Mozilla/5.0 (compatible; ssturasp_bot/v1.0.0; testapp; l27001@ezdomain.ru)"
}


def parse_groups():
    groups = []
    attempts = 0
    response = None
    while attempts < 3:
        try:
            response = requests.get("https://rasp.sstu.ru/", headers=headers, timeout=5)
            if(response.status_code != 200):
                raise RuntimeError(f'Unexpected http code for parse_groups - {response.status_code}')
            break
        except Exception as e:
            logger.error(e)
            sleep(1)
            attempts += 1
    if(response is None):
        logger.error("Can't parse group list")
        return groups
    page = BeautifulSoup(response.text, "lxml")
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
                group = models.Groups.query.filter_by(name = group_name).one_or_none()
                if(not group):
                    new_group = models.Groups(group_id, group_name, edu_form, group_type, group_start, course, institute)
                    db.session.add(new_group)
                    db.session.flush()
                    db_group_id = new_group.id
                else:
                    if(group.sstu_id):
                        duplicate_group = models.Groups.query.filter(and_(models.Groups.sstu_id == group_id, models.Groups.id != group.id)).one_or_none()
                        if(duplicate_group):
                            duplicate_group.sstu_id = None
                    group.last_appearance = datetime.now()
                    group.sstu_id = group_id
                    db_group_id = group.id
                groups.append(db_group_id)
    db.session.execute(models.Groups.__table__.delete().where(models.Groups.last_appearance <= (date.today() - timedelta(days=2))))
    db.session.execute(models.Lessons.__table__.delete().where(models.Lessons.date <= (date.today() - timedelta(days=7))))
    db.session.commit()
    return groups


def parse_rasp(group):
    attempts = 0
    response = None
    sstugroup = models.Groups.query.filter_by(id = group).one_or_none()
    if(not sstugroup):
        return
    while attempts < 3:
        try:
            response = requests.get(f"https://rasp.sstu.ru/rasp/group/{sstugroup.sstu_id}", headers=headers, timeout=5)
            if(response.status_code != 200):
                raise RuntimeError(f'Unexpected http code for group #{group} - {response.status_code}')
            break
        except Exception as e:
            logger.error(e)
            sleep(1)
            attempts += 1
    page = BeautifulSoup(response.text, "lxml")
    days = page.findAll("div", class_="day")
    for day in days:
        if("day-color-red" in day.get("class") or "day-color-blue" in day.get("class") or "day-header-empty" in day.get("class")): continue
        day_header = day.find("div", class_="day-header")
        if("day-header-hour" in day_header.get("class")): continue
        day_header = day_header.find("div").contents
        lesson_day = [day_header[0].text, [int(i) for i in day_header[1].text.split(".")]]
        cur_date = date.today()
        if(lesson_day[1][1] == 1 and cur_date.month == 12):
            cur_date.replace(year=cur_date.year + 1)
        cur_date = cur_date.replace(day=lesson_day[1][0], month=lesson_day[1][1])
        db.session.execute(models.Lessons.__table__.delete().where(and_(models.Lessons.date == cur_date, models.Lessons.group_id == group)))
        db.session.flush()
        lesson_num = 1
        for div in day.findAll("div", class_="day-lesson"):
            if("day-lesson-empty" not in div.get("class")):
                lesson_hours = div.find("div", class_="lesson-hour").text.strip().replace("\u2014", "").split(" - ")
                lesson_name = div.find("div", class_="lesson-name").text.strip()
                lesson_type = div.find("div", class_="lesson-type").text.strip()
                lesson_room = [i.text.strip().replace("_", "") for i in div.findAll("div", class_="lesson-room")]
                lesson_teacher = [i.text.strip() for i in div.findAll("div", class_="lesson-teacher")]
                try:
                    lesson_room.remove("")
                except ValueError:
                    pass
                lesson_room = " ".join(lesson_room)
                lesson_teacher = "/".join(lesson_teacher)
                if(lesson_teacher == ""): lesson_teacher = "Нет данных"
                lesson = models.Lessons(cur_date, group, lesson_teacher, lesson_day[0], lesson_num, lesson_name, lesson_type, lesson_room, lesson_hours[0], lesson_hours[1])
                db.session.add(lesson)
            lesson_num += 1
    db.session.commit()


def parse_weather():
    if(config.OPENWEATHERMAP_API_KEY == None):
        return 0
    response = requests.get(f"https://api.openweathermap.org/data/2.5/forecast?appid={config.OPENWEATHERMAP_API_KEY}&units=metric&lat=51.530018&lon=46.034683&lang=ru", headers=headers)
    if(response.status_code != 200):
        logger.error(f"Weather got unknown HTTP status code: {response.status_code}")
        return
    data = response.json()
    for n in data['list']:
        weather = models.Weather.query.filter_by(date=datetime.fromtimestamp(n['dt'])).one_or_none()
        if(weather):
            weather.temp = int(round(n['main']['temp']))
            weather.weather = n['weather'][0]['description'].title()
            weather.weather_main = n['weather'][0]['main']
            weather.weather_icon = n['weather'][0]['icon']
        else:
            weather = models.Weather(datetime.fromtimestamp(n['dt']), int(round(n['main']['temp'])), n['weather'][0]['main'], n['weather'][0]['description'].title(), n['weather'][0]['icon'])
            db.session.add(weather)
    db.session.execute(models.Weather.__table__.delete().where(models.Weather.date <= (date.today() - timedelta(days=2))))
    db.session.commit()


def notify_tomorrow():
    pass


def do_parse():
    groups = parse_groups()
    p = Pool()
    p.map(parse_rasp, groups)
    p.close()
    p.join()


def run_scheduler():
    jobstores = {
        'default': SQLAlchemyJobStore(url=config.SQLALCHEMY_DATABASE_URI)
    }
    executors = {
        'default': ProcessPoolExecutor(max_workers=os.cpu_count())
    }
    job_defaults = {
        'coalesce': False,
        'max_instances': 3
    }
    scheduler = BlockingScheduler()

    scheduler.add_job(do_parse, 'cron', hour='*/3', minute='00', id='rasp', replace_existing=True)
    scheduler.add_job(parse_weather, 'cron', hour='*', minute='00', id='weather', replace_existing=True)
    scheduler.add_job(notify_tomorrow, 'cron', hour='19', minute='00', id='notify', replace_existing=True)

    scheduler.configure(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone=timezone("Europe/Saratov"))
    scheduler.start()
