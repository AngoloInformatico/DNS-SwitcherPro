# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /source/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DNS_SWITCHER_CONTAINER=1 \
    DNS_SWITCHER_WORK_DIR=/data \
    DNS_SWITCHER_ALLOWED_HOSTS=*

WORKDIR /app

COPY Docker/requirements-container.txt /tmp/requirements-container.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-container.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip

COPY backend/ ./backend/
COPY --from=frontend-builder /source/frontend/dist ./frontend/dist/

RUN mkdir -p /data/data /data/logs /data/temp \
    && chmod 700 /data /data/data /data/logs /data/temp

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request; r=urllib.request.Request('http://127.0.0.1:8765/api/health',headers={'X-Session-Token':os.environ['DNS_SWITCHER_SESSION_TOKEN']}); urllib.request.urlopen(r,timeout=3).read()" || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8765", "--proxy-headers", "--forwarded-allow-ips=*"]
