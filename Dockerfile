FROM python:3.11.5

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app ./app
COPY *.py .
COPY run.sh .
RUN chmod +x run.sh

STOPSIGNAL SIGINT

CMD [ "./run.sh" ]
