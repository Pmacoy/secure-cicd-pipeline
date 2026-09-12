"""
Thin SQLite persistence layer for the link store.

Kept deliberately dependency-free (stdlib ``sqlite3`` only) so the app's own
supply chain is as small as realistically possible — the point of this repo
is the CI/CD pipeline around it, and every extra dependency is one more
thing for the security-scanning workflow to have an opinion about.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code        TEXT PRIMARY KEY,
    target_url  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    clicks      INTEGER NOT NULL DEFAULT 0
);
"""


def init_db(db_path: str) -> None:
    """Create the schema if it doesn't exist yet. Safe to call repeatedly."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def _connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_link(db_path: str, code: str, target_url: str) -> dict:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO links (code, target_url) VALUES (?, ?)",
            (code, target_url),
        )
        row = conn.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return dict(row)


def get_link(db_path: str, code: str) -> Optional[dict]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def record_click(db_path: str, code: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code,))


def delete_link(db_path: str, code: str) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM links WHERE code = ?", (code,))
        return cur.rowcount > 0


def code_exists(db_path: str, code: str) -> bool:
    return get_link(db_path, code) is not None
