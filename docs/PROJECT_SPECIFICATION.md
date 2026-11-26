# DayPlan project specification

**Daily Task and Reminder Manager**  
Plan your day. Own your time.

Shiv Nadar University Chennai · 25IT1833 – Open-Source Tools and Prompt Engineering · Exercises 9 and 10

**Status:** Approved Phase 2 requirements, with implementation status updated for Phase 3.2H. The assignment requirements come from the supplied brief.

## 1. Overview and objectives

DayPlan helps a user organize tasks, deadlines, and follow-up activities. The user should be able to record work, identify what needs attention today, spot missed deadlines, and review weekly progress.

The project also demonstrates reusable Python functions and modules, input validation, exception handling, automated tests, structured prompting with verification, and collaboration by three contributors using GitHub.

The current checkout implements the Flask dashboard and SQLite-backed task creation, viewing, editing, completion, and deletion with browser confirmation. Users can set due dates and priorities, combine status and priority filters, and distinguish overdue tasks from Pending tasks due today. The daily and weekly summaries use all saved tasks. Flask also provides a database initialization command, a health endpoint, and generic 404 and 500 responses.

Pytest covers backend logic, persistence, and Flask routes with real templates. The repository includes a GitHub Actions test workflow. Live GitHub checks, protection settings, and release evidence still require verification. The local demo is the baseline. Render remains optional, and hosted deployment is unverified.

## 2. Scope

| In scope | Out of scope for the baseline |
|---|---|
| A browser-based task list with add, view, edit, delete, and mark-complete operations | Accounts, authentication, multiple users, or shared task lists |
| Due dates, Low/Medium/High priorities, and automatic in-app overdue indicators | Browser notifications, email reminders, background scheduling, or recurring reminders |
| Status and priority filters, plus daily and weekly summaries | Cloud synchronization, external calendars, and integrations |
| Flask, Jinja, HTML/CSS, SQLite, pytest, GitHub collaboration and Actions, and a demo | Advanced analytics, a SPA, and native mobile apps |

The app has one task list. GitHub collaboration applies to the development team. Text search, reopening completed tasks, and historical report navigation are outside the initial implementation.

## 3. Task fields

| Field | Expected behavior |
|---|---|
| ID | Stable, unique, system-assigned identifier. An edit preserves the ID. |
| Title | Required plain text, 1–100 characters after trimming. Separate tasks may share a title. |
| Description | Optional plain text up to 500 characters after trimming. A blank description is treated as absent. |
| Due date | Calendar date with no time of day. The date is optional and valid past dates are accepted. Store and validate dates in ISO form (`YYYY-MM-DD`). |
| Priority | One of Low, Medium, or High. The create default is Medium. |
| Status | System-controlled. Starts as Pending and changes to Completed through the complete action. |
| Completion date | Set by the application to the project-local date when a Pending task is completed. Pending tasks have no completion date. An edit or repeated completion request preserves the original completion date. This supports the daily completed-today count. |

## 4. Lifecycle, priorities, and dates

### Task lifecycle

- **Pending** means the task is unfinished. A task can remain pending whether its due date is past, today, in the future, or absent.
- **Completed** means the user marked the task done. A completed task stays completed when its title, description, date, or priority is edited.
- **Overdue** is a derived label for a Pending task whose due date is strictly earlier than today. Compute it when displaying or summarizing tasks so it updates as the date changes.
- **Due today** means the due date equals today. The dashboard's actionable “Due today” view includes Pending tasks only. The daily summary includes both Pending and Completed tasks with that due date.
- Both Pending and Completed tasks may be deleted. Ask for confirmation before permanently removing the task. Reopening is outside the initial implementation.

### Priority

| Priority | Meaning |
|---|---|
| Low | Can wait behind more important work. |
| Medium | Normal importance. |
| High | Should receive attention first when the user decides what to work on. |

Priority is independent of due date and status. It does not change how overdue is calculated.

### Date rules

- Calculate “today” using one configured project timezone for the dashboard and both summaries. Use `Asia/Kolkata` with Python's `ZoneInfo` and the required `tzdata` dependency.
- A Pending task with a past due date is overdue. A Pending task due today remains due today until the next local calendar day. Future tasks and undated tasks are never overdue. Completed tasks are never flagged overdue, even if finished after their deadline.
- Use the same local date for every date calculation within a request. Tests must supply a known date so their results stay stable across midnight and across machines.

## 5. Daily and weekly summaries

Both reports use all saved tasks. Dashboard filters affect the task list and its actionable due-today view. They do not change the reports.

### Daily summary

| Measure | Definition for local date D |
|---|---|
| Due today | All retained tasks with due date D. Show the total and its Pending and Completed counts. |
| Overdue | All retained Pending tasks with due dates before D. This count is separate from “Due today.” |
| Completed today | All retained tasks whose recorded completion date is D, regardless of due date. This activity count can overlap with “Due today.” |

Example for 21 November. A Pending task due on 20 November contributes to overdue. A Pending task due on 21 November contributes to due today. A task completed on 21 November with a due date of 20 November contributes to completed today. Show zero for each empty measure.

### Weekly summary

- Use the current local calendar week, **Monday through Sunday inclusive**. Find the Monday of the week containing today's local date. Sunday is six days later. Show both dates in the UI. This is a calendar week, including when it crosses a month or year boundary.
- Count all retained tasks with a due date in that week. Group them as Pending or Completed using their current status. Count overdue tasks in that week as a subset of Pending.
- **Completion rate = (Completed tasks due in the week ÷ all tasks due in the week) × 100.** A task counts as completed for the rate if it is currently Completed and due in the week, even if it was finished before Monday. A task completed in the week with a due date outside the week does not enter this calculation.
- For zero tasks due, show **“No tasks due”** in place of a percentage. Otherwise, display one decimal place. For example, two completed tasks out of three due gives **66.7%**.
- Undated tasks are excluded from due-date counts. Summaries reflect the current saved tasks. Edits and deletions may change the totals. Historical snapshots and previous-week navigation are outside the initial implementation.

## 6. Functional requirements and acceptance criteria

| ID | Feature and expected behavior | Acceptance criteria |
|---|---|---|
| FR-01 | Add a task using validated fields. | A valid submission creates one Pending task with a generated ID. It appears in the task list and survives an app restart. Invalid input creates no task. |
| FR-02 | View saved tasks with title, due date if present, priority, and status. Show details where available. | The list shows accurate saved values, including an empty state when there are no tasks. An overdue label is visible without relying on color alone. |
| FR-03 | Edit a task's title, description, due date, and priority. | Valid edits persist on the same ID. Invalid edits preserve saved values. Editing a Completed task preserves its status and completion date. An identical edit leaves all values, including `updated_at`, unchanged. |
| FR-04 | Mark a Pending task Completed. | The resulting task is shown as Completed and is excluded from overdue counts. Repeating the action creates no duplicate and leaves the completion date unchanged. |
| FR-05 | Permanently delete a task after confirmation. | Cancelling confirmation leaves the task unchanged. Confirming removes the correct task from the list and from live summaries. An unknown ID is handled cleanly. |
| FR-06 | Distinguish past, today, future, and absent due dates. | With a fixed local date, only a Pending task with a past due date is overdue. A Pending task due today appears in the actionable due-today view. A completed task with a past due date is never shown as overdue. |
| FR-07 | Filter by status and priority. Choices are All, Pending, Completed, or Overdue for status and All, Low, Medium, or High for priority. | Pending includes overdue tasks. Overdue shows only overdue tasks. With both filters selected, a task must match both. Clearing filters restores the full list. A redirect after a task action preserves both active filters, even when the task leaves the filtered view. No matches show an empty result message. |
| FR-08 | Show the daily summary defined in Section 5. | Count a Completed task due today in the due total while keeping it out of the actionable list. Count overdue and completed-today tasks separately. An empty list produces zeroes. |
| FR-09 | Show the weekly summary defined in Section 5. | Monday and Sunday due dates are included, adjacent dates are excluded, and a week that crosses a year boundary is calculated correctly. Two out of three displays 66.7%. A week with no due tasks shows “No tasks due,” including when all tasks fall outside the week. A week with due tasks and no completions shows 0.0%. Both reports stay the same when dashboard filters change. |
| FR-10 | Validate all create and edit submissions on the server. | Invalid fields receive clear feedback, submitted values can be corrected, and no invalid record or partial edit is saved. |
| FR-11 | Handle missing records and unexpected failures. | Missing IDs produce a user-friendly 404. A simulated unexpected save failure leaves stored data consistent, logs the cause, and returns a generic error. |

## 7. Input validation and exception handling

### Input validation

- Trim title and description. Reject a missing, whitespace-only, or overlong title and an overlong description. Apply the same limits on create and edit.
- Check the priority server-side against Low, Medium, and High. Reject values outside the allowed set. Use Medium for an omitted create priority. On edit, require a valid submitted priority.
- Parse the complete date value and reject impossible dates such as `2026-02-30` and malformed values. Treat a blank date as absent.
- Use application-controlled IDs, statuses, and completion dates. Accept a state change through a dedicated action. Reject unknown filter values with clear feedback. Parse navigation filters from the URL and task values from the form body.
- Preserve user-entered form values on validation failures. Browser validation may give immediate feedback. The server enforces the rules for every submission.

### Exception handling

- Handle expected input errors separately from missing records and unexpected failures. Unknown task IDs return 404. Use HTTP 400 with HTML feedback for invalid submissions or filter values.
- For an unexpected storage error, roll back an incomplete write and preserve saved data. Log useful technical details server-side and show a generic 500 error to the user. Keep SQL details, tracebacks, and private configuration out of the response.
- Use parameterized SQLite queries and escape user-entered text when rendering HTML. Use POST for actions that change data. Use the `SECRET_KEY` environment variable in development, testing, and deployment before enabling task routes with flash messages. Keep real secrets out of source control. Review access and form protection if hosting is selected.

## 8. Non-functional and architecture requirements

- Use Python 3.13, Flask, SQLite, and server-rendered Jinja templates with HTML and CSS. JavaScript can enhance interactions where needed.
- Preserve the Flask app factory. Keep HTTP handling in Flask, reusable task and validation logic in Python modules, and SQL in the persistence layer. Use one place for date and reporting calculations so routes and summaries share the same rules.
- Organize work by role. The team lead owns Flask integration, settings, routes, route tests, CI, and documentation. Frontend owns Jinja, HTML, CSS, JavaScript, and presentation. Backend owns SQLite, task services, validation, date rules, and core-logic tests. Agree on the function inputs, returned fields, and errors before integrating.
- Make forms and filters usable by keyboard. Give inputs visible labels and provide readable feedback at desktop and mobile widths. Use text for priority and status alongside any color.
- Store settings and runtime data separately from source code. Keep credentials and the working database out of Git. Use isolated test settings and data so tests leave a developer's task list untouched.

## 9. Testing and collaboration requirements

- Use pytest for task operations, reusable validation, date and summary calculations, and data processing. Cover ordinary cases, blank and invalid inputs, exact length boundaries, impossible dates, leap dates, daily rollover, week boundaries, empty data, and zero-denominator calculations. Test due yesterday, today, and tomorrow, the transition at local midnight, and old deadlines on Completed tasks. Test completed tasks due today in the daily total, an empty week with records outside it, and an identical edit that preserves `updated_at`.
- Test database operations against isolated temporary data. Include persistence across reconnection, missing IDs, and failed writes. Test HTTP routes with Flask's test client, including valid and invalid forms, a URL priority distinct from the task form priority, filter preservation after task actions, unfiltered summaries, and 404 and 500 handling.
- Run GitHub Actions on **pushes and pull requests**. Install pinned dependencies, including `tzdata`, and run the suite on Python 3.13. Establish CI and verify the named pytest check runs on a PR before making it required on protected `main`. Require reviewed pull requests and successful checks before merging feature work. Each of the three contributors uses a feature branch, focused commits, and peer-reviewed PRs. Record review and test evidence before merging.
- Keep evidence of structured prompt engineering for the exercises. Record the task, context, constraints, and expected output of representative prompts. For generated output, record who reviewed it, what was accepted or corrected, and the tests or manual checks used to verify it.

## 10. Deployment and documentation requirements

- Use a local demo for the baseline. Render is optional. If hosting is selected, use a production server with debug mode off, configure safe access, and verify SQLite persistence across restarts and redeploys.
- Update the README with the purpose, features, Python version, setup and database initialization, run and test commands, screenshots or a demo, deployment details if applicable, limitations, and each team member's contributions. Include links to prompt-engineering evidence, screenshots or demo, reviewed PRs and reviews, and CI results.
- For handoff, verify the documented steps from a clean environment. The demo should show adding and editing a task, invalid-input feedback, overdue versus due today, completion, filtering, deletion, and both summaries. For a hosted deployment, also check the health endpoint and the documented persistence behavior.

## 11. Remaining coordination

- The team can confirm the default list order and the presentation of deletion confirmation during implementation. The required behavior is unchanged.
- Choose where to store assessment evidence and verify the GitHub merge settings before feature PRs merge.
- If the team chooses optional hosting, agree on access, form protection, persistent storage, and demo data before deployment.
