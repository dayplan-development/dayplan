# DayPlan

Daily Task and Reminder Manager

Plan your day. Own your time.

## Run locally

Use Python 3.13. From the repository root in PowerShell, create a fresh virtual environment and install the dependencies. If `.venv` already belongs to another Python version, use a new environment path in these commands.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Open [the dashboard](http://127.0.0.1:5000/) or check [application health](http://127.0.0.1:5000/health). The dashboard is a placeholder, and the health endpoint checks that Flask can respond.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
