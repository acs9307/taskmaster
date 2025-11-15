"""Task list parsing and loading."""

import json
from pathlib import Path
from typing import Any

import yaml

from taskmaster.models import Task, TaskList, TaskStatus


class TaskListParseError(Exception):
    """Raised when a task list cannot be parsed."""

    pass


def load_task_list_file(path: Path) -> dict[str, Any]:
    """
    Load a task list file (YAML or JSON).

    Args:
        path: Path to the task list file

    Returns:
        Parsed task list dictionary

    Raises:
        TaskListParseError: If the file cannot be loaded or parsed
    """
    if not path.exists():
        raise TaskListParseError(f"Task list file not found: {path}")

    suffix = path.suffix.lower()

    try:
        with open(path) as f:
            if suffix in [".yml", ".yaml"]:
                data = yaml.safe_load(f)
            elif suffix == ".json":
                data = json.load(f)
            else:
                raise TaskListParseError(
                    f"Unsupported file format: {suffix}. Use .yml, .yaml, or .json"
                )

        if data is None:
            raise TaskListParseError(f"Task list file is empty: {path}")

        if not isinstance(data, dict):
            raise TaskListParseError(
                f"Task list root must be a dictionary, got {type(data).__name__}"
            )

        return data

    except yaml.YAMLError as e:
        raise TaskListParseError(f"Failed to parse YAML file {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise TaskListParseError(f"Failed to parse JSON file {path}: {e}") from e
    except Exception as e:
        raise TaskListParseError(f"Failed to load task list file {path}: {e}") from e


def validate_task_data(task_data: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single task's data.

    Args:
        task_data: Task data dictionary
        index: Task index in the list (for error messages)

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    task_id = task_data.get("id", f"task[{index}]")

    # Required fields
    if "id" not in task_data:
        errors.append(f"Task at index {index}: Missing required field 'id'")
    elif not isinstance(task_data["id"], str):
        errors.append(
            f"Task '{task_id}': Field 'id' must be a string, "
            f"got {type(task_data['id']).__name__}"
        )
    elif not task_data["id"].strip():
        errors.append(f"Task at index {index}: Field 'id' cannot be empty")

    if "title" not in task_data:
        errors.append(f"Task '{task_id}': Missing required field 'title'")
    elif not isinstance(task_data["title"], str):
        errors.append(
            f"Task '{task_id}': Field 'title' must be a string, "
            f"got {type(task_data['title']).__name__}"
        )
    elif not task_data["title"].strip():
        errors.append(f"Task '{task_id}': Field 'title' cannot be empty")

    if "description" not in task_data:
        errors.append(f"Task '{task_id}': Missing required field 'description'")
    elif not isinstance(task_data["description"], str):
        errors.append(
            f"Task '{task_id}': Field 'description' must be a string, "
            f"got {type(task_data['description']).__name__}"
        )

    # Optional fields with type checking
    if "path" in task_data and not isinstance(task_data["path"], str):
        errors.append(
            f"Task '{task_id}': Field 'path' must be a string, "
            f"got {type(task_data['path']).__name__}"
        )

    if "metadata" in task_data and not isinstance(task_data["metadata"], dict):
        errors.append(
            f"Task '{task_id}': Field 'metadata' must be a dictionary, "
            f"got {type(task_data['metadata']).__name__}"
        )

    if "pre_hooks" in task_data:
        if not isinstance(task_data["pre_hooks"], list):
            errors.append(
                f"Task '{task_id}': Field 'pre_hooks' must be a list, "
                f"got {type(task_data['pre_hooks']).__name__}"
            )
        elif not all(isinstance(h, str) for h in task_data["pre_hooks"]):
            errors.append(
                f"Task '{task_id}': All items in 'pre_hooks' must be strings"
            )

    if "post_hooks" in task_data:
        if not isinstance(task_data["post_hooks"], list):
            errors.append(
                f"Task '{task_id}': Field 'post_hooks' must be a list, "
                f"got {type(task_data['post_hooks']).__name__}"
            )
        elif not all(isinstance(h, str) for h in task_data["post_hooks"]):
            errors.append(
                f"Task '{task_id}': All items in 'post_hooks' must be strings"
            )

    return errors


def parse_task(task_data: dict[str, Any]) -> Task:
    """
    Parse a task from dictionary data.

    Args:
        task_data: Task data dictionary

    Returns:
        Task object
    """
    return Task(
        id=task_data["id"],
        title=task_data["title"],
        description=task_data["description"],
        path=task_data.get("path", "."),
        metadata=task_data.get("metadata", {}),
        pre_hooks=task_data.get("pre_hooks", []),
        post_hooks=task_data.get("post_hooks", []),
        status=TaskStatus.PENDING,
        failure_count=0,
    )


def parse_task_list(data: dict[str, Any]) -> TaskList:
    """
    Parse a task list from dictionary data.

    Args:
        data: Task list data dictionary

    Returns:
        TaskList object

    Raises:
        TaskListParseError: If the task list is invalid
    """
    # Validate root structure
    if "tasks" not in data:
        raise TaskListParseError("Task list must contain a 'tasks' field")

    tasks_data = data["tasks"]
    if not isinstance(tasks_data, list):
        raise TaskListParseError(
            f"Field 'tasks' must be a list, got {type(tasks_data).__name__}"
        )

    if len(tasks_data) == 0:
        raise TaskListParseError("Task list cannot be empty")

    # Validate all tasks
    all_errors = []
    for i, task_data in enumerate(tasks_data):
        if not isinstance(task_data, dict):
            all_errors.append(
                f"Task at index {i} must be a dictionary, "
                f"got {type(task_data).__name__}"
            )
            continue

        errors = validate_task_data(task_data, i)
        all_errors.extend(errors)

    # If there are validation errors, raise with all messages
    if all_errors:
        error_msg = "Task list validation failed:\n" + "\n".join(
            f"  - {err}" for err in all_errors
        )
        raise TaskListParseError(error_msg)

    # Check for duplicate task IDs
    task_ids = [task_data["id"] for task_data in tasks_data]
    duplicates = [tid for tid in task_ids if task_ids.count(tid) > 1]
    if duplicates:
        unique_duplicates = sorted(set(duplicates))
        raise TaskListParseError(
            f"Duplicate task IDs found: {', '.join(unique_duplicates)}"
        )

    # Parse tasks
    task_list = TaskList()
    for task_data in tasks_data:
        task = parse_task(task_data)
        task_list.add_task(task)

    # Parse dependencies if present
    dependencies = data.get("dependencies", {})
    if dependencies:
        if not isinstance(dependencies, dict):
            raise TaskListParseError(
                f"Field 'dependencies' must be a dictionary, "
                f"got {type(dependencies).__name__}"
            )

        # Validate dependencies
        for task_id, deps in dependencies.items():
            if task_id not in task_ids:
                raise TaskListParseError(
                    f"Dependency references unknown task ID: {task_id}"
                )

            if not isinstance(deps, list):
                raise TaskListParseError(
                    f"Dependencies for task '{task_id}' must be a list, "
                    f"got {type(deps).__name__}"
                )

            for dep_id in deps:
                if not isinstance(dep_id, str):
                    raise TaskListParseError(
                        f"Dependency IDs must be strings, got {type(dep_id).__name__}"
                    )
                if dep_id not in task_ids:
                    raise TaskListParseError(
                        f"Task '{task_id}' depends on unknown task: {dep_id}"
                    )

        # Apply dependencies
        task_list.dependencies = dependencies

    return task_list


def load_task_list(path: Path) -> TaskList:
    """
    Load and parse a task list from a file.

    Args:
        path: Path to the task list file (YAML or JSON)

    Returns:
        TaskList object

    Raises:
        TaskListParseError: If the file cannot be loaded or parsed
    """
    data = load_task_list_file(path)
    return parse_task_list(data)
