# syntax=docker/dockerfile:1.7

FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    DATABASE_PATH=/data/billbox.db \
    MIGRATIONS_DIR=/app/migrations \
    FRONTEND_DIST=/app/frontend/dist

RUN groupadd --system --gid 10001 billbox \
    && useradd --system --uid 10001 --gid billbox \
        --home-dir /app --shell /usr/sbin/nologin billbox

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=billbox:billbox backend/ ./backend/
COPY --chown=billbox:billbox migrations/ ./migrations/
COPY --chown=billbox:billbox docker/entrypoint.sh ./docker/entrypoint.sh
COPY --chown=billbox:billbox --from=frontend-build /app/frontend/dist ./frontend/dist/

RUN install -d -o billbox -g billbox -m 0750 /data \
    && chmod 0555 /app/docker/entrypoint.sh

USER billbox
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"]

ENTRYPOINT ["/app/docker/entrypoint.sh"]
