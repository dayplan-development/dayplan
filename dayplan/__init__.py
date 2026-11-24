from pathlib import Path

from flask import Flask, Response, current_app, g, render_template

from config import DevelopmentConfig, resolve_database_path, resolve_secret_key

from . import database


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

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

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
