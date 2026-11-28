# DayPlan

**Daily Task and Reminder Manager**  
*Plan your day. Own your time.*

DayPlan helps you keep track of tasks and deadlines in one place. Use the dashboard to see what needs attention today, spot overdue work, and review your progress. DayPlan stores one task list in a local SQLite database.

## Features

- Create, edit, complete, and permanently delete tasks. Deletion asks for confirmation.
- Set Low, Medium, or High priority and an optional due date. Type a date or choose one using the calendar.
- Filter the dashboard by status and priority. See pending tasks due today and distinguish them from overdue tasks.
- View daily totals and a Monday–Sunday weekly report with completion rates. DayPlan uses Asia/Kolkata for calendar dates.
- Correct invalid form entries without losing the other values you entered.

DayPlan is a single-list application. It has no accounts, shared lists, or scheduled notifications. Its reminders appear as due-date and overdue indicators in the dashboard. JavaScript enables the calendar and delete confirmation, and dates can still be typed without it.

## Technology stack

Python 3.13, Flask, Jinja, SQLite, HTML, CSS, and vanilla JavaScript. Tests use pytest. GitHub Actions runs the test suite on Ubuntu with Python 3.13. See the [Python tests workflow](.github/workflows/python-tests.yml).

## Local setup

You need Git, Python 3.13 with pip, and a browser. Use PowerShell on Windows or a POSIX shell on macOS/Linux. Run the commands from the repository root after cloning.

~~~sh
git clone https://github.com/dayplan-development/dayplan.git
cd dayplan
~~~

### 1. Create and activate a virtual environment

**Windows PowerShell**

~~~powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
~~~

If the launcher cannot find Python 3.13, run `py -0p` and use the full path of the listed Python 3.13 executable to create the environment:

~~~powershell
& 'C:\path\to\python.exe' -m venv .venv
~~~

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python` in the remaining commands.

**macOS or Linux**

~~~sh
python3.13 -m venv .venv
source .venv/bin/activate
~~~

### 2. Install dependencies

~~~sh
python -m pip install -r requirements.txt
~~~

### 3. Configure the environment

Set `SECRET_KEY` before running any Flask command. Flask uses it to sign session cookies. Generate a local key in the terminal you will use to run the app, and set it again in each new terminal session. Keep the key out of source control.

**Windows PowerShell**

~~~powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
~~~

**macOS or Linux**

~~~sh
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
~~~

`DATABASE_PATH` is optional. When it is unset, DayPlan uses `instance/dayplan.sqlite3`. To keep a separate local task list, set a different writable path before initializing and running the app:

- PowerShell: `$env:DATABASE_PATH = Join-Path $PWD.Path 'instance\dayplan-dev.sqlite3'`
- macOS or Linux: `export DATABASE_PATH="$PWD/instance/dayplan-dev.sqlite3"`

### 4. Initialize SQLite and start DayPlan

~~~sh
python -m flask --app app init-db
python -m flask --app app run --debug
~~~

Open the [dashboard](http://127.0.0.1:5000/) or [summaries](http://127.0.0.1:5000/summaries). The [health endpoint](http://127.0.0.1:5000/health) checks whether Flask responds. Press Ctrl+C to stop the server. Use the debug server only for local development. Running `init-db` again against the current schema preserves existing tasks.

## Automated tests

From the repository root, use the same virtual environment:

~~~sh
python -m pytest -q
~~~

The tests use isolated SQLite databases. They cover validation, database operations, routes, and template rendering.

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py`, `config.py` | Flask entry point, environment configuration, and project timezone. |
| `dayplan/` | Flask routes, task services, validation, date rules, reports, and SQLite access. |
| `templates/` | Shared layout, dashboard, edit form, and summary pages. |
| `static/css/` | Application styles. |
| `static/js/` | Calendar, flash messages, and delete confirmation. |
| `tests/` | Backend and Flask route tests. |
| `docs/` | Project specification, architecture, API contract, database schema, and team workflow. |
| `.github/workflows/` | GitHub Actions test workflow. |

## Screenshots

| View | Screenshot |
| --- | --- |
| Dashboard | Pending capture |
| Edit Task | Pending capture |
| Daily and Weekly Summaries | Pending capture |

## Deployment readiness

Local setup is the supported demo. Render hosting is optional and has not been verified. DayPlan has no authentication or CSRF tokens for task-changing forms. Restrict access and review form protection before exposing a writable instance to the public. A Flask session secret signs cookies and does not restrict access to tasks.

For a controlled Render trial, use a Python Web Service with its root set to the repository root. Render supports dashboard configuration, so a `render.yaml`, Dockerfile, and Procfile are optional. The Flask entry point is `app:app`. Templates and browser assets are bundled in `templates/` and `static/` and Flask serves them without a frontend build.

| Render setting | Value |
| --- | --- |
| Branch | `main` |
| Python version | Set `PYTHON_VERSION=3.13.18`. |
| Build command | `python -m pip install -r requirements.txt gunicorn==27.0.1` |
| Start command | `python -m flask --app app init-db && exec gunicorn --workers 1 --bind "0.0.0.0:$PORT" app:app` |
| Environment variables | Set a separate, stable, randomly generated `SECRET_KEY` using Render's secret settings. Set `FLASK_DEBUG=0` and `DATABASE_PATH=/var/data/dayplan.sqlite3`. |
| Storage | Mount a paid persistent disk at `/var/data` and use one service instance. |
| Health check path | `/health` checks Flask liveness. Open the dashboard separately to verify SQLite access. |

The production build adds Gunicorn on Render. The local requirements pin Flask, pytest, and tzdata. Run SQLite initialization at startup because Render mounts the persistent disk at runtime. Without the disk, tasks created on Render may be lost on restart or redeploy.

After configuring the service, check `/health`, open the dashboard and summaries, and verify that the styles and scripts load. Create a test task, restart and redeploy the service, and confirm the same task remains. Keep the local demo if controlled access or data persistence cannot be verified.

[Render Flask guide](https://render.com/docs/deploy-flask) · [Python version configuration](https://render.com/docs/python-version) · [Persistent disks](https://render.com/docs/disks) · [Health checks](https://render.com/docs/health-checks)
