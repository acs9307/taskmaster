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
        assert "--stop-on-failure" in result.output
        assert "--provider" in result.output

    def test_run_with_valid_file(self):
        """Test run command with valid file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("tasks: []")
            f.flush()
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file)])
            assert result.exit_code == 0
            assert f"Running tasks from: {task_file}" in result.output
            assert "not yet implemented" in result.output
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
            f.write("tasks: []")
            f.flush()
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(main, ["run", str(task_file), "--dry-run"])
            assert result.exit_code == 0
            assert "DRY RUN MODE" in result.output
        finally:
            task_file.unlink()

    def test_run_stop_on_failure_flag(self):
        """Test run command with --stop-on-failure flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("tasks: []")
            f.flush()
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(
                main, ["run", str(task_file), "--stop-on-failure"]
            )
            assert result.exit_code == 0
        finally:
            task_file.unlink()

    def test_run_with_provider_override(self):
        """Test run command with provider override."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("tasks: []")
            f.flush()
            task_file = Path(f.name)

        try:
            result = self.runner.invoke(
                main, ["run", str(task_file), "--provider", "openai"]
            )
            assert result.exit_code == 0
            assert "Using provider: openai" in result.output
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
        result = self.runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "TaskMaster Status" in result.output
        assert "not yet implemented" in result.output

    def test_status_verbose(self):
        """Test status command with verbose flag."""
        result = self.runner.invoke(main, ["status", "--verbose"])
        assert result.exit_code == 0
        assert "TaskMaster Status" in result.output
        assert "Verbose mode would show:" in result.output
        assert "Full task details" in result.output


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
        """Test basic resume command."""
        result = self.runner.invoke(main, ["resume"])
        assert result.exit_code == 0
        assert "Resuming task execution" in result.output
        assert "not yet implemented" in result.output

    def test_resume_force_flag(self):
        """Test resume command with --force flag."""
        result = self.runner.invoke(main, ["resume", "--force"])
        assert result.exit_code == 0
        assert "Force mode enabled" in result.output

    def test_resume_with_provider(self):
        """Test resume command with provider override."""
        result = self.runner.invoke(main, ["resume", "--provider", "claude"])
        assert result.exit_code == 0
        assert "Using provider: claude" in result.output


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
