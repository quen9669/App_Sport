# Image of the whole app for the VPS (Coolify): one container serves the API and
# the built interface on port 8000, like `make prod` on the PC.
#
# Two stages: the first builds the interface with Node, the second only keeps the
# result next to Python. Node and its 300 MB of node_modules never reach the final image.

# ---------- Stage 1: build the interface (React + Vite) ----------
FROM node:22.23.0-slim AS frontend
WORKDIR /src/frontend
# Dependencies first: Docker reuses this layer while package*.json do not change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Empty API address: the interface calls the API on its own address (same origin).
RUN VITE_API_BASE_URL= npm run build

# ---------- Stage 2: the Python app ----------
FROM python:3.12.12-slim AS app
# uv installs the exact versions locked in uv.lock.
RUN pip install --no-cache-dir uv==0.11.32

# PYTHONDONTWRITEBYTECODE: the file system is read-only in production, no .pyc files.
# UV_PROJECT_ENVIRONMENT: the virtual environment lives outside the code folder.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
COPY --from=frontend /src/frontend/dist /app/frontend/dist

# An unprivileged user: even if the app were broken into, it is not root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appsport \
    && mkdir -p /data && chown appsport /data
USER appsport

# Everything that changes lives in /data (a Docker volume): database, nightly
# copies and Garmin session tokens. HOME=/tmp because the rest is read-only.
ENV APP_ENV=production \
    FRONTEND_DIST=/app/frontend/dist \
    DATABASE_URL=sqlite:////data/app_sport.db \
    BACKUP_DIR=/data/backups \
    GARMIN_TOKENSTORE=/data/garmin \
    HOME=/tmp

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

# Apply the database migrations, then start one server (one process: the
# scheduler that runs the syncs must not run twice).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
