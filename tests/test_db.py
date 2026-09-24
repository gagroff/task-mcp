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


def test_completed_tasks_are_hidden_by_default(conn):
    open_task = db.insert_task(conn, TaskCreate(title="Open"))
    done = db.insert_task(conn, TaskCreate(title="Done"))
    conn.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (done.id,))
    conn.commit()

    assert [t.id for t in db.fetch_tasks(conn)] == [open_task.id]
    assert len(db.fetch_tasks(conn, include_completed=True)) == 2


def test_priority_filter(conn):
    db.insert_task(conn, TaskCreate(title="Low", priority=Priority.LOW))
    high = db.insert_task(conn, TaskCreate(title="High", priority=Priority.HIGH))

    found = db.fetch_tasks(conn, priority=Priority.HIGH)

    assert [t.id for t in found] == [high.id]


def test_due_before_filter_excludes_undated_tasks(conn):
    soon = db.insert_task(conn, TaskCreate(title="Soon", due_date=date(2026, 1, 1)))
    db.insert_task(conn, TaskCreate(title="Later", due_date=date(2026, 12, 1)))
    db.insert_task(conn, TaskCreate(title="Someday"))

    found = db.fetch_tasks(conn, due_before=date(2026, 6, 1))

    assert [t.id for t in found] == [soon.id]


def test_due_before_is_exclusive(conn):
    db.insert_task(conn, TaskCreate(title="On the day", due_date=date(2026, 6, 1)))

    assert db.fetch_tasks(conn, due_before=date(2026, 6, 1)) == []


def test_ordering(conn):
    # Inserted in deliberately wrong order; the expected order is the rule below.
    undated_low = db.insert_task(
        conn, TaskCreate(title="Undated low", priority=Priority.LOW)
    )
    undated_high = db.insert_task(
        conn, TaskCreate(title="Undated high", priority=Priority.HIGH)
    )
    later = db.insert_task(conn, TaskCreate(title="Later", due_date=date(2026, 12, 1)))
    sooner = db.insert_task(conn, TaskCreate(title="Sooner", due_date=date(2026, 1, 1)))

    order = [t.id for t in db.fetch_tasks(conn)]

    # Dated before undated, sooner before later, then high before low.
    assert order == [sooner.id, later.id, undated_high.id, undated_low.id]


def test_completed_tasks_sort_last(conn):
    done = db.insert_task(conn, TaskCreate(title="Done", due_date=date(2026, 1, 1)))
    conn.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (done.id,))
    conn.commit()
    open_task = db.insert_task(conn, TaskCreate(title="Open", due_date=date(2026, 12, 1)))

    order = [t.id for t in db.fetch_tasks(conn, include_completed=True)]

    assert order == [open_task.id, done.id]


def test_empty_database_returns_an_empty_list(conn):
    assert db.fetch_tasks(conn) == []
