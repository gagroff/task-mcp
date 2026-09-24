"""SQLite access for tasks. This module never imports from fastmcp."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from task_mcp.models import Task, TaskCreate

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    title      TEXT    NOT NULL,
    notes      TEXT,
    priority   TEXT    NOT NULL,
    due_date   TEXT,
    completed  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
"""


def default_db_path() -> Path:
    """Where the database lives unless a caller says otherwise."""
    override = os.environ.get("TASK_MCP_DB")
    if override:
        return Path(override)
    return Path.home() / ".task-mcp" / "tasks.db"


def get_connection(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection, creating the file and schema if needed."""
    db_path = Path(path) if path is not None else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _to_task(row: sqlite3.Row) -> Task:
    """Turn a database row into a Task, letting Pydantic decode the strings."""
    return Task(**dict(row))


def fetch_task(conn: sqlite3.Connection, task_id: int) -> Task | None:
    """Return the task with this id, or None when there is no such row."""
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_task(row) if row is not None else None


def insert_task(conn: sqlite3.Connection, task: TaskCreate) -> Task:
    """Store a new task and return it, including its assigned id."""
    cursor = conn.execute(
        "INSERT INTO tasks (title, notes, priority, due_date, completed, created_at)"
        " VALUES (?, ?, ?, ?, 0, ?)",
        (
            task.title,
            task.notes,
            task.priority.value,
            task.due_date.isoformat() if task.due_date is not None else None,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    created = fetch_task(conn, int(cursor.lastrowid))
    assert created is not None  # the row was inserted on the line above
    return created
