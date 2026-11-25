from pathlib import Path
import tempfile

from flask import Flask, Response, flash, g, redirect, render_template, request, url_for

from config import DevelopmentConfig
from . import database, task_service
from .date_service import local_today
from .validators import TaskNotFound, ValidationError, validate_filters


def create_app(config_class=DevelopmentConfig):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    if app.config.get("DATABASE_PATH") is None:
        handle, path = tempfile.mkstemp(prefix="dayplan-test-", suffix=".sqlite3")
        import os
        os.close(handle)
        app.config["DATABASE_PATH"] = path
    database.init_db(app.config["DATABASE_PATH"])

    def db():
        if "db" not in g:
            g.db = database.connect(app.config["DATABASE_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.cli.command("init-db")
    def init_db_command():
        database.init_db(app.config["DATABASE_PATH"])
        print("Initialized the database.")

    def filters_from_request():
        return validate_filters({
            "status": request.args.getlist("status"),
            "priority": request.args.getlist("priority"),
        })

    def query_values(filters):
        return {key: value for key, value in filters.items() if value != "All"}

    def require_secret():
        if not app.config.get("SECRET_KEY"):
            return Response("Server is not configured for task writes.\n", status=500, mimetype="text/plain")
        return None

    @app.get("/")
    def dashboard():
        try:
            filters = filters_from_request()
            today = local_today(app.config["TIMEZONE"])
            result = task_service.list_tasks(db(), filters, today)
            return render_template("dashboard.html", tasks=result.tasks, due_today_tasks=result.due_today_tasks,
                                   today=today, filters=filters, form_values={"title": "", "description": "", "due_date": "", "priority": "Medium"},
                                   errors={}, query_filters=query_values(filters))
        except ValidationError as error:
            return render_template("dashboard.html", tasks=[], due_today_tasks=[], today=local_today(app.config["TIMEZONE"]),
                                   filters={"status": "All", "priority": "All"}, form_values={"title": "", "description": "", "due_date": "", "priority": "Medium"},
                                   errors=error.errors, query_filters={}), 400

    @app.post("/tasks")
    def create_task():
        secret_error = require_secret()
        if secret_error:
            return secret_error
        submitted = {key: request.form.getlist(key) for key in ("title", "description", "due_date", "priority")}
        try:
            filters = filters_from_request()
            task_service.create_task(db(), submitted)
        except ValidationError as error:
            try:
                filters = filters_from_request()
            except ValidationError:
                filters = {"status": "All", "priority": "All"}
            result = task_service.list_tasks(db(), filters, local_today(app.config["TIMEZONE"]))
            values = {key: (value[0] if len(value) == 1 else "") for key, value in submitted.items()}
            return render_template("dashboard.html", tasks=result.tasks, due_today_tasks=result.due_today_tasks,
                                   today=local_today(app.config["TIMEZONE"]), filters=filters, form_values=values,
                                   errors=error.errors, query_filters=query_values(filters)), 400
        flash("Task added.", "success")
        return redirect(url_for("dashboard", **query_values(filters)), code=303)

    @app.get("/tasks/<int:task_id>/edit")
    def edit_task(task_id):
        filters = filters_from_request()
        task = task_service.get_task(db(), task_id)
        values = {"title": task.title, "description": task.description or "", "due_date": task.due_date.isoformat() if task.due_date else "", "priority": task.priority}
        return render_template("edit_task.html", task=task, filters=filters, form_values=values, errors={}, query_filters=query_values(filters))

    @app.post("/tasks/<int:task_id>/edit")
    def update_task(task_id):
        secret_error = require_secret()
        if secret_error:
            return secret_error
        submitted = {key: request.form.getlist(key) for key in ("title", "description", "due_date", "priority")}
        filters = filters_from_request()
        try:
            result = task_service.update_task(db(), task_id, submitted)
        except ValidationError as error:
            task = task_service.get_task(db(), task_id)
            values = {key: (value[0] if len(value) == 1 else "") for key, value in submitted.items()}
            return render_template("edit_task.html", task=task, filters=filters, form_values=values, errors=error.errors, query_filters=query_values(filters)), 400
        if result.changed:
            flash("Task updated.", "success")
        else:
            flash("No changes to save.", "info")
        return redirect(url_for("dashboard", **query_values(filters)), code=303)

    @app.post("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        secret_error = require_secret()
        if secret_error:
            return secret_error
        filters = filters_from_request()
        result = task_service.complete_task(db(), task_id, local_today(app.config["TIMEZONE"]))
        flash("Task completed." if result.changed else "Task is already completed.", "success" if result.changed else "info")
        return redirect(url_for("dashboard", **query_values(filters)), code=303)

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        secret_error = require_secret()
        if secret_error:
            return secret_error
        filters = filters_from_request()
        task_service.delete_task(db(), task_id)
        flash("Task deleted.", "success")
        return redirect(url_for("dashboard", **query_values(filters)), code=303)

    @app.get("/summaries")
    def summaries():
        filters = filters_from_request()
        result = task_service.get_summaries(db(), local_today(app.config["TIMEZONE"]))
        return render_template("summaries.html", daily=result["daily"], weekly=result["weekly"], filters=filters, query_filters=query_values(filters))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(404)
    def page_not_found(_error):
        return Response("Page not found.\n", status=404, mimetype="text/plain")

    @app.errorhandler(500)
    def internal_server_error(_error):
        return Response("Internal server error.\n", status=500, mimetype="text/plain")

    @app.errorhandler(TaskNotFound)
    def task_not_found(_error):
        return Response("Page not found.\n", status=404, mimetype="text/plain")

    @app.errorhandler(ValidationError)
    def invalid_request(error):
        details = "; ".join(f"{key}: {message}" for key, message in error.errors.items())
        return Response(f"Invalid request. {details}\n", status=400, mimetype="text/plain")

    return app
