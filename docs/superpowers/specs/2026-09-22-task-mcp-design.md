# Task MCP Server — Design

**Date:** 2026-09-22
**Status:** Approved for planning

## Purpose

A Model Context Protocol server that lets Claude manage a personal to-do
list stored in SQLite. The project exists primarily as a learning
vehicle: it is the author's first exposure to Python, MCP, and FastMCP.
Design decisions therefore favor clarity and teaching value over
feature coverage.

## Goals

- Expose a working set of task-management tools to any MCP client.
- Demonstrate each core MCP concept — tools, resources, typed schemas,
  and structured errors — exactly once, without repetition.
- Keep business logic testable without running a server.
- Ship as a public GitHub repository containing code only, never data.

## Non-Goals

- Multi-user support, authentication, or remote hosting.
- Recurring tasks, subtasks, projects, tags, or search.
- A web or graphical interface. The MCP client is the only front end.

## Success Criteria

1. `uv run pytest` passes.
2. The server registers with Claude Code via `claude mcp add`.
3. Asking Claude in natural language to add, list, and complete a task
   results in the correct rows in the database.
4. `git status` is clean of database files before the first push, and
   the pushed repository contains no personal data.

## Architecture

Three modules with a strict dependency direction: `server` depends on
`db`, `db` depends on `models`, and nothing depends upward.

```
task-mcp/
├── pyproject.toml
├── uv.lock
├── .gitignore
├── README.md
├── docs/superpowers/specs/
├── src/task_mcp/
│   ├── __init__.py
│   ├── models.py     # Pydantic models — the shared vocabulary
│   ├── db.py         # SQLite access — no MCP imports
│   └── server.py     # FastMCP tools and resources — no SQL
└── tests/
    ├── conftest.py   # temp-database fixture
    ├── test_db.py
    └── test_server.py
```

The central constraint: **`db.py` contains no MCP code and `server.py`
contains no SQL.** `db.py` exposes plain functions that accept and
return Pydantic models. `server.py` is a thin adapter that decorates
calls to them. This allows the logic to be tested directly and keeps
each file small enough to read in one sitting.

### models.py

```python
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None

class Task(TaskCreate):
    id: int
    completed: bool = False
    created_at: datetime
```

`Task` extends `TaskCreate` because a stored task is a submitted task
plus server-assigned fields. Validation rules are declared once.

### db.py

Module-level functions, each taking an explicit `sqlite3.Connection` as
its first argument so tests can pass a temporary database:

| Function | Returns | Notes |
|---|---|---|
| `get_connection(path)` | `Connection` | Creates parent dirs; sets `row_factory`; applies schema |
| `insert_task(conn, TaskCreate)` | `Task` | Returns the row including its new id |
| `fetch_tasks(conn, ...)` | `list[Task]` | Filters: `include_completed`, `priority`, `due_before` |
| `fetch_task(conn, id)` | `Task \| None` | Used by callers needing existence checks |
| `mark_complete(conn, id)` | `Task \| None` | `None` when the id does not exist |
| `remove_task(conn, id)` | `bool` | `True` when a row was deleted |

Returning `None` and `bool` for missing rows — rather than raising —
keeps `db.py` free of presentation concerns. Translating absence into a
user-facing message is `server.py`'s job.

### Schema

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    notes      TEXT,
    priority   TEXT    NOT NULL DEFAULT 'medium',
    due_date   TEXT,
    completed  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
```

SQLite has no native date or boolean type. Dates are stored as ISO 8601
strings and booleans as `0`/`1`; Pydantic converts both at the module
boundary, so no other code handles the encoding.

Ordering for `fetch_tasks` is `completed ASC, due_date IS NULL ASC,
due_date ASC, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1
ELSE 2 END`, so open work comes before completed, dated before undated,
sooner before later, and higher priority first. The `CASE` expression is
necessary because priority is stored as text, and alphabetical order
would rank `high` before `low` before `medium` — meaningless.

### Database location

`~/.task-mcp/tasks.db`, created on first use. The path is overridden by
the `TASK_MCP_DB` environment variable, which tests use to point at a
temporary file. The database is deliberately outside the repository
directory so task data cannot be committed.

### server.py

A single `FastMCP` instance exposing four tools and one resource.
Parameters are annotated with Pydantic types, which FastMCP converts
into the JSON schema the client sees; docstrings become the tool
descriptions the model reads when deciding what to call, and are
therefore written as interface documentation rather than as comments.

| Tool | Parameters | Returns |
|---|---|---|
| `add_task` | `title`, `notes=None`, `priority="medium"`, `due_date=None` | The created `Task` |
| `list_tasks` | `include_completed=False`, `priority=None`, `due_before=None` | `list[Task]` |
| `complete_task` | `task_id` | The updated `Task` |
| `delete_task` | `task_id` | Confirmation string |

Resource `tasks://today` returns a plain-text agenda of tasks that are
overdue or due today, grouped under those two headings, with an
explicit message when there are none.

## Error Handling

Three tiers:

1. **Invalid input** — a `priority` outside the enum, an empty title, an
   unparseable date. Rejected by Pydantic before the function body
   runs; FastMCP reports the validation error to the client.
2. **Valid input, absent target** — `complete_task(999)` where no such
   row exists. Raises `ToolError` with a message written for a reader:
   `"No task with id 999. Use list_tasks to see available tasks."`
   `ToolError` is the FastMCP exception whose message is intended to
   reach the client.
3. **Unexpected failures** — disk errors, corrupt database. Caught at
   the tool boundary, logged, and re-raised as `ToolError` with a
   generic message. Internal details are never leaked to the client,
   and the server stays running.

No tool returns a raw traceback.

## Testing

Test-first throughout: each function's test is written and observed
failing before its implementation.

- `conftest.py` provides a `conn` fixture backed by `tmp_path`, giving
  every test a fresh database.
- `test_db.py` covers the logic directly: round-tripping a task,
  each filter in `fetch_tasks`, ordering, completing an existing and a
  missing task, deleting an existing and a missing task, and date and
  boolean conversion in both directions.
- `test_server.py` uses FastMCP's in-memory `Client`, which calls tools
  through the real MCP protocol without spawning a subprocess. It
  covers one success path per tool, the `ToolError` raised for a
  missing id, rejection of an invalid priority, and the resource's
  output including its empty case.

Run with `uv run pytest`.

## Repository Hygiene

The repository is public at `github.com/gagroff`. It contains source,
tests, configuration, and documentation — no data and no secrets. The
project has no API keys, tokens, or credentials by design.

`.gitignore` covers `__pycache__/`, `.venv/`, `*.db`, `*.db-journal`,
`.env`, `.pytest_cache/`, and `.idea/`. `uv.lock` and `pyproject.toml`
are committed. Before the first push, `git status --short` and
`git ls-files` are reviewed manually rather than relying on the ignore
file alone.

## Build Sequence

1. Scaffold with `uv init`; add `fastmcp` and dev dependency `pytest`.
2. Write `.gitignore` and make the first commit.
3. `models.py` with its validation tests.
4. `db.py`, test-first, one function at a time.
5. `server.py`, test-first, one tool at a time, then the resource.
6. Register with Claude Code and smoke-test each tool by conversation.
7. Write `README.md` covering install, run, test, and client setup.
8. Create the public GitHub repository and push.

## Open Risks

- **Windows path handling.** `~` expansion and directory creation are
  done with `pathlib.Path.home()` rather than string concatenation.
- **Date parsing ambiguity.** Natural-language dates ("next Tuesday")
  are the client's responsibility to resolve; the tool accepts only
  ISO dates, and its docstring states this so the model converts before
  calling.
