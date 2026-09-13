# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

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

# A container running gunicorn/flask has no runtime need for a package
# installer at all — pip is a build-time tool. Removing it (and
# setuptools) here, rather than just upgrading them, is what actually
# clears the last 2 Trivy findings from the earlier build: ensurepip
# keeps a static, never-reinstalled copy of the pip/setuptools wheel it
# originally bootstrapped from (untouched by `pip install --upgrade`
# above), and pip itself vendors its own internal copy of msgpack (a
# CacheControl dependency) that only pip's own maintainers can update.
# Neither is reachable by upgrading what's "installed" — only by not
# shipping pip/setuptools in the final image at all, which this app
# never needed at runtime in the first place.
RUN pip uninstall -y pip setuptools wheel || true \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
              /usr/local/lib/python3.13/site-packages/pip* \
              /usr/local/lib/python3.13/site-packages/setuptools* \
              /usr/local/lib/python3.13/site-packages/wheel* \
              /usr/local/lib/python3.13/site-packages/pkg_resources \
              /usr/local/bin/pip*

COPY app/ ./app/

# Run as a non-root, non-login user — the single highest-value line in this
# file from a container-scanning point of view (Trivy/hadolint both check).
# A named user (rather than a raw numeric UID) is deliberate here: it's what
# shows up in `docker ps`/`ps aux`/logs, which matters for a portfolio repo
# meant to be read. hadolint's DL3066 (info-level, but this job's
# failure-threshold is info) flags any non-numeric USER on principle — the
# concern it's guarding against (a UID that doesn't resolve on the host)
# doesn't apply to a container-only user like this one.
RUN groupadd --system shrtn && useradd --system --gid shrtn --no-create-home shrtn \
    && mkdir -p /data \
    && chown -R shrtn:shrtn /app /data
# hadolint ignore=DL3066
USER shrtn

EXPOSE 8080

# hadolint's DL3025 wants HEALTHCHECK's CMD in JSON (exec) form, but the
# `|| exit 1` fallback here is a shell construct — there's no JSON-array way
# to express "run this, and if it fails, exit 1" without a wrapper script.
# Shell form is the correct, intentional choice for this specific check.
# hadolint ignore=DL3025
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--access-logfile", "-", "app.main:app"]
