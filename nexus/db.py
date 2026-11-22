
"""Работа с данными Nexus Fitness: профили, планы, прогресс — в SQLite."""

import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    email TEXT PRIMARY KEY,
    data  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
    email TEXT PRIMARY KEY,
    data  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
    email TEXT PRIMARY KEY,
    data  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    email   TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    title   TEXT,
    history TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (email, chat_id)
);
"""

def _conn():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn

def _get(conn, table: str, email: str):
    row = conn.execute(f"SELECT data FROM {table} WHERE email=?", (email,)).fetchone()
    return json.loads(row[0]) if row else None

def _put(conn, table: str, email: str, data):
    conn.execute(
        f"INSERT INTO {table} (email, data) VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET data=excluded.data",
        (email, json.dumps(data, ensure_ascii=False))
    )

def get_profile(email: str) -> dict | None:
    conn = _conn()
    try:
        return _get(conn, "profiles", email)
    finally:
        conn.close()

def save_profile(email: str, profile: dict) -> None:
    conn = _conn()
    try:
        _put(conn, "profiles", email, profile)
        conn.commit()
    finally:
        conn.close()

def get_plan(email: str):
    conn = _conn()
    try:
        return _get(conn, "plans", email)
    finally:
        conn.close()

def save_plan(email: str, plan: dict) -> None:
    conn = _conn()
    try:
        _put(conn, "plans", email, plan)
        conn.commit()
    finally:
        conn.close()

def get_progress(email: str) -> list:
    conn = _conn()
    try:
        return _get(conn, "progress", email) or []
    finally:
        conn.close()

def save_progress(email: str, completed: list) -> None:
    conn = _conn()
    try:
        _put(conn, "progress", email, list(completed))
        conn.commit()
    finally:
        conn.close()

def get_chats(email: str) -> list:
    conn = _conn()
    try:
        rows = conn.execute("SELECT chat_id, title, history FROM chats WHERE email=? ORDER BY rowid DESC", (email,)).fetchall()
    finally:
        conn.close()
    return [{"id": r[0], "title": r[1], "history": json.loads(r[2])} for r in rows]

def save_chat(email: str, chat: dict) -> None:
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO chats (email, chat_id, title, history) VALUES (?, ?, ?, ?) ON CONFLICT(email, chat_id) DO UPDATE SET title=excluded.title, history=excluded.history",
            (email, chat["id"], chat["title"], json.dumps(chat["history"], ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()

def delete_chat(email: str, chat_id: str) -> None:
    conn = _conn()
    try:
        conn.execute("DELETE FROM chats WHERE email=? AND chat_id=?", (email, chat_id))
        conn.commit()
    finally:
        conn.close()

