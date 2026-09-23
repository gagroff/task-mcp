"""The shared vocabulary passed between the database and the MCP layers."""

from datetime import date, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

# Declared once and reused by the add_task tool signature, so the same limits
# validate stored tasks and appear in the JSON schema the client sees.
Title = Annotated[str, Field(min_length=1, max_length=200)]


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCreate(BaseModel):
    """A task as submitted by a caller, before the server assigns anything."""

    title: Title
    notes: str | None = None
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None


class Task(TaskCreate):
    """A stored task: a submitted task plus the fields the server owns."""

    id: int
    completed: bool = False
    created_at: datetime
