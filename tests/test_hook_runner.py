"""Tests for hook runner."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from taskmaster.config import Config, HookConfig
from taskmaster.hook_runner import (
    HookExecutionError,
    HookResult,
    HookRunner,
)


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_hook_result_creation(self):
        """Test creating a hook result."""
        result = HookResult(
            hook_id="test-hook",
            command="pytest",
            exit_code=0,
            stdout="All tests passed",
            stderr="",
            duration=2.5,
            timestamp="2025-01-01T00:00:00",
            success=True,
        )

        assert result.hook_id == "test-hook"
        assert result.command == "pytest"
        assert result.exit_code == 0
        assert result.success is True
        assert result.timed_out is False
        assert result.duration == 2.5

    def test_hook_result_failed(self):
        """Test hook result for failed execution."""
        result = HookResult(
            hook_id="test-hook",
            command="failing-command",
            exit_code=1,
            stdout="",
            stderr="Command failed",
            duration=0.5,
            timestamp="2025-01-01T00:00:00",
            success=False,
        )

        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "Command failed"

    def test_hook_result_timeout(self):
        """Test hook result for timeout."""
        result = HookResult(
            hook_id="test-hook",
            command="sleep 1000",
            exit_code=-1,
            stdout="",
            stderr="",
            duration=5.0,
            timestamp="2025-01-01T00:00:00",
            success=False,
            timed_out=True,
        )

        assert result.timed_out is True
        assert result.success is False


class TestHookRunner:
    """Tests for HookRunner."""

    def test_runner_creation(self):
        """Test creating a hook runner."""
        config = Config()
        runner = HookRunner(config)

        assert runner.config is config
        assert runner.working_dir == Path.cwd()

    def test_runner_with_custom_dirs(self):
        """Test hook runner with custom directories."""
        config = Config()
        working_dir = Path("/tmp")
        log_dir = Path("/tmp/logs")

        runner = HookRunner(config, working_dir=working_dir, log_dir=log_dir)

        assert runner.working_dir == working_dir
        assert runner.log_dir == log_dir

    @patch("subprocess.run")
    def test_run_hook_success(self, mock_run):
        """Test running a successful hook."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

        config = Config()
        runner = HookRunner(config)
        hook_config = HookConfig(command="pytest")

        result = runner.run_hook("test", hook_config)

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Success"
        assert result.hook_id == "test"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_hook_failure(self, mock_run):
        """Test running a failed hook."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Test failed")

        config = Config()
        runner = HookRunner(config)
        hook_config = HookConfig(command="pytest")

        result = runner.run_hook("test", hook_config)

        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "Test failed"

    @patch("subprocess.run")
    def test_run_hook_timeout(self, mock_run):
        """Test hook timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(
            "pytest", 10, output=b"partial", stderr=b"timeout"
        )

        config = Config()
        runner = HookRunner(config)
        hook_config = HookConfig(command="pytest", timeout=10)

        result = runner.run_hook("test", hook_config)

        assert result.success is False
        assert result.timed_out is True
        assert result.exit_code == -1
        assert result.stdout == "partial"
        assert result.stderr == "timeout"

    @patch("subprocess.run")
    def test_run_hook_with_working_dir(self, mock_run):
        """Test hook with custom working directory."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            runner = HookRunner(config, working_dir=Path(tmpdir))
            hook_config = HookConfig(command="ls", working_dir="subdir")

            # Create subdir
            (Path(tmpdir) / "subdir").mkdir()

            runner.run_hook("test", hook_config)

            # Verify working directory was used
            call_args = mock_run.call_args
            assert call_args[1]["cwd"] == Path(tmpdir) / "subdir"

    @patch("subprocess.run")
    def test_run_hook_with_environment(self, mock_run):
        """Test hook with environment variables."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        config = Config()
        runner = HookRunner(config)
        hook_config = HookConfig(command="pytest", environment={"TEST_VAR": "test_value"})

        runner.run_hook("test", hook_config)

        # Verify environment variables were passed
        call_args = mock_run.call_args
        assert call_args[1]["env"]["TEST_VAR"] == "test_value"

    @patch("subprocess.run")
    def test_run_hooks_success(self, mock_run):
        """Test running multiple hooks successfully."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        config = Config(
            hooks={
                "hook1": HookConfig(command="echo test1"),
                "hook2": HookConfig(command="echo test2"),
            }
        )

        runner = HookRunner(config)
        results = runner.run_hooks(["hook1", "hook2"])

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].hook_id == "hook1"
        assert results[1].hook_id == "hook2"

    @patch("subprocess.run")
    def test_run_hooks_stop_on_failure(self, mock_run):
        """Test that hooks stop on first failure."""
        # First hook succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Failed"),
        ]

        config = Config(
            hooks={
                "hook1": HookConfig(command="echo test1"),
                "hook2": HookConfig(command="fail", continue_on_failure=False),
                "hook3": HookConfig(command="echo test3"),
            }
        )

        runner = HookRunner(config)

        with pytest.raises(HookExecutionError) as exc_info:
            runner.run_hooks(["hook1", "hook2", "hook3"])

        assert exc_info.value.hook_result.hook_id == "hook2"
        # Only two hooks should have been executed
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_run_hooks_continue_on_failure(self, mock_run):
        """Test continuing execution despite failures."""
        # Second hook fails but has continue_on_failure=True
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Failed"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        config = Config(
            hooks={
                "hook1": HookConfig(command="echo test1"),
                "hook2": HookConfig(command="fail", continue_on_failure=True),
                "hook3": HookConfig(command="echo test3"),
            }
        )

        runner = HookRunner(config)
        results = runner.run_hooks(["hook1", "hook2", "hook3"])

        # All three hooks should have executed
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        assert mock_run.call_count == 3

    def test_run_hooks_missing_hook(self):
        """Test running a hook that doesn't exist in config."""
        config = Config()
        runner = HookRunner(config)

        with pytest.raises(HookExecutionError) as exc_info:
            runner.run_hooks(["nonexistent"])

        assert "not found in configuration" in str(exc_info.value)
        assert exc_info.value.hook_result.hook_id == "nonexistent"

    @patch("subprocess.run")
    def test_run_pre_hooks(self, mock_run):
        """Test running pre-task hooks."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        config = Config(hooks={"install": HookConfig(command="npm install")})
        runner = HookRunner(config)

        results = runner.run_pre_hooks(["install"])

        assert len(results) == 1
        assert results[0].hook_id == "install"
        assert results[0].success is True

    @patch("subprocess.run")
    def test_run_post_hooks(self, mock_run):
        """Test running post-task hooks."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        config = Config(hooks={"test": HookConfig(command="pytest")})
        runner = HookRunner(config)

        results = runner.run_post_hooks(["test"])

        assert len(results) == 1
        assert results[0].hook_id == "test"
        assert results[0].success is True


class TestHookLogging:
    """Tests for hook result logging."""

    def test_save_hook_results(self):
        """Test saving hook results to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            config = Config()
            runner = HookRunner(config, log_dir=log_dir)

            results = [
                HookResult(
                    hook_id="test1",
                    command="pytest",
                    exit_code=0,
                    stdout="All tests passed",
                    stderr="",
                    duration=2.5,
                    timestamp="2025-01-01T00:00:00",
                    success=True,
                ),
                HookResult(
                    hook_id="test2",
                    command="ruff check",
                    exit_code=1,
                    stdout="",
                    stderr="Linting failed",
                    duration=1.0,
                    timestamp="2025-01-01T00:00:01",
                    success=False,
                ),
            ]

            runner.save_hook_results("task-123", results, "pre")

            # Check log file was created
            log_file = log_dir / "task-123" / "pre.log"
            assert log_file.exists()

            # Check log contents
            content = log_file.read_text()
            assert "=== PRE-TASK HOOKS ===" in content
            assert "Task: task-123" in content
            assert "Total hooks: 2" in content
            assert "Hook: test1" in content
            assert "Command: pytest" in content
            assert "Exit code: 0" in content
            assert "Success: True" in content
            assert "All tests passed" in content
            assert "Hook: test2" in content
            assert "Linting failed" in content

    def test_save_hook_results_creates_directory(self):
        """Test that hook logging creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            config = Config()
            runner = HookRunner(config, log_dir=log_dir)

            results = [
                HookResult(
                    hook_id="test",
                    command="echo test",
                    exit_code=0,
                    stdout="test",
                    stderr="",
                    duration=0.1,
                    timestamp="2025-01-01T00:00:00",
                    success=True,
                )
            ]

            runner.save_hook_results("task-456", results, "post")

            # Verify directory was created
            task_dir = log_dir / "task-456"
            assert task_dir.exists()
            assert task_dir.is_dir()

            # Verify log file was created
            log_file = task_dir / "post.log"
            assert log_file.exists()


class TestHookExecutionError:
    """Tests for HookExecutionError."""

    def test_hook_execution_error(self):
        """Test creating a hook execution error."""
        result = HookResult(
            hook_id="test",
            command="pytest",
            exit_code=1,
            stdout="",
            stderr="Tests failed",
            duration=2.0,
            timestamp="2025-01-01T00:00:00",
            success=False,
        )

        error = HookExecutionError("Hook failed", result)

        assert str(error) == "Hook failed"
        assert error.hook_result is result
        assert error.hook_result.hook_id == "test"
