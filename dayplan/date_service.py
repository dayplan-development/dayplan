from datetime import date, timedelta
from zoneinfo import ZoneInfo

from .models import Task


def local_today(timezone: str) -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo(timezone)).date()


def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def is_overdue(task: Task, today: date) -> bool:
    return task.status == "Pending" and task.due_date is not None and task.due_date < today


def is_due_today(task: Task, today: date) -> bool:
    return task.status == "Pending" and task.due_date == today