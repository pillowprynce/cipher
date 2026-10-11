"""Task loading and validation against tasks/schema.json (stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path


class TaskError(Exception):
    """The task file is missing or invalid."""


REQUIRED_TOP = ["id", "goal", "success_criteria"]
REQUIRED_CRITERION = ["id", "description", "type"]


def load_task(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise TaskError(f"task file not found: {path}")
    try:
        task = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TaskError(f"task file is not valid JSON: {e}")
    validate_task(task)
    return task


def validate_task(task: dict) -> None:
    """Validate a task dict against the schema. Raises TaskError."""
    if not isinstance(task, dict):
        raise TaskError("task must be a JSON object")
    for key in REQUIRED_TOP:
        if key not in task:
            raise TaskError(f"task missing required field: {key!r}")
    if not isinstance(task["goal"], str) or not task["goal"].strip():
        raise TaskError("task.goal must be a non-empty string")
    crits = task["success_criteria"]
    if not isinstance(crits, list) or not crits:
        raise TaskError("task.success_criteria must be a non-empty list")
    for c in crits:
        if not isinstance(c, dict):
            raise TaskError("each success_criteria entry must be an object")
        for key in REQUIRED_CRITERION:
            if key not in c:
                raise TaskError(f"criterion missing required field: {key!r}")
        if c["type"] == "file_exists" and "path" not in c:
            raise TaskError(f"criterion {c.get('id')!r}: file_exists needs 'path'")
        if c["type"] == "command" and "cmd" not in c:
            raise TaskError(f"criterion {c.get('id')!r}: command needs 'cmd'")
        if c["type"] not in ("file_exists", "command"):
            raise TaskError(f"criterion {c.get('id')!r}: unknown type {c['type']!r}")
    budget = task.get("budget", {})
    if not isinstance(budget, dict):
        raise TaskError("task.budget must be an object")
    for k in ("max_retries", "max_steps"):
        if k in budget and (not isinstance(budget[k], int) or budget[k] < 0):
            raise TaskError(f"task.budget.{k} must be a non-negative integer")
