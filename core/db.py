"""SQLite storage using Python's built-in sqlite3 (no extra dependency).

Personal tables (document, skill, chat_message, interest, roadmap_item) must only be read through
core/access.py. Pages never query them directly.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "career_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS team (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, lead_id TEXT, manager_id TEXT
);
CREATE TABLE IF NOT EXISTS employee (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, band TEXT NOT NULL, role_id TEXT NOT NULL,
    team_id TEXT, manager_id TEXT, performance_rating REAL
);
-- personal tables -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document (
    id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL, kind TEXT NOT NULL,
    text TEXT NOT NULL, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS skill (
    employee_id TEXT NOT NULL, skill TEXT NOT NULL, level INTEGER NOT NULL,
    evidence TEXT, source TEXT, confidence REAL,
    PRIMARY KEY (employee_id, skill)
);
CREATE TABLE IF NOT EXISTS interest (
    employee_id TEXT NOT NULL, topic TEXT NOT NULL, strength REAL NOT NULL,
    PRIMARY KEY (employee_id, topic)
);
CREATE TABLE IF NOT EXISTS roadmap_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL, title TEXT NOT NULL,
    horizon INTEGER NOT NULL, catalog_id TEXT, url TEXT, done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chat_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS share_consent (
    employee_id TEXT PRIMARY KEY, share_readiness INTEGER DEFAULT 0
);
-- cache for LLM answers (keeps free-tier usage low) ----------------------------
CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def reset(conn: sqlite3.Connection) -> None:
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        if t != "sqlite_sequence":
            conn.execute(f"DELETE FROM {t}")
    conn.commit()


# --- org structure (not personal) ------------------------------------------------
def all_employees(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM employee ORDER BY band DESC, name").fetchall()


def get_employee(conn, emp_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM employee WHERE id=?", (emp_id,)).fetchone()


def get_team(conn, team_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM team WHERE id=?", (team_id,)).fetchone()


def all_teams(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM team ORDER BY name").fetchall()


# --- low-level personal reads: ONLY core/access.py may call these ---------------------
def _skills(conn, emp_id: str) -> dict[str, int]:
    rows = conn.execute("SELECT skill, level FROM skill WHERE employee_id=?", (emp_id,))
    return {r["skill"]: r["level"] for r in rows}


def _skill_rows(conn, emp_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM skill WHERE employee_id=? ORDER BY level DESC, skill", (emp_id,)
    ).fetchall()


def _interests(conn, emp_id: str) -> dict[str, float]:
    rows = conn.execute("SELECT topic, strength FROM interest WHERE employee_id=?", (emp_id,))
    return {r["topic"]: r["strength"] for r in rows}


def _roadmap(conn, emp_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM roadmap_item WHERE employee_id=? ORDER BY horizon, id", (emp_id,)
    ).fetchall()


def _chat(conn, emp_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT role, content FROM chat_message WHERE employee_id=? ORDER BY id", (emp_id,)
    ).fetchall()


def _documents(conn, emp_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT kind, text, uploaded_at FROM document WHERE employee_id=? ORDER BY id", (emp_id,)
    ).fetchall()


def _consent(conn, emp_id: str) -> bool:
    row = conn.execute("SELECT share_readiness FROM share_consent WHERE employee_id=?", (emp_id,))
    r = row.fetchone()
    return bool(r and r["share_readiness"])


def _evidence_count(conn, emp_id: str) -> int:
    """Number of distinct evidence sources (resume, review, GitHub, transcript, ...)."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT kind) AS n FROM document WHERE employee_id=?", (emp_id,)
    ).fetchone()
    return int(row["n"])


# --- personal writes (always by the owner, enforced in access.py) ----------------------
def _upsert_skill(conn, emp_id, skill, level, evidence, source, confidence) -> None:
    conn.execute(
        """INSERT INTO skill(employee_id, skill, level, evidence, source, confidence)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(employee_id, skill) DO UPDATE SET
             level=excluded.level, evidence=excluded.evidence,
             source=excluded.source, confidence=excluded.confidence""",
        (emp_id, skill, level, evidence, source, confidence),
    )


def cache_get(conn, key: str):
    row = conn.execute("SELECT value FROM llm_cache WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def cache_set(conn, key: str, value) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO llm_cache(key, value) VALUES (?,?)", (key, json.dumps(value))
    )
    conn.commit()
