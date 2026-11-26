from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
import sqlite3
from threading import Barrier

import pytest

from dayplan import analytics, database, task_service
from dayplan.date_service import local_today
from dayplan.validators import TaskNotFound, ValidationError, validate_filters


def make_db(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    database.init_db(path)
    return database.connect(path)


@pytest.fixture
def db(tmp_path):
    with closing(make_db(tmp_path)) as connection:
        yield connection


def test_create_update_complete_and_repeat_preserves_completion(db):
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


def test_validation_rejects_impossible_date_and_repeated_filter():
    with pytest.raises(ValidationError) as date_error:
        task_service.create_task(None, {"title": "Task", "due_date": "2026-02-30", "priority": "Low"})
    assert "due_date" in date_error.value.errors

    with pytest.raises(ValidationError):
        validate_filters({"status": ["Pending", "Completed"], "priority": "All"})


def test_daily_and_weekly_summaries_use_status_and_due_date(db):
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


def test_daily_summary_counts_completed_tasks_by_due_and_completion_dates(db):
    today = date(2026, 11, 21)
    due_today = task_service.create_task(db, {"title": "Due today", "due_date": "2026-11-21"})
    past_due = task_service.create_task(db, {"title": "Finished late", "due_date": "2026-11-20"})
    task_service.create_task(db, {"title": "Still overdue", "due_date": "2026-11-20"})
    task_service.complete_task(db, due_today.id, today)
    task_service.complete_task(db, past_due.id, today)

    assert task_service.get_summaries(db, today)["daily"] == {
        "date": today,
        "due_total": 1,
        "due_pending": 0,
        "due_completed": 1,
        "overdue": 1,
        "completed_today": 2,
    }


@pytest.mark.parametrize(
    ("utc_minute", "expected_date"),
    [(29, date(2026, 11, 21)), (30, date(2026, 11, 22))],
    ids=["before-local-midnight", "at-local-midnight"],
)
def test_local_today_rolls_over_at_kolkata_midnight(monkeypatch, utc_minute, expected_date):
    instant = datetime(2026, 11, 21, 18, utc_minute, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is not None
            return instant.astimezone(tz)

    monkeypatch.setattr("datetime.datetime", FixedDatetime)

    assert local_today("Asia/Kolkata") == expected_date


def test_weekly_summary_includes_both_boundaries_across_years(db):
    today = date(2025, 1, 1)
    for title, due_date in (
        ("Previous Sunday", "2024-12-29"),
        ("First day of this week", "2024-12-30"),
        ("Last day of this week", "2025-01-05"),
        ("Next Monday", "2025-01-06"),
    ):
        task_service.create_task(db, {"title": title, "due_date": due_date})
    task_service.create_task(db, {"title": "Undated"})
    completed = task_service.create_task(db, {"title": "Finished late", "due_date": "2024-12-31"})
    task_service.complete_task(db, completed.id, today)
    completed_early = task_service.create_task(db, {"title": "Finished early", "due_date": "2025-01-02"})
    task_service.complete_task(db, completed_early.id, date(2024, 12, 29))

    assert task_service.get_summaries(db, today)["weekly"] == {
        "week_start": date(2024, 12, 30),
        "week_end": date(2025, 1, 5),
        "due_total": 4,
        "due_pending": 2,
        "due_completed": 2,
        "overdue": 1,
        "completion_rate": 50.0,
    }


@pytest.mark.parametrize("due_date", [None, "2026-11-15", "2026-11-23"])
def test_weekly_summary_has_no_rate_when_no_tasks_are_due(db, due_date):
    if due_date is not None:
        task_service.create_task(db, {"title": "Due outside this week", "due_date": due_date})

    assert task_service.get_summaries(db, date(2026, 11, 21))["weekly"] == {
        "week_start": date(2026, 11, 16),
        "week_end": date(2026, 11, 22),
        "due_total": 0,
        "due_pending": 0,
        "due_completed": 0,
        "overdue": 0,
        "completion_rate": None,
    }


def test_weekly_summary_returns_zero_rate_when_due_tasks_are_all_pending(db):
    task_service.create_task(db, {"title": "Still pending", "due_date": "2026-11-21"})

    assert task_service.get_summaries(db, date(2026, 11, 21))["weekly"] == {
        "week_start": date(2026, 11, 16),
        "week_end": date(2026, 11, 22),
        "due_total": 1,
        "due_pending": 1,
        "due_completed": 0,
        "overdue": 0,
        "completion_rate": 0.0,
    }


def test_initialize_database_preserves_saved_tasks_when_reopened(tmp_path):
    database_path = tmp_path / "nested" / "tasks.sqlite3"
    database.initialize_database(database_path)

    with closing(database.get_connection(database_path)) as connection:
        task = task_service.create_task(connection, {"title": "Keep this task"})

    database.initialize_database(str(database_path))

    with closing(database.get_connection(database_path)) as connection:
        assert task_service.get_task(connection, task.id) == task


def test_get_connection_configures_rows_and_close_connection_closes_it(tmp_path):
    database_path = tmp_path / "tasks.sqlite3"
    database.initialize_database(database_path)
    connection = database.get_connection(str(database_path))
    try:
        row = connection.execute("PRAGMA foreign_keys").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row[0] == 1
    finally:
        database.close_connection(connection)

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


@pytest.mark.parametrize("schema_fails", [False, True], ids=["success", "failure"])
def test_initializer_closes_its_connection(tmp_path, monkeypatch, schema_fails):
    database_path = tmp_path / "tasks.sqlite3"
    with closing(database.get_connection(database_path)) as connection:
        monkeypatch.setattr(database, "get_connection", lambda path: connection)

        if schema_fails:
            monkeypatch.setattr(database, "SCHEMA", "INVALID SQL;")
            with pytest.raises(sqlite3.OperationalError):
                database.initialize_database(database_path)
        else:
            database.initialize_database(database_path)

        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connection.execute("SELECT 1")


def test_schema_supplies_task_and_utc_timestamp_defaults(db):
    with database.transaction(db):
        task_id = db.execute(
            "INSERT INTO tasks (title) VALUES (?)", ("Only a title",)
        ).lastrowid
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    assert row["priority"] == "Medium"
    assert row["status"] == "Pending"
    assert row["description"] is None
    assert row["due_date"] is None
    assert row["completed_on"] is None
    assert row["created_at"] == row["updated_at"]
    assert len(row["created_at"]) == 20 and row["created_at"].endswith("Z")
    assert task_service.get_task(db, task_id).created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    ("due_date", "status", "completed_on"),
    [
        ("2026-1-08", "Pending", None),
        (None, "Completed", "2026/01/08"),
        (None, "Pending", "2026-01-08"),
        (None, "Completed", None),
    ],
    ids=["bad-due-format", "bad-completion-format", "pending-with-date", "completed-without-date"],
)
def test_schema_rejects_invalid_dates_and_completion_state(db, due_date, status, completed_on):
    with pytest.raises(sqlite3.IntegrityError), database.transaction(db):
        db.execute(
            "INSERT INTO tasks (title, due_date, status, completed_on) VALUES (?, ?, ?, ?)",
            ("Task", due_date, status, completed_on),
        )


def test_editing_completed_task_reports_changes_and_preserves_completion(db, monkeypatch):
    task = task_service.create_task(db, {"title": "Original"})
    completed = task_service.complete_task(db, task.id, date(2026, 11, 25)).task
    monkeypatch.setattr(database, "utc_now", lambda: "2026-11-27T12:00:00Z")
    fields = {"title": "Edited", "priority": "Medium"}

    updated = task_service.update_task(db, task.id, fields)

    assert updated.changed is True
    assert updated.task.title == "Edited"
    assert updated.task.status == "Completed"
    assert updated.task.completed_on == completed.completed_on
    assert updated.task.created_at == completed.created_at
    assert updated.task.updated_at.isoformat() == "2026-11-27T12:00:00+00:00"

    monkeypatch.setattr(database, "utc_now", lambda: "2026-11-28T12:00:00Z")
    unchanged = task_service.update_task(db, task.id, fields)
    repeated_completion = task_service.complete_task(db, task.id, date(2026, 11, 28))

    assert unchanged.changed is False
    assert unchanged.task == updated.task
    assert repeated_completion.changed is False
    assert repeated_completion.task == updated.task


def test_mutations_report_missing_task(db):
    with pytest.raises(TaskNotFound):
        task_service.update_task(db, 1, {"title": "Missing", "priority": "Medium"})
    with pytest.raises(TaskNotFound):
        task_service.complete_task(db, 1, date(2026, 11, 25))
    with pytest.raises(TaskNotFound):
        task_service.delete_task(db, 1)


def test_delete_reports_success_only_when_a_row_was_deleted(db):
    task = task_service.create_task(db, {"title": "Delete me"})

    assert task_service.delete_task(db, task.id) is None
    assert database.get_task(db, task.id) is None
    with pytest.raises(TaskNotFound):
        task_service.delete_task(db, task.id)


def test_transaction_rolls_back_partial_write_after_reopening(tmp_path):
    database_path = tmp_path / "tasks.sqlite3"
    database.initialize_database(database_path)

    with closing(database.get_connection(database_path)) as connection:
        task_service.create_task(connection, {"title": "Keep this task"})
        with pytest.raises(sqlite3.IntegrityError), database.transaction(connection):
            connection.execute("INSERT INTO tasks (title) VALUES (?)", ("Partial write",))
            connection.execute(
                "INSERT INTO tasks (title, priority) VALUES (?, ?)", ("Invalid", "Urgent")
            )

    with closing(database.get_connection(database_path)) as connection:
        assert [task.title for task in database.list_tasks(connection)] == ["Keep this task"]


def test_concurrent_completions_report_exactly_one_change(tmp_path, monkeypatch):
    database_path = tmp_path / "tasks.sqlite3"
    database.initialize_database(database_path)
    with closing(database.get_connection(database_path)) as connection:
        task_id = task_service.create_task(connection, {"title": "Finish once"}).id

    start = Barrier(2)
    completion_dates = (date(2026, 11, 25), date(2026, 11, 26))
    transaction = database.transaction

    @contextmanager
    def synchronized_transaction(connection):
        start.wait(timeout=5)
        with transaction(connection):
            yield

    monkeypatch.setattr(database, "transaction", synchronized_transaction)

    def complete_on(today):
        with closing(database.get_connection(database_path)) as connection:
            return task_service.complete_task(connection, task_id, today)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(complete_on, completion_dates, timeout=15))

    assert sum(result.changed for result in results) == 1
    winning_date = next(day for day, result in zip(completion_dates, results) if result.changed)
    with closing(database.get_connection(database_path)) as connection:
        saved = task_service.get_task(connection, task_id)
    assert saved.completed_on == winning_date
    assert all(result.task == saved for result in results)
