# DayPlan frontend and service contract

Daily Task and Reminder Manager · Approved Phase 2 contract, implementation updated for Phase 3.2H

This contract follows the [project specification](PROJECT_SPECIFICATION.md), [architecture](ARCHITECTURE.md), and [database schema](DATABASE_SCHEMA.md). The dashboard, task routes, daily and weekly summaries, health endpoint, static files, and generic error handlers are implemented. The examples illustrate the approved behavior.

## 1. Communication and ownership

DayPlan uses ordinary HTML forms and server-rendered Jinja pages. The browser sends URL query parameters with navigation and form-encoded fields with POST requests. Flask returns HTML or a redirect. The existing JSON health endpoint stays independent of task data.

| Owner | Responsibility |
|---|---|
| Team lead | Flask endpoint names, request parsing, route wiring, redirects, flash messages, template context, and HTTP error responses. |
| Backend developer | Plain Python service functions, validation, task and date rules, summary calculations, and SQLite access and transactions. |
| Frontend developer | Jinja templates, HTML forms with the agreed field names, links built from Flask endpoint names, CSS, and accessible display of feedback and server-provided values. |

The route extracts plain values, obtains the request's SQLite connection as needed, and resolves the configured local date once for any operation that needs it. The service receives those values directly and has no dependency on Flask request objects, sessions, or templates. SQL and transaction handling belong to `dayplan/database.py`.

## 2. Accepted parameters and validation

### Task form fields

| Field | Create | Edit | Server validation |
|---|---|---|---|
| `title` | Required | Required | Trim whitespace. Require 1–100 characters. Duplicate titles are allowed. |
| `description` | Optional | Optional | Trim whitespace and accept up to 500 characters. Blank or omitted means no description. |
| `due_date` | Optional | Optional | Accept a real calendar date in exact `YYYY-MM-DD` form. Blank or omitted means no due date. Past dates are valid. |
| `priority` | Optional | Required | Accept exactly `Low`, `Medium`, or `High`. Omission on create defaults to `Medium`. An explicitly blank priority is invalid. |
| `task_id` | None | Required in URL | Accept a positive integer within SQLite's signed 64-bit ID range. Malformed or out-of-range IDs return 404, as do IDs with no record. |

Edit is a full form submission. Leaving description or due date blank clears that value. The route passes only permitted editable fields to the service. ID, status, completion date, and timestamps are controlled by the application. Repeated values for a single named field are a malformed request and must be rejected with field feedback before any write. The server uses the approved limits and defaults on every submission.

### Dashboard filter parameters

Both filters are optional query parameters. Read them from the URL query alone. Read task fields from the POST body alone, so two values named `priority` can have independent meanings. Values are case-sensitive. Flask rejects repeated parameters during parsing and passes the remaining plain values to the validator before any task change or redirect.

| Parameter | Accepted values | Default and meaning |
|---|---|---|
| `status` | `All`, `Pending`, `Completed`, `Overdue` | Omitted means `All`. Pending includes overdue tasks. Overdue selects only Pending tasks with a due date before today. |
| `priority` | `All`, `Low`, `Medium`, `High` | Omitted means `All`. A selected priority matches that exact value. |

Both active filters must match when listing tasks on the dashboard. Summary calculations use all tasks, and the summaries page uses filters for return navigation. Invalid, blank, or repeated filter values produce an HTTP 400 HTML response with filter feedback and a link to the unfiltered dashboard. A write request with invalid filters performs no write. Create and edit preserve the submitted task fields and reset invalid filters to `All` for the form action. If only the task fields are invalid, active filters are preserved. Complete, delete, and summaries reuse the dashboard's filter error view. For edit, a missing task returns 404 even when the form or filters are invalid. Text search and reopening are outside the initial implementation.

## 3. Route contract

`task_id` in the table denotes the required path value described above. **Filters** means the optional `status` and `priority` query parameters. Apply the shared validation above and the error rules in Section 5. Use these endpoint names with Flask's URL builder.

| Method and URL | Purpose and endpoint | Parameters and validation | Service call | Success and redirect | Errors |
|---|---|---|---|---|---|
| `GET /` | Open dashboard. `dashboard` | Filters optional. | `list_tasks` | 200 dashboard HTML with task list and create form. No redirect. | 400 invalid filters, 500 unexpected failure. |
| `GET /?status=Pending` | Filter by status using `dashboard`. The URL illustrates one valid choice. | `status` supplies the filter. `priority` is optional. | `list_tasks` | 200 dashboard HTML with selection and matching tasks, including an empty state. No redirect. | 400 invalid filters, 500 unexpected failure. |
| `GET /?priority=High` | Filter by priority using `dashboard`. The URL illustrates one valid choice. | `priority` supplies the filter. `status` is optional. | `list_tasks` | 200 dashboard HTML with selection and matching tasks, including an empty state. No redirect. | 400 invalid filters, 500 unexpected failure. |
| `POST /tasks` | Create a task. `create_task` | Required title. Optional description, due date, priority, and filters. Apply create rules. | `create_task` | On commit, flash “Task added.” and return 303 to the dashboard with active filters. | 400 with the dashboard form and feedback for invalid fields or filters. 500 unexpected failure. |
| `GET /tasks/<int:task_id>/edit` | Open the edit form. `edit_task` | Required ID. Filters optional. | `get_task` | 200 edit form HTML prefilled with saved values. No redirect. | 400 invalid filters, 404 invalid or missing ID, 500 unexpected failure. |
| `POST /tasks/<int:task_id>/edit` | Save edits. `edit_task` | Required ID, title, and priority. Optional description, due date, and filters. Apply edit rules. | `update_task` | After a committed change, flash “Task updated.” For an identical edit, flash “No changes to save.” without updating the row. Return 303 to the dashboard with active filters. | 400 with the edit form and feedback for invalid fields or filters. 404 invalid or missing ID. 500 unexpected failure. |
| `POST /tasks/<int:task_id>/delete` | Delete a task. `delete_task` | Required ID. Filters optional. No task form fields. Ask the user to confirm before submission. Cancelling makes no request. | `delete_task` | On commit, flash “Task deleted.” and return 303 to the dashboard with active filters. | 400 invalid filters, 404 invalid or missing ID, 500 unexpected failure. |
| `POST /tasks/<int:task_id>/complete` | Mark a task completed. `complete_task` | Required ID. Filters optional. No task form fields or client-supplied completion date. | `complete_task` | Flash “Task completed.” after a committed change, or “Task is already completed.” on a repeat. Return 303 to the dashboard with active filters. | 400 invalid filters, 404 invalid or missing ID, 500 unexpected failure. |
| `GET /summaries#daily` | View the daily section of `summaries`. The browser requests `GET /summaries`. | Filters optional for the back link. No date parameter. | `get_summaries` | 200 HTML with both summaries. The browser jumps to `#daily`. No redirect. | 400 invalid filters, 500 unexpected failure. |
| `GET /summaries#weekly` | View the weekly section of `summaries`. The browser requests `GET /summaries`. | Filters optional for the back link. No week parameter. | `get_summaries` | 200 HTML with both summaries. The browser jumps to `#weekly`. No redirect. | 400 invalid filters, 500 unexpected failure. |
| `GET /health` | Liveness check. `health` | None. | None. | 200 JSON with `{"status": "ok"}`. | Independent of the task database. |

Filtering uses one dashboard endpoint. Daily and weekly reports use one summaries endpoint and a single read of the task list. A fragment such as `#weekly` selects a location on the rendered page and is never sent to Flask. The date service uses `Asia/Kolkata` through `ZoneInfo` and the required `tzdata` dependency. Reports use the current local date and the inclusive Monday–Sunday week.

For a new local database, set `SECRET_KEY` and run `flask --app app init-db` before opening task or summary pages. The command initializes the resolved `DATABASE_PATH`, which defaults to `instance/dayplan.sqlite3`, and preserves records on repeated runs of the same schema. See the [README](../README.md) for setup commands.

## 4. Backend service contract

### Task data passed between layers

| Attribute | Python type | Meaning |
|---|---|---|
| `id` | `int` | Stable task ID generated by SQLite. |
| `title` | `str` | Trimmed title. |
| `description` | `str or None` | Optional task details. |
| `due_date` | `date or None` | Optional local calendar deadline. |
| `priority` | `str` | Low, Medium, or High. |
| `status` | `str` | Pending or Completed. |
| `completed_on` | `date or None` | Project-local completion day, present only for Completed tasks. |
| `created_at`, `updated_at` | UTC-aware `datetime` | Recordkeeping timestamps. SQLite stores ISO text with second precision and a trailing `Z`. |

`Task` is the plain Python record returned from storage. The persistence module maps SQLite text to Python dates and timestamps. A `TaskView` wraps a `task` record with two server-calculated booleans, `is_overdue` and `is_due_today`. The second flag is for the dashboard's actionable Pending tasks. Neither flag is stored.

### Function names, inputs, and outputs

Functions below live in `dayplan/task_service.py` unless stated otherwise. `db` is the explicit request connection. `fields` is a plain mapping of submitted strings for the allowed form fields. An absent optional key stays absent so the validator can distinguish omission from an explicitly blank value. `today` is a Python date computed once for the request.

| Function | Inputs and responsibility | Result |
|---|---|---|
| `validate_filters(values)` | In `dayplan/validators.py`. Validate submitted query values and supply All defaults. | A pair of normalized values keyed by `status` and `priority`, or `ValidationError`. |
| `list_tasks(db, filters, today)` | Read tasks, apply the chosen filters, derive display flags, and collect the actionable due-today subset. | `DashboardTasks` with `tasks` and `due_today_tasks`, each a list of `TaskView` objects in ascending task ID order. |
| `get_task(db, task_id)` | Fetch one saved task for the edit form. | `Task` or `TaskNotFound`. |
| `create_task(db, fields)` | Validate create fields and coordinate a Pending insert. | Saved `Task` after commit or `ValidationError`. |
| `update_task(db, task_id, fields)` | Validate edits and update only editable fields. Preserve ID, creation timestamp, status, and completion date. Compare normalized editable values with the saved row before writing. | A result containing `task` and `changed` (true for a committed edit, false for an identical edit), or `TaskNotFound` or `ValidationError`. |
| `delete_task(db, task_id)` | Permanently remove the requested task. The frontend asks for confirmation before submitting. | `None` after commit or `TaskNotFound`. |
| `complete_task(db, task_id, today)` | Atomically mark a Pending task Completed and set its completion date. Leave an already completed task unchanged. | A result containing `task` and `changed` (true for a committed change, false for a repeat), or `TaskNotFound`. |
| `get_summaries(db, today)` | Read retained tasks once and pass them with the local date to analytics. | A pair of results keyed by `daily` and `weekly` with the shapes in Section 6. |

The validator owns task-field and filter rules. The date service owns the overdue comparison and week boundaries. Analytics owns the counts and completion rate. The task service coordinates these operations, and Flask translates results into HTTP responses.

## 5. Errors and flash messages

- **Validation.** A `ValidationError` carries an `errors` mapping of field or parameter name to one user-facing string. Flask can use the same format for a repeated form field detected during parsing. Example: `{"title": "Enter a title.", "due_date": "Enter a valid date in YYYY-MM-DD format."}`. Return 400 HTML with visible feedback and the submitted form values. An absent field is shown as blank when re-rendering. Do not write or redirect on validation failure.
- **Missing task.** The service raises `TaskNotFound` for a valid-looking ID with no task. Flask maps it to 404, as it does for an invalid task ID. A repeated completion of an existing task is a successful no-op.
- **Unexpected failure.** The database layer rolls back an open write transaction on failure. Allow the error to reach Flask for server-side logging and a generic 500 response. Keep SQL, file paths, credentials, and tracebacks out of the HTML. No success message is sent if a write fails.
- **Flash conventions.** Flask flashes short plain-text messages after a committed create, update, delete, or completion using `success`, and for an identical edit or already-completed result using `info`. The shared base template renders them once on the redirected page. Field errors appear next to their controls.
- **Session configuration.** The factory requires a nonblank `SECRET_KEY` before startup. It uses an explicit config value when supplied and otherwise reads the environment. Development and deployment supply distinct environment secrets. Tests use test-only values. Keep production secrets out of source control.

## 6. Jinja template context and navigation

### Dashboard and edit form

| Context key | Purpose |
|---|---|
| `tasks` | Filtered task rows as `TaskView` objects. |
| `due_today_tasks` | The server-selected Pending subset due today, using the same active filters. |
| `today` | The request's project-local date. |
| `filters` | Validated `status` and `priority` selections, including All defaults. |
| `form_values` | The initial dashboard uses empty fields with Medium priority. A rejected create or edit preserves raw submitted strings and uses a blank for absent fields. Repeated values are kept in the context as a list, and the form displays the first with the duplicate-field error. Edit GET uses the saved values with an ISO due date or a blank. |
| `errors` | Task-field feedback on create and edit. Dashboard filter errors also use this mapping when no `filter_errors` key is supplied. Empty for a normal render. |
| `filter_errors` | Separate URL filter feedback on rejected create requests and edit form renders. Keeps the URL and body `priority` errors distinct. |
| `task` | Saved `Task` on the edit page, used to identify the form target. |

The create form is part of `dashboard.html`. `task_form.html` uses `task`, `filters`, `form_values`, `errors`, and `filter_errors` and reuses the dashboard's field markup. Both forms use a text field for due dates so a malformed value can be shown after validation fails. If a rejected edit's task can no longer be loaded, Flask returns 404. The dashboard shows filter feedback and suppresses empty-list text for invalid queries.

Use the `is_overdue` flag to display a visible **Overdue** label, with color as a secondary cue. Display **Due today** for the actionable due-today flag. Keep the stored Pending or Completed status visible separately. Render user-entered text with normal Jinja escaping.

### Daily and weekly summaries

| Context key | Fields and meaning |
|---|---|
| `daily` | `date`, `due_total`, `due_pending`, `due_completed`, `overdue`, and `completed_today`. Use integer counts. Due-today counts include both statuses. Completed today is a distinct measure that may overlap. |
| `weekly` | `week_start`, `week_end`, `due_total`, `due_pending`, `due_completed`, `overdue`, and `completion_rate`. Bounds are inclusive, Monday through Sunday. Weekly overdue covers only Pending tasks due within that week that are already overdue. |
| `filters` | Validated dashboard selections used for the return link. Both reports use the full retained task list, independently of dashboard filters. |

`completion_rate` is a percentage from 0 to 100, computed as completed tasks due in the week divided by all tasks due in the week, multiplied by 100. Pass `None` and display “No tasks due” when the week contains zero due tasks, including when other tasks exist. Display `0.0%` for a nonempty due group with zero completions. Format percentages to one decimal place. Dates in the context are Python `date` values that Jinja may format for display.

### Preserving filters

Pass only the validated `status` and `priority` query values when building edit links, form action URLs, summary links, cancel links, and successful redirects. Omit `All` in generated URLs. A filter change preserves the other filter selection. Clearing both returns to `/`. Build links from known endpoint names and query values so the browser supplies no arbitrary return URL. A task that no longer matches the active filters may disappear from that view after a change. The flash message confirms the outcome.

## 7. Examples

Requests below show a method, URL, and form-encoded body when there is one. Summary examples show template data used to render HTML.

### Valid creation

```text
POST /tasks?priority=High

title=Submit+worksheet&description=Attach+the+final+PDF&due_date=2026-11-20&priority=High
```

The service returns a saved task with a generated ID, Pending status, and no completion date. Flask flashes “Task added.” and sends **303** with `Location: /?priority=High`. The browser then requests that page.

### Invalid creation

```text
POST /tasks

title=++&description=Attach+the+final+PDF&due_date=2026-02-30&priority=High
```

Flask returns **400** with the dashboard form and the submitted values. No task is saved. The illustrative error mapping is `{"title": "Enter a title.", "due_date": "Enter a valid date in YYYY-MM-DD format."}`.

### Successful completion

```text
POST /tasks/3/complete?status=Pending
```

For a Pending task and project-local date `2026-11-21`, the service saves Completed and `completed_on=2026-11-21` together. Flask flashes “Task completed.” and returns **303** with `Location: /?status=Pending`. Task 3 leaves that view because the Pending filter still applies.

### Task update

```text
POST /tasks/2/edit?priority=Medium

title=Review+lecture+notes&description=&due_date=2026-11-22&priority=Medium
```

Task 2 keeps its ID and status. Its description is cleared and its title and due date change. Flask flashes “Task updated.” and returns **303** with `Location: /?priority=Medium`.

### Daily summary context

Using the four illustrative records from the database schema and a local date of `2026-11-21`, **200** HTML includes these values for `daily`.

```text
date: 2026-11-21
due_total: 1
due_pending: 1
due_completed: 0
overdue: 1
completed_today: 1
```

### Weekly summary context

Using the same records and date, the same **200** HTML includes these values for `weekly`. The service rate is one out of three times 100, displayed as **33.3%**. The undated row is excluded.

```text
week_start: 2026-11-16
week_end: 2026-11-22
due_total: 3
due_pending: 2
due_completed: 1
overdue: 1
completion_rate: 33.33333333333333
```

## 8. Route acceptance tests and handoff

- Submit a whitespace-only title, invalid or blank priority, malformed date, and impossible date. Verify 400 with field feedback and preserved inputs. Verify that the row count or saved values stay the same.
- Submit a Low task priority from a URL filtered by High and Pending. Check that the stored priority is Low and the 303 retains both URL filters. Test the same filter retention after edit, completion, and deletion. A completed task may leave the Pending view.
- Edit a Completed task and verify its status and completion date survive. Resubmit identical normalized fields and verify that no row values change. A repeat completion also leaves the timestamps unchanged.
- Render Pending tasks due yesterday, today, and tomorrow, plus a Completed task with an old deadline. Verify the overdue and due-today labels. A Completed task due today counts in the daily due total and stays out of the actionable list.
- Verify both report contexts are unchanged by dashboard filters. Check an empty database, a week with tasks outside it only, and a nonempty week with zero completions. The former two display “No tasks due” and the last displays 0.0%.
- Check that a successful write flashes its outcome once after the redirect. Use an environment-supplied test secret and an initialized temporary database.

The current task order is ascending ID. The Delete form uses a native browser confirmation dialog. Local demo is the baseline. Review access and form protection if Render is selected.
