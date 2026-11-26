import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


class DevelopmentConfig:
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE_PATH = PROJECT_ROOT / "instance" / "dayplan.sqlite3"
    TIMEZONE = "Asia/Kolkata"


class TestingConfig(DevelopmentConfig):
    TESTING = True
    DATABASE_PATH = None
