from pathlib import Path

import click
from flask import (
    Flask, Response, current_app, flash, g, redirect, render_template, request, url_for,
)

from config import DevelopmentConfig, resolve_database_path, resolve_secret_key

from . import database, task_service
from .date_service import local_today
from .task_service import list_tasks
from .validators import ValidationError, validate_filters, validate_task_fields


TASK_FIELDS = ("title", "description", "due_date", "priority")


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


def _render_dashboard(filters, form_values, errors, *, filter_errors=None):
    today = local_today(current_app.config["TIMEZONE"])
    invalid_filters = errors if filter_errors is None else filter_errors
    if invalid_filters:
        tasks, due_today_tasks = [], []
    else:
        result = list_tasks(get_db(), filters, today)
        tasks, due_today_tasks = result.tasks, result.due_today_tasks

    context = dict(
        tasks=tasks,
        due_today_tasks=due_today_tasks,
        today=today,
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
    app.config["DATABASE_PATH"] = resolve_database_path(
        app.config.get("DATABASE_PATH"), app.instance_path
    )
    app.teardown_appcontext(close_db)

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
        fields, errors = _read_single_values(request.form, TASK_FIELDS)
        form_values = {name: fields.get(name, "") for name in TASK_FIELDS}
        for name in errors:
            form_values[name] = request.form.getlist(name)

        if filter_errors or errors:
            # Check the remaining fields for feedback without attempting a write.
            try:
                validate_task_fields(fields, editing=False)
            except ValidationError as error:
                errors = error.errors | errors
        else:
            db = get_db()
            try:
                task_service.create_task(db, fields)
            except ValidationError as error:
                errors = error.errors
            else:
                flash("Task added.", "success")
                active_filters = {name: value for name, value in filters.items() if value != "All"}
                return redirect(url_for("dashboard", **active_filters), code=303)

        return _render_dashboard(filters, form_values, errors, filter_errors=filter_errors), 400

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
