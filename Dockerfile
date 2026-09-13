# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# Keep Python from writing .pyc files / buffering stdout — standard
# container hygiene, not security-relevant but avoids surprises in logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/shrtn.db

# python:3.13-slim's OS packages (perl, glibc, sqlite3, pcre2, gzip, ...)
# are frozen at whatever was current when that image layer was published,
# and accumulate real CVEs over time even though this app never touches
# any of them directly — Trivy's image scan (not the filesystem scan,
# which only sees our own tracked files) caught a batch of these.
# Pulling Debian's own security-patched versions at build time, without
# changing the base image tag, is the standard fix.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Same idea for the Python-side tooling bundled into the base image
# (pip/setuptools) — Trivy also flagged a setuptools path-traversal CVE.
# Deliberately left unpinned: the whole point of this line is to always
# grab whatever the current patched release is, which is the opposite of
# pinning — so DL3013 is suppressed here rather than guessed at with a
# hardcoded version number.
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip setuptools

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
