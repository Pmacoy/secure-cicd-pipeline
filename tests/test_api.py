"""
Tests for the Shrtn API.

Written in plain pytest style (function-based, ``assert``), but with no
pytest-only features (no fixtures/parametrize) so they can also be executed
by a trivial stdlib runner — useful in environments where installing pytest
isn't an option. CI runs them with real pytest (see .github/workflows/ci.yml).
"""

import os
import tempfile

from app.main import create_app


def _client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let init_db create it fresh
    app = create_app(db_path=path)
    app.config["TESTING"] = True
    return app.test_client()


def test_healthz_returns_ok():
    client = _client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_create_link_returns_201_with_short_url():
    client = _client()
    resp = client.post("/api/links", json={"url": "https://example.com/some/page"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["target_url"] == "https://example.com/some/page"
    assert len(body["code"]) == 7
    assert body["short_url"].endswith(f"/{body['code']}")
    assert body["clicks"] == 0


def test_create_link_rejects_missing_url():
    client = _client()
    resp = client.post("/api/links", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_url"


def test_create_link_rejects_non_http_scheme():
    client = _client()
    resp = client.post("/api/links", json={"url": "javascript:alert(1)"})
    assert resp.status_code == 400


def test_create_link_rejects_url_without_netloc():
    client = _client()
    resp = client.post("/api/links", json={"url": "https://"})
    assert resp.status_code == 400


def test_create_link_rejects_overlong_url():
    client = _client()
    huge = "https://example.com/" + ("a" * 3000)
    resp = client.post("/api/links", json={"url": huge})
    assert resp.status_code == 400


def test_follow_link_redirects_and_counts_click():
    client = _client()
    created = client.post("/api/links", json={"url": "https://example.com"}).get_json()
    code = created["code"]

    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com"

    stats = client.get(f"/api/links/{code}").get_json()
    assert stats["clicks"] == 1

    client.get(f"/{code}")
    stats = client.get(f"/api/links/{code}").get_json()
    assert stats["clicks"] == 2


def test_follow_unknown_code_returns_404():
    client = _client()
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


def test_link_stats_for_unknown_code_returns_404():
    client = _client()
    resp = client.get("/api/links/nope123")
    assert resp.status_code == 404


def test_delete_link_removes_it():
    client = _client()
    created = client.post("/api/links", json={"url": "https://example.com"}).get_json()
    code = created["code"]

    resp = client.delete(f"/api/links/{code}")
    assert resp.status_code == 204

    resp = client.get(f"/api/links/{code}")
    assert resp.status_code == 404


def test_delete_unknown_code_returns_404():
    client = _client()
    resp = client.delete("/api/links/nope123")
    assert resp.status_code == 404


def test_two_links_get_different_codes():
    client = _client()
    a = client.post("/api/links", json={"url": "https://example.com/a"}).get_json()
    b = client.post("/api/links", json={"url": "https://example.com/b"}).get_json()
    assert a["code"] != b["code"]
