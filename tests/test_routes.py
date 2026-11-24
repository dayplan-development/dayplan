import pytest
from flask import Flask

from config import TestingConfig as AppTestingConfig
from dayplan import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dayplan-route-tests-only")
    return create_app(AppTestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


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


def test_dashboard_renders_placeholder(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<h1>DayPlan</h1>" in response.data


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
