# Frontend notes

## Templates
- `base.html`: layout, header, flash messages, footer
- `dashboard.html`: summary tiles, filters, task cards
- `task_form.html`: add and edit form

## Variables the templates expect
- Dashboard: `tasks`, `summary`, `selected_status`, `selected_priority`
  - Each task: `id`, `title`, `description`, `due_date`, `priority`, `status`, `reminder_at`, `completed_at`, `is_overdue`
  - `summary`: `due_today`, `overdue`, `completed_today`, `weekly_percent`, `weekly_total`
- Form: `mode` ('add' or 'edit'), `form`, `errors`, `form_action`
- Optional: `task_base_url` (default `/tasks`), `new_task_url` (default `/tasks/new`)

## Colour palette
Muted Sage #A3AD98, Warm Cream Beige #F3EBDD, Deep Burgundy #702D3C, Charcoal Black #252522