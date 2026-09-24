"""The MCP surface: tools and resources. This module contains no SQL."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from task_mcp import db
from task_mcp.models import Priority, Task, TaskCreate, Title

logger = logging.getLogger(__name__)

# Masking means an unexpected exception reaches the client only as
# "Error calling tool '<name>'". ToolError messages are still sent as written.
mcp = FastMCP("task-mcp", mask_error_details=True)


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    """Open a connection for one call, and turn failures into ToolErrors.

    A connection per call costs almost nothing for a single-user list, and it
    means no connection is shared across threads or left open on shutdown.
    """
    try:
        conn = db.get_connection()
    except (sqlite3.Error, OSError):
        logger.exception("could not open the task database")
        raise ToolError("The task database could not be opened.")

    try:
        yield conn
    except ToolError:
        raise
    except (sqlite3.Error, OSError):
        logger.exception("task database operation failed")
        raise ToolError("The task database could not be read or written.")
    finally:
        conn.close()


@mcp.tool
def add_task(
    title: Title,
    notes: str | None = None,
    priority: Priority = Priority.MEDIUM,
    due_date: date | None = None,
) -> Task:
    """Add a task to the to-do list.

    Args:
        title: What needs doing, 1-200 characters.
        notes: Optional detail.
        priority: One of "low", "medium", or "high".
        due_date: Optional ISO 8601 date, e.g. "2026-10-15". Resolve a relative
            date like "next Tuesday" to an ISO date before calling.
    """
    with _connection() as conn:
        return db.insert_task(
            conn,
            TaskCreate(title=title, notes=notes, priority=priority, due_date=due_date),
        )


@mcp.tool(annotations={"readOnlyHint": True})
def list_tasks(
    include_completed: bool = False,
    priority: Priority | None = None,
    due_before: date | None = None,
) -> list[Task]:
    """List tasks, most urgent first.

    Args:
        include_completed: Include tasks already finished. Off by default.
        priority: Only tasks at this priority.
        due_before: Only tasks due strictly before this ISO 8601 date. Tasks
            with no due date are excluded whenever this is set.
    """
    with _connection() as conn:
        return db.fetch_tasks(
            conn,
            include_completed=include_completed,
            priority=priority,
            due_before=due_before,
        )


def _missing(task_id: int) -> ToolError:
    """The one message for an id that is well-formed but matches no row."""
    return ToolError(
        f"No task with id {task_id}. Use list_tasks to see available tasks."
    )


@mcp.tool(annotations={"idempotentHint": True})
def complete_task(task_id: int) -> Task:
    """Mark a task as done.

    Args:
        task_id: The id of the task, as shown by list_tasks.

    Completing an already-completed task succeeds and changes nothing.
    """
    with _connection() as conn:
        updated = db.mark_complete(conn, task_id)
        if updated is None:
            raise _missing(task_id)
        return updated


@mcp.tool(annotations={"destructiveHint": True})
def delete_task(task_id: int) -> Task:
    """Delete a task permanently and return what was deleted.

    Args:
        task_id: The id of the task, as shown by list_tasks.

    There is no undo. There is also no way to edit a task — deleting it and
    adding it again is how a task gets changed.
    """
    with _connection() as conn:
        removed = db.remove_task(conn, task_id)
        if removed is None:
            raise _missing(task_id)
        return removed


def main() -> None:
    """Entry point for the `task-mcp` console script; serves over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
