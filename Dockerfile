FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    ROADGUARD_ENV=production

WORKDIR /app

# Runtime deps only; dev/test deps are not installed in the image.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code + model artifact + static web assets.
COPY app/ ./app/
COPY ml/artifacts/ ./ml/artifacts/
COPY scripts/ ./scripts/

# Non-root: create an unprivileged user and hand it an app-owned data dir.
RUN useradd --create-home --uid 10001 roadguard \
    && mkdir -p /app/data \
    && chown -R roadguard:roadguard /app
USER roadguard

# DB and any writes land in a volume so they survive container restart.
VOLUME ["/app/data"]

# Config is env-driven; override DB/artifact paths via environment.
ENV ROADGUARD_DB_PATH=/app/data/roadguard.sqlite3 \
    ROADGUARD_MODEL_ARTIFACT=/app/ml/artifacts/model.joblib \
    ROADGUARD_COOKIE_SECURE=false \
    ROADGUARD_REQUIRE_MODEL=false

EXPOSE 8000

# Liveness uses the app's own unauthenticated /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
