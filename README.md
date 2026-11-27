# DayPlan

Daily Task and Reminder Manager

Plan your day. Own your time.

DayPlan is a Flask app for managing a single task list stored in SQLite. You can create, edit, complete, and delete tasks, set optional due dates and priorities, filter by status or priority, and view daily and weekly summaries. DayPlan uses `Asia/Kolkata` for calendar dates and counts overdue tasks separately from tasks due today.

## Development setup on Windows

Use Git, Python 3.13, and PowerShell.

### Choose one clone command

Run only the example that applies to you, then continue to the virtual environment setup.

**Pre-release.** Clone `feature/app-integration` while the release is awaiting independent approval or merge.

```powershell
git clone --branch feature/app-integration https://github.com/dayplan-development/dayplan.git
Set-Location dayplan
```

**After release.** Once [PR #3](https://github.com/dayplan-development/dayplan/pull/3) is independently approved and merged, new users should clone the default `main` branch.

```powershell
git clone https://github.com/dayplan-development/dayplan.git
Set-Location dayplan
```

From the repository root, create the virtual environment.

```powershell
py -3.13 -m venv .venv
```

On some Windows installations, `py -3.13` may fail even when Python 3.13 is installed. Run `py -0p` to list registered interpreters, then replace the example path below with the full path to your Python 3.13 executable.

```powershell
py -0p
& 'C:\path\to\python.exe' -m venv .venv
```

If `.venv` already uses another Python version, choose a new environment directory and use that path in the remaining commands. Install the pinned dependencies using the virtual environment's Python. Activation is optional.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

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

The [Python tests workflow](.github/workflows/python-tests.yml) uses Python 3.13 on Ubuntu and runs `python -m pytest -q` on pushes to `main` and `feature/**` and on pull requests targeting `main`.

## Project structure

| Path | Purpose |
|---|---|
| `app.py`, `config.py` | Flask entry point and configuration. |
| `dayplan/` | App factory, routes, task services, validation, SQLite access, date handling, and summary calculations. |
| `templates/` | Jinja templates for the dashboard, edit form, and summaries. |
| `static/css/` | Application styles. |
| `static/js/` | `notifications.js` handles flash notification dismissal. |
| `tests/` | Backend and Flask route tests. |
| `docs/` | Project requirements, architecture, database schema, API contract, and team workflow. |
| `.github/workflows/` | GitHub Actions test workflow. |

## Deployment configuration

The commands above are for local development. For a hosted deployment, use a production WSGI server with debug mode off, configure a separate `SECRET_KEY` through the host's secret settings, set `DATABASE_PATH` to a writable persistent location, and run `init-db` against that path. The baseline demo is local. Render is optional.
