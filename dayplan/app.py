from datetime import date, datetime, timedelta, timezone
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from database import db_connection, init_db

ALLOWED_PRIORITIES = {"low", "medium", "high"}
ALLOWED_STATUSES = {"pending", "in_progress", "completed"}

app = Flask(__name__)
CORS(app)  # For development. Restrict origins before production use.
init_db()


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def valid_date(value):
    if value in (None, ""):
        return True
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def valid_datetime(value):
    if value in (None, ""):
        return True
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def task_to_dict(row):
    task = dict(row)
    today = date.today().isoformat()
    task["is_overdue"] = bool(
        task["due_date"]
        and task["due_date"] < today
        and task["status"] != "completed"
    )
    return task


def validate_task(payload, partial=False):
    errors = {}
    if not partial or "title" in payload:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            errors["title"] = "Title is required."
    if "priority" in payload and payload["priority"] not in ALLOWED_PRIORITIES:
        errors["priority"] = "Use low, medium, or high."
    if "status" in payload and payload["status"] not in ALLOWED_STATUSES:
        errors["status"] = "Use pending, in_progress, or completed."
    if "due_date" in payload and not valid_date(payload["due_date"]):
        errors["due_date"] = "Use YYYY-MM-DD."
    if "reminder_at" in payload and not valid_datetime(payload["reminder_at"]):
        errors["reminder_at"] = "Use ISO 8601, for example 2026-11-25T09:00:00+05:30."
    return errors


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/tasks")
def create_task():
    payload = request.get_json(silent=True) or {}
    errors = validate_task(payload)
    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 400

    now = utc_now()
    status = payload.get("status", "pending")
    completed_at = now if status == "completed" else None
    with db_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO tasks
            (title, description, due_date, priority, status, reminder_at,
             created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload["title"].strip(),
            str(payload.get("description", "")).strip(),
            payload.get("due_date") or None,
            payload.get("priority", "medium"),
            status,
            payload.get("reminder_at") or None,
            now, now, completed_at
        ))
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.get("/api/tasks")
def list_tasks():
    clauses, values = [], []
    status = request.args.get("status")
    priority = request.args.get("priority")
    overdue = request.args.get("overdue")
    search = request.args.get("search")
    due_from = request.args.get("due_from")
    due_to = request.args.get("due_to")

    if status:
        if status not in ALLOWED_STATUSES:
            return jsonify({"error": "Invalid status"}), 400
        clauses.append("status = ?")
        values.append(status)
    if priority:
        if priority not in ALLOWED_PRIORITIES:
            return jsonify({"error": "Invalid priority"}), 400
        clauses.append("priority = ?")
        values.append(priority)
    if overdue == "true":
        clauses.append("due_date < ? AND status != 'completed'")
        values.append(date.today().isoformat())
    if search:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        values.extend([f"%{search}%", f"%{search}%"])
    if due_from:
        if not valid_date(due_from):
            return jsonify({"error": "due_from must use YYYY-MM-DD"}), 400
        clauses.append("due_date >= ?")
        values.append(due_from)
    if due_to:
        if not valid_date(due_to):
            return jsonify({"error": "due_to must use YYYY-MM-DD"}), 400
        clauses.append("due_date <= ?")
        values.append(due_to)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    order_by = " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date IS NULL, due_date, created_at DESC"
    with db_connection() as connection:
        rows = connection.execute("SELECT * FROM tasks" + where + order_by, values).fetchall()
    return jsonify({"items": [task_to_dict(row) for row in rows], "count": len(rows)})


@app.get("/api/tasks/<int:task_id>")
def get_task(task_id):
    with db_connection() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/api/tasks/<int:task_id>", methods=["PUT", "PATCH"])
def update_task(task_id):
    payload = request.get_json(silent=True) or {}
    partial = request.method == "PATCH"
    errors = validate_task(payload, partial=partial)
    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 400

    editable = ["title", "description", "due_date", "priority", "status", "reminder_at"]
    with db_connection() as connection:
        existing = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not existing:
            return jsonify({"error": "Task not found"}), 404
        current = dict(existing)
        if not partial:
            required = {"title"}
            missing = [key for key in required if key not in payload]
            if missing:
                return jsonify({"error": "PUT requires title"}), 400

        merged = {key: payload.get(key, current[key]) for key in editable}
        if merged["title"] is not None:
            merged["title"] = merged["title"].strip()
        now = utc_now()
        completed_at = current["completed_at"]
        if merged["status"] == "completed" and current["status"] != "completed":
            completed_at = now
        elif merged["status"] != "completed":
            completed_at = None

        connection.execute("""
            UPDATE tasks SET title=?, description=?, due_date=?, priority=?,
                status=?, reminder_at=?, updated_at=?, completed_at=?
            WHERE id=?
        """, (
            merged["title"], merged["description"] or "", merged["due_date"] or None,
            merged["priority"], merged["status"], merged["reminder_at"] or None,
            now, completed_at, task_id
        ))
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(task_to_dict(row))


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    with db_connection() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cursor.rowcount == 0:
        return jsonify({"error": "Task not found"}), 404
    return "", 204


def summary_for(start, end):
    with db_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM tasks
            WHERE due_date BETWEEN ? AND ?
            ORDER BY due_date,
              CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
        """, (start.isoformat(), end.isoformat())).fetchall()
        counts = connection.execute("""
            SELECT status, COUNT(*) AS count FROM tasks GROUP BY status
        """).fetchall()
        overdue_count = connection.execute("""
            SELECT COUNT(*) AS count FROM tasks
            WHERE due_date < ? AND status != 'completed'
        """, (date.today().isoformat(),)).fetchone()["count"]
    status_counts = {"pending": 0, "in_progress": 0, "completed": 0}
    status_counts.update({row["status"]: row["count"] for row in counts})
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "due_tasks": [task_to_dict(row) for row in rows],
        "due_count": len(rows),
        "overall_by_status": status_counts,
        "overall_overdue_count": overdue_count
    }


@app.get("/api/summaries/daily")
def daily_summary():
    value = request.args.get("date", date.today().isoformat())
    if not valid_date(value):
        return jsonify({"error": "date must use YYYY-MM-DD"}), 400
    selected = date.fromisoformat(value)
    return jsonify(summary_for(selected, selected))


@app.get("/api/summaries/weekly")
def weekly_summary():
    start_value = request.args.get("start")
    start = date.fromisoformat(start_value) if start_value and valid_date(start_value) else date.today()
    if start_value and not valid_date(start_value):
        return jsonify({"error": "start must use YYYY-MM-DD"}), 400
    return jsonify(summary_for(start, start + timedelta(days=6)))


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.exception(error)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
