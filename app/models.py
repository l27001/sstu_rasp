from datetime import datetime, time, date as dt_date
from dataclasses import dataclass

from app import db


@dataclass
class Groups(db.Model):
    id: int
    sstu_id: int
    name: str
    form: str
    type: str
    abbreviation: str
    course: int
    institute: str
    last_appearance: datetime

    id = db.Column(db.Integer, primary_key = True)
    sstu_id = db.Column(db.Integer, unique = True)
    name = db.Column(db.String(16), index = True)
    form = db.Column(db.String(64))
    type = db.Column(db.String(64))
    abbreviation = db.Column(db.String(8))
    course = db.Column(db.SmallInteger)
    institute = db.Column(db.String(64))
    last_appearance = db.Column(db.DateTime)

    def __init__(self, sstu_id, name, form, type_, abbreviation, course, institute, last_appearance = datetime.now()):
        self.sstu_id = sstu_id
        self.name = name
        self.form = form
        self.type = type_
        self.abbreviation = abbreviation
        self.course = course
        self.institute = institute
        self.last_appearance = last_appearance

    def __repr__(self):
        return f"<Group {self.name}[{self.id}]>"


@dataclass
class Lessons(db.Model):
    date: dt_date
    group_id: int
    teacher: str
    weekday: str
    lesson_num: int
    name: str
    type: str
    room: str
    time_start: time
    time_end: time

    date = db.Column(db.Date, primary_key = True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key = True)
    teacher = db.Column(db.String(128))
    weekday = db.Column(db.String(16))
    lesson_num = db.Column(db.SmallInteger, primary_key = True)
    name = db.Column(db.String(256))
    type = db.Column(db.String(16))
    room = db.Column(db.String(32))
    time_start = db.Column(db.Time)
    time_end = db.Column(db.Time)

    def __init__(self, date_, group_id, teacher, weekday, lesson_num, name, type_, room, time_start, time_end):
        self.date = date_
        self.group_id = group_id
        self.teacher = teacher
        self.weekday = weekday
        self.lesson_num = lesson_num
        self.name = name
        self.type = type_
        self.room = room
        self.time_start = time_start
        self.time_end = time_end

    def __repr__(self):
        return f"<Lesson {self.group_id} [{self.date.isoformat()} #{self.lesson_num}]>"


@dataclass
class Users(db.Model):
    id: int
    
    id = db.Column(db.BigInteger, primary_key = True)

    def __init__(self, id_):
        self.id = id_
    
    def __repr__(self):
        return f"<User {self.id}>"


@dataclass
class GroupFavorites(db.Model):
    user_id: int
    group_id: int
    subscribe: bool

    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), primary_key = True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key = True)
    subscribe = db.Column(db.Boolean)

    def __init__(self, user_id, group_id, subscribe = 0):
        self.user_id = user_id
        self.group_id = group_id
        self.subscribe = subscribe

    def toggle_subscribe(self):
        self.subscribe = not self.subscribe
        db.session.commit()
        return self.subscribe
    
    def enable_subscribe(self):
        self.subscribe = 1
        db.session.commit()
    
    def disable_subscribe(self):
        self.subscribe = 0
        db.session.commit()

    def __repr__(self):
        return f"<Sub {self.user_id} -> {self.group_id}>"


@dataclass
class Weather(db.Model):
    date: datetime
    temp: int
    weather_main: str
    weather: str
    weather_icon: str

    date = db.Column(db.DateTime, primary_key = True)
    temp = db.Column(db.Integer)
    weather_main = db.Column(db.String(32))
    weather = db.Column(db.String(32))
    weather_icon = db.Column(db.String(8))

    def __init__(self, date_, temp, weather_main, weather, weather_icon):
        self.date = date_
        self.temp = temp
        self.weather_main = weather_main
        self.weather = weather
        self.weather_icon = weather_icon
    
    def __repr__(self):
        return f"<Weather {self.date.isoformat()}>"