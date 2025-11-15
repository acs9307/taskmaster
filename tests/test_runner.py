"""Tests for task runner."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from taskmaster.cli import main
from taskmaster.models import Task, TaskList, TaskStatus
from taskmaster.runner import TaskRunner, run_tasks


class TestTaskRunner:
    """Tests for TaskRunner class."""

    def test_runner_creation(self):
        """Test creating a task runner."""
        task_list = TaskList()
        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        assert runner.task_list == task_list
        assert runner.task_file == task_file
        assert runner.dry_run is False
        assert runner.state is not None

    def test_runner_creation_dry_run(self):
        """Test creating a task runner in dry run mode."""
        task_list = TaskList()
        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file, dry_run=True)
        assert runner.dry_run is True

    def test_run_empty_task_list(self):
        """Test running with no tasks."""
        task_list = TaskList()
        task_list.tasks = []  # Override to allow empty list for testing
        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        success = runner.run()
        assert success is True

    def test_run_single_task(self):
        """Test running a single task."""
        task = Task(
            id="T1",
            title="Test task",
            description="A test task",
        )
        task_list = TaskList()
        task_list.add_task(task)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        success = runner.run()

        assert success is True
        assert task.status == TaskStatus.COMPLETED

    def test_run_multiple_tasks(self):
        """Test running multiple tasks."""
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")
        task3 = Task(id="T3", title="Third", description="Third task")

        task_list = TaskList()
        task_list.add_task(task1)
        task_list.add_task(task2)
        task_list.add_task(task3)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        success = runner.run()

        assert success is True
        assert task1.status == TaskStatus.COMPLETED
        assert task2.status == TaskStatus.COMPLETED
        assert task3.status == TaskStatus.COMPLETED

    def test_run_task_with_metadata(self):
        """Test running task with metadata."""
        task = Task(
            id="T1",
            title="Task with metadata",
            description="Test",
            metadata={"priority": "high", "tags": ["important"]},
        )
        task_list = TaskList()
        task_list.add_task(task)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        success = runner.run()

        assert success is True
        assert task.status == TaskStatus.COMPLETED

    def test_run_task_with_hooks(self):
        """Test running task with hooks."""
        task = Task(
            id="T1",
            title="Task with hooks",
            description="Test",
            pre_hooks=["hook1", "hook2"],
            post_hooks=["hook3"],
        )
        task_list = TaskList()
        task_list.add_task(task)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        success = runner.run()

        assert success is True
        assert task.status == TaskStatus.COMPLETED

    def test_run_dry_run_mode(self):
        """Test running in dry run mode."""
        task = Task(id="T1", title="Test", description="Test task")
        task_list = TaskList()
        task_list.add_task(task)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file, dry_run=True)
        success = runner.run()

        assert success is True
        # Task should still be marked as completed in dry run
        assert task.status == TaskStatus.COMPLETED

    def test_get_summary_all_completed(self):
        """Test getting summary with all tasks completed."""
        task1 = Task(id="T1", title="First", description="First")
        task2 = Task(id="T2", title="Second", description="Second")
        task1.mark_completed()
        task2.mark_completed()

        task_list = TaskList()
        task_list.add_task(task1)
        task_list.add_task(task2)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        summary = runner.get_summary()

        assert summary["total"] == 2
        assert summary["completed"] == 2
        assert summary["pending"] == 0
        assert summary["failed"] == 0

    def test_get_summary_mixed_status(self):
        """Test getting summary with mixed task statuses."""
        task1 = Task(id="T1", title="First", description="First")
        task2 = Task(id="T2", title="Second", description="Second")
        task3 = Task(id="T3", title="Third", description="Third")

        task1.mark_completed()
        task2.mark_failed()
        # task3 remains PENDING

        task_list = TaskList()
        task_list.add_task(task1)
        task_list.add_task(task2)
        task_list.add_task(task3)

        task_file = Path("tasks.yml")
        runner = TaskRunner(task_list, task_file)
        summary = runner.get_summary()

        assert summary["total"] == 3
        assert summary["completed"] == 1
        assert summary["pending"] == 1
        assert summary["failed"] == 1


class TestRunTasks:
    """Tests for run_tasks function."""

    def test_run_tasks_valid_yaml(self):
        """Test running tasks from valid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
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
            success = run_tasks(path, dry_run=True)
            assert success is True
        finally:
            path.unlink()

    def test_run_tasks_valid_json(self):
        """Test running tasks from valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
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
            success = run_tasks(path, dry_run=True)
            assert success is True
        finally:
            path.unlink()

    def test_run_tasks_multiple_tasks(self):
        """Test running multiple tasks from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
tasks:
  - id: T1
    title: First task
    description: First
  - id: T2
    title: Second task
    description: Second
  - id: T3
    title: Third task
    description: Third
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            success = run_tasks(path, dry_run=True)
            assert success is True
        finally:
            path.unlink()

    def test_run_tasks_dry_run(self):
        """Test running tasks in dry run mode."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
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
            success = run_tasks(path, dry_run=True)
            assert success is True
        finally:
            path.unlink()

    def test_run_tasks_invalid_file(self):
        """Test running tasks with invalid file."""
        path = Path("/nonexistent/file.yml")
        success = run_tasks(path)
        assert success is False

    def test_run_tasks_invalid_yaml(self):
        """Test running tasks with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: [")
            f.flush()
            path = Path(f.name)

        try:
            success = run_tasks(path)
            assert success is False
        finally:
            path.unlink()


class TestRunCommandIntegration:
    """Integration tests for run command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_run_command_with_valid_task_file(self):
        """Test run command with valid task file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
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
            result = self.runner.invoke(main, ["run", str(path), "--dry-run"])
            assert result.exit_code == 0
            assert "Test task" in result.output
            assert "completed successfully" in result.output
        finally:
            path.unlink()

    def test_run_command_dry_run(self):
        """Test run command with dry run flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
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
            result = self.runner.invoke(main, ["run", str(path), "--dry-run"])
            assert result.exit_code == 0
            assert "DRY RUN" in result.output
        finally:
            path.unlink()

    def test_run_command_multiple_tasks(self):
        """Test run command with multiple tasks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(
                """
tasks:
  - id: T1
    title: First task
    description: First
  - id: T2
    title: Second task
    description: Second
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(path), "--dry-run"])
            assert result.exit_code == 0
            assert "First task" in result.output
            assert "Second task" in result.output
            assert "Task 1/2" in result.output
            assert "Task 2/2" in result.output
        finally:
            path.unlink()

    def test_run_command_with_example_file(self):
        """Test run command with example task file."""
        example_path = Path("examples/tasks.minimal.yml")
        if example_path.exists():
            result = self.runner.invoke(main, ["run", str(example_path), "--dry-run"])
            assert result.exit_code == 0
            assert "completed successfully" in result.output

    def test_run_command_invalid_file(self):
        """Test run command with invalid file."""
        result = self.runner.invoke(main, ["run", "/nonexistent/file.yml"])
        assert result.exit_code != 0
