from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import sqlite3
from pathlib import Path

from .models import Task


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 100),
    description TEXT DEFAULT NULL CHECK (description IS NULL OR length(description) BETWEEN 1 AND 500),
    due_date TEXT DEFAULT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Low', 'Medium', 'High')),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Completed')),
    completed_on TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK ((status = 'Pending' AND completed_on IS NULL) OR (status = 'Completed' AND completed_on IS NOT NULL))
);
"""


def connect(path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript(SCHEMA)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date(value):
    return date.fromisoformat(value) if value else None


def _datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def row_to_task(row) -> Task:
    return Task(row["id"], row["title"], row["description"], _date(row["due_date"]),
                row["priority"], row["status"], _date(row["completed_on"]),
                _datetime(row["created_at"]), _datetime(row["updated_at"]))


def get_task(db, task_id: int) -> Task | None:
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_task(row) if row else None


def list_tasks(db) -> list[Task]:
    rows = db.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    return [row_to_task(row) for row in rows]


@contextmanager
def transaction(db):
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def insert_task(db, fields: dict) -> Task:
    now = utc_now()
    with transaction(db):
        cursor = db.execute(
            "INSERT INTO tasks (title, description, due_date, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (fields["title"], fields["description"], fields["due_date"].isoformat() if fields["due_date"] else None,
             fields["priority"], now, now),
        )
        return get_task(db, cursor.lastrowid)


def update_task(db, task_id: int, fields: dict) -> Task | None:
    current = get_task(db, task_id)
    if current is None:
        return None
    values = (fields["title"], fields["description"], fields["due_date"].isoformat() if fields["due_date"] else None, fields["priority"])
    if (current.title, current.description, current.due_date.isoformat() if current.due_date else None, current.priority) == values:
        return current
    with transaction(db):
        db.execute("UPDATE tasks SET title = ?, description = ?, due_date = ?, priority = ?, updated_at = ? WHERE id = ?",
                   (*values, utc_now(), task_id))
        return get_task(db, task_id)


def delete_task(db, task_id: int) -> bool:
    with transaction(db):
        cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount == 1


def complete_task(db, task_id: int, today: date) -> Task | None:
    current = get_task(db, task_id)
    if current is None or current.status == "Completed":
        return current
    with transaction(db):
        db.execute("UPDATE tasks SET status = 'Completed', completed_on = ?, updated_at = ? WHERE id = ? AND status = 'Pending'",
                   (today.isoformat(), utc_now(), task_id))
        return get_task(db, task_id)