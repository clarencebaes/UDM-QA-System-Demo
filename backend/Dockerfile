# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System build deps: needed to build wheels for scikit-learn / numpy / scipy.
# mysqlclient is NOT used (we use PyMySQL, pure Python), so no libmysqlclient.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .
RUN python -m ml.train_demo

# Render injects $PORT at runtime (default 10000) and routes traffic to it,
# which overrides this default; 7860 only matters for local runs:
# `docker run -p 8000:7860 ...`.
ENV PORT=7860

# Run from /app so "python -m app.main" and the relative model paths resolve.
# Gunicorn manages Uvicorn workers. We run ONE worker: it loads the ML models
# once and a survey burst is light, so a single worker keeps memory low and
# responses fast. (Bump --workers only on a larger, always-on tier.)
CMD exec gunicorn app.main:app \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
