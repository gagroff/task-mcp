"""SQLite access for tasks. This module never imports from fastmcp."""

import os
import sqlite3
from pathlib import Path

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
