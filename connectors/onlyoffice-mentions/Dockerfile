# Self-contained build context: this directory only (see docker-compose.yml,
# `context: ../connectors/onlyoffice-mentions`).
# docker build -t onlyoffice-mentions .   # from connectors/onlyoffice-mentions/
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 4004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4004"]
