# Backend implementation report

## What was implemented

The Phase 2 backend contract is now wired through Flask:

- SQLite schema initialization, connection lifecycle, row mapping, parameterized CRUD, transactions, rollback, and UTC timestamps in `dayplan/database.py`.
- Typed task records and display views in `dayplan/models.py`.
- Server-side task and filter validation, including trimming, length limits, ISO calendar dates, priorities, and repeated-field rejection.
- Asia/Kolkata local-date resolution, overdue/due-today rules, and Monday-Sunday week boundaries.
- Daily and weekly analytics, including completed-today counts, weekly completion rates, and the zero-due “No tasks due” case.
- Task service operations for create, read, edit, complete, delete, filtering, and summaries.
- Flask routes for the dashboard, task actions, edit form, summaries, health, `init-db`, 400 validation responses, 404 missing-task responses, and generic 500 handling.
- Server-rendered templates that submit the documented field names, preserve validated filters, display server-calculated labels, and confirm deletion in the browser.
- Focused backend tests for CRUD state transitions, repeated completion, validation, and report calculations.

## Verification performed

Commands run in this workspace:

```text
python3 -m compileall -q dayplan app.py
python3 -m pytest -q
```

Result: **8 tests passed** after installing locally available compatible packages.

The repository pins `pytest==9.2.0`, which was not available from the configured package index on this machine; `pytest==8.4.2` was used only for local verification. The declared dependency should be checked in a Python 3.13 environment before release.

A separate Flask test-client smoke check successfully created a task, followed the 303 contract, reopened the saved row, and rendered summaries.

## Frontend integration contract

The frontend should use the existing server-rendered pages rather than inventing a separate JSON API:

1. Render `GET /` as the dashboard. Use `tasks` for filtered `TaskView` rows and `due_today_tasks` for the actionable due-today section.
2. Submit `POST /tasks` with `title`, `description`, `due_date`, and `priority`. Keep `status` and `priority` filters in the query string, not the form body.
3. Use `GET /tasks/<id>/edit` and `POST /tasks/<id>/edit` for editing. Preserve the `status` and `priority` query values in the form action and cancel link.
4. Use POST forms for `/tasks/<id>/complete` and `/tasks/<id>/delete`; the delete form should ask for confirmation before submitting.
5. Render `GET /summaries#daily` and `GET /summaries#weekly` from the `daily` and `weekly` context objects. A `None` weekly `completion_rate` means “No tasks due”.
6. Display `is_overdue` and `is_due_today` as text labels; color may supplement but must not be the only indication.
7. Display flashed messages once on the redirected dashboard. Validation errors are returned as HTTP 400 with submitted values preserved.

## Pending work

These items are intentionally not claimed as complete:

- **Visual frontend work:** responsive CSS, polished layout, accessible error styling, and a final keyboard/mobile review remain with the frontend owner. The templates provide usable labels and controls but are minimal.
- **Full route acceptance coverage:** add the contract's complete Flask integration matrix, including every filter-preserving redirect, invalid-filter rendering, repeated POST fields, edit-after-completion, missing IDs for every action, and rollback simulation.
- **CI:** `.github/workflows/` still needs a Python 3.13 workflow that installs the pinned dependencies and runs pytest on pushes and pull requests. The current `pytest==9.2.0` pin must first be confirmed or corrected to a published version.
- **Security hardening:** add CSRF protection if the app is hosted, review access requirements, and keep `SECRET_KEY` supplied by the environment. This local baseline does not provide authentication.
- **Deployment:** no Render or other hosted deployment is configured. SQLite persistence across restart/redeploy must be verified before calling a hosted demo ready.
- **Team evidence:** record PR links, independent reviews, CI results, screenshots/demo evidence, and prompt-review notes required by the assignment.
- **List-order decision:** the implementation currently orders tasks by ascending SQLite ID. Confirm this presentation choice with the team.

## Suggested handoff order

1. Run the app with Python 3.13 and fix/confirm the dependency pin.
2. Have the frontend owner style the existing templates without changing field names or endpoint names.
3. Add route acceptance tests around the stable service and template contract.
4. Add CI and verify the check on a pull request.
5. Perform the documented demo: add, invalid input, edit, complete, filter, delete, overdue/due-today, and both summaries.
