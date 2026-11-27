from datetime import date
from pathlib import Path
import re
from unittest.mock import Mock, call

import pytest
from flask import Flask, g, template_rendered
from werkzeug.datastructures import MultiDict

import dayplan
from config import TestingConfig as AppTestingConfig
from dayplan import close_db, create_app, database, get_db, task_service


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    return create_app(AppTestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def database_helpers(monkeypatch):
    opener = Mock(side_effect=lambda database_path: object())
    closer = Mock()
    monkeypatch.setattr(database, "get_connection", opener, raising=False)
    monkeypatch.setattr(database, "close_connection", closer, raising=False)
    return opener, closer


@pytest.fixture
def dashboard_app(app, tmp_path, monkeypatch):
    database_path = str(tmp_path / "dashboard.sqlite3")
    database.initialize_database(database_path)
    app.config["DATABASE_PATH"] = database_path
    monkeypatch.setattr(dayplan, "local_today", Mock(return_value=date(2026, 11, 26)))
    return app


@pytest.fixture
def populated_dashboard_app(dashboard_app):
    with dashboard_app.app_context():
        connection = get_db()
        for title, priority, due_date in (
            ("High due today", "High", "2026-11-26"),
            ("High overdue", "High", "2026-11-25"),
            ("Low overdue", "Low", "2026-11-25"),
            ("Low due today", "Low", "2026-11-26"),
            ("High due tomorrow", "High", "2026-11-27"),
        ):
            task_service.create_task(
                connection, {"title": title, "priority": priority, "due_date": due_date}
            )
        completed = task_service.create_task(
            connection,
            {"title": "Completed today", "priority": "High", "due_date": "2026-11-26"},
        )
        task_service.complete_task(connection, completed.id, date(2026, 11, 26))
    return dashboard_app


@pytest.fixture
def edit_app(dashboard_app):
    with dashboard_app.app_context():
        task_service.create_task(get_db(), {
            "title": "Original",
            "description": "Original notes",
            "due_date": "2026-11-25",
            "priority": "Medium",
        })
    return dashboard_app


def get_dashboard(app, query_string=None):
    return request_dashboard(app, "/", query_string=query_string)


def request_dashboard(app, path, **kwargs):
    return request_template(app, path, "dashboard.html", **kwargs)


def request_template(app, path, expected_template, **kwargs):
    renders = []

    def record_render(sender, template, context, **extra):
        renders.append((template, context))

    with template_rendered.connected_to(record_render, app):
        response = app.test_client().open(path, **kwargs)

    [(template, context)] = renders
    assert template.name == expected_template
    assert template.filename is not None
    assert Path(template.filename).resolve() == (
        Path(__file__).resolve().parents[1] / "templates" / expected_template
    )
    flask_keys = {"g", "request", "session"}
    return response, {key: value for key, value in context.items() if key not in flask_keys}


def saved_tasks(app):
    with app.app_context():
        return database.list_tasks(get_db())


def test_create_app_loads_secret_key_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dayplan-environment-test-only")

    assert create_app().secret_key == "dayplan-environment-test-only"


def test_explicit_test_config_overrides_environment_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dayplan-environment-test-only")

    class ExplicitTestConfig(AppTestingConfig):
        SECRET_KEY = "dayplan-config-test-only"

    assert create_app(ExplicitTestConfig).secret_key == "dayplan-config-test-only"


def test_explicit_blank_secret_key_is_rejected_even_with_environment_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dayplan-environment-test-only")

    class ExplicitTestConfig(AppTestingConfig):
        SECRET_KEY = ""

    with pytest.raises(RuntimeError, match="Set a non-blank SECRET_KEY"):
        create_app(ExplicitTestConfig)


@pytest.mark.parametrize("secret_key", [None, "", "  "])
def test_create_app_rejects_missing_or_blank_secret_key(monkeypatch, secret_key):
    if secret_key is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", secret_key)

    with pytest.raises(RuntimeError, match="Set a non-blank SECRET_KEY"):
        create_app()


def test_default_database_path_is_inside_flask_instance_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    instance_path = tmp_path / "instance"
    monkeypatch.setattr(Flask, "auto_find_instance_path", lambda self: str(instance_path))

    app = create_app(AppTestingConfig)

    assert app.instance_path == str(instance_path)
    assert app.config["DATABASE_PATH"] == str(instance_path / "dayplan.sqlite3")


def test_explicit_database_path_overrides_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "environment.sqlite3"))
    configured_path = tmp_path / "explicit.sqlite3"

    class ExplicitTestConfig(AppTestingConfig):
        DATABASE_PATH = configured_path

    assert create_app(ExplicitTestConfig).config["DATABASE_PATH"] == str(configured_path)


def test_create_app_loads_database_path_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    database_path = tmp_path / "environment.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    assert create_app(AppTestingConfig).config["DATABASE_PATH"] == str(database_path)


def test_create_app_does_not_create_database_file(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    database_path = tmp_path / "absent" / "dayplan.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    create_app(AppTestingConfig)

    assert not database_path.exists()
    assert not database_path.parent.exists()


def test_unused_app_context_does_not_open_or_close_a_connection(
    monkeypatch, database_helpers
):
    opener, closer = database_helpers
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")

    app = create_app(AppTestingConfig)
    opener.assert_not_called()

    with app.app_context():
        opener.assert_not_called()

    opener.assert_not_called()
    closer.assert_not_called()


def test_get_db_opens_configured_path_and_reuses_connection(app, database_helpers):
    opener, closer = database_helpers

    with app.app_context():
        connection = get_db()
        assert get_db() is connection
        opener.assert_called_once_with(app.config["DATABASE_PATH"])
        closer.assert_not_called()

    closer.assert_called_once_with(connection)


def test_separate_app_contexts_have_separate_connections(app, database_helpers):
    opener, closer = database_helpers

    with app.app_context():
        outer_connection = get_db()
        with app.app_context():
            inner_connection = get_db()
            assert inner_connection is not outer_connection
        closer.assert_called_once_with(inner_connection)
        assert get_db() is outer_connection

    assert opener.call_count == 2
    assert closer.call_args_list == [call(inner_connection), call(outer_connection)]


def test_close_db_removes_connection_before_context_teardown(app, database_helpers):
    _, closer = database_helpers

    with app.app_context():
        connection = get_db()
        close_db()
        assert "db" not in g
        closer.assert_called_once_with(connection)

    closer.assert_called_once_with(connection)


def test_teardown_closes_connection_after_context_error(app, database_helpers):
    _, closer = database_helpers

    with pytest.raises(RuntimeError, match="test context error"):
        with app.app_context():
            connection = get_db()
            raise RuntimeError("test context error")

    closer.assert_called_once_with(connection)


def test_init_db_command_is_registered(app):
    result = app.test_cli_runner().invoke(args=["init-db", "--help"])

    assert result.exit_code == 0
    assert "Initialize the configured DayPlan database." in result.output


def test_init_db_passes_configured_path_and_reports_success(app, monkeypatch, tmp_path):
    database_path = str(tmp_path / "configured.sqlite3")
    app.config["DATABASE_PATH"] = database_path
    initializer = Mock()
    monkeypatch.setattr(database, "initialize_database", initializer, raising=False)

    result = app.test_cli_runner().invoke(args=["init-db"])

    initializer.assert_called_once_with(database_path)
    assert result.exit_code == 0
    assert result.output == "Database initialized successfully.\n"


def test_init_db_hides_initializer_failure_details(app, monkeypatch):
    initializer = Mock(side_effect=RuntimeError("CREATE TABLE failed at a private path"))
    monkeypatch.setattr(database, "initialize_database", initializer, raising=False)

    result = app.test_cli_runner().invoke(args=["init-db"])

    assert result.exit_code == 1
    assert result.output == "Error: Database initialization failed.\n"


def test_init_db_reports_unavailable_initializer(app, monkeypatch):
    monkeypatch.delattr(database, "initialize_database", raising=False)

    result = app.test_cli_runner().invoke(args=["init-db"])

    assert result.exit_code == 1
    assert result.output == "Error: Database initialization is unavailable.\n"


def test_dashboard_renders_empty_lists_and_create_form_with_default_context(dashboard_app, monkeypatch):
    list_tasks = Mock(wraps=dayplan.list_tasks)
    monkeypatch.setattr(dayplan, "list_tasks", list_tasks)

    response, context = get_dashboard(dashboard_app)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<h1>DayPlan</h1>" in response.data
    html = response.get_data(as_text=True)
    assert "No pending tasks due today match these filters." in html
    assert "No tasks match these filters." in html
    assert 'method="post" aria-labelledby="new-task-heading"' in html
    assert 'action="/tasks"' in html
    assert 'id="create-title" name="title" type="text" required' in html
    assert 'value="Medium" selected' in html
    assert 'href="/static/css/style.css"' in html
    assert context == {
        "tasks": [],
        "due_today_tasks": [],
        "today": date(2026, 11, 26),
        "daily": {
            "date": date(2026, 11, 26),
            "due_total": 0,
            "due_pending": 0,
            "due_completed": 0,
            "overdue": 0,
            "completed_today": 0,
        },
        "filters": {"status": "All", "priority": "All"},
        "form_values": {"title": "", "description": "", "due_date": "", "priority": "Medium"},
        "errors": {},
    }
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")
    list_tasks.assert_called_once()


def test_dashboard_renders_full_task_text_and_actions_by_status(populated_dashboard_app):
    app = populated_dashboard_app
    title = "W" * 100
    description = "https://example.test/".ljust(500, "W")
    with app.app_context():
        long_task = task_service.create_task(
            get_db(), {"title": title, "description": description, "priority": "High"}
        )
    tasks = {task.title: task for task in saved_tasks(app)}

    response, _ = get_dashboard(app, {"status": "All", "priority": "High"})

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="High" selected' in html
    assert 'href="/summaries?priority=High">Summaries</a>' in html
    assert "Low due today" not in html
    cards = re.findall(r'<article class="task-card\b.*?</article>', html, re.DOTALL)
    for name, expected_count in (("High due today", 2), ("Completed today", 1), (title, 1)):
        task = tasks[name]
        matching = [card for card in cards if f'<h3 class="task-title">{name}</h3>' in card]
        assert len(matching) == expected_count
        for card in matching:
            assert f'href="/tasks/{task.id}/edit?priority=High"' in card
            assert f'method="post" action="/tasks/{task.id}/delete?priority=High"' in card
            assert 'onsubmit="return confirm(\'Delete this task permanently?\')"' in card
            complete = f'method="post" action="/tasks/{task.id}/complete?priority=High"'
            if task.status == "Pending":
                assert complete in card
            else:
                assert "/complete" not in card
            if task.id == long_task.id:
                assert f'<p class="task-desc">{description}</p>' in card


def test_dashboard_overview_counts_all_tasks_independently_of_filters(
    populated_dashboard_app, monkeypatch
):
    app = populated_dashboard_app
    with app.app_context():
        db = get_db()
        for title, due_date, completion_date in (
            ("Past deadline, completed today", "2026-11-23", date(2026, 11, 26)),
            ("Completed yesterday", "2026-11-25", date(2026, 11, 25)),
        ):
            task = task_service.create_task(db, {"title": title, "due_date": due_date})
            task_service.complete_task(db, task.id, completion_date)
    get_summaries = Mock(wraps=task_service.get_summaries)
    monkeypatch.setattr(task_service, "get_summaries", get_summaries)

    for filters in (None, {"status": "Pending", "priority": "Low"}):
        response, context = get_dashboard(app, filters)

        assert response.status_code == 200
        assert context["daily"] == {
            "date": date(2026, 11, 26),
            "due_total": 3,
            "due_pending": 2,
            "due_completed": 1,
            "overdue": 2,
            "completed_today": 2,
        }
        html = response.get_data(as_text=True)
        overview = html.split('<dl class="dashboard-overview"', 1)[1].split("</dl>", 1)[0]
        assert re.findall(r"<dd>(\d+)</dd>", overview) == ["3", "2", "2"]
        if filters:
            assert {row.task.title for row in context["tasks"]} == {"Low due today", "Low overdue"}

    assert dayplan.local_today.call_args_list == [call("Asia/Kolkata")] * 2
    assert get_summaries.call_count == 2
    assert [invocation.args[1] for invocation in get_summaries.call_args_list] == [
        date(2026, 11, 26)
    ] * 2


def test_dashboard_applies_status_and_priority_together(populated_dashboard_app):
    response, context = get_dashboard(
        populated_dashboard_app, {"status": "Overdue", "priority": "High"}
    )

    assert response.status_code == 200
    assert context["filters"] == {"status": "Overdue", "priority": "High"}
    [task_view] = context["tasks"]
    assert task_view.task.title == "High overdue"
    assert task_view.is_overdue
    assert context["due_today_tasks"] == []


def test_dashboard_pending_includes_overdue(populated_dashboard_app):
    response, context = get_dashboard(
        populated_dashboard_app, {"status": "Pending", "priority": "High"}
    )

    assert response.status_code == 200
    assert {view.task.title for view in context["tasks"]} == {
        "High due today",
        "High overdue",
        "High due tomorrow",
    }


def test_dashboard_due_today_contains_only_matching_pending_tasks(populated_dashboard_app):
    response, context = get_dashboard(populated_dashboard_app, {"priority": "High"})

    assert response.status_code == 200
    assert "Completed today" in {view.task.title for view in context["tasks"]}
    [due_today] = context["due_today_tasks"]
    assert due_today.task.title == "High due today"
    assert due_today.task.status == "Pending"
    assert due_today.task.due_date == context["today"]
    assert due_today.is_due_today


def test_dashboard_valid_filters_with_no_matches_return_empty_lists(populated_dashboard_app):
    response, context = get_dashboard(
        populated_dashboard_app, {"status": "Completed", "priority": "Low"}
    )

    assert response.status_code == 200
    assert context["tasks"] == []
    assert context["due_today_tasks"] == []
    assert context["errors"] == {}


@pytest.mark.parametrize(
    ("query_string", "errors"),
    [
        ("status=", {"status": "Choose a valid status filter."}),
        ("priority=high", {"priority": "Choose a valid priority filter."}),
        ("status=Pending&status=Completed", {"status": "Submit this value only once."}),
        ("priority=Low&priority=High", {"priority": "Submit this value only once."}),
    ],
)
def test_dashboard_invalid_filters_do_not_open_database(
    dashboard_app, monkeypatch, query_string, errors
):
    opener = Mock(side_effect=AssertionError("Invalid filters must not open SQLite"))
    monkeypatch.setattr(database, "get_connection", opener)
    get_summaries = Mock(side_effect=AssertionError("Invalid filters must not load summaries"))
    monkeypatch.setattr(task_service, "get_summaries", get_summaries)

    response, context = get_dashboard(dashboard_app, query_string)

    assert response.status_code == 400
    assert response.mimetype == "text/html"
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert context["tasks"] == []
    assert context["due_today_tasks"] == []
    assert context["errors"] == errors
    assert context["daily"] is None
    assert b'class="dashboard-overview"' not in response.data
    opener.assert_not_called()
    get_summaries.assert_not_called()
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")


def test_dashboard_unexpected_service_error_returns_generic_500(dashboard_app, monkeypatch):
    dashboard_app.config["PROPAGATE_EXCEPTIONS"] = False
    monkeypatch.setattr(
        dayplan, "list_tasks", Mock(side_effect=RuntimeError("Private database detail"))
    )

    response = dashboard_app.test_client().get("/")

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."


def test_post_tasks_persists_approved_fields_and_redirects_with_filters(dashboard_app, monkeypatch):
    create = Mock(wraps=task_service.create_task)
    monkeypatch.setattr(task_service, "create_task", create)
    client = dashboard_app.test_client()
    fields = {"title": "  Write notes  ", "description": "  Draft  ", "priority": "Low"}

    response = client.post(
        "/tasks?status=Pending&priority=High&unrelated=ignored",
        data={**fields, "status": "Completed", "id": "42"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/?status=Pending&priority=High"
    assert create.call_count == 1
    assert create.call_args.args[1] == fields
    [task] = saved_tasks(dashboard_app)
    assert (task.title, task.description, task.priority) == ("Write notes", "Draft", "Low")
    assert task.status == "Pending"
    assert task.completed_on is None
    with client.session_transaction() as session:
        assert session["_flashes"] == [("success", "Task added.")]
    dayplan.local_today.assert_not_called()


def test_post_tasks_renders_success_notification_once_after_redirect(dashboard_app):
    client = dashboard_app.test_client()

    response = client.post("/tasks", data={"title": "Draft"}, follow_redirects=True)

    assert [redirect.status_code for redirect in response.history] == [303]
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count("Task added.") == 1
    assert html.count('data-flash-category="success"') == 1
    assert "<strong>Success:</strong>" in html
    assert 'role="status" aria-live="polite" aria-atomic="true"' in html
    assert 'role="alert" aria-live="assertive" aria-atomic="true"' in html
    assert 'type="button" aria-label="Dismiss notification" hidden' in html
    assert 'src="/static/js/notifications.js" defer' in html

    next_response = client.get("/")
    assert next_response.status_code == 200
    assert b"Task added." not in next_response.data
    assert b"data-flash-stack" not in next_response.data


@pytest.mark.parametrize(
    ("query", "location", "due_date", "expected_date"),
    [
        ("", "/", None, None),
        ("?status=All&priority=High", "/?priority=High", "2026-01-01", date(2026, 1, 1)),
        ("?status=Pending&priority=All", "/?status=Pending", "2024-02-29", date(2024, 2, 29)),
    ],
)
def test_post_tasks_defaults_priority_and_accepts_calendar_dates(
    dashboard_app, query, location, due_date, expected_date
):
    fields = {"title": "Plan project"}
    if due_date is not None:
        fields["due_date"] = due_date

    response = dashboard_app.test_client().post(f"/tasks{query}", data=fields)

    assert response.status_code == 303
    assert response.headers["Location"] == location
    [task] = saved_tasks(dashboard_app)
    assert task.priority == "Medium"
    assert task.due_date == expected_date


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("priority", "", "Choose Low, Medium, or High."),
        ("priority", "Urgent", "Choose Low, Medium, or High."),
        ("due_date", "26/11/2026", "Enter a valid date in YYYY-MM-DD format."),
        ("due_date", "2026-02-30", "Enter a valid date in YYYY-MM-DD format."),
        ("title", "  \t ", "Enter a title."),
        ("title", "x" * 101, "Use 100 characters or fewer."),
        ("description", "x" * 501, "Use 500 characters or fewer."),
    ],
)
def test_post_tasks_invalid_fields_preserve_values_and_filtered_dashboard(
    populated_dashboard_app, field, value, message
):
    fields = {"title": "  Draft  ", "description": " Notes ", "due_date": "", "priority": "Low"}
    fields[field] = value
    before = saved_tasks(populated_dashboard_app)

    response, context = request_dashboard(
        populated_dashboard_app, "/tasks?status=Pending&priority=High", method="POST", data=fields
    )

    assert response.status_code == 400
    assert context["form_values"] == fields
    assert context["errors"] == {field: message}
    html = response.get_data(as_text=True)
    field_id = field.replace("_", "-")
    assert f'aria-describedby="create-{field_id}-error"' in html
    assert f'id="create-{field_id}-error">{message}</p>' in html
    assert 'action="/tasks?status=Pending&amp;priority=High"' in html
    if field == "due_date":
        assert f'value="{value}"' in html
    assert context["filter_errors"] == {}
    assert context["filters"] == {"status": "Pending", "priority": "High"}
    assert context["today"] == date(2026, 11, 26)
    assert {row.task.title for row in context["tasks"]} == {
        "High due today",
        "High overdue",
        "High due tomorrow",
    }
    assert [row.task.title for row in context["due_today_tasks"]] == ["High due today"]
    assert saved_tasks(populated_dashboard_app) == before
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")


@pytest.mark.parametrize("operation", ["create", "edit"])
@pytest.mark.parametrize("field", ["title", "description"])
@pytest.mark.parametrize("value", ["\x00", "Normal text\x00"], ids=["nul-only", "trailing-nul"])
def test_task_forms_reject_nul_without_changing_records(edit_app, operation, field, value):
    before = saved_tasks(edit_app)
    if operation == "create":
        path, template, prefix = "/tasks", "dashboard.html", "create"
    else:
        path, template, prefix = f"/tasks/{before[0].id}/edit", "task_form.html", "edit"
    fields = {"title": "Revised title", "description": "Revised description", "priority": "High"}
    fields[field] = value

    response, context = request_template(edit_app, path, template, method="POST", data=fields)

    assert response.status_code == 400
    message = "Remove null characters from this field."
    assert context["errors"] == {field: message}
    html = response.get_data(as_text=True)
    assert f'aria-describedby="{prefix}-{field}-error"' in html
    assert f'id="{prefix}-{field}-error">{message}</p>' in html
    assert saved_tasks(edit_app) == before


@pytest.mark.parametrize("field", ["title", "description", "due_date", "priority"])
def test_post_tasks_rejects_duplicate_fields(dashboard_app, monkeypatch, field):
    create = Mock(wraps=task_service.create_task)
    monkeypatch.setattr(task_service, "create_task", create)
    fields = MultiDict({"title": "Draft", "description": "Notes", "due_date": "", "priority": "Low"})
    fields.add(field, "Second value")

    response, context = request_dashboard(dashboard_app, "/tasks", method="POST", data=fields)

    assert response.status_code == 400
    assert context["errors"] == {field: "Submit this value only once."}
    assert context["form_values"][field] == fields.getlist(field)
    assert context["filter_errors"] == {}
    create.assert_not_called()
    assert saved_tasks(dashboard_app) == []


@pytest.mark.parametrize(
    ("query", "filter_errors"),
    [
        ("status=Pending&status=Pending", {"status": "Submit this value only once."}),
        ("priority=Low&priority=High", {"priority": "Submit this value only once."}),
        (
            "status=Invalid&priority=",
            {
                "status": "Choose a valid status filter.",
                "priority": "Choose a valid priority filter.",
            },
        ),
    ],
)
def test_post_tasks_rejects_invalid_filters_without_calling_service(
    dashboard_app, monkeypatch, query, filter_errors
):
    create = Mock(wraps=task_service.create_task)
    monkeypatch.setattr(task_service, "create_task", create)
    fields = {"title": "Draft", "description": "", "due_date": "bad date", "priority": ""}

    response, context = request_dashboard(
        dashboard_app, f"/tasks?{query}", method="POST", data=fields
    )

    assert response.status_code == 400
    assert context["form_values"] == fields
    assert context["errors"] == {
        "due_date": "Enter a valid date in YYYY-MM-DD format.",
        "priority": "Choose Low, Medium, or High.",
    }
    assert context["filter_errors"] == filter_errors
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert context["tasks"] == context["due_today_tasks"] == []
    create.assert_not_called()
    assert saved_tasks(dashboard_app) == []
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")


def test_post_tasks_invalid_filter_blocks_valid_task_without_opening_database(
    dashboard_app, monkeypatch
):
    create = Mock(wraps=task_service.create_task)
    monkeypatch.setattr(task_service, "create_task", create)
    opener = Mock(side_effect=AssertionError("Invalid filters must not open SQLite"))
    with monkeypatch.context() as patch:
        patch.setattr(database, "get_connection", opener)
        response, context = request_dashboard(
            dashboard_app, "/tasks?status=Invalid", method="POST", data={"title": "Draft"}
        )

    assert response.status_code == 400
    assert context["errors"] == {}
    assert context["filter_errors"] == {"status": "Choose a valid status filter."}
    assert context["form_values"] == {"title": "Draft", "description": "", "due_date": "", "priority": ""}
    opener.assert_not_called()
    create.assert_not_called()
    assert saved_tasks(dashboard_app) == []


def test_post_tasks_failed_write_returns_generic_500_without_success_flash(dashboard_app):
    dashboard_app.config["PROPAGATE_EXCEPTIONS"] = False
    with dashboard_app.app_context():
        connection = get_db()
        connection.execute(
            """CREATE TRIGGER reject_task BEFORE INSERT ON tasks
               BEGIN SELECT RAISE(ABORT, 'Private database detail'); END"""
        )
        connection.commit()
    client = dashboard_app.test_client()

    response = client.post("/tasks", data={"title": "Draft"})

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."
    assert saved_tasks(dashboard_app) == []
    with client.session_transaction() as session:
        assert "_flashes" not in session
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert b"Task added." not in dashboard.data
    assert b'data-flash-category="success"' not in dashboard.data


def test_edit_task_get_prefills_context_and_preserves_filters(edit_app):
    [task] = saved_tasks(edit_app)

    response, context = request_template(
        edit_app, f"/tasks/{task.id}/edit?status=Pending&priority=High", "task_form.html"
    )

    assert response.status_code == 200
    assert context == {
        "task": task,
        "filters": {"status": "Pending", "priority": "High"},
        "form_values": {
            "title": "Original", "description": "Original notes",
            "due_date": "2026-11-25", "priority": "Medium",
        },
        "errors": {},
        "filter_errors": {},
    }
    html = response.get_data(as_text=True)
    assert f'action="/tasks/{task.id}/edit?status=Pending&amp;priority=High"' in html
    assert 'href="/?status=Pending&amp;priority=High">Cancel' in html
    assert 'method="post" aria-labelledby="edit-task-heading"' in html
    assert 'value="Original"' in html
    assert "Original notes</textarea>" in html
    assert 'value="Medium" selected' in html
    assert 'name="due_date" type="text" inputmode="numeric" placeholder="YYYY-MM-DD"' in html
    assert 'value="2026-11-25"' in html
    assert 'name="status"' not in html
    assert 'name="completed_on"' not in html


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("task_id", ["0", "-1", "abc", str(2**63)])
def test_edit_task_rejects_invalid_ids_before_backend(dashboard_app, monkeypatch, method, task_id):
    opener = Mock(side_effect=AssertionError("Invalid IDs must not open SQLite"))
    monkeypatch.setattr(database, "get_connection", opener)

    response = dashboard_app.test_client().open(f"/tasks/{task_id}/edit", method=method)

    assert response.status_code == 404
    opener.assert_not_called()


@pytest.mark.parametrize(
    ("method", "query", "fields"),
    [
        ("GET", "", None),
        ("POST", "", {"title": "Valid", "priority": "Low"}),
        ("POST", "", {"title": "", "priority": "Low"}),
        ("POST", "?priority=wrong", {"title": "Valid", "priority": "Low"}),
    ],
)
def test_edit_task_missing_returns_404_even_with_validation_errors(edit_app, method, query, fields):
    # The largest in-range ID is accepted by the route and SQLite, but has no row.
    response = edit_app.test_client().open(
        f"/tasks/{2**63 - 1}/edit{query}", method=method, data=fields
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("query", "filter_errors"),
    [
        ("status=Pending&status=Completed", {"status": "Submit this value only once."}),
        ("priority=", {"priority": "Choose a valid priority filter."}),
    ],
)
def test_edit_task_get_rejects_invalid_filters(edit_app, query, filter_errors):
    [task] = saved_tasks(edit_app)

    response, context = request_template(
        edit_app, f"/tasks/{task.id}/edit?{query}", "task_form.html"
    )

    assert response.status_code == 400
    assert context["task"] == task
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert context["filter_errors"] == filter_errors
    assert context["errors"] == {}


def test_edit_task_post_updates_all_fields_and_preserves_completion(edit_app, monkeypatch):
    [original] = saved_tasks(edit_app)
    with edit_app.app_context():
        task_service.complete_task(get_db(), original.id, date(2026, 11, 26))
    update = Mock(wraps=task_service.update_task)
    monkeypatch.setattr(task_service, "update_task", update)
    client = edit_app.test_client()
    fields = {
        "title": "  Revised task  ", "description": "  Revised notes  ",
        "due_date": "2024-02-29", "priority": "Low",
    }

    response = client.post(
        f"/tasks/{original.id}/edit?status=Completed&priority=High",
        data={**fields, "status": "Pending", "completed_on": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/?status=Completed&priority=High"
    assert update.call_count == 1
    assert update.call_args.args[1:] == (original.id, fields)
    [saved] = saved_tasks(edit_app)
    assert saved.id == original.id and saved.created_at == original.created_at
    assert (saved.title, saved.description, saved.priority) == ("Revised task", "Revised notes", "Low")
    assert saved.due_date == date(2024, 2, 29)
    assert saved.status == "Completed" and saved.completed_on == date(2026, 11, 26)
    with client.session_transaction() as session:
        assert session["_flashes"] == [("success", "Task updated.")]


def test_edit_task_post_clears_optional_fields(edit_app):
    [task] = saved_tasks(edit_app)
    path = f"/tasks/{task.id}/edit"

    response = edit_app.test_client().post(
        f"{path}?status=All&priority=Medium",
        data={"title": task.title, "priority": task.priority, "description": "", "due_date": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/?priority=Medium"
    [saved] = saved_tasks(edit_app)
    assert saved.description is None and saved.due_date is None
    _, context = request_template(edit_app, path, "task_form.html")
    assert context["form_values"]["description"] == context["form_values"]["due_date"] == ""


def test_edit_task_post_identical_edit_flashes_info_and_preserves_timestamp(edit_app, monkeypatch):
    [original] = saved_tasks(edit_app)
    monkeypatch.setattr(database, "utc_now", lambda: "2000-01-01T00:00:00Z")
    client = edit_app.test_client()

    response = client.post(f"/tasks/{original.id}/edit", data={
        "title": " Original ", "description": " Original notes ", "due_date": "2026-11-25",
        "priority": "Medium",
    })

    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    assert saved_tasks(edit_app) == [original]
    with client.session_transaction() as session:
        assert session["_flashes"] == [("info", "No changes to save.")]


def test_edit_task_post_invalid_fields_preserves_raw_values_and_active_filters(edit_app):
    [task] = saved_tasks(edit_app)

    response, context = request_template(
        edit_app, f"/tasks/{task.id}/edit?status=Pending&priority=High", "task_form.html",
        method="POST", data={"title": " \t ", "description": " Notes ", "due_date": "2026-02-30"},
    )

    assert response.status_code == 400
    assert context["task"] == task
    assert context["form_values"] == {
        "title": " \t ", "description": " Notes ", "due_date": "2026-02-30", "priority": "",
    }
    assert context["errors"] == {
        "title": "Enter a title.", "due_date": "Enter a valid date in YYYY-MM-DD format.",
        "priority": "Choose Low, Medium, or High.",
    }
    assert context["filter_errors"] == {}
    assert context["filters"] == {"status": "Pending", "priority": "High"}
    html = response.get_data(as_text=True)
    assert f'action="/tasks/{task.id}/edit?status=Pending&amp;priority=High"' in html
    assert 'href="/?status=Pending&amp;priority=High">Cancel' in html
    assert 'value="2026-02-30"' in html
    assert " Notes </textarea>" in html
    for field, message in context["errors"].items():
        field_id = field.replace("_", "-")
        assert f'aria-describedby="edit-{field_id}-error"' in html
        assert f'id="edit-{field_id}-error">{message}</p>' in html
    assert saved_tasks(edit_app) == [task]


def test_edit_task_post_rejects_duplicate_form_and_filter_priority(edit_app, monkeypatch):
    [task] = saved_tasks(edit_app)
    update = Mock(wraps=task_service.update_task)
    monkeypatch.setattr(task_service, "update_task", update)
    fields = MultiDict([("title", "Revised"), ("priority", "Low"), ("priority", "High")])

    response, context = request_template(
        edit_app, f"/tasks/{task.id}/edit?priority=High&priority=Low", "task_form.html",
        method="POST", data=fields,
    )

    assert response.status_code == 400
    assert context["errors"] == {"priority": "Submit this value only once."}
    assert context["filter_errors"] == {"priority": "Submit this value only once."}
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert context["form_values"]["priority"] == ["Low", "High"]
    html = response.get_data(as_text=True)
    assert f'action="/tasks/{task.id}/edit"' in html and 'href="/">Cancel' in html
    assert "<strong>Priority filter:</strong> Submit this value only once." in html
    assert 'id="edit-priority-error">Submit this value only once.</p>' in html
    update.assert_not_called()
    assert saved_tasks(edit_app) == [task]


def test_edit_task_post_failed_write_returns_generic_500_without_flash(edit_app):
    [task] = saved_tasks(edit_app)
    edit_app.config["PROPAGATE_EXCEPTIONS"] = False
    with edit_app.app_context():
        db = get_db()
        db.execute(
            """CREATE TRIGGER reject_edit AFTER UPDATE ON tasks
               BEGIN SELECT RAISE(FAIL, 'Private database detail'); END"""
        )
        db.commit()
    client = edit_app.test_client()

    response = client.post(f"/tasks/{task.id}/edit", data={"title": "New", "priority": "Low"})

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."
    assert saved_tasks(edit_app) == [task]
    with client.session_transaction() as session:
        assert "_flashes" not in session


def test_complete_task_persists_status_and_server_date(populated_dashboard_app, monkeypatch):
    app = populated_dashboard_app
    task = next(task for task in saved_tasks(app) if task.title == "High overdue")
    complete = Mock(wraps=task_service.complete_task)
    monkeypatch.setattr(task_service, "complete_task", complete)
    client = app.test_client()

    response = client.post(
        f"/tasks/{task.id}/complete?status=Pending&priority=High&completed_on=2000-01-01",
        data={"completed_on": "2000-01-02"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/?status=Pending&priority=High"
    complete.assert_called_once()
    assert complete.call_args.args[1:] == (task.id, date(2026, 11, 26))
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")
    saved = next(saved for saved in saved_tasks(app) if saved.id == task.id)
    assert saved.status == "Completed"
    assert saved.completed_on == date(2026, 11, 26)
    with client.session_transaction() as session:
        assert session["_flashes"] == [("success", "Task completed.")]


def test_complete_task_repeat_preserves_original_completion_and_timestamp(
    populated_dashboard_app, monkeypatch
):
    app = populated_dashboard_app
    task = next(task for task in saved_tasks(app) if task.title == "High due today")
    client = app.test_client()
    path = f"/tasks/{task.id}/complete?status=All&priority=High"
    monkeypatch.setattr(database, "utc_now", lambda: "2026-11-26T12:00:00Z")
    first_response = client.post(path)
    assert first_response.status_code == 303
    first = next(saved for saved in saved_tasks(app) if saved.id == task.id)
    assert first.completed_on == date(2026, 11, 26)
    assert first.updated_at.isoformat() == "2026-11-26T12:00:00+00:00"
    # Follow the first redirect so its success flash is consumed before the repeat.
    client.get(first_response.headers["Location"])

    monkeypatch.setattr(database, "utc_now", lambda: "2026-11-27T12:00:00Z")
    dayplan.local_today.return_value = date(2026, 11, 27)
    dayplan.local_today.reset_mock()
    repeat = client.post(path)

    assert repeat.status_code == 303
    assert repeat.headers["Location"] == "/?priority=High"
    assert next(saved for saved in saved_tasks(app) if saved.id == task.id) == first
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")
    with client.session_transaction() as session:
        assert session["_flashes"] == [("info", "Task is already completed.")]


@pytest.mark.parametrize(
    ("title", "status", "context_key"),
    [("High overdue", "Overdue", "tasks"), ("High due today", "All", "due_today_tasks")],
)
def test_complete_task_removes_task_from_actionable_dashboard_results(
    populated_dashboard_app, title, status, context_key
):
    app = populated_dashboard_app
    filters = {"status": status, "priority": "High"}
    _, before = get_dashboard(app, filters)
    [task] = [row.task for row in before[context_key] if row.task.title == title]

    response = app.test_client().post(f"/tasks/{task.id}/complete", query_string=filters)

    assert response.status_code == 303
    dashboard_response, after = request_dashboard(app, response.headers["Location"])
    assert dashboard_response.status_code == 200
    assert after["filters"] == filters
    assert task.id not in [row.task.id for row in after[context_key]]


@pytest.mark.parametrize(
    ("query", "errors"),
    [
        ("status=Archived", {"status": "Choose a valid status filter."}),
        ("priority=", {"priority": "Choose a valid priority filter."}),
        ("status=Pending&status=Pending", {"status": "Submit this value only once."}),
        ("priority=Low&priority=High", {"priority": "Submit this value only once."}),
    ],
)
def test_complete_task_invalid_filters_return_400_without_calling_service(
    populated_dashboard_app, monkeypatch, query, errors
):
    app = populated_dashboard_app
    before = saved_tasks(app)
    task = next(task for task in before if task.status == "Pending")
    complete = Mock(wraps=task_service.complete_task)
    opener = Mock(side_effect=AssertionError("Invalid filters must not open SQLite"))
    with monkeypatch.context() as patch:
        patch.setattr(task_service, "complete_task", complete)
        patch.setattr(database, "get_connection", opener)
        response, context = request_dashboard(
            app, f"/tasks/{task.id}/complete?{query}", method="POST"
        )

    assert response.status_code == 400
    assert context["errors"] == errors
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert 'href="/">Reset</a>' in response.get_data(as_text=True)
    complete.assert_not_called()
    opener.assert_not_called()
    assert saved_tasks(app) == before


@pytest.mark.parametrize("task_id", ["0", "-1", str(2**63)])
def test_complete_task_invalid_ids_return_404_before_backend(dashboard_app, monkeypatch, task_id):
    complete = Mock(wraps=task_service.complete_task)
    opener = Mock(side_effect=AssertionError("Invalid IDs must not open SQLite"))
    monkeypatch.setattr(task_service, "complete_task", complete)
    monkeypatch.setattr(database, "get_connection", opener)

    response = dashboard_app.test_client().post(f"/tasks/{task_id}/complete")

    assert response.status_code == 404
    complete.assert_not_called()
    opener.assert_not_called()
    dayplan.local_today.assert_not_called()


def test_complete_task_missing_task_returns_404(dashboard_app):
    response = dashboard_app.test_client().post(f"/tasks/{2**63 - 1}/complete")

    assert response.status_code == 404
    assert response.get_data(as_text=True).strip() == "Page not found."


def test_complete_task_failed_write_returns_generic_500_without_flash(populated_dashboard_app):
    app = populated_dashboard_app
    before = saved_tasks(app)
    task = next(task for task in before if task.status == "Pending")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.app_context():
        db = get_db()
        db.execute(
            """CREATE TRIGGER reject_completion AFTER UPDATE ON tasks
               BEGIN SELECT RAISE(FAIL, 'Private database detail'); END"""
        )
        db.commit()
    client = app.test_client()

    response = client.post(f"/tasks/{task.id}/complete")

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."
    assert saved_tasks(app) == before
    with client.session_transaction() as session:
        assert "_flashes" not in session


@pytest.mark.parametrize(
    ("title", "query", "location"),
    [
        ("High overdue", "?status=Pending&priority=High", "/?status=Pending&priority=High"),
        ("Completed today", "?status=All&priority=High", "/?priority=High"),
        ("Low due today", "?status=All&priority=All", "/"),
    ],
)
def test_delete_task_removes_only_target_and_preserves_filters(
    populated_dashboard_app, monkeypatch, title, query, location
):
    app = populated_dashboard_app
    before = saved_tasks(app)
    task = next(task for task in before if task.title == title)
    delete = Mock(wraps=task_service.delete_task)
    monkeypatch.setattr(task_service, "delete_task", delete)
    client = app.test_client()

    response = client.post(f"/tasks/{task.id}/delete{query}")

    assert response.status_code == 303
    assert response.headers["Location"] == location
    delete.assert_called_once()
    assert delete.call_args.args[1:] == (task.id,)
    assert saved_tasks(app) == [saved for saved in before if saved.id != task.id]
    with client.session_transaction() as session:
        assert session["_flashes"] == [("success", "Task deleted.")]
    dashboard = client.get(location)
    assert dashboard.status_code == 200
    html = dashboard.get_data(as_text=True)
    assert f'<h3 class="task-title">{title}</h3>' not in html
    assert html.count("Task deleted.") == 1


@pytest.mark.parametrize(
    ("query", "errors"),
    [
        ("status=Archived", {"status": "Choose a valid status filter."}),
        ("priority=", {"priority": "Choose a valid priority filter."}),
        ("status=Pending&status=Pending", {"status": "Submit this value only once."}),
        ("priority=Low&priority=High", {"priority": "Submit this value only once."}),
    ],
)
def test_delete_task_invalid_filters_return_400_without_calling_service(
    populated_dashboard_app, monkeypatch, query, errors
):
    app = populated_dashboard_app
    before = saved_tasks(app)
    task = before[0]
    delete = Mock(wraps=task_service.delete_task)
    opener = Mock(side_effect=AssertionError("Invalid filters must not open SQLite"))
    with monkeypatch.context() as patch:
        patch.setattr(task_service, "delete_task", delete)
        patch.setattr(database, "get_connection", opener)
        response, context = request_dashboard(
            app, f"/tasks/{task.id}/delete?{query}", method="POST"
        )

    assert response.status_code == 400
    assert context["errors"] == errors
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert 'href="/">Reset</a>' in response.get_data(as_text=True)
    delete.assert_not_called()
    opener.assert_not_called()
    assert saved_tasks(app) == before


@pytest.mark.parametrize("task_id", ["0", "-1", "abc", str(2**63)])
def test_delete_task_invalid_ids_return_404_before_backend(dashboard_app, monkeypatch, task_id):
    delete = Mock(wraps=task_service.delete_task)
    opener = Mock(side_effect=AssertionError("Invalid IDs must not open SQLite"))
    monkeypatch.setattr(task_service, "delete_task", delete)
    monkeypatch.setattr(database, "get_connection", opener)

    response = dashboard_app.test_client().post(f"/tasks/{task_id}/delete")

    assert response.status_code == 404
    delete.assert_not_called()
    opener.assert_not_called()


def test_delete_task_missing_task_returns_404(dashboard_app):
    client = dashboard_app.test_client()

    response = client.post(f"/tasks/{2**63 - 1}/delete")

    assert response.status_code == 404
    assert response.get_data(as_text=True).strip() == "Page not found."
    with client.session_transaction() as session:
        assert "_flashes" not in session


def test_delete_task_get_does_not_delete(populated_dashboard_app):
    app = populated_dashboard_app
    before = saved_tasks(app)

    response = app.test_client().get(f"/tasks/{before[0].id}/delete")

    assert response.status_code == 405
    assert saved_tasks(app) == before


def test_delete_task_failed_write_returns_generic_500_without_flash(populated_dashboard_app):
    app = populated_dashboard_app
    before = saved_tasks(app)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.app_context():
        db = get_db()
        db.execute(
            """CREATE TRIGGER reject_deletion AFTER DELETE ON tasks
               BEGIN SELECT RAISE(FAIL, 'Private database detail'); END"""
        )
        db.commit()
    client = app.test_client()

    response = client.post(f"/tasks/{before[0].id}/delete")

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."
    assert saved_tasks(app) == before
    with client.session_transaction() as session:
        assert "_flashes" not in session


def test_summaries_renders_exact_reports_using_one_service_call(populated_dashboard_app, monkeypatch):
    get_summaries = Mock(wraps=task_service.get_summaries)
    monkeypatch.setattr(task_service, "get_summaries", get_summaries)

    response, context = request_template(populated_dashboard_app, "/summaries", "summaries.html")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert context == {
        "daily": {
            "date": date(2026, 11, 26),
            "due_total": 3,
            "due_pending": 2,
            "due_completed": 1,
            "overdue": 2,
            "completed_today": 1,
        },
        "weekly": {
            "week_start": date(2026, 11, 23),
            "week_end": date(2026, 11, 29),
            "due_total": 6,
            "due_pending": 5,
            "due_completed": 1,
            "overdue": 2,
            "completion_rate": pytest.approx(100 / 6),
        },
        "filters": {"status": "All", "priority": "All"},
    }
    html = response.get_data(as_text=True)
    assert 'href="#daily">Daily</a>' in html and 'href="#weekly">Weekly</a>' in html
    assert 'href="/">Back to dashboard</a>' in html
    assert "<h2>Your progress</h2>" in html
    values_by_section = {
        "daily": [
            ("Total tasks due today", "3"),
            ("Overdue tasks", "2"),
            ("Tasks completed today", "1"),
            ("Pending tasks due today", "2"),
            ("Completed tasks due today", "1"),
        ],
        "weekly": [
            ("Total tasks due this week", "6"),
            ("Pending tasks due this week", "5"),
            ("Completed tasks due this week", "1"),
            ("Overdue tasks this week", "2"),
        ],
    }
    for section, expected in values_by_section.items():
        content = html.split(f'<section id="{section}"', 1)[1].split("</section>", 1)[0]
        actual = re.findall(
            r'<dt class="stat-label">([^<]+)</dt>\s*<dd><span class="stat-value">([^<]+)</span>',
            content,
        )
        assert actual == expected
    assert '<span class="stat-value">16.7%</span>' in html
    assert "1 of 6 tasks due this week completed" in html
    rate = context["weekly"]["completion_rate"]
    assert f'<meter class="completion-meter" min="0" max="100" value="{rate}"' in html
    assert 'aria-labelledby="completion-heading"></meter>' in html
    for day in ("2026-11-26", "2026-11-23", "2026-11-29"):
        assert f'<time datetime="{day}">' in html
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")
    get_summaries.assert_called_once()
    assert get_summaries.call_args.args[1:] == (date(2026, 11, 26),)
    assert get_summaries.call_args.kwargs == {}


def test_summaries_filters_change_navigation_but_not_reports(populated_dashboard_app):
    app = populated_dashboard_app
    _, unfiltered = request_template(app, "/summaries", "summaries.html")

    response, filtered = request_template(
        app, "/summaries?status=Completed&priority=Low", "summaries.html"
    )

    assert response.status_code == 200
    assert filtered == {**unfiltered, "filters": {"status": "Completed", "priority": "Low"}}
    assert 'href="/?status=Completed&amp;priority=Low">Back to dashboard</a>' in response.get_data(as_text=True)
    one_filter = app.test_client().get("/summaries?status=All&priority=Low")
    assert one_filter.status_code == 200
    assert 'href="/?priority=Low">Back to dashboard</a>' in one_filter.get_data(as_text=True)


@pytest.mark.parametrize(
    ("due_dates", "display"),
    [([], "No tasks due"), (["2026-11-30"], "No tasks due"), (["2026-11-26"], "0.0%")],
    ids=["empty-database", "empty-week", "no-completions"],
)
def test_summaries_distinguishes_empty_weeks_from_zero_completion(dashboard_app, due_dates, display):
    with dashboard_app.app_context():
        for due_date in due_dates:
            task_service.create_task(get_db(), {"title": "Pending task", "due_date": due_date})

    response, _ = request_template(dashboard_app, "/summaries", "summaries.html")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    expected_class = "stat-empty" if display == "No tasks due" else "stat-value"
    assert f'<span class="{expected_class}">{display}</span>' in html
    other_display = "0.0%" if display == "No tasks due" else "No tasks due"
    assert other_display not in html
    if display == "No tasks due":
        assert '<meter class="completion-meter"' not in html
    else:
        assert '<meter class="completion-meter" min="0" max="100" value="0.0"' in html
        assert "0 of 1 task due this week completed" in html


@pytest.mark.parametrize(
    ("query", "field", "message"),
    [
        ("status=Archived", "status", "Choose a valid status filter."),
        ("priority=high", "priority", "Choose a valid priority filter."),
        ("status=", "status", "Choose a valid status filter."),
        ("priority=", "priority", "Choose a valid priority filter."),
        ("status=Pending&status=Pending", "status", "Submit this value only once."),
        ("priority=Low&priority=High", "priority", "Submit this value only once."),
    ],
)
def test_summaries_rejects_invalid_filters_before_opening_database(
    dashboard_app, monkeypatch, query, field, message
):
    opener = Mock(side_effect=AssertionError("Invalid filters must not open SQLite"))
    get_summaries = Mock(wraps=task_service.get_summaries)
    monkeypatch.setattr(database, "get_connection", opener)
    monkeypatch.setattr(task_service, "get_summaries", get_summaries)

    response, context = request_dashboard(dashboard_app, f"/summaries?{query}")

    assert response.status_code == 400
    assert response.mimetype == "text/html"
    assert context["errors"] == {field: message}
    html = response.get_data(as_text=True)
    assert f'id="{field}-error">{message}' in html
    assert 'href="/">Reset</a>' in html
    opener.assert_not_called()
    get_summaries.assert_not_called()


def test_summaries_unexpected_service_failure_returns_generic_500(dashboard_app, monkeypatch):
    dashboard_app.config["PROPAGATE_EXCEPTIONS"] = False
    monkeypatch.setattr(
        task_service, "get_summaries", Mock(side_effect=RuntimeError("Private database detail"))
    )

    response = dashboard_app.test_client().get("/summaries")

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_serves_top_level_static_files(client):
    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert response.mimetype == "text/css"


def test_unknown_route_returns_404(client):
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.get_data(as_text=True).strip() == "Page not found."


def test_unhandled_exception_returns_generic_500(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/test-error")
    def raise_error():
        raise RuntimeError("Private exception detail")

    response = client.get("/test-error")

    assert response.status_code == 500
    assert response.get_data(as_text=True).strip() == "Internal server error."
