# Cloud Run: listens on $PORT (default 8080)
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8080

# Do not rely on .env inside the image — use Cloud Run env vars + Secret Manager
CMD exec uvicorn main:app --host 0.0.0.0 --port "${PORT}"
