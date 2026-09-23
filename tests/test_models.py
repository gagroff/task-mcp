from datetime import date, datetime

import pytest
from pydantic import ValidationError

from task_mcp.models import Priority, Task, TaskCreate


def test_defaults_are_applied():
    task = TaskCreate(title="Buy milk")

    assert task.priority is Priority.MEDIUM
    assert task.notes is None
    assert task.due_date is None


def test_empty_title_is_rejected():
    with pytest.raises(ValidationError):
        TaskCreate(title="")


def test_overlong_title_is_rejected():
    with pytest.raises(ValidationError):
        TaskCreate(title="x" * 201)


def test_invalid_priority_is_rejected():
    with pytest.raises(ValidationError):
        TaskCreate(title="Buy milk", priority="urgent")


def test_iso_strings_are_coerced():
    task = Task(
        id=1,
        title="Buy milk",
        priority="high",
        due_date="2026-09-30",
        completed=0,
        created_at="2026-09-22T08:30:00",
    )

    assert task.due_date == date(2026, 9, 30)
    assert task.created_at == datetime(2026, 9, 22, 8, 30)
    assert task.completed is False
    assert task.priority is Priority.HIGH
