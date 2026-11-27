from os import environ
from pathlib import Path


class DevelopmentConfig:
    TESTING = False
    TIMEZONE = "Asia/Kolkata"


class TestingConfig(DevelopmentConfig):
    TESTING = True


def resolve_secret_key(configured_key):
    secret_key = configured_key
    if secret_key is None:
        secret_key = environ.get("SECRET_KEY")

    if not isinstance(secret_key, (str, bytes)) or not secret_key.strip():
        raise RuntimeError(
            "Set a non-blank SECRET_KEY in the environment or application configuration."
        )

    return secret_key


def resolve_database_path(configured_path, instance_path):
    database_path = configured_path
    if database_path is None:
        database_path = environ.get("DATABASE_PATH")
    if database_path is None:
        database_path = Path(instance_path) / "dayplan.sqlite3"
    if isinstance(database_path, str) and not database_path.strip():
        raise RuntimeError("DATABASE_PATH must be a non-blank file path.")

    return str(Path(database_path))
