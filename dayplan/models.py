from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("Pending", "Completed")


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    description: Optional[str]
    due_date: Optional[date]
    priority: str
    status: str
    completed_on: Optional[date]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TaskView:
    task: Task
    is_overdue: bool
    is_due_today: bool


@dataclass(frozen=True)
class DashboardTasks:
    tasks: list[TaskView]
    due_today_tasks: list[TaskView]


@dataclass(frozen=True)
class MutationResult:
    task: Task
    changed: bool