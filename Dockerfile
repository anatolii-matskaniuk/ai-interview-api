FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     postgresql-client \
     netcat-traditional \
     build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN pip install gevent

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN chmod +x /app/start.sh

EXPOSE 8000
