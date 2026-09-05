# Self-contained build: build context is this directory (peertube-ingest/),
# consistent with docker-compose/docker-compose.yml's `context: ../connectors/peertube-ingest`.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 4005
ENV PORT=4005

# The HTTP service (real-time webhook) is the default command; batch mode is
# invoked separately in the same image, e.g. from cron:
#   docker run --rm <image> python -m app.batch [--since=<ISO8601>]
# Shell form so the PORT env var (read the same way app/main.py does) is honored.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --loop uvloop
