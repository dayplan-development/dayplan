# DayPlan team workflow

Daily Task and Reminder Manager · Phase 2 · Exercises 9 and 10

This workflow is for exactly three contributors. It follows the [project specification](PROJECT_SPECIFICATION.md), [architecture](ARCHITECTURE.md), [database schema](DATABASE_SCHEMA.md), and [frontend and service contract](API_CONTRACT.md). Responsibilities, existing branch names, and the Phase 2 product baseline are agreed. The workflow below defines the handoffs and checks to establish.

The local repository metadata shows `main` and `feature/app-integration` as local branches and records all four agreed branches under `origin`. The current checkout contains only `.gitkeep` in `.github/workflows/`. Live branch protection and Actions settings were not verified.

## 1. Responsibilities and file ownership

| Member and branch | Responsibilities | Primary files |
|---|---|---|
| **Member 1 · Team Lead** · `feature/app-integration` | Flask startup and configuration, HTTP routes and error handling, frontend/backend integration, integration tests, CI and deployment coordination, documentation, and PR reviews | `app.py`, `config.py`, `dayplan/__init__.py`, any agreed Flask route modules, `tests/test_routes.py`, `.github/workflows/`, `README.md`, `docs/`, and deployment configuration if approved |
| **Member 2 · Backend** · `feature/backend` | SQLite schema and access, task models and CRUD, validation and business rules, date and overdue rules, daily and weekly calculations, and backend unit and database tests | `dayplan/database.py`, `dayplan/models.py`, `dayplan/task_service.py`, `dayplan/validators.py`, `dayplan/date_service.py`, `dayplan/analytics.py`, `tests/test_tasks.py`, and any focused backend test modules |
| **Member 3 · Frontend** · `feature/frontend` | Jinja and HTML templates, responsive CSS, dashboard, task forms, filter controls, summary presentation, and browser JavaScript where needed | `templates/` and `static/` |

The Team Lead coordinates all GitHub Actions and deployment work. The Frontend developer may edit frontend-related workflow files only with the Team Lead's prior agreement. The Team Lead reviews those changes and verifies that the required checks still run.

### Shared files and boundaries

| Shared area | How to coordinate |
|---|---|
| `docs/PROJECT_SPECIFICATION.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE_SCHEMA.md`, and `docs/API_CONTRACT.md` | The Team Lead coordinates updates. The relevant owners approve changes to behavior, schema, or interfaces before dependent code is changed. |
| `requirements.txt` and `.gitignore` | The Team Lead coordinates changes. The member proposing an addition explains why it is needed and checks how it affects setup and CI. |
| `tests/conftest.py` | The Team Lead coordinates common app and HTTP fixtures with Backend. Backend provides the database initialization and test data needs. |
| `config.py` and database initialization | The Team Lead owns configuration and Flask CLI registration. Backend owns schema creation, connection and transaction behavior. Use `DATABASE_PATH` and agree on the temporary database fixture. The Team Lead registers `flask --app app init-db` and the teardown hook. Backend supplies the repeatable initializer and connection helpers. |
| Routes, services, and templates | Use the API contract for URLs, HTML field names, redirects, errors, and context keys. The Team Lead keeps URL filters separate from task form fields and maps HTTP input to services. Backend owns validation, database writes, and authoritative date and summary values. Frontend displays the supplied results and may add immediate form feedback. |
| Page behavior tested by `tests/test_routes.py` | Frontend flags template changes that affect test expectations. The Team Lead coordinates changes to the route tests so they check stable visible behavior. |

When a change touches another member's files, agree who will edit each file before starting. Prefer an owner-led change with an explicit handoff. If both sides must land together for tests to pass, use one coordinated PR with each affected owner reviewing the relevant files.

## 2. Dependencies and implementation order

1. **Use the approved baseline.** All three members review the specification and contract before starting. Use the agreed task fields, date rules, service signatures, routes, forms, context, and error format. Confirm implementation details such as list order and the confirmation UI during the handoff.
2. **Set up the review and CI baseline.** The Team Lead opens a reviewed Actions setup PR for Python 3.13 and pytest, verifies the named check runs on a PR, and then makes it required on protected `main`. Verify live review and merge settings before merging feature work.
3. **Develop backend and frontend in parallel.** Backend implements schema initialization, the task record, CRUD, validation, and date rules with pytest. The Team Lead verifies the pinned `tzdata` installation and supplies `SECRET_KEY` through the environment for development and isolated test runs. Frontend builds templates and forms from the agreed context and can use example values locally to check their presentation. Those examples stay out of production routes.
4. **Integrate one complete task flow.** Once the Backend PR exposes the agreed persistence and service functions and the Frontend PR exposes a usable form, the Team Lead wires creation and dashboard listing. Confirm a valid task persists, a rejected task shows its field errors, and the page appears correctly after redirect. Merge compatible groundwork before the integration PR. If neither side can pass checks alone, coordinate one integration PR.
5. **Complete the remaining task and report flows.** Add editing, completion, deletion, and filters, then connect due-date handling and both summaries. Backend supplies tested rules and counts. Frontend supplies the views. The Team Lead integrates and tests them with Flask's test client.
6. **Verify the release.** Review the resulting behavior together, finish documentation and demo evidence, and run the release checks in Section 7.

## 3. Branch usage and commits

| Existing branch | Use |
|---|---|
| `main` | Integration and release branch. Verify protection before feature merges. Changes enter through reviewed PRs. |
| `feature/app-integration` | Team Lead's integration, documentation, and CI work. |
| `feature/backend` | Backend implementation and tests. |
| `feature/frontend` | Frontend implementation and presentation work. |

Keep these exact branch names and retain the branches after merges. Work on the branch assigned to your role. Coordinate with its owner before committing to another member's branch. Keep one active merge-bound PR per feature branch so unrelated changes do not get mixed into a review. Use a Draft PR for early feedback if a handoff still depends on another change.

Keep each commit focused and use an action verb in a short subject. A lightweight convention is `type(scope): action`. For example, `feat(tasks): validate due dates`, `test(routes): cover invalid task forms`, or `docs(setup): explain database initialization`. Check the staged files before committing and keep local databases, virtual environments, and credentials out of commits.

## 4. Pull requests and review

1. Update the assigned branch from `main`, run the relevant local tests, and push the branch. Open a PR with base `main` and the assigned feature branch as the head.
2. Use a short title and describe the behavior, changed areas, dependencies, and how to verify it. Include actual test results and screenshots for UI changes. Link related PRs and record any AI-generated work used, the verification performed, and any corrections.
3. Request reviewers using the table below. Review the changed files, behavior, tests, and any contract changes. Authors respond to and resolve review feedback before requesting another review.
4. The Team Lead merges through GitHub after the required independent approval, applicable owner reviews, resolved feedback, and successful checks. For these long-lived feature branches, use a merge commit where repository settings permit so the original commits are retained. Keep the head branch after merging.

| PR author | Reviewer assignment |
|---|---|
| Team Lead | Backend reviews persistence, business rules, and service boundaries. Frontend reviews route-to-template wiring and UI behavior. Request both for shared contracts, full integration, or release handoff. For CI or documentation changes, assign the teammate affected by the change. |
| Backend | Team Lead reviews behavior, tests, and integration. Frontend also reviews visible fields, filters, or summary values when those change. |
| Frontend | Team Lead reviews integration, routes, and form behavior. Backend also reviews changes to data fields, error feedback, and the meaning of task or report values. |

The PR author cannot satisfy the independent review requirement. Each member contributes commits, opens PRs, and completes reviews of a teammate's work. Keep PR links, approval records, and CI results for the assignment.

## 5. Updating branches and resolving conflicts

Update after relevant changes land on `main` and before marking a PR ready to merge. Save your current work and start from a clean working tree. The following is an example for the owner of the existing Backend feature branch. Each member uses their own branch.

```text
git fetch origin
git switch feature/backend
git merge origin/main
python -m pytest
git push origin feature/backend
```

Fetch refreshes your local view of GitHub, switch selects your branch, and merge brings the current `main` changes into that branch. For initial setup, track the existing matching branch on `origin` locally. If the remote feature branch has additional commits, reconcile them with the branch owner before pushing. Merge updates preserve published history. Coordinate before touching another member's branch, and avoid force-pushing the shared feature branches.

If a merge stops with conflicts, pause before pushing. The feature branch owner leads the resolution on that branch. Ask the file owner to agree on the intended result, especially for configuration, fixtures, workflow, or interface files. Resolve the overlapping changes, remove conflict markers, and inspect the resolved diff. Stage the resolved files and finish the merge on the feature branch. Rerun pytest and any affected manual checks, then push and request re-review if the resolution changes behavior. Keep `main` protected throughout.

## 6. GitHub Actions and protected main

- The Team Lead coordinates one baseline workflow under `.github/workflows/` that runs on pushes and pull requests. The job uses Python 3.13, installs `requirements.txt` including `tzdata`, and runs `python -m pytest` against isolated test data with a test-only `SECRET_KEY` supplied through the environment. Give it a stable check name, such as `pytest`. [GitHub's Python workflow guide](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- Establish CI and verify the named check runs on a PR before making that check required on protected `main`. Configure required PRs, at least one independent approval, successful required checks, and an up-to-date branch before merging. Require resolution of review conversations and apply the no-bypass policy to the team, including the Team Lead. If the settings are unavailable, raise that with the repository administrator before reporting assignment compliance. [GitHub branch protection settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- Ban direct pushes, branch deletion, and force pushes on `main`. Keep automatic deletion of merged head branches disabled for this repository so the assigned branches survive. [GitHub branch deletion settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches)
- Before merging, check the latest PR revision. A failed, pending, or missing required check needs investigation. After any fix or merge from `main`, wait for the new check result and get fresh review where needed. Use explicit manual UI checks for work such as keyboard navigation or responsive layout.

## 7. Integration and final release

The Team Lead sequences PRs so `main` stays runnable. Before the final merge, have Backend verify data integrity and date and report results, and Frontend verify form feedback, keyboard use, responsive layout, and the demo pages. The Team Lead checks setup from a clean environment and verifies add, edit, completion, deletion, filtering, overdue versus due today, and both summaries on the integration PR. Include the README update in a reviewed PR before declaring the release ready. Cover setup, database initialization, run and test commands, screenshots or demo, limitations, and team contributions.

After the final merge, verify the `main` Actions run. The Team Lead collects links to each member's PRs and reviews, CI and test results, screenshots or demo, limitations, and contributions. Each member supplies representative prompts, generated-output review notes, corrections, and verification evidence for the submission.

The Team Lead coordinates the baseline local demo from the reviewed `main` revision. Render is optional. If chosen, the Team Lead configures the deployment `SECRET_KEY` via the environment and verifies health, access, that debug mode is off, and SQLite persistence before calling the hosted demo ready. Use the local demo if hosted persistence or appropriate access cannot be verified. Record the release revision and demo location.

## 8. Onboarding checklist

- [ ] Confirm the three members have repository access and know their assigned branch.
- [ ] Find the four existing branches on GitHub and track the assigned branch locally.
- [ ] Read the planning documents and use the approved product baseline and integration contract.
- [ ] Set up Python 3.13, a local `.venv/`, and the pinned dependencies from the README.
- [ ] Run Flask and pytest locally. Use a temporary database for tests once database support is available.
- [ ] Confirm file ownership, an isolated database fixture and test-only environment secret, handoff order, and reviewer assignments.
- [ ] Verify the actual GitHub Actions run, required status check, PR protection, and branch retention settings.
- [ ] Agree where to record PRs, reviews, screenshots, demo instructions, and prompt verification evidence.

## 9. Coordination during implementation

| Potential overlap or dependency | Agreement needed |
|---|---|
| Database startup and test setup | Backend owns schema initialization and transactions. The Team Lead supplies configuration and registers lifecycle hooks. Coordinate the isolated test fixtures. |
| Form fields, routes, and Jinja context | All three use the documented names, allowed values, and error format. Frontend and Team Lead coordinate updates to dashboard tests when replacing the placeholder. |
| Date, completion, and report rules | Backend applies the approved Asia/Kolkata and Monday–Sunday rules. Frontend displays the server-provided results, and the Team Lead tests that dashboard filters leave both reports unchanged. |
| Merge sequence | Agree which independent pieces can merge first and which changes require one coordinated PR. |
| CI and deployment | The Team Lead confirms GitHub settings and any frontend workflow edits. The local demo is the baseline. The Team Lead verifies release checks and, if Render is chosen, storage and access. |
