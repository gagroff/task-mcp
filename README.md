# task-mcp

An MCP server for managing a personal to-do list stored in SQLite. Built as a
first project in Python, MCP, and FastMCP.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Install

```bash
git clone https://github.com/gagroff/task-mcp.git
cd task-mcp
uv sync
```

## Run the tests

```bash
uv run pytest
```

## Register with Claude Code

```bash
claude mcp add --scope user task-mcp -- uv --directory /absolute/path/to/task-mcp run task-mcp
```

`--scope user` makes the server available in every Claude Code session, not
just ones started inside this repository.

Then ask in plain language: "add a task to buy milk, high priority, due Friday",
"what's on my list?", "mark task 3 done".

## Tools and resources

| Tool | What it does |
|---|---|
| `add_task` | Add a task with an optional note, priority, and ISO due date |
| `list_tasks` | List tasks, most urgent first, with optional filters |
| `complete_task` | Mark a task done by id |
| `delete_task` | Delete a task by id and return what was deleted |

The resource `tasks://today` gives a plain-text agenda of what is overdue or
due today.

Tasks cannot be edited after creation — delete and re-add instead.

## Where the data lives

`~/.task-mcp/tasks.db`, outside this repository so task data is never
committed. Set `TASK_MCP_DB` to point somewhere else, which is useful for
trying the server against a scratch database:

```bash
TASK_MCP_DB=/tmp/scratch.db uv run task-mcp
```

On Windows PowerShell:

```powershell
$env:TASK_MCP_DB = "$env:TEMP\scratch.db"; uv run task-mcp
```
