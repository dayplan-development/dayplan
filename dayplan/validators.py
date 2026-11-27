from __future__ import annotations

from datetime import date
from typing import Mapping

from .models import PRIORITIES


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("Invalid input")


class TaskNotFound(LookupError):
    pass


FILTER_VALUES = {
    "status": ("All", "Pending", "Completed", "Overdue"),
    "priority": ("All", *PRIORITIES),
}


def _single(values: Mapping[str, object], key: str) -> object:
    value = values.get(key)
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return None
        if len(value) != 1:
            raise ValidationError({key: "Submit this value only once."})
        return value[0]
    return value


def validate_filters(values: Mapping[str, object]) -> dict[str, str]:
    result = {}
    errors = {}
    for key, allowed in FILTER_VALUES.items():
        value = _single(values, key)
        if value is None:
            result[key] = "All"
        elif not isinstance(value, str) or value not in allowed:
            errors[key] = f"Choose a valid {key} filter."
        else:
            result[key] = value
    if errors:
        raise ValidationError(errors)
    return result


def _text(value: object, key: str, maximum: int, required: bool) -> str | None:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError({key: "Enter a valid value."})
    if "\x00" in value:
        raise ValidationError({key: "Remove null characters from this field."})
    value = value.strip()
    if required and not value:
        raise ValidationError({key: "Enter a title."})
    if len(value) > maximum:
        raise ValidationError({key: f"Use {maximum} characters or fewer."})
    return value or None


def _due_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValidationError({"due_date": "Enter a valid date in YYYY-MM-DD format."})
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValidationError({"due_date": "Enter a valid date in YYYY-MM-DD format."})
    if parsed.isoformat() != value:
        raise ValidationError({"due_date": "Enter a valid date in YYYY-MM-DD format."})
    return parsed


def validate_task_fields(fields: Mapping[str, object], *, editing: bool) -> dict:
    errors = {}
    try:
        title = _text(_single(fields, "title"), "title", 100, True)
    except ValidationError as error:
        errors.update(error.errors)
        title = None
    try:
        description = _text(_single(fields, "description"), "description", 500, False)
    except ValidationError as error:
        errors.update(error.errors)
        description = None
    try:
        due_date = _due_date(_single(fields, "due_date"))
    except ValidationError as error:
        errors.update(error.errors)
        due_date = None

    priority_value = _single(fields, "priority")
    if priority_value is None and not editing:
        priority = "Medium"
    elif priority_value not in PRIORITIES:
        errors["priority"] = "Choose Low, Medium, or High."
        priority = None
    else:
        priority = priority_value
    if errors:
        raise ValidationError(errors)
    return {"title": title, "description": description, "due_date": due_date, "priority": priority}
