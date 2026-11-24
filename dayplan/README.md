# Daily Task and Reminder Manager Backend

A small REST API built with Python Flask and SQLite. It supports task CRUD, due dates, priorities, overdue flags, filters, and daily/weekly summaries.

## 1. Prerequisites

- Python 3.10 or later
- pip

## 2. Run locally

### Windows PowerShell

```powershell
cd task-reminder-backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### macOS/Linux

```bash
cd task-reminder-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

API base URL: `http://127.0.0.1:5000/api`

The `tasks.db` SQLite database is created automatically on first start.

## 3. Test the backend

```bash
python test_api.py
```

Expected result: `All API tests passed.`

## 4. API contract

### Health check

`GET /api/health`

### Create task

`POST /api/tasks`

```json
{
  "title": "Submit project",
  "description": "Send final version to the team",
  "due_date": "2026-11-30",
  "priority": "high",
  "status": "pending",
  "reminder_at": "2026-11-30T09:00:00+05:30"
}
```

Allowed priority values: `low`, `medium`, `high`.
Allowed status values: `pending`, `in_progress`, `completed`.
`due_date` uses `YYYY-MM-DD`. `reminder_at` uses ISO 8601.

### List/filter tasks

`GET /api/tasks`

Supported query parameters:

- `status=pending`
- `priority=high`
- `overdue=true`
- `search=project`
- `due_from=2026-11-24`
- `due_to=2026-11-30`

Example:

`GET /api/tasks?status=pending&priority=high&overdue=true`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "title": "Submit project",
      "description": "Send final version to the team",
      "due_date": "2026-11-23",
      "priority": "high",
      "status": "pending",
      "reminder_at": null,
      "created_at": "2026-11-24T18:00:00+00:00",
      "updated_at": "2026-11-24T18:00:00+00:00",
      "completed_at": null,
      "is_overdue": true
    }
  ],
  "count": 1
}
```

### Get one task

`GET /api/tasks/{id}`

### Update selected fields

`PATCH /api/tasks/{id}`

```json
{
  "status": "completed"
}
```

`PUT /api/tasks/{id}` is also supported and requires `title`.

### Delete task

`DELETE /api/tasks/{id}`

Returns HTTP `204 No Content`.

### Daily summary

`GET /api/summaries/daily?date=2026-11-24`

If `date` is omitted, the server's current date is used.

### Weekly summary

`GET /api/summaries/weekly?start=2026-11-24`

The result covers the supplied start date plus the next six days. If `start` is omitted, today is used.

## 5. Frontend JavaScript examples

Set the base URL once:

```javascript
const API_BASE = "http://127.0.0.1:5000/api";
```

Load tasks:

```javascript
async function loadTasks() {
  const response = await fetch(`${API_BASE}/tasks?status=pending`);
  if (!response.ok) throw new Error("Could not load tasks");
  const data = await response.json();
  return data.items;
}
```

Create a task:

```javascript
async function createTask(task) {
  const response = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not create task");
  return data;
}

createTask({
  title: "Prepare presentation",
  due_date: "2026-11-30",
  priority: "high"
});
```

Update a task:

```javascript
async function updateTask(id, changes) {
  const response = await fetch(`${API_BASE}/tasks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not update task");
  return data;
}
```

Delete a task:

```javascript
async function deleteTask(id) {
  const response = await fetch(`${API_BASE}/tasks/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error("Could not delete task");
}
```

Load daily summary:

```javascript
async function loadDailySummary(date) {
  const response = await fetch(`${API_BASE}/summaries/daily?date=${date}`);
  if (!response.ok) throw new Error("Could not load summary");
  return response.json();
}
```

## 6. Notes and limitations

- The API calculates and returns `is_overdue`; it does not store that flag because overdue status changes with time.
- `reminder_at` is stored for the frontend to display. This simple version does not send emails or operating-system notifications.
- CORS is open for local development. Before deployment, replace `CORS(app)` with an allowed origin, for example `CORS(app, origins=["https://your-frontend.example"])`.
- This version has no login/user table. It is suitable for a simple single-user/student project. Add authentication and a `user_id` foreign key for multi-user use.
