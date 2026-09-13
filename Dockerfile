# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# Keep Python from writing .pyc files / buffering stdout — standard
# container hygiene, not security-relevant but avoids surprises in logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/shrtn.db

WORKDIR /app

# Install deps in their own layer so `docker build` cache is only busted by
# requirements changes, not every code edit.
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY app/ ./app/

# Run as a non-root, non-login user — the single highest-value line in this
# file from a container-scanning point of view (Trivy/hadolint both check).
RUN groupadd --system shrtn && useradd --system --gid shrtn --no-create-home shrtn \
    && mkdir -p /data \
    && chown -R shrtn:shrtn /app /data
USER shrtn

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--access-logfile", "-", "app.main:app"]
