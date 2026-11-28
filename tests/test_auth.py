from contextlib import closing
from datetime import date
import re
import sqlite3

import pytest
from flask import template_rendered
from werkzeug.security import check_password_hash, generate_password_hash

from config import TestingConfig as AppTestingConfig
import dayplan
from dayplan import create_app, database


@pytest.fixture
def auth_app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "auth-test-key")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setattr(dayplan, "local_today", lambda timezone: date(2026, 11, 28))
    app = create_app(AppTestingConfig)
    database.initialize_database(app.config["DATABASE_PATH"])
    return app


def token(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def sign_in(client, username):
    login_token = token(client.get("/login"))
    result = client.post("/login", data={
        "username": username, "password": "12345678", "csrf_token": login_token,
    })
    assert result.status_code == 303 and result.location == "/"
    dashboard = client.get(result.location)
    assert dashboard.data.count(f"Welcome back {username}!".encode()) == 1
    assert b"Logged in as" not in dashboard.data
    assert f'aria-label="Open profile menu for {username}"'.encode() in dashboard.data
    assert f'<p class="profile-username">{username}</p>'.encode() in dashboard.data
    assert b"Logged in to DayPlan" in dashboard.data
    assert b"Demo account" in dashboard.data
    assert b"/static/js/profile-menu.js" in dashboard.data
    return login_token, token(dashboard)


@pytest.mark.parametrize("username", database.DEMO_USERS)
def test_demo_login_rotates_csrf_and_logout_clears_session(auth_app, username):
    client = auth_app.test_client()
    before, after = sign_in(client, username)
    assert before != after
    with client.session_transaction() as session:
        assert session["username"] == username
        assert isinstance(session["user_id"], int)
        assert session.permanent
        assert "password" not in session

    assert client.get("/logout").status_code == 405
    assert client.post("/logout", data={"csrf_token": before}).status_code == 400
    assert client.get("/").status_code == 200
    logout = client.post("/logout", data={"csrf_token": after})
    assert logout.status_code == 303 and logout.location == "/login"
    with client.session_transaction() as session:
        assert not session
    assert client.get("/").location == "/login"


@pytest.mark.parametrize("username", ["charu", "unknown"])
def test_invalid_credentials_are_generic_and_preserve_only_username(auth_app, username):
    client = auth_app.test_client()
    response = client.post("/login", data={
        "username": username, "password": "incorrect-test-password",
        "csrf_token": token(client.get("/login")),
    })
    assert response.status_code == 401
    assert b"Incorrect username or password. Please try again." in response.data
    assert f'value="{username}"'.encode() in response.data
    assert b"incorrect-test-password" not in response.data
    assert client.get("/").location == "/login"


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/"), ("GET", "/summaries"), ("GET", "/tasks/1/edit"),
    ("POST", "/tasks"), ("POST", "/tasks/1/edit"),
    ("POST", "/tasks/1/complete"), ("POST", "/tasks/1/delete"), ("POST", "/logout"),
])
def test_anonymous_requests_are_redirected(auth_app, method, path):
    response = auth_app.test_client().open(path, method=method)
    assert response.status_code == 303 and response.location == "/login"
    assert response.cache_control.no_store


def test_csrf_rejects_login_and_every_task_mutation(auth_app):
    client = auth_app.test_client()
    assert client.post("/login", data={"username": "christiv", "password": "12345678"}).status_code == 400
    _, csrf = sign_in(client, "christiv")
    for path in ("/tasks", "/tasks/1/edit", "/tasks/1/complete", "/tasks/1/delete", "/logout"):
        assert client.post(path).status_code == 400
        assert client.post(path, data={"csrf_token": "wrong"}).status_code == 400
        assert client.post(path, data={"csrf_token": [csrf, csrf]}).status_code == 400


def test_filters_actions_and_reports_are_owner_scoped(auth_app):
    clients = {}
    for count, username in enumerate(database.DEMO_USERS, 1):
        client = auth_app.test_client()
        _, csrf = sign_in(client, username)
        clients[username] = (client, csrf)
        for number in range(count):
            assert client.post("/tasks", data={
                "csrf_token": csrf, "title": f"Private {username} {number}",
                "due_date": "2026-11-28", "priority": "High", "user_id": 9999,
            }).status_code == 303
    for count, (username, (client, csrf)) in enumerate(clients.items(), 1):
        dashboard = client.get("/?status=Pending&priority=High")
        assert dashboard.data.count(f'<h3 class="task-title">Private {username}'.encode()) >= count
        assert all(f"Private {other}".encode() not in dashboard.data for other in clients if other != username)
        reports = []

        def capture(sender, template, context, **extra):
            reports.append(context)

        with template_rendered.connected_to(capture, auth_app):
            assert client.get("/summaries?priority=Low").status_code == 200
        assert reports[0]["weekly"]["due_total"] == count
        assert reports[0]["daily"]["due_total"] == count
        if username != "christiv":
            assert client.get("/tasks/1/edit").status_code == 404
            for action in ("edit", "complete", "delete"):
                assert client.post(f"/tasks/1/{action}", data={
                    "csrf_token": csrf, "title": "Forbidden title", "priority": "High",
                }).status_code == 404
    assert b"Private christiv 0" in clients["christiv"][0].get("/tasks/1/edit").data


def test_https_cookie_flags(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "cookie-test-key")
    monkeypatch.setenv("DAYPLAN_SESSION_COOKIE_SECURE", "true")
    app = create_app(AppTestingConfig)
    response = app.test_client().get("/login", base_url="https://localhost")
    cookie = response.headers["Set-Cookie"]
    assert all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=Lax"))


def test_legacy_upgrade_preserves_tasks_ids_and_changed_password(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as db:
        db.execute(database.LEGACY_TASK_SCHEMA)
        db.execute("INSERT INTO tasks (id, title, status, completed_on) VALUES (7, 'Legacy', 'Completed', '2026-11-25')")
        db.execute("INSERT INTO tasks (id, title) VALUES (9, 'Deleted')")
        db.execute("DELETE FROM tasks WHERE id = 9")
        original = db.execute("SELECT * FROM tasks").fetchone()
        db.commit()

    database.initialize_database(path)
    with closing(database.get_connection(path)) as db:
        rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
        assert [row["username"] for row in rows] == list(database.DEMO_USERS)
        for row in rows:
            assert row["password_hash"] != "12345678"
            assert check_password_hash(row["password_hash"], "12345678")
        owner = rows[0]["id"]
        assert tuple(db.execute(f"SELECT {database.TASK_COLUMNS} FROM tasks").fetchone()) == original
        assert db.execute("SELECT user_id FROM tasks").fetchone()[0] == owner
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO tasks (title, user_id) VALUES ('Invalid owner', 9999)")
        changed_hash = generate_password_hash("replacement-test-password")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (changed_hash, owner))
        db.commit()

    database.initialize_database(path)
    with closing(database.get_connection(path)) as db:
        assert database.find_user(db, "christiv")["password_hash"] == changed_hash
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 3
        assert db.execute("INSERT INTO tasks (title, user_id) VALUES ('New', ?)", (owner,)).lastrowid == 10


def test_failed_upgrade_leaves_legacy_schema_and_records_intact(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as db:
        db.execute(database.LEGACY_TASK_SCHEMA)
        db.execute("INSERT INTO tasks (title) VALUES ('Keep on failure')")
        db.commit()

    monkeypatch.setattr(database, "SCHEMA", "INVALID SQL")
    with pytest.raises(sqlite3.OperationalError):
        database.initialize_database(path)

    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT title FROM tasks").fetchall() == [("Keep on failure",)]
        assert "user_id" not in {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
        assert db.execute("SELECT name FROM sqlite_master WHERE name IN ('users', 'legacy_tasks')").fetchall() == []
