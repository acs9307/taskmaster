"""Tests for task list parser."""

import tempfile
from pathlib import Path

from taskmaster.models import TaskStatus
from taskmaster.task_parser import (
    TaskListParseError,
    load_task_list,
    load_task_list_file,
    parse_task_list,
    validate_task_data,
)


class TestLoadTaskListFile:
    """Tests for loading task list files."""

    def test_load_yaml_file(self):
        """Test loading a valid YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(
                """
tasks:
  - id: T1
    title: Test task
    description: A test task
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            data = load_task_list_file(path)
            assert "tasks" in data
            assert len(data["tasks"]) == 1
            assert data["tasks"][0]["id"] == "T1"
        finally:
            path.unlink()

    def test_load_json_file(self):
        """Test loading a valid JSON file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(
                """{
  "tasks": [
    {
      "id": "T1",
      "title": "Test task",
      "description": "A test task"
    }
  ]
}"""
            )
            f.flush()
            path = Path(f.name)

        try:
            data = load_task_list_file(path)
            assert "tasks" in data
            assert len(data["tasks"]) == 1
            assert data["tasks"][0]["id"] == "T1"
        finally:
            path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        path = Path("/nonexistent/tasks.yml")
        raised = False
        try:
            load_task_list_file(path)
        except TaskListParseError as e:
            raised = True
            assert "not found" in str(e)
        assert raised, "Should have raised TaskListParseError"

    def test_load_unsupported_format(self):
        """Test loading a file with unsupported format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("tasks: []")
            f.flush()
            path = Path(f.name)

        try:
            raised = False
            try:
                load_task_list_file(path)
            except TaskListParseError as e:
                raised = True
                assert "Unsupported file format" in str(e)
            assert raised, "Should have raised TaskListParseError"
        finally:
            path.unlink()

    def test_load_empty_file(self):
        """Test loading an empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write("")
            f.flush()
            path = Path(f.name)

        try:
            raised = False
            try:
                load_task_list_file(path)
            except TaskListParseError as e:
                raised = True
                assert "empty" in str(e).lower()
            assert raised, "Should have raised TaskListParseError"
        finally:
            path.unlink()

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            path = Path(f.name)

        try:
            raised = False
            try:
                load_task_list_file(path)
            except TaskListParseError as e:
                raised = True
                assert "parse" in str(e).lower()
            assert raised, "Should have raised TaskListParseError"
        finally:
            path.unlink()

    def test_load_invalid_json(self):
        """Test loading invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json")
            f.flush()
            path = Path(f.name)

        try:
            raised = False
            try:
                load_task_list_file(path)
            except TaskListParseError as e:
                raised = True
                assert "parse" in str(e).lower()
            assert raised, "Should have raised TaskListParseError"
        finally:
            path.unlink()


class TestValidateTaskData:
    """Tests for task data validation."""

    def test_valid_task_minimal(self):
        """Test validation of minimal valid task."""
        task_data = {
            "id": "T1",
            "title": "Test task",
            "description": "A test task",
        }
        errors = validate_task_data(task_data, 0)
        assert len(errors) == 0

    def test_valid_task_full(self):
        """Test validation of fully specified task."""
        task_data = {
            "id": "T1",
            "title": "Test task",
            "description": "A test task",
            "path": "./project",
            "metadata": {"priority": "high"},
            "pre_hooks": ["hook1"],
            "post_hooks": ["hook2", "hook3"],
        }
        errors = validate_task_data(task_data, 0)
        assert len(errors) == 0

    def test_missing_id(self):
        """Test validation with missing id."""
        task_data = {"title": "Test", "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("id" in e.lower() and "missing" in e.lower() for e in errors)

    def test_missing_title(self):
        """Test validation with missing title."""
        task_data = {"id": "T1", "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("title" in e.lower() and "missing" in e.lower() for e in errors)

    def test_missing_description(self):
        """Test validation with missing description."""
        task_data = {"id": "T1", "title": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("description" in e.lower() and "missing" in e.lower() for e in errors)

    def test_empty_id(self):
        """Test validation with empty id."""
        task_data = {"id": "  ", "title": "Test", "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("id" in e.lower() and "empty" in e.lower() for e in errors)

    def test_empty_title(self):
        """Test validation with empty title."""
        task_data = {"id": "T1", "title": "", "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("title" in e.lower() and "empty" in e.lower() for e in errors)

    def test_invalid_id_type(self):
        """Test validation with non-string id."""
        task_data = {"id": 123, "title": "Test", "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("id" in e.lower() and "string" in e.lower() for e in errors)

    def test_invalid_title_type(self):
        """Test validation with non-string title."""
        task_data = {"id": "T1", "title": ["Test"], "description": "Test"}
        errors = validate_task_data(task_data, 0)
        assert any("title" in e.lower() and "string" in e.lower() for e in errors)

    def test_invalid_description_type(self):
        """Test validation with non-string description."""
        task_data = {"id": "T1", "title": "Test", "description": 123}
        errors = validate_task_data(task_data, 0)
        assert any("description" in e.lower() and "string" in e.lower() for e in errors)

    def test_invalid_path_type(self):
        """Test validation with non-string path."""
        task_data = {
            "id": "T1",
            "title": "Test",
            "description": "Test",
            "path": 123,
        }
        errors = validate_task_data(task_data, 0)
        assert any("path" in e.lower() and "string" in e.lower() for e in errors)

    def test_invalid_metadata_type(self):
        """Test validation with non-dict metadata."""
        task_data = {
            "id": "T1",
            "title": "Test",
            "description": "Test",
            "metadata": "invalid",
        }
        errors = validate_task_data(task_data, 0)
        assert any(
            "metadata" in e.lower() and "dictionary" in e.lower() for e in errors
        )

    def test_invalid_pre_hooks_type(self):
        """Test validation with non-list pre_hooks."""
        task_data = {
            "id": "T1",
            "title": "Test",
            "description": "Test",
            "pre_hooks": "hook",
        }
        errors = validate_task_data(task_data, 0)
        assert any("pre_hooks" in e.lower() and "list" in e.lower() for e in errors)

    def test_invalid_pre_hooks_items(self):
        """Test validation with non-string items in pre_hooks."""
        task_data = {
            "id": "T1",
            "title": "Test",
            "description": "Test",
            "pre_hooks": ["hook1", 123],
        }
        errors = validate_task_data(task_data, 0)
        assert any("pre_hooks" in e.lower() and "string" in e.lower() for e in errors)

    def test_invalid_post_hooks_type(self):
        """Test validation with non-list post_hooks."""
        task_data = {
            "id": "T1",
            "title": "Test",
            "description": "Test",
            "post_hooks": "hook",
        }
        errors = validate_task_data(task_data, 0)
        assert any("post_hooks" in e.lower() and "list" in e.lower() for e in errors)


class TestParseTaskList:
    """Tests for parsing task lists."""

    def test_parse_minimal_task_list(self):
        """Test parsing a minimal task list."""
        data = {
            "tasks": [
                {"id": "T1", "title": "Test", "description": "Test task"},
            ]
        }
        task_list = parse_task_list(data)
        assert len(task_list.tasks) == 1
        assert task_list.tasks[0].id == "T1"
        assert task_list.tasks[0].title == "Test"
        assert task_list.tasks[0].description == "Test task"
        assert task_list.tasks[0].status == TaskStatus.PENDING

    def test_parse_multiple_tasks(self):
        """Test parsing multiple tasks."""
        data = {
            "tasks": [
                {"id": "T1", "title": "First", "description": "First task"},
                {"id": "T2", "title": "Second", "description": "Second task"},
                {"id": "T3", "title": "Third", "description": "Third task"},
            ]
        }
        task_list = parse_task_list(data)
        assert len(task_list.tasks) == 3
        assert task_list.tasks[0].id == "T1"
        assert task_list.tasks[1].id == "T2"
        assert task_list.tasks[2].id == "T3"

    def test_parse_task_with_hooks(self):
        """Test parsing task with hooks."""
        data = {
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test",
                    "description": "Test",
                    "pre_hooks": ["hook1", "hook2"],
                    "post_hooks": ["hook3"],
                }
            ]
        }
        task_list = parse_task_list(data)
        task = task_list.tasks[0]
        assert task.pre_hooks == ["hook1", "hook2"]
        assert task.post_hooks == ["hook3"]

    def test_parse_task_with_metadata(self):
        """Test parsing task with metadata."""
        data = {
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test",
                    "description": "Test",
                    "metadata": {"priority": "high", "tags": ["backend"]},
                }
            ]
        }
        task_list = parse_task_list(data)
        task = task_list.tasks[0]
        assert task.metadata["priority"] == "high"
        assert task.metadata["tags"] == ["backend"]

    def test_parse_task_with_dependencies(self):
        """Test parsing task list with dependencies."""
        data = {
            "tasks": [
                {"id": "T1", "title": "First", "description": "First task"},
                {"id": "T2", "title": "Second", "description": "Second task"},
                {"id": "T3", "title": "Third", "description": "Third task"},
            ],
            "dependencies": {
                "T2": ["T1"],
                "T3": ["T1", "T2"],
            },
        }
        task_list = parse_task_list(data)
        assert "T2" in task_list.dependencies
        assert task_list.dependencies["T2"] == ["T1"]
        assert task_list.dependencies["T3"] == ["T1", "T2"]

    def test_missing_tasks_field(self):
        """Test parsing without tasks field."""
        data = {}
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "tasks" in str(e).lower()
        assert raised, "Should have raised TaskListParseError"

    def test_tasks_not_list(self):
        """Test parsing with tasks not being a list."""
        data = {"tasks": "not a list"}
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "list" in str(e).lower()
        assert raised, "Should have raised TaskListParseError"

    def test_empty_task_list(self):
        """Test parsing empty task list."""
        data = {"tasks": []}
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "empty" in str(e).lower()
        assert raised, "Should have raised TaskListParseError"

    def test_duplicate_task_ids(self):
        """Test parsing with duplicate task IDs."""
        data = {
            "tasks": [
                {"id": "T1", "title": "First", "description": "First"},
                {"id": "T1", "title": "Duplicate", "description": "Duplicate"},
            ]
        }
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "duplicate" in str(e).lower()
            assert "T1" in str(e)
        assert raised, "Should have raised TaskListParseError"

    def test_invalid_dependency_unknown_task(self):
        """Test parsing with dependency on unknown task."""
        data = {
            "tasks": [
                {"id": "T1", "title": "Test", "description": "Test"},
            ],
            "dependencies": {
                "T1": ["T2"],  # T2 doesn't exist
            },
        }
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "unknown" in str(e).lower()
            assert "T2" in str(e)
        assert raised, "Should have raised TaskListParseError"

    def test_invalid_dependency_unknown_dependent(self):
        """Test parsing with unknown task having dependencies."""
        data = {
            "tasks": [
                {"id": "T1", "title": "Test", "description": "Test"},
            ],
            "dependencies": {
                "T2": ["T1"],  # T2 doesn't exist
            },
        }
        raised = False
        try:
            parse_task_list(data)
        except TaskListParseError as e:
            raised = True
            assert "unknown" in str(e).lower()
        assert raised, "Should have raised TaskListParseError"


class TestLoadTaskList:
    """Tests for loading task list from file."""

    def test_load_valid_yaml_file(self):
        """Test loading a valid YAML task list file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(
                """
tasks:
  - id: T1
    title: Test task
    description: A test task
    path: ./project
    pre_hooks: [hook1]
    post_hooks: [hook2]
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            task_list = load_task_list(path)
            assert len(task_list.tasks) == 1
            assert task_list.tasks[0].id == "T1"
            assert task_list.tasks[0].path == "./project"
            assert task_list.tasks[0].pre_hooks == ["hook1"]
        finally:
            path.unlink()

    def test_load_valid_json_file(self):
        """Test loading a valid JSON task list file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(
                """{
  "tasks": [
    {
      "id": "T1",
      "title": "Test task",
      "description": "A test task"
    }
  ]
}"""
            )
            f.flush()
            path = Path(f.name)

        try:
            task_list = load_task_list(path)
            assert len(task_list.tasks) == 1
            assert task_list.tasks[0].id == "T1"
        finally:
            path.unlink()

    def test_load_example_files(self):
        """Test loading the example task list files."""
        # Test minimal example
        minimal_path = Path("examples/tasks.minimal.yml")
        if minimal_path.exists():
            task_list = load_task_list(minimal_path)
            assert len(task_list.tasks) >= 1

        # Test full YAML example
        yaml_path = Path("examples/tasks.example.yml")
        if yaml_path.exists():
            task_list = load_task_list(yaml_path)
            assert len(task_list.tasks) >= 1
            assert len(task_list.dependencies) > 0

        # Test JSON example
        json_path = Path("examples/tasks.example.json")
        if json_path.exists():
            task_list = load_task_list(json_path)
            assert len(task_list.tasks) >= 1
