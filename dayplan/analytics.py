from datetime import date

from .date_service import is_overdue, week_bounds
from .models import Task


def daily_summary(tasks: list[Task], today: date) -> dict:
    due = [task for task in tasks if task.due_date == today]
    return {
        "date": today,
        "due_total": len(due),
        "due_pending": sum(task.status == "Pending" for task in due),
        "due_completed": sum(task.status == "Completed" for task in due),
        "overdue": sum(is_overdue(task, today) for task in tasks),
        "completed_today": sum(task.completed_on == today for task in tasks),
    }


def weekly_summary(tasks: list[Task], today: date) -> dict:
    week_start, week_end = week_bounds(today)
    due = [task for task in tasks if task.due_date is not None and week_start <= task.due_date <= week_end]
    return {
        "week_start": week_start,
        "week_end": week_end,
        "due_total": len(due),
        "due_pending": sum(task.status == "Pending" for task in due),
        "due_completed": sum(task.status == "Completed" for task in due),
        "overdue": sum(is_overdue(task, today) for task in due),
        "completion_rate": None if not due else (sum(task.status == "Completed" for task in due) / len(due) * 100),
    }