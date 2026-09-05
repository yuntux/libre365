# Self-contained build: build context is this directory (notification-hub/),
# consistent with docker-compose/docker-compose.yml's `context: ../connectors/notification-hub`.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 4001
ENV PORT=4001

# Shell form so the PORT env var (read the same way app/main.py does) is honored.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --loop uvloop
