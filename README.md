# DayPlan

Daily Task and Reminder Manager

Plan your day. Own your time.

## Run locally

Use Python 3.13. From the repository root, create a fresh virtual environment and install the dependencies. If `.venv` already belongs to another Python version, use a new environment path.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app init-db
.venv/bin/python -m flask --app app run --debug
```

Open [the dashboard](http://127.0.0.1:5000/) or check [application health](http://127.0.0.1:5000/health). The dashboard supports task CRUD, filters, and links to daily and weekly summaries.

## Run tests

```bash
.venv/bin/python -m pytest -q
```

The backend implementation and remaining handoff work are documented in
[the backend implementation report](docs/BACKEND_IMPLEMENTATION_REPORT.md).
