from pathlib import Path
from secrets import compare_digest, token_urlsafe

import click
from flask import (
    Flask, Response, abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from config import DevelopmentConfig, resolve_database_path, resolve_secret_key, resolve_secure_cookie

from . import database, task_service
from .date_service import local_today
from .task_service import list_tasks
from .validators import TaskNotFound, ValidationError, validate_filters, validate_task_fields


TASK_FIELDS = ("title", "description", "due_date", "priority")
MAX_TASK_ID = 2**63 - 1
LOGIN_ERROR = "Incorrect username or password. Please try again."
DUMMY_PASSWORD_HASH = generate_password_hash(token_urlsafe())


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return session["csrf_token"]


def _read_single_values(source, names):
    fields = {}
    errors = {}
    for name in names:
        values = source.getlist(name)
        if len(values) > 1:
            errors[name] = "Submit this value only once."
        elif values:
            fields[name] = values[0]
    return fields, errors


def _read_dashboard_filters():
    submitted, errors = _read_single_values(request.args, ("status", "priority"))
    try:
        filters = validate_filters(submitted)
    except ValidationError as error:
        errors.update(error.errors)
    if errors:
        filters = {"status": "All", "priority": "All"}
    return filters, errors


def _read_task_form(*, editing, filter_errors):
    fields, errors = _read_single_values(request.form, TASK_FIELDS)
    form_values = {name: fields.get(name, "") for name in TASK_FIELDS}
    for name in errors:
        form_values[name] = request.form.getlist(name)

    if filter_errors or errors:
        # Check the remaining fields for feedback without attempting a write.
        try:
            validate_task_fields(fields, editing=editing)
        except ValidationError as error:
            errors = error.errors | errors
    return fields, form_values, errors


def _redirect_to_dashboard(filters):
    active_filters = {name: value for name, value in filters.items() if value != "All"}
    return redirect(url_for("dashboard", **active_filters), code=303)


def _render_dashboard(filters, form_values, errors, *, filter_errors=None):
    today = local_today(current_app.config["TIMEZONE"])
    invalid_filters = errors if filter_errors is None else filter_errors
    daily = None
    if invalid_filters:
        tasks, due_today_tasks = [], []
    else:
        db = get_db()
        result = list_tasks(db, filters, today, user_id=session["user_id"])
        tasks, due_today_tasks = result.tasks, result.due_today_tasks
        daily = task_service.get_summaries(db, today, user_id=session["user_id"])["daily"]

    context = dict(
        tasks=tasks,
        due_today_tasks=due_today_tasks,
        today=today,
        daily=daily,
        filters=filters,
        form_values=form_values,
        errors=errors,
    )
    if filter_errors is not None:
        context["filter_errors"] = filter_errors
    return render_template("dashboard.html", **context)


def get_db():
    if "db" not in g:
        g.db = database.get_connection(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        database.close_connection(connection)


def create_app(config_class=DevelopmentConfig):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    app.secret_key = resolve_secret_key(app.secret_key)
    app.config["SESSION_COOKIE_SECURE"] = resolve_secure_cookie(app.config["SESSION_COOKIE_SECURE"])
    app.config["DATABASE_PATH"] = resolve_database_path(
        app.config.get("DATABASE_PATH"), app.instance_path
    )
    app.teardown_appcontext(close_db)
    app.add_template_global(csrf_token)

    @app.before_request
    def protect_routes():
        if request.endpoint is None or request.endpoint in {"static", "health"}:
            return
        if request.endpoint != "login" and "user_id" not in session:
            return redirect(url_for("login"), code=303)
        if request.method == "POST":
            expected = session.get("csrf_token")
            tokens = request.form.getlist("csrf_token")
            if not expected or len(tokens) != 1 or not compare_digest(
                expected.encode("utf-8"), tokens[0].encode("utf-8")
            ):
                return Response("Invalid or expired security token. Reload the page and try again.\n",
                                status=400, mimetype="text/plain")

    @app.after_request
    def prevent_private_caching(response):
        if request.endpoint not in {"static", "health"}:
            response.cache_control.no_store = True
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"), code=303)
        if request.method == "GET":
            return render_template("login.html", username="", error=None)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.find_user(get_db(), username) if len(username) <= 128 else None
        stored_hash = user["password_hash"] if user is not None else DUMMY_PASSWORD_HASH
        if len(password) > 1024 or not check_password_hash(stored_hash, password) or user is None:
            return render_template("login.html", username=username, error=LOGIN_ERROR), 401

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash(f"Welcome back {user['username']}!", "success")
        return redirect(url_for("dashboard"), code=303)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"), code=303)

    @app.cli.command("init-db")
    def init_db():
        """Initialize the configured DayPlan database."""
        initializer = getattr(database, "initialize_database", None)
        if initializer is None:
            raise click.ClickException("Database initialization is unavailable.")

        database_path = current_app.config["DATABASE_PATH"]
        try:
            initializer(database_path)
        except Exception as error:
            raise click.ClickException("Database initialization failed.") from error

        click.echo("Database initialized successfully.")

    @app.get("/")
    def dashboard():
        filters, errors = _read_dashboard_filters()
        form_values = {"title": "", "description": "", "due_date": "", "priority": "Medium"}
        return _render_dashboard(filters, form_values, errors), 400 if errors else 200

    @app.post("/tasks")
    def create_task():
        filters, filter_errors = _read_dashboard_filters()
        fields, form_values, errors = _read_task_form(editing=False, filter_errors=filter_errors)
        if not filter_errors and not errors:
            db = get_db()
            try:
                task = task_service.create_task(db, fields, user_id=session["user_id"])
            except ValidationError as error:
                errors = error.errors
            else:
                flash("Task Added", f"success:create:{task.id}")
                return _redirect_to_dashboard(filters)

        return _render_dashboard(filters, form_values, errors, filter_errors=filter_errors), 400

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    def edit_task(task_id):
        if not 1 <= task_id <= MAX_TASK_ID:
            abort(404)

        filters, filter_errors = _read_dashboard_filters()
        db = get_db()
        form_values = None
        errors = {}
        if request.method == "POST":
            fields, form_values, errors = _read_task_form(editing=True, filter_errors=filter_errors)
            if not filter_errors and not errors:
                try:
                    result = task_service.update_task(db, task_id, fields, user_id=session["user_id"])
                except TaskNotFound:
                    abort(404)
                except ValidationError as error:
                    errors = error.errors
                else:
                    if result.changed:
                        flash("Task Updated", f"success:edit:{task_id}")
                    else:
                        flash("No changes to save.", "info")
                    return _redirect_to_dashboard(filters)

        try:
            task = task_service.get_task(db, task_id, user_id=session["user_id"])
        except TaskNotFound:
            abort(404)

        if form_values is None:
            form_values = {
                "title": task.title,
                "description": task.description or "",
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else "",
            }
        status = 400 if errors or filter_errors else 200
        return render_template(
            "task_form.html",
            task=task,
            filters=filters,
            form_values=form_values,
            errors=errors,
            filter_errors=filter_errors,
        ), status

    @app.post("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        if not 1 <= task_id <= MAX_TASK_ID:
            abort(404)

        filters, filter_errors = _read_dashboard_filters()
        if filter_errors:
            form_values = {"title": "", "description": "", "due_date": "", "priority": "Medium"}
            return _render_dashboard(filters, form_values, filter_errors), 400

        today = local_today(current_app.config["TIMEZONE"])
        db = get_db()
        try:
            result = task_service.complete_task(db, task_id, today, user_id=session["user_id"])
        except TaskNotFound:
            abort(404)

        if result.changed:
            flash("Task Completed", f"success:complete:{task_id}")
        else:
            flash("Task is already completed.", "info")
        return _redirect_to_dashboard(filters)

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        if not 1 <= task_id <= MAX_TASK_ID:
            abort(404)

        filters, filter_errors = _read_dashboard_filters()
        if filter_errors:
            form_values = {"title": "", "description": "", "due_date": "", "priority": "Medium"}
            return _render_dashboard(filters, form_values, filter_errors), 400

        db = get_db()
        try:
            task_service.delete_task(db, task_id, user_id=session["user_id"])
        except TaskNotFound:
            abort(404)

        flash("Task Deleted", "success")
        return _redirect_to_dashboard(filters)

    @app.get("/summaries")
    def summaries():
        filters, filter_errors = _read_dashboard_filters()
        if filter_errors:
            form_values = {"title": "", "description": "", "due_date": "", "priority": "Medium"}
            return _render_dashboard(filters, form_values, filter_errors), 400

        today = local_today(current_app.config["TIMEZONE"])
        reports = task_service.get_summaries(get_db(), today, user_id=session["user_id"])
        return render_template(
            "summaries.html", daily=reports["daily"], weekly=reports["weekly"], filters=filters
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(404)
    def page_not_found(_error):
        return Response("Page not found.\n", status=404, mimetype="text/plain")

    @app.errorhandler(500)
    def internal_server_error(_error):
        return Response("Internal server error.\n", status=500, mimetype="text/plain")

    return app
