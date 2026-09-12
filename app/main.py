"""
Shrtn — a small, real URL-shortener API.

This app exists to give the CI/CD pipeline something genuine to build, test,
scan and ship — not to be architecturally interesting on its own. It still
does the things a real service has to get right: input validation, no
string-built SQL, a sane HTTP status per case, and a health endpoint a
container orchestrator can actually probe.
"""

from __future__ import annotations

import os
import secrets
import string
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, redirect, request
from werkzeug.exceptions import NotFound

from app import db

_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 7
_ALLOWED_SCHEMES = {"http", "https"}
_MAX_URL_LENGTH = 2048


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def _is_valid_target_url(url: str) -> bool:
    if not url or len(url) > _MAX_URL_LENGTH:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    # Relative default so importing this module never tries (and fails) to
    # create a directory under the filesystem root outside a container; the
    # Dockerfile overrides DB_PATH to a proper mounted volume path.
    app.config["DB_PATH"] = db_path or os.environ.get("DB_PATH", "instance/shrtn.db")
    db.init_db(app.config["DB_PATH"])

    @app.get("/healthz")
    def healthz() -> Response:
        return jsonify(status="ok")

    @app.post("/api/links")
    def create_link() -> tuple[Response, int]:
        payload = request.get_json(silent=True) or {}
        target_url = payload.get("url", "")

        if not _is_valid_target_url(target_url):
            return (
                jsonify(
                    error="invalid_url",
                    message="'url' must be an http(s) URL, non-empty and "
                    f"under {_MAX_URL_LENGTH} characters.",
                ),
                400,
            )

        db_path = app.config["DB_PATH"]
        code = _generate_code()
        while db.code_exists(db_path, code):  # astronomically unlikely, but be correct
            code = _generate_code()

        link = db.create_link(db_path, code, target_url)
        return jsonify(_serialize(link, request.host_url)), 201

    @app.get("/api/links/<code>")
    def link_stats(code: str) -> Response:
        link = db.get_link(app.config["DB_PATH"], code)
        if link is None:
            raise NotFound(description="no link with that code")
        return jsonify(_serialize(link, request.host_url))

    @app.delete("/api/links/<code>")
    def delete_link(code: str) -> tuple[Response, int]:
        deleted = db.delete_link(app.config["DB_PATH"], code)
        if not deleted:
            raise NotFound(description="no link with that code")
        return "", 204

    @app.get("/<code>")
    def follow_link(code: str):
        link = db.get_link(app.config["DB_PATH"], code)
        if link is None:
            raise NotFound(description="no link with that code")
        db.record_click(app.config["DB_PATH"], code)
        return redirect(link["target_url"], code=302)

    @app.errorhandler(404)
    def not_found(err) -> tuple[Response, int]:
        message = getattr(err, "description", "not found")
        return jsonify(error="not_found", message=message), 404

    return app


def _serialize(link: dict, host_url: str) -> dict:
    return {
        "code": link["code"],
        "target_url": link["target_url"],
        "short_url": f"{host_url.rstrip('/')}/{link['code']}",
        "created_at": link["created_at"],
        "clicks": link["clicks"],
    }


app = create_app()

if __name__ == "__main__":
    # Dev-only entrypoint — the Dockerfile runs gunicorn in production, which
    # is where the real host/port binding decision belongs.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))  # noqa: S104
