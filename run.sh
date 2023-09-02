#!/bin/bash

# preparing db
if [[ "$DROPTABLES" == "1" ]]; then
    python manage.py drop_db
fi
python manage.py create_db
python manage.py setup_webhook

# turn on bash's job control
set -m

# start primary process in background
python3 -m gunicorn -w 4 -b [::]:5100 app:app &

# start additional process
python manage.py init_scheduler

# return primary process back into the foreground
fg %1
