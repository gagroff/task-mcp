import sqlite3
from datetime import date, datetime
from pathlib import Path

from task_mcp import db
from task_mcp.models import Priority, TaskCreate


def test_get_connection_creates_the_file_and_schema(tmp_path):
    path = tmp_path / "nested" / "tasks.db"

    connection = db.get_connection(path)

    assert path.exists()
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert "tasks" in [row["name"] for row in tables]
    connection.close()


def test_get_connection_is_idempotent(tmp_path):
    path = tmp_path / "tasks.db"

    first = db.get_connection(path)
    first.close()
    second = db.get_connection(path)

    assert second.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"] == 0
    second.close()


def test_rows_are_accessible_by_name(conn):
    row = conn.execute("SELECT 1 AS answer").fetchone()

    assert isinstance(row, sqlite3.Row)
    assert row["answer"] == 1


def test_default_path_honours_the_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("TASK_MCP_DB", str(tmp_path / "custom.db"))

    assert db.default_db_path() == tmp_path / "custom.db"


def test_default_path_falls_back_to_the_home_directory(monkeypatch):
    monkeypatch.delenv("TASK_MCP_DB", raising=False)

    assert db.default_db_path() == Path.home() / ".task-mcp" / "tasks.db"


def test_insert_returns_the_stored_task(conn):
    created = db.insert_task(conn, TaskCreate(title="Buy milk"))

    assert created.id > 0
    assert created.title == "Buy milk"
    assert created.completed is False
    assert created.priority is Priority.MEDIUM
    assert isinstance(created.created_at, datetime)


def test_insert_round_trips_every_field(conn):
    created = db.insert_task(
        conn,
        TaskCreate(
            title="File taxes",
            notes="Gather receipts first",
            priority=Priority.HIGH,
            due_date=date(2026, 10, 15),
        ),
    )

    fetched = db.fetch_task(conn, created.id)

    assert fetched == created
    assert fetched.notes == "Gather receipts first"
    assert fetched.due_date == date(2026, 10, 15)
    assert fetched.priority is Priority.HIGH


def test_insert_persists_across_connections(conn, tmp_path):
    db.insert_task(conn, TaskCreate(title="Buy milk"))
    conn.close()

    reopened = db.get_connection(tmp_path / "tasks.db")
    assert db.fetch_task(reopened, 1).title == "Buy milk"
    reopened.close()


def test_fetch_missing_task_returns_none(conn):
    assert db.fetch_task(conn, 999) is None
