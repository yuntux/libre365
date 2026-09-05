# Build context: this directory (connectors/presence-aggregator), self-contained.
# docker build -t presence-aggregator .   # from connectors/presence-aggregator/
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 4003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4003"]
