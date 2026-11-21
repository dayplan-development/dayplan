import pytest

from config import TestingConfig as AppTestingConfig
from dayplan import create_app


@pytest.fixture
def app():
    return create_app(AppTestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


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
