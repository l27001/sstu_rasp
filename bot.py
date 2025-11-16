#!env python3
import os
import sys
import logging
import sys
from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError
import methods
from commands import execute_command

logger = logging.getLogger("sstu_rasp")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt="%(asctime)s %(name)s.%(levelname)s: %(message)s", datefmt="%Y.%m.%d %H:%M:%S")
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

dir_path = os.path.dirname(os.path.realpath(__file__))

try:
    logger.info("Запуск бота...")
    Tg = methods.Tg()
    if(os.path.isfile(dir_path+"/tg_TS") == True):
        with open(dir_path+"/tg_TS") as f:
            Tg.setOffset(f.read())
    while True:
        offset = Tg.getOffset()
        data = Tg.getUpdates(offset=offset)
        if(offset != Tg.getOffset()):
            with open(dir_path+"/tg_TS", "w") as f:
                f.write(str(Tg.getOffset()))
        for n in data['result']:
            execute_command(logger, Tg, n)

except KeyboardInterrupt:
    pass
except(ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError) as e:
    logger.critical(e, exc_info=True)
    logger.critical("Запуск не удался.")
    sys.exit(1)
finally:
    logger.info("Завершение...")
