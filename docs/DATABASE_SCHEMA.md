# DayPlan database schema

Daily Task and Reminder Manager · Approved Phase 2 schema, implementation updated for Phase 3.2H

This schema follows the [project specification](PROJECT_SPECIFICATION.md) and [architecture](ARCHITECTURE.md). `dayplan/database.py` defines and initializes the SQLite schema and maps rows to records from `dayplan/models.py`. The example records are illustrative.

## 1. Database overview

Use one SQLite file with one application table, `tasks`. Each row holds one task and the information needed to display, filter, complete, and summarize it. A nullable field can be left blank without changing the rest of the row.

DayPlan uses a single task table. Due dates and derived overdue labels provide in-app reminders. Daily and weekly reports are calculated from the current rows. User, account, reminder, priority, and summary tables are outside the baseline schema.

## 2. Tasks table

| Column | SQLite type | Required and default | Meaning |
|---|---|---|---|
| `id` | `INTEGER` | Primary key. SQLite generates it. | Identifies one task when viewing, editing, completing, or deleting it. It stays the same throughout that task's lifetime. |
| `title` | `TEXT` | Required. No default. | Short name, trimmed to 1–100 characters. Separate tasks can have the same title. |
| `description` | `TEXT` | Optional. Defaults to `NULL`. | Extra details, with a maximum of 500 trimmed characters. Blank text is saved as `NULL`. |
| `due_date` | `TEXT` | Optional. Defaults to `NULL`. | The calendar deadline in `YYYY-MM-DD`. Valid past dates are accepted. |
| `priority` | `TEXT` | Required. Defaults to `Medium`. | Exactly `Low`, `Medium`, or `High`. The default applies when creating a task without a priority. |
| `status` | `TEXT` | Required. Defaults to `Pending`. | Exactly `Pending` or `Completed`. The application controls this value. |
| `completed_on` | `TEXT` | Conditionally required. Defaults to `NULL`. | The project-local calendar date on which the task was completed. Required for a Completed task and empty for a Pending task. Used for the “Completed today” count. |
| `created_at` | `TEXT` | Required. SQLite supplies a UTC default if the column is omitted. | When the row was first saved. The value stays the same during edits and completion. |
| `updated_at` | `TEXT` | Required. SQLite supplies a UTC default if the column is omitted. | When a saved field or status last changed. The database module sets it on a change. A read, identical edit, or repeated completion leaves it unchanged. |

`NULL` means no value has been recorded. A primary key uniquely identifies a row. `AUTOINCREMENT` prevents SQLite from automatically assigning a previously used, committed ID to a new task, so an old edit link cannot target a different task after deletion. SQLite manages the internal sequence record. [SQLite ID allocation](https://www.sqlite.org/autoinc.html)

### Date and time conventions

- **Calendar dates** (`due_date`, `completed_on`) use `YYYY-MM-DD` text, for example `2026-11-21`. They describe local calendar days without a time or offset. The date service supplies “today” in `Asia/Kolkata`, using `ZoneInfo` with the required `tzdata` dependency. A deadline is interpreted as the whole local day.
- **Timestamps** (`created_at`, `updated_at`) use UTC text with second precision in `YYYY-MM-DDTHH:MM:SSZ` form, for example `2026-11-21T06:30:00Z`. The two values start equal on insertion. Changes within the same second may have the same timestamp. Use the project-local date for reports and the UTC timestamps for recordkeeping. [SQLite date and time functions](https://www.sqlite.org/lang_datefunc.html)
- `insert_task()` calls `utc_now()` once and binds the same UTC value to both timestamp columns. The schema also keeps its `strftime` defaults for direct inserts that omit those columns.
- Convert stored calendar dates to Python dates at the persistence boundary. For writes, validate and serialize the Python dates before binding SQL parameters. The date service supplies the completion day explicitly so it uses the same local date as the rest of the request.

### Completion, overdue labels, and reports

Completing a Pending task sets `status` to `Completed` and sets `completed_on` in the same transaction. A later edit or repeated completion leaves the completion date unchanged. Reopening is outside the initial implementation.

Overdue is calculated when reading tasks. A task is overdue only if it is Pending, has a due date, and that date is before today's local date. A task due today is in a separate category. Only Pending tasks appear in the actionable due-today list. The daily due total includes both statuses. Completed and undated tasks are never overdue.

Analytics reads task records to produce the reports. Due dates drive the daily due counts and the weekly due-date group. Completion dates support the “Completed today” count. The weekly rate uses the current Monday–Sunday week and divides completed tasks due in it by all tasks due in it, then multiplies by 100. A week with no tasks due displays “No tasks due,” even when tasks exist outside it. Both reports use all retained rows, independently of dashboard filters. Changes and permanent deletions affect live summaries.

## 3. Implemented SQL schema

The following definition matches `dayplan/database.py`, with formatting adjusted for readability. SQLite defaults and constraints complement Python validation. [SQLite table definition and constraints](https://www.sqlite.org/lang_createtable.html)

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL
        CHECK (length(trim(title)) BETWEEN 1 AND 100),
    description TEXT DEFAULT NULL
        CHECK (description IS NULL OR length(description) BETWEEN 1 AND 500),
    due_date TEXT DEFAULT NULL
        CHECK (due_date IS NULL OR due_date GLOB
            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    priority TEXT NOT NULL DEFAULT 'Medium'
        CHECK (priority IN ('Low', 'Medium', 'High')),
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'Completed')),
    completed_on TEXT DEFAULT NULL
        CHECK (completed_on IS NULL OR completed_on GLOB
            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK (
        (status = 'Pending' AND completed_on IS NULL)
        OR (status = 'Completed' AND completed_on IS NOT NULL)
    )
);
```

### Indexes

The primary key provides lookup by ID. There are no secondary indexes. The service reads the small task list and summarizes it in Python. Revisit an index on `due_date` if the database later performs frequent date-range queries and measurements show a need.

### Example task records

These are illustrative rows for a report viewed on the local date `2026-11-21`.

| id | title | description | due_date | priority | status | completed_on | created_at | updated_at |
|---|---|---|---|---|---|---|---|---|
| 1 | Submit worksheet | Attach the final PDF | 2026-11-20 | High | Pending | `NULL` | 2026-11-18T10:00:00Z | 2026-11-18T10:00:00Z |
| 2 | Review notes | `NULL` | 2026-11-21 | Medium | Pending | `NULL` | 2026-11-21T04:00:00Z | 2026-11-21T04:00:00Z |
| 3 | Confirm meeting | Send agenda before calling | 2026-11-19 | Low | Completed | 2026-11-21 | 2026-11-17T08:00:00Z | 2026-11-21T05:30:00Z |
| 4 | Read exercise brief | `NULL` | `NULL` | Low | Pending | `NULL` | 2026-11-21T05:00:00Z | 2026-11-21T05:00:00Z |

Task 1 is overdue. Task 2 is due today. Task 3 counts as completed today and is excluded from overdue. Task 4 is undated and excluded from due-date counts.

## 4. Initialization and connection lifecycle

1. `flask --app app init-db` calls the database module with the resolved `DATABASE_PATH`. Set the development `SECRET_KEY` before running the command. The path defaults to the ignored `instance/dayplan.sqlite3`, and tests use isolated temporary files. The local demo is the baseline. An optional deployment uses a writable persistent path initialized at runtime.
2. The command prepares the local directory as needed and creates the baseline table. Running it again against the same baseline preserves records. Run it before the first task request. Normal task requests expect an initialized schema. `CREATE TABLE IF NOT EXISTS` only initializes a missing table. A future schema change needs an explicit upgrade plan.
3. `initialize_database()` closes its setup connection on success or failure. During app use, `get_db()` opens a connection on demand, stores it in Flask's context-local `g`, and reuses it until teardown closes it. `dayplan/database.py` owns SQL, transaction control, and row mapping. The task service coordinates operations and supplies validated values.

## 5. CRUD expectations

| Operation | Expected behavior |
|---|---|
| Create | Validate form values and insert one Pending task. SQLite assigns the ID. The application supplies the same initial UTC value for both timestamps and applies Medium when the create priority is omitted. Return the saved record after commit. |
| Read | Fetch by ID or list records in ascending ID order. Translate rows to task models. The service raises `TaskNotFound` for a missing task requested by ID. Task filtering and reports use the approved service and date rules. |
| Update | Change only the editable fields. Keep `id`, `created_at`, `status`, and `completed_on`. Compare normalized editable values with stored values within the operation. Identical values mean no write and no timestamp change. For an actual edit, set `updated_at` in the same SQL statement as the field changes. |
| Complete | Update only a matching Pending row, setting status, completion date, and `updated_at` together. Distinguish an already-completed task from an unknown ID. A repeat completion preserves the saved dates. |
| Delete | Delete the row for the requested ID after confirmation. Report a missing ID explicitly. Permanent deletion removes the task from live summaries. |

## 6. Validation, integrity, and error handling

- Python validation trims text, rejects empty titles, enforces the length limits, converts blank optional fields to `NULL`, and checks priority values. The completion route passes the project-local date through the service. The database writes the completion date with the status change and updates `updated_at` only when the stored task changes.
- The SQL date checks enforce the shape of a date string. Python validation checks that it represents a real date and that its canonical `YYYY-MM-DD` representation matches the accepted input. For example, `2026-02-30` has the right shape and fails calendar validation.
- Writes use bound SQL parameters and a short `BEGIN IMMEDIATE` transaction. The database commits before returning success and rolls back an open transaction if the operation or commit fails. Flask teardown closes the request connection.
- Return user-correctable validation errors to the route for field feedback. Report a missing row separately so Flask can return 404. For unexpected constraint, connection, or write failures, preserve stored data where the transaction permits, log useful technical context on the server, and let Flask return its generic 500 response. Keep SQL, file paths, and tracebacks out of the response.

## 7. Database and persistence acceptance tests

The acceptance cases below guide coverage in `tests/test_tasks.py` and `tests/test_routes.py`. Existing tests use temporary SQLite files and cover initialization, persistence, schema defaults and date constraints, mutations, rollback, and summaries.

| Test | Expected result |
|---|---|
| Fresh and repeated initialization | First setup creates the table. A second run preserves an inserted task. |
| Create using defaults and reconnect | An insert with a valid title generates an ID, uses Pending and Medium, leaves optional fields `NULL`, and sets both timestamps. The row survives closing and reopening the connection. |
| Required and allowed values | SQLite rejects a null or space-only title, an out-of-range title length, an unknown priority or status, and a duplicate explicit ID. |
| Dates and text at the write boundary | Valid leap dates round-trip. Wrong date formats and impossible dates fail validation and are never saved. A quoted title round-trips as ordinary text. |
| Edit an existing task | Editable values change on the same ID. The creation timestamp and completion state stay fixed. With a known earlier timestamp, verify that an actual edit refreshes `updated_at`. Repeat an identical normalized edit and verify no saved value changes. |
| Complete and repeat | The first completion sets both status and completion day. The second completion preserves `completed_on` and `updated_at`. The database rejects a Pending row with a completion date or a Completed row without one. |
| Delete and missing ID | The chosen task disappears and other tasks remain. Read, edit, complete, or delete using an unknown ID produces the agreed missing-record outcome. A later insert does not reuse the deleted task's ID under this key policy. |
| Rollback after a partial write | Force a failure after an initial write within the same transaction. Reopen the database and verify that neither the partial write nor an unintended change was saved. |
| Date and report integration | With a fixed local date, read the example records back. Confirm that the date service marks only task 1 overdue and the daily summary counts task 3 as completed today. Add a Completed task due today and verify its contribution to the due total and exclusion from the actionable list. Test weekly boundaries, the completion-rate formula, and a week with no due tasks and records outside it. |

## 8. Backend handoff

- Review the row mapping, generated ID policy, and transaction tests with the Team Lead. Use the `init-db` command and configure an isolated path in test fixtures.
- Start with only the primary key for lookup. Revisit indexes when measured queries justify them.
- If optional hosting is selected, verify persistence for the configured SQLite path.
