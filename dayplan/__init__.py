from pathlib import Path

import click
from flask import Flask, Response, current_app, g, render_template, request

from config import DevelopmentConfig, resolve_database_path, resolve_secret_key

from . import database
from .date_service import local_today
from .task_service import list_tasks
from .validators import ValidationError, validate_filters


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
        submitted_filters = {}
        errors = {}
        for field in ("status", "priority"):
            values = request.args.getlist(field)
            if len(values) > 1:
                errors[field] = "Submit this value only once."
            elif values:
                submitted_filters[field] = values[0]

        try:
            filters = validate_filters(submitted_filters)
        except ValidationError as error:
            errors.update(error.errors)

        today = local_today(current_app.config["TIMEZONE"])
        if errors:
            filters = {"status": "All", "priority": "All"}
            tasks = []
            due_today_tasks = []
            status = 400
        else:
            result = list_tasks(get_db(), filters, today)
            tasks = result.tasks
            due_today_tasks = result.due_today_tasks
            status = 200

        return render_template(
            "dashboard.html",
            tasks=tasks,
            due_today_tasks=due_today_tasks,
            today=today,
            filters=filters,
            form_values={"title": "", "description": "", "due_date": "", "priority": "Medium"},
            errors=errors,
        ), status

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
