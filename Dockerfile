FROM bluelens/tensorflow:1.3.0-py3
MAINTAINER bluehackmaster <master@bluehack.net>

USER root

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install -r requirements.txt
RUN pip install --upgrade google-cloud-bigquery

CMD ["python", "main.py"]
