from datetime import date
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


def get_dashboard(app, query_string=None):
    return request_dashboard(app, "/", query_string=query_string)


def request_dashboard(app, path, **kwargs):
    renders = []

    def record_render(sender, template, context, **extra):
        renders.append((template.name, context))

    with template_rendered.connected_to(record_render, app):
        response = app.test_client().open(path, **kwargs)

    [(template_name, context)] = renders
    assert template_name == "dashboard.html"
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


def test_dashboard_renders_placeholder_with_default_context(dashboard_app, monkeypatch):
    list_tasks = Mock(wraps=dayplan.list_tasks)
    monkeypatch.setattr(dayplan, "list_tasks", list_tasks)

    response, context = get_dashboard(dashboard_app)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<h1>DayPlan</h1>" in response.data
    assert context == {
        "tasks": [],
        "due_today_tasks": [],
        "today": date(2026, 11, 26),
        "filters": {"status": "All", "priority": "All"},
        "form_values": {"title": "", "description": "", "due_date": "", "priority": "Medium"},
        "errors": {},
    }
    dayplan.local_today.assert_called_once_with("Asia/Kolkata")
    list_tasks.assert_called_once()


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

    response, context = get_dashboard(dashboard_app, query_string)

    assert response.status_code == 400
    assert response.mimetype == "text/html"
    assert context["filters"] == {"status": "All", "priority": "All"}
    assert context["tasks"] == []
    assert context["due_today_tasks"] == []
    assert context["errors"] == errors
    opener.assert_not_called()
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
