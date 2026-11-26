from __future__ import annotations

from datetime import date

from . import analytics, database
from .date_service import is_due_today, is_overdue
from .models import DashboardTasks, MutationResult, TaskView
from .validators import TaskNotFound, validate_task_fields


def list_tasks(db, filters: dict, today: date) -> DashboardTasks:
    views = []
    for task in database.list_tasks(db):
        view = TaskView(task, is_overdue(task, today), is_due_today(task, today))
        if filters["status"] == "Pending" and task.status != "Pending":
            continue
        if filters["status"] == "Completed" and task.status != "Completed":
            continue
        if filters["status"] == "Overdue" and not view.is_overdue:
            continue
        if filters["priority"] != "All" and task.priority != filters["priority"]:
            continue
        views.append(view)
    return DashboardTasks(views, [view for view in views if view.is_due_today])


def get_task(db, task_id: int):
    task = database.get_task(db, task_id)
    if task is None:
        raise TaskNotFound
    return task


def create_task(db, fields):
    return database.insert_task(db, validate_task_fields(fields, editing=False))


def update_task(db, task_id: int, fields):
    values = validate_task_fields(fields, editing=True)
    before = get_task(db, task_id)
    task = database.update_task(db, task_id, values)
    changed = (before.title, before.description, before.due_date, before.priority) != (
        values["title"], values["description"], values["due_date"], values["priority"])
    return MutationResult(task, changed)


def delete_task(db, task_id: int):
    if not database.get_task(db, task_id):
        raise TaskNotFound
    database.delete_task(db, task_id)


def complete_task(db, task_id: int, today: date):
    before = get_task(db, task_id)
    task = database.complete_task(db, task_id, today)
    return MutationResult(task, before.status != "Completed")


def get_summaries(db, today: date):
    tasks = database.list_tasks(db)
    return {"daily": analytics.daily_summary(tasks, today), "weekly": analytics.weekly_summary(tasks, today)}