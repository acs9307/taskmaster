"""Tests for CLI commands."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from taskmaster.cli import main


class TestCLI:
    """Tests for main CLI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_main_help(self):
        """Test main --help command."""
        result = self.runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "TaskMaster" in result.output
        assert "AI-powered task orchestration" in result.output
        assert "run" in result.output
        assert "status" in result.output
        assert "resume" in result.output
        assert "debug" in result.output
        assert "config" in result.output

    def test_version(self):
        """Test --version flag."""
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestRunCommand:
    """Tests for 'run' command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_run_help(self):
        """Test run --help command."""
        result = self.runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run tasks from a task list file" in result.output
        assert "--dry-run" in result.output
        assert "--stop-on-first-failure" in result.output
        assert "--provider" in result.output
        assert "--ignore-config-limits" in result.output
        assert "--quiet" in result.output

    def test_run_with_valid_file(self):
        """Test run command with valid file."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file), "--dry-run"])
            assert result.exit_code == 0
            assert "Test task" in result.output
            assert "completed successfully" in result.output
        finally:
            task_file.unlink()

    def test_run_with_nonexistent_file(self):
        """Test run command with non-existent file."""
        result = self.runner.invoke(main, ["run", "/nonexistent/file.yml"])
        assert result.exit_code != 0
        assert "does not exist" in result.output or "Invalid value" in result.output

    def test_run_dry_run_flag(self):
        """Test run command with --dry-run flag."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file), "--dry-run"])
            assert result.exit_code == 0
            assert "DRY RUN" in result.output
        finally:
            task_file.unlink()

    def test_run_stop_on_first_failure_flag(self):
        """Test run command with --stop-on-first-failure flag."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(
                main, ["run", str(task_file), "--stop-on-first-failure", "--dry-run"]
            )
            assert result.exit_code == 0
        finally:
            task_file.unlink()

    def test_run_ignore_config_limits_flag(self):
        """Test run command with --ignore-config-limits flag."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(
                main, ["run", str(task_file), "--ignore-config-limits", "--dry-run"]
            )
            assert result.exit_code == 0
        finally:
            task_file.unlink()

    def test_run_with_provider_override(self):
        """Test run command with provider override."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(
                main, ["run", str(task_file), "--provider", "openai", "--dry-run"]
            )
            assert result.exit_code == 0
            # Provider override is accepted and used
            assert "completed successfully" in result.output
        finally:
            task_file.unlink()

    def test_run_quiet_flag(self):
        """Test run command with --quiet flag."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file), "--quiet", "--dry-run"])
            assert result.exit_code == 0
            # Quiet mode should have minimal output
            assert "Test task" in result.output
            assert "All tasks completed" in result.output
            # Should NOT have verbose output like "Starting TaskMaster Execution"
            assert "Starting TaskMaster Execution" not in result.output
        finally:
            task_file.unlink()

    def test_run_timing_output(self):
        """Test that timing information is displayed for tasks."""
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
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file), "--dry-run"])
            assert result.exit_code == 0
            # Should display timing in format like "0.0s" or "1.5s"
            assert "s)" in result.output  # Timing suffix
        finally:
            task_file.unlink()


class TestStatusCommand:
    """Tests for 'status' command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_status_help(self):
        """Test status --help command."""
        result = self.runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0
        assert "Show current task queue and progress" in result.output
        assert "--verbose" in result.output

    def test_status_basic(self):
        """Test basic status command."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "TaskMaster Status" in result.output
            assert "No active task execution found" in result.output

    def test_status_verbose(self):
        """Test status command with verbose flag."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["status", "--verbose"])
            assert result.exit_code == 0
            assert "TaskMaster Status" in result.output
            assert "No active task execution found" in result.output


class TestResumeCommand:
    """Tests for 'resume' command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_resume_help(self):
        """Test resume --help command."""
        result = self.runner.invoke(main, ["resume", "--help"])
        assert result.exit_code == 0
        assert "Resume task execution after interruption" in result.output
        assert "--force" in result.output
        assert "--provider" in result.output

    def test_resume_basic(self):
        """Test basic resume command without saved state."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["resume"])
            # Should fail with no saved state
            assert result.exit_code == 1
            assert "Resuming task execution" in result.output
            assert "No saved state found" in result.output

    def test_resume_force_flag(self):
        """Test resume command with --force flag."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["resume", "--force"])
            # Should still fail with no saved state
            assert result.exit_code == 1
            assert "Force mode enabled" in result.output
            assert "No saved state found" in result.output

    def test_resume_with_provider(self):
        """Test resume command with provider override."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["resume", "--provider", "claude"])
            # Should fail with no saved state
            assert result.exit_code == 1
            assert "No saved state found" in result.output


class TestDebugCommand:
    """Tests for 'debug' command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_debug_help(self):
        """Test debug --help command."""
        result = self.runner.invoke(main, ["debug", "--help"])
        assert result.exit_code == 0
        assert "Display detailed debugging information" in result.output
        assert "per-task status" in result.output
        # "failure counts" may be wrapped across lines
        assert "counts" in result.output

    def test_debug_no_state(self):
        """Test debug command when no state exists."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["debug"])
            assert result.exit_code == 0
            assert "TaskMaster Debug State" in result.output
            assert "No saved state found" in result.output

    def test_debug_with_state(self):
        """Test debug command with saved state."""
        import json
        from pathlib import Path

        with self.runner.isolated_filesystem():
            # Create a fake state file
            state_dir = Path(".taskmaster")
            state_dir.mkdir()
            state_file = state_dir / "state.json"

            # Create task file
            task_file = Path("tasks.yml")
            task_file.write_text(
                """
tasks:
  - id: T1
    title: First task
    description: Test task 1
  - id: T2
    title: Second task
    description: Test task 2
"""
            )

            # Create state with some data
            state_data = {
                "task_file": str(task_file),
                "completed_task_ids": ["T1"],
                "current_task_index": 1,
                "failure_counts": {"T1": 2},
                "attempt_counts": {"T1": 3},
                "non_progress_counts": {"T1": 1},
                "user_interventions": {},
                "last_errors": {"T1": "Some error occurred"},
                "usage_records": [
                    {
                        "timestamp": "2025-01-01T12:00:00",
                        "provider": "claude",
                        "tokens": 1000,
                        "requests": 1,
                    }
                ],
                "created_at": "2025-01-01T10:00:00",
                "updated_at": "2025-01-01T12:00:00",
            }

            with open(state_file, "w") as f:
                json.dump(state_data, f)

            # Run debug command
            result = self.runner.invoke(main, ["debug"])
            assert result.exit_code == 0
            assert "TaskMaster Debug State" in result.output
            assert "tasks.yml" in result.output
            assert "PER-TASK STATUS" in result.output
            assert "First task" in result.output
            assert "Second task" in result.output
            assert "COMPLETED" in result.output
            assert "CURRENT/NEXT" in result.output
            assert "Failures: 2" in result.output
            assert "Attempts: 3" in result.output
            assert "RATE LIMIT USAGE" in result.output
            assert "claude" in result.output

    def test_debug_with_state_no_task_file(self):
        """Test debug command when task file doesn't exist."""
        import json
        from pathlib import Path

        with self.runner.isolated_filesystem():
            # Create a fake state file
            state_dir = Path(".taskmaster")
            state_dir.mkdir()
            state_file = state_dir / "state.json"

            # Create state pointing to non-existent task file
            state_data = {
                "task_file": "nonexistent.yml",
                "completed_task_ids": ["T1"],
                "current_task_index": 1,
                "failure_counts": {"T1": 2},
                "attempt_counts": {"T1": 3},
                "non_progress_counts": {},
                "user_interventions": {},
                "last_errors": {"T1": "Some error"},
                "usage_records": [],
                "created_at": "2025-01-01T10:00:00",
                "updated_at": "2025-01-01T12:00:00",
            }

            with open(state_file, "w") as f:
                json.dump(state_data, f)

            # Run debug command - should fall back to raw state data
            result = self.runner.invoke(main, ["debug"])
            assert result.exit_code == 0
            assert "TaskMaster Debug State" in result.output
            assert "Warning: Could not load task list" in result.output
            assert "Showing raw state data" in result.output
            assert "Completed Task IDs" in result.output
            assert "T1" in result.output
            assert "Failure Counts" in result.output


class TestConfigCommand:
    """Tests for 'config' subcommands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_config_help(self):
        """Test config --help command."""
        result = self.runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0
        assert "Manage TaskMaster configuration" in result.output
        assert "validate" in result.output
        assert "show" in result.output

    def test_config_validate_help(self):
        """Test config validate --help command."""
        result = self.runner.invoke(main, ["config", "validate", "--help"])
        assert result.exit_code == 0
        assert "Validate configuration files" in result.output

    def test_config_show_help(self):
        """Test config show --help command."""
        result = self.runner.invoke(main, ["config", "show", "--help"])
        assert result.exit_code == 0
        assert "Display the current merged configuration" in result.output

    def test_config_validate_no_configs(self):
        """Test config validate when no configs exist."""
        result = self.runner.invoke(main, ["config", "validate"])
        # Should show warnings but not fail hard
        assert "Global config not found" in result.output or "not found" in result.output

    def test_config_show_no_configs(self):
        """Test config show with no configuration files."""
        result = self.runner.invoke(main, ["config", "show"])
        # Should show default config
        assert "Current TaskMaster Configuration" in result.output
