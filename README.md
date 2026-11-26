# DayPlan

Daily Task and Reminder Manager

Plan your day. Own your time.

DayPlan is a Flask app for managing a single task list stored in SQLite. You can create, edit, complete, and delete tasks, set optional due dates and priorities, filter by status or priority, and view daily and weekly summaries. DayPlan uses `Asia/Kolkata` for calendar dates and counts overdue tasks separately from tasks due today.

## Development setup on Windows

Use Git, Python 3.13, and PowerShell. Clone the repository, then create a virtual environment and install the pinned dependencies.

```powershell
git clone https://github.com/dayplan-development/dayplan.git
Set-Location dayplan
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `py -3.13` cannot find your installed interpreter, use `py -0p` to list registered interpreters and run the Python 3.13 executable directly with `-m venv .venv`. If `.venv` already uses another Python version, choose a new environment directory and use that path in the remaining commands.

In the same PowerShell session, generate a nonblank development `SECRET_KEY`. Flask uses it to sign session cookies. Keep the key private and out of Git. If you open a new terminal, set the variable again before running Flask.

```powershell
$env:SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

With `DATABASE_PATH` unset, DayPlan uses `instance/dayplan.sqlite3`. To use a separate local task list, optionally set this before initializing and starting the app.

```powershell
$env:DATABASE_PATH = Join-Path $PWD.Path 'instance\dayplan-dev.sqlite3'
```

Initialize SQLite, then start the Flask development server. The initialization command can be rerun on the current schema without removing existing tasks.

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Open the [dashboard](http://127.0.0.1:5000/) or the [daily and weekly summaries](http://127.0.0.1:5000/summaries). The [health endpoint](http://127.0.0.1:5000/health) reports whether Flask responds. Press `Ctrl+C` in the terminal to stop the server.

## Run tests

From the repository root, run pytest with the Python 3.13 virtual environment. Tests use isolated test databases.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Project structure

| Path | Purpose |
|---|---|
| `app.py`, `config.py` | Flask entry point and configuration. |
| `dayplan/` | App factory, routes, task services, validation, SQLite access, date handling, and summary calculations. |
| `templates/`, `static/` | Jinja templates and styles. |
| `tests/` | Backend and Flask route tests. |
| `docs/` | Project requirements, architecture, database schema, API contract, and team workflow. |
| `.github/workflows/` | GitHub Actions test workflow. |

## Deployment configuration

The commands above are for local development. For a hosted deployment, use a production WSGI server with debug mode off, configure a separate `SECRET_KEY` through the host's secret settings, set `DATABASE_PATH` to a writable persistent location, and run `init-db` against that path. The baseline demo is local. Render is optional.
