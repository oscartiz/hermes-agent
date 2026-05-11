"""SQLite persistence layer for the fitness agent."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).parent / "fitness.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'default',
    date        TEXT    NOT NULL,
    logged_at   TEXT    NOT NULL,
    description TEXT    NOT NULL,
    calories    REAL    NOT NULL DEFAULT 0,
    protein_g   REAL    NOT NULL DEFAULT 0,
    carbs_g     REAL    NOT NULL DEFAULT 0,
    fat_g       REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'default',
    date        TEXT    NOT NULL,
    logged_at   TEXT    NOT NULL,
    weight_kg   REAL    NOT NULL,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS goals (
    user_id     TEXT PRIMARY KEY,
    calories    REAL,
    protein_g   REAL,
    carbs_g     REAL,
    fat_g       REAL
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
"""


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Meals ──────────────────────────────────────────────────────────────────────

def insert_meal(
    user_id: str,
    description: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    for_date: str | None = None,
) -> int:
    d = for_date or _today()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO meals (user_id, date, logged_at, description, calories, protein_g, carbs_g, fat_g) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, d, _now(), description, calories, protein_g, carbs_g, fat_g),
        )
        return cur.lastrowid  # type: ignore[return-value]


def get_daily_meals(user_id: str, for_date: str | None = None) -> list[sqlite3.Row]:
    d = for_date or _today()
    with _conn() as con:
        return con.execute(
            "SELECT * FROM meals WHERE user_id=? AND date=? ORDER BY logged_at",
            (user_id, d),
        ).fetchall()


def get_meals_range(user_id: str, start: str, end: str) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM meals WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date, logged_at",
            (user_id, start, end),
        ).fetchall()


# ── Weights ────────────────────────────────────────────────────────────────────

def insert_weight(user_id: str, weight_kg: float, notes: str = "", for_date: str | None = None) -> int:
    d = for_date or _today()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO weights (user_id, date, logged_at, weight_kg, notes) VALUES (?, ?, ?, ?, ?)",
            (user_id, d, _now(), weight_kg, notes),
        )
        return cur.lastrowid  # type: ignore[return-value]


def get_weights_range(user_id: str, start: str, end: str) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM weights WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date",
            (user_id, start, end),
        ).fetchall()


# ── Goals ──────────────────────────────────────────────────────────────────────

def set_goals(user_id: str, calories: float, protein_g: float, carbs_g: float, fat_g: float) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO goals (user_id, calories, protein_g, carbs_g, fat_g) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET calories=excluded.calories, protein_g=excluded.protein_g, "
            "carbs_g=excluded.carbs_g, fat_g=excluded.fat_g",
            (user_id, calories, protein_g, carbs_g, fat_g),
        )


def get_goals(user_id: str) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM goals WHERE user_id=?", (user_id,)).fetchone()


# ── Conversation history ────────────────────────────────────────────────────────

def append_message(user_id: str, role: str, content: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, _now()),
        )


def get_recent_messages(user_id: str, limit: int = 20) -> list[sqlite3.Row]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return list(reversed(rows))
