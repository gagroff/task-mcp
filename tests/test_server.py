import sqlite3
from datetime import date

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from task_mcp import db
from task_mcp.server import mcp


@pytest.fixture
async def client(temp_db):
    """An in-memory MCP client talking to a server backed by a temp database."""
    async with Client(transport=mcp) as connected:
        yield connected


async def test_add_task_returns_the_created_task(client):
    result = await client.call_tool("add_task", {"title": "Buy milk"})

    assert result.data.title == "Buy milk"
    assert result.data.id > 0
    assert result.data.completed is False


async def test_add_task_accepts_every_field(client):
    result = await client.call_tool(
        "add_task",
        {
            "title": "File taxes",
            "notes": "Gather receipts",
            "priority": "high",
            "due_date": "2026-10-15",
        },
    )

    assert result.data.priority == "high"
    assert result.data.due_date == "2026-10-15"
    assert result.data.notes == "Gather receipts"


async def test_list_tasks_hides_completed_by_default(client):
    await client.call_tool("add_task", {"title": "Buy milk"})

    result = await client.call_tool("list_tasks", {})

    assert [task.title for task in result.data] == ["Buy milk"]


async def test_invalid_priority_is_rejected(client):
    with pytest.raises(Exception):
        await client.call_tool("add_task", {"title": "Buy milk", "priority": "urgent"})


async def test_empty_title_is_rejected(client):
    with pytest.raises(Exception):
        await client.call_tool("add_task", {"title": ""})


async def test_title_limits_are_advertised_in_the_schema(client):
    tools = {tool.name: tool for tool in await client.list_tools()}

    title = tools["add_task"].input_schema["properties"]["title"]

    assert title["minLength"] == 1
    assert title["maxLength"] == 200


async def test_database_errors_become_a_generic_tool_error(client, monkeypatch):
    def broken_connection(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error in C:/private/path")

    monkeypatch.setattr(db, "get_connection", broken_connection)

    with pytest.raises(ToolError) as excinfo:
        await client.call_tool("list_tasks", {})

    assert "could not be opened" in str(excinfo.value)
    assert "private" not in str(excinfo.value)


async def test_unexpected_errors_are_masked(client, monkeypatch):
    def broken_fetch(*args, **kwargs):
        raise RuntimeError("internal detail in C:/private/path")

    monkeypatch.setattr(db, "fetch_tasks", broken_fetch)

    with pytest.raises(ToolError) as excinfo:
        await client.call_tool("list_tasks", {})

    assert "private" not in str(excinfo.value)
