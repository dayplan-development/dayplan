from datetime import date

import pytest

from dayplan import analytics, database, task_service
from dayplan.validators import ValidationError, validate_filters


def make_db(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    database.init_db(path)
    return database.connect(path)


def test_create_update_complete_and_repeat_preserves_completion(tmp_path):
    db = make_db(tmp_path)
    task = task_service.create_task(db, {
        "title": "  Study  ", "description": "  Notes ", "due_date": "2026-11-24", "priority": "High",
    })
    assert task.title == "Study"
    assert task.status == "Pending"

    unchanged = task_service.update_task(db, task.id, {
        "title": "Study", "description": "Notes", "due_date": "2026-11-24", "priority": "High",
    })
    assert unchanged.changed is False

    completed = task_service.complete_task(db, task.id, date(2026, 11, 25))
    repeated = task_service.complete_task(db, task.id, date(2026, 11, 26))
    assert completed.changed is True
    assert repeated.changed is False
    assert repeated.task.completed_on == date(2026, 11, 25)
    db.close()


def test_validation_rejects_impossible_date_and_repeated_filter():
    with pytest.raises(ValidationError) as date_error:
        task_service.create_task(None, {"title": "Task", "due_date": "2026-02-30", "priority": "Low"})
    assert "due_date" in date_error.value.errors

    with pytest.raises(ValidationError):
        validate_filters({"status": ["Pending", "Completed"], "priority": "All"})


def test_daily_and_weekly_summaries_use_status_and_due_date(tmp_path):
    db = make_db(tmp_path)
    pending = task_service.create_task(db, {"title": "Past", "due_date": "2026-11-20", "priority": "Low"})
    today = task_service.create_task(db, {"title": "Today", "due_date": "2026-11-21", "priority": "Medium"})
    task_service.complete_task(db, pending.id, date(2026, 11, 21))
    task_service.create_task(db, {"title": "Sunday", "due_date": "2026-11-22", "priority": "High"})
    summaries = task_service.get_summaries(db, date(2026, 11, 21))

    assert summaries["daily"]["due_total"] == 1
    assert summaries["daily"]["due_pending"] == 1
    assert summaries["daily"]["completed_today"] == 1
    assert summaries["weekly"]["due_total"] == 3
    assert summaries["weekly"]["due_completed"] == 1
    assert summaries["weekly"]["completion_rate"] == pytest.approx(33.3333333333)
    db.close()