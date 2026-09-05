# Self-contained build context: this directory only
# (docker-compose/docker-compose.yml builds with `context: ../connectors/unified-search`).
# docker build -t unified-search .   # from connectors/unified-search/
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 4002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4002"]
