FROM radiansoftware/sleeping-beauty:v4.1.0 AS sleepingd

# EOL April 2029
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y python3 python3-pip python3-venv pipx && rm -rf /var/lib/apt/lists/*
ENV PATH=/root/.local/bin:${PATH}
RUN pipx install "poetry>=2.1,<2.2"
RUN pipx inject poetry "poetry-plugin-export>=1.9,<1.10"

WORKDIR /src
COPY pyproject.toml poetry.lock /src/
RUN poetry export > requirements.txt

RUN python3 -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH=/venv/bin:${PATH}
RUN pip3 install -r requirements.txt

COPY photoprismproxy.py /src/
COPY pages/ /src/pages/

COPY --from=sleepingd /sleepingd /usr/local/bin/sleepingd
ENV SLEEPING_BEAUTY_COMMAND="gunicorn photoprismproxy:app -b 127.0.0.1:5001 -t 60 --access-logfile - -R"
ENV SLEEPING_BEAUTY_TIMEOUT_SECONDS=300
ENV SLEEPING_BEAUTY_COMMAND_PORT=5001
ENV SLEEPING_BEAUTY_LISTEN_PORT=5000

CMD ["sleepingd"]
EXPOSE 5000
