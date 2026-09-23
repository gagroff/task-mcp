import pytest

from task_mcp import db


@pytest.fixture
def conn(tmp_path):
    """A connection to a fresh database, for testing db.py directly."""
    connection = db.get_connection(tmp_path / "tasks.db")
    yield connection
    connection.close()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the server's own connections at a fresh database.

    The server opens a connection per tool call rather than accepting one,
    so server tests redirect it through the environment instead of through
    the `conn` fixture.
    """
    path = tmp_path / "server-tasks.db"
    monkeypatch.setenv("TASK_MCP_DB", str(path))
    return path
