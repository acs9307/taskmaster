"""Hook execution and management."""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from taskmaster.config import Config, HookConfig


@dataclass
class HookResult:
    """
    Result of executing a hook.

    Attributes:
        hook_id: The hook identifier
        command: The command that was executed
        exit_code: Exit code from the command
        stdout: Standard output from the command
        stderr: Standard error from the command
        duration: Execution duration in seconds
        timestamp: When the hook was executed
        success: Whether the hook succeeded (exit_code == 0)
        timed_out: Whether the hook timed out
    """

    hook_id: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timestamp: str
    success: bool
    timed_out: bool = False


class HookExecutionError(Exception):
    """Raised when a hook execution fails and should not continue."""

    def __init__(self, message: str, hook_result: HookResult):
        """
        Initialize hook execution error.

        Args:
            message: Error message
            hook_result: The result of the failed hook
        """
        super().__init__(message)
        self.hook_result = hook_result


class HookRunner:
    """
    Executes command hooks with output capture and error handling.

    This class runs pre- and post-task hooks, capturing their output
    and managing failures according to configuration.
    """

    def __init__(
        self,
        config: Config,
        working_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None,
    ):
        """
        Initialize hook runner.

        Args:
            config: TaskMaster configuration
            working_dir: Working directory for hook execution (defaults to cwd)
            log_dir: Directory to store hook logs (defaults to .taskmaster/logs)
        """
        self.config = config
        self.working_dir = working_dir or Path.cwd()
        self.log_dir = log_dir or Path(".taskmaster") / "logs"

    def run_hook(self, hook_id: str, hook_config: HookConfig) -> HookResult:
        """
        Execute a single hook.

        Args:
            hook_id: The hook identifier
            hook_config: The hook configuration

        Returns:
            HookResult with execution details
        """
        # Determine working directory
        if hook_config.working_dir:
            work_dir = self.working_dir / hook_config.working_dir
        else:
            work_dir = self.working_dir

        # Prepare environment
        env = dict(subprocess.os.environ)
        if hook_config.environment:
            env.update(hook_config.environment)

        # Execute command
        timestamp = datetime.now().isoformat()
        start_time = datetime.now()

        try:
            result = subprocess.run(
                hook_config.command,
                shell=True,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=hook_config.timeout,
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return HookResult(
                hook_id=hook_id,
                command=hook_config.command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                timestamp=timestamp,
                success=(result.returncode == 0),
                timed_out=False,
            )

        except subprocess.TimeoutExpired as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Get partial output if available
            stdout = e.stdout.decode("utf-8") if e.stdout else ""
            stderr = e.stderr.decode("utf-8") if e.stderr else ""

            return HookResult(
                hook_id=hook_id,
                command=hook_config.command,
                exit_code=-1,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                timestamp=timestamp,
                success=False,
                timed_out=True,
            )

    def run_hooks(self, hook_ids: list[str], hook_type: str = "pre") -> list[HookResult]:
        """
        Execute multiple hooks in sequence.

        Args:
            hook_ids: List of hook IDs to execute
            hook_type: Type of hooks being run (for logging/display)

        Returns:
            List of HookResult objects

        Raises:
            HookExecutionError: If a hook fails and should not continue
        """
        results = []

        for hook_id in hook_ids:
            # Get hook configuration
            hook_config = self.config.get_hook(hook_id)
            if not hook_config:
                # Create a failed result for missing hook
                result = HookResult(
                    hook_id=hook_id,
                    command="",
                    exit_code=-1,
                    stdout="",
                    stderr=f"Hook '{hook_id}' not found in configuration",
                    duration=0.0,
                    timestamp=datetime.now().isoformat(),
                    success=False,
                )
                results.append(result)

                # Missing hooks always fail
                raise HookExecutionError(f"Hook '{hook_id}' not found in configuration", result)

            # Execute the hook
            result = self.run_hook(hook_id, hook_config)
            results.append(result)

            # Check if hook failed
            if not result.success:
                # If continue_on_failure is False, raise error
                if not hook_config.continue_on_failure:
                    raise HookExecutionError(
                        f"Hook '{hook_id}' failed with exit code {result.exit_code}",
                        result,
                    )

        return results

    def run_pre_hooks(self, hook_ids: list[str]) -> list[HookResult]:
        """
        Execute pre-task hooks.

        Args:
            hook_ids: List of pre-hook IDs to execute

        Returns:
            List of HookResult objects

        Raises:
            HookExecutionError: If a hook fails and should not continue
        """
        return self.run_hooks(hook_ids, hook_type="pre")

    def run_post_hooks(self, hook_ids: list[str]) -> list[HookResult]:
        """
        Execute post-task hooks.

        Args:
            hook_ids: List of post-hook IDs to execute

        Returns:
            List of HookResult objects

        Raises:
            HookExecutionError: If a hook fails and should not continue
        """
        return self.run_hooks(hook_ids, hook_type="post")

    def save_hook_results(self, task_id: str, results: list[HookResult], hook_type: str) -> None:
        """
        Save hook results to log files.

        Args:
            task_id: The task identifier
            results: List of hook results
            hook_type: Type of hooks (pre/post)
        """
        # Create task log directory
        task_log_dir = self.log_dir / task_id
        task_log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file
        log_file = task_log_dir / f"{hook_type}.log"

        with open(log_file, "w") as f:
            f.write(f"=== {hook_type.upper()}-TASK HOOKS ===\n")
            f.write(f"Task: {task_id}\n")
            f.write(f"Total hooks: {len(results)}\n\n")

            for result in results:
                f.write(f"--- Hook: {result.hook_id} ---\n")
                f.write(f"Command: {result.command}\n")
                f.write(f"Timestamp: {result.timestamp}\n")
                f.write(f"Duration: {result.duration:.2f}s\n")
                f.write(f"Exit code: {result.exit_code}\n")
                f.write(f"Success: {result.success}\n")

                if result.timed_out:
                    f.write("Status: TIMED OUT\n")

                if result.stdout:
                    f.write(f"\nStdout:\n{result.stdout}\n")

                if result.stderr:
                    f.write(f"\nStderr:\n{result.stderr}\n")

                f.write("\n")
