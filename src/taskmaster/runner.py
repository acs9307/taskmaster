"""Task runner for sequential task execution."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from taskmaster.agent_client import AgentClient, AgentError, CompletionRequest, RateLimitError
from taskmaster.change_applier import ChangeApplier
from taskmaster.config import Config
from taskmaster.git_utils import get_git_diff, has_changes
from taskmaster.hook_runner import HookExecutionError, HookRunner
from taskmaster.models import Task, TaskList, TaskStatus
from taskmaster.prompt_builder import PromptBuilder, PromptContext
from taskmaster.state import RunState, load_state, save_state
from taskmaster.task_parser import load_task_list


class TaskRunner:
    """
    Sequential task runner.

    Executes tasks in order, tracking progress and status.
    """

    def __init__(
        self,
        task_list: TaskList,
        task_file: Path,
        dry_run: bool = False,
        state: Optional[RunState] = None,
        agent_client: Optional[AgentClient] = None,
        provider_name: Optional[str] = None,
        log_dir: Optional[Path] = None,
        auto_apply_changes: bool = False,
        stop_on_first_failure: bool = False,
        ignore_config_limits: bool = False,
        config: Optional[Config] = None,
        quiet: bool = False,
    ):
        """
        Initialize task runner.

        Args:
            task_list: TaskList to execute
            task_file: Path to task list file (for state tracking)
            dry_run: If True, don't actually execute tasks
            state: Optional existing state to resume from
            agent_client: Optional AI agent client for task execution
            provider_name: Name of the provider being used
            log_dir: Directory to store agent response logs (defaults to .taskmaster/logs)
            auto_apply_changes: If True, automatically apply code changes from agent responses
            stop_on_first_failure: If True, prompt user immediately on first post-hook failure
            ignore_config_limits: If True, ignore configured rate limits (not recommended)
            config: Optional TaskMaster configuration (for hooks)
            quiet: If True, minimal output (useful for CI environments)
        """
        self.task_list = task_list
        self.task_file = task_file
        self.dry_run = dry_run
        self.agent_client = agent_client
        self.provider_name = provider_name
        self.log_dir = log_dir or Path(".taskmaster") / "logs"
        self.auto_apply_changes = auto_apply_changes
        self.stop_on_first_failure = stop_on_first_failure
        self.ignore_config_limits = ignore_config_limits
        self.config = config
        self.quiet = quiet
        self.prompt_builder = PromptBuilder()

        # Track task timings
        self.task_start_times = {}
        self.task_durations = {}

        # Initialize hook runner if config is available
        if config:
            self.hook_runner = HookRunner(config, log_dir=self.log_dir)
        else:
            self.hook_runner = None

        # Initialize or use provided state
        if state is None:
            self.state = RunState(task_file=str(task_file))
        else:
            self.state = state

    def run(self) -> bool:
        """
        Run all tasks sequentially.

        Returns:
            True if all tasks completed successfully, False otherwise
        """
        total_tasks = len(self.task_list.tasks)

        if self.quiet:
            # Quiet mode: minimal header
            click.echo(f"TaskMaster: Running {total_tasks} tasks")
            if self.dry_run:
                click.echo("[DRY RUN]")
        else:
            # Normal mode: rich header
            click.echo("\n" + "=" * 60)
            click.secho("Starting TaskMaster Execution", fg="cyan", bold=True)
            click.echo("=" * 60)

            click.echo(f"\nTotal tasks: {total_tasks}")

            # Show provider information if available
            if self.provider_name:
                click.echo(f"Provider: {self.provider_name}")
                if self.agent_client:
                    model = self.agent_client.get_model_name()
                    click.echo(f"Model: {model}")

            # Check if we're resuming
            if self.state.current_task_index > 0:
                completed = len(self.state.completed_task_ids)
                click.secho(
                    f"\n[RESUMING] Completed {completed}/{total_tasks} tasks",
                    fg="yellow",
                )

            if self.dry_run:
                click.secho("\n[DRY RUN MODE - No actual execution]", fg="yellow")

            click.echo()

        all_successful = True

        # Get max attempts from config
        max_attempts = self.config.max_attempts_per_task if self.config else 3

        try:
            # Start from the current task index (for resume support)
            start_index = self.state.current_task_index
            for i in range(start_index, len(self.task_list.tasks)):
                task = self.task_list.tasks[i]
                task_num = i + 1

                # Skip if already completed
                if self.state.is_task_completed(task.id):
                    if self.quiet:
                        click.secho(
                            f"[{task_num}/{total_tasks}] {task.title} - Skipped", fg="yellow"
                        )
                    else:
                        click.echo("-" * 60)
                        click.secho(
                            f"\n[SKIPPED] Task {task_num}/{total_tasks}: {task.title}",
                            fg="yellow",
                        )
                        click.echo(f"ID: {task.id}")
                        click.echo("Task already completed in previous run")
                    continue

                # Retry loop for failed tasks
                while True:
                    # Increment attempt counter
                    task.increment_attempt()
                    self.state.increment_attempt_count(task.id)

                    attempt_num = task.attempt_count

                    if not self.quiet:
                        click.echo("-" * 60)
                    if attempt_num > 1:
                        if self.quiet:
                            click.secho(
                                f"[{task_num}/{total_tasks}] {task.title} - Retry {attempt_num}/{max_attempts}",
                                fg="yellow",
                            )
                        else:
                            click.secho(
                                f"\n[RETRY {attempt_num}/{max_attempts}] Task {task_num}/{total_tasks}: {task.title}",
                                fg="yellow",
                                bold=True,
                            )

                    success = self._run_task(task, task_num, total_tasks)

                    if success:
                        # Mark task as completed in state and save
                        self.state.mark_task_completed(task.id)
                        self.state.current_task_index = i + 1
                        if not self.dry_run:
                            save_state(self.state)
                        break  # Exit retry loop on success
                    else:
                        # Task failed
                        self.state.increment_failure_count(task.id, "Task execution failed")

                        # Check if we should escalate to user intervention immediately
                        should_prompt = (
                            self.stop_on_first_failure and attempt_num == 1
                        ) or attempt_num >= max_attempts

                        if should_prompt:
                            # Either stop-on-first-failure mode or max attempts reached
                            # Escalate to user intervention
                            if self.stop_on_first_failure and attempt_num == 1:
                                click.secho(
                                    "\n⚠ Stop-on-first-failure mode: Task failed on first attempt",
                                    fg="yellow",
                                    bold=True,
                                )
                            user_choice = self._prompt_user_intervention(task, max_attempts)

                            # Record user intervention
                            self.state.record_user_intervention(task.id, user_choice)
                            if not self.dry_run:
                                save_state(self.state)

                            if user_choice == "retry":
                                click.secho("\n⚙  Retrying task once more...", fg="yellow")
                                # Reset for one more attempt
                                task.reset_for_retry()
                                # Continue to next iteration of retry loop
                            elif user_choice == "skip":
                                click.secho(f"\n⊘ Skipping task: {task.title}", fg="yellow")
                                task.mark_skipped()
                                if not self.dry_run:
                                    save_state(self.state)
                                break  # Exit retry loop, continue to next task
                            elif user_choice == "abort":
                                click.secho(
                                    "\n✗ Aborting execution as requested", fg="red", bold=True
                                )
                                all_successful = False
                                if not self.dry_run:
                                    save_state(self.state)
                                # Set success to False to trigger outer loop exit
                                success = False
                                break  # Exit retry loop
                        else:
                            # Normal retry logic (attempt_num < max_attempts and not stop_on_first_failure)
                            click.secho(
                                f"\n⚠ Task failed (attempt {attempt_num}/{max_attempts}), retrying...",
                                fg="yellow",
                            )
                            # Reset task for retry
                            task.reset_for_retry()
                            if not self.dry_run:
                                save_state(self.state)
                            # Continue to next iteration of retry loop

                # If task ultimately failed or aborted, stop execution
                # But allow continuing if task was skipped
                if not success and task.status != TaskStatus.SKIPPED:
                    break

        except KeyboardInterrupt:
            # User pressed Ctrl+C - save state before exiting
            click.echo("\n")
            click.secho("⚠ Interrupted by user (Ctrl+C)", fg="yellow", bold=True)
            click.echo("Saving state...")
            if not self.dry_run:
                save_state(self.state)
            click.secho("✓ State saved. You can resume by running with --resume", fg="green")
            return False

        # Display summary
        if self.quiet:
            # Quiet mode: minimal summary
            if all_successful:
                click.secho("✓ All tasks completed", fg="green")
            else:
                click.secho("✗ Execution failed", fg="red")
        else:
            # Normal mode: rich summary
            click.echo("\n" + "=" * 60)
            if all_successful:
                click.secho("✓ All tasks completed successfully!", fg="green", bold=True)
            else:
                click.secho("✗ Task execution stopped due to failure", fg="red", bold=True)
            click.echo("=" * 60 + "\n")

        return all_successful

    def _run_task(self, task: Task, task_num: int, total_tasks: int) -> bool:
        """
        Execute a single task.

        Args:
            task: Task to execute
            task_num: Current task number (1-indexed)
            total_tasks: Total number of tasks

        Returns:
            True if task completed successfully, False otherwise
        """
        # Start timing
        start_time = time.time()
        self.task_start_times[task.id] = start_time

        # Display task header
        if self.quiet:
            # Quiet mode: minimal output
            click.echo(f"[{task_num}/{total_tasks}] {task.title}")
        else:
            # Normal mode: rich output
            click.echo("\n" + "━" * 60)
            click.secho(f"Task {task_num}/{total_tasks}: {task.title}", fg="cyan", bold=True)
            click.echo(f"ID: {task.id}")
            click.echo(f"Description: {task.description}")
            if task.path:
                click.echo(f"Path: {task.path}")

            if task.metadata:
                click.echo(f"Metadata: {task.metadata}")

            if task.pre_hooks:
                click.echo(f"Pre-hooks: {', '.join(task.pre_hooks)}")

            if task.post_hooks:
                click.echo(f"Post-hooks: {', '.join(task.post_hooks)}")

        # Mark task as running
        task.mark_running()
        if not self.quiet:
            click.secho(f"\nStatus: ▶ {task.status.value}", fg="yellow")
            click.echo()

        # Execute task
        success = False
        if self.dry_run:
            if not self.quiet:
                click.secho("[DRY RUN] Would execute task", fg="yellow")
            task.mark_completed()
            success = True
        elif self.agent_client:
            success = self._execute_with_agent(task)
        else:
            # No agent available - just mark as completed
            if not self.quiet:
                click.secho("⚙  No agent configured - marking as completed", fg="yellow")
            task.mark_completed()
            success = True

        # Record timing
        end_time = time.time()
        duration = end_time - start_time
        self.task_durations[task.id] = duration

        # Display completion status with timing
        if success:
            if self.quiet:
                click.secho(f"  ✓ Completed ({duration:.1f}s)", fg="green")
            else:
                click.secho(
                    f"\n✓ Task completed: {task.title} ({duration:.1f}s)", fg="green", bold=True
                )
        else:
            if self.quiet:
                click.secho(f"  ✗ Failed ({duration:.1f}s)", fg="red")
            else:
                click.secho(f"\n✗ Task failed: {task.title} ({duration:.1f}s)", fg="red", bold=True)

        return success

    def _execute_with_agent(self, task: Task) -> bool:
        """
        Execute a task using the AI agent.

        Args:
            task: Task to execute

        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            # Run pre-hooks if configured
            pre_hooks = task.pre_hooks or (
                self.config.hook_defaults.pre_hooks if self.config else []
            )

            if pre_hooks and self.hook_runner:
                if not self.quiet:
                    click.secho(f"\n⚙  Running {len(pre_hooks)} pre-task hook(s)...", fg="yellow")

                try:
                    results = self.hook_runner.run_pre_hooks(pre_hooks)

                    # Display hook results
                    if not self.quiet:
                        for result in results:
                            if result.success:
                                click.secho(
                                    f"  ✓ {result.hook_id} ({result.duration:.1f}s)",
                                    fg="green",
                                )
                            else:
                                click.secho(f"  ✗ {result.hook_id} failed", fg="red")
                                if result.stderr:
                                    click.echo(f"    {result.stderr[:200]}")

                    # Save pre-hook results
                    self.hook_runner.save_hook_results(task.id, results, "pre")

                except HookExecutionError as e:
                    click.secho(f"\n✗ Pre-hook failed: {e}", fg="red")
                    click.echo(f"  Hook: {e.hook_result.hook_id}")
                    click.echo(f"  Exit code: {e.hook_result.exit_code}")

                    if e.hook_result.stderr:
                        click.echo(f"  Error: {e.hook_result.stderr[:500]}")

                    # Save failed hook results
                    self.hook_runner.save_hook_results(task.id, [e.hook_result], "pre")

                    task.mark_failed()
                    return False

            # Capture git diff before agent execution (for non-progress detection)
            diff_before = get_git_diff(Path.cwd())

            # Build prompt for the task
            if not self.quiet:
                click.secho("\n⚙  Building prompt...", fg="yellow")
            context = PromptContext(
                task=task,
                repo_path=Path.cwd(),
                include_git_status=True,
                include_file_snippets=False,
            )
            prompt_components = self.prompt_builder.build_prompt(context)

            # Create completion request
            request = CompletionRequest(
                prompt=prompt_components.to_full_prompt(),
                system_prompt=prompt_components.system_prompt,
            )

            # Check rate limits before calling agent (unless limits are disabled)
            if not self.ignore_config_limits and self.config and self.provider_name:
                provider_config = self.config.get_active_provider_config()
                if provider_config and provider_config.rate_limits:
                    # Estimate tokens (rough estimate based on prompt length)
                    estimated_tokens = len(request.prompt) // 4 + 1000

                    can_proceed, limit_type, next_reset = self.state.check_rate_limit(
                        self.provider_name, estimated_tokens, provider_config.rate_limits
                    )

                    if not can_proceed:
                        # Rate limit would be exceeded - save state and exit gracefully
                        from taskmaster.state import save_state

                        save_state(self.state)

                        # Format next reset time
                        reset_str = next_reset.strftime("%Y-%m-%d %H:%M UTC")

                        click.echo()
                        click.secho("⚠ RATE LIMIT REACHED", fg="yellow", bold=True)
                        click.echo("=" * 60)
                        click.echo(f"Limit type: {limit_type}")
                        click.echo(f"Provider: {self.provider_name}")
                        click.echo(f"Safe to re-run after: {reset_str}")
                        click.echo()
                        click.echo("State has been saved. You can resume by running:")
                        click.secho("  taskmaster run <task-file> --resume", fg="cyan")
                        click.echo("=" * 60)

                        # Exit gracefully - the run will fail but state is saved
                        return False

            # Call agent with retry logic for rate limit errors
            if not self.quiet:
                click.secho(f"⚙  Calling agent ({self.provider_name})...", fg="yellow")

            max_retries = self.config.max_rate_limit_retries if self.config else 5
            max_backoff = self.config.max_backoff_seconds if self.config else 300
            retry_count = 0
            base_backoff = 2  # Start with 2 seconds

            while True:
                try:
                    response = self.agent_client.generate_completion(request)

                    # Success - break out of retry loop
                    if retry_count > 0:
                        click.secho(f"  ✓ Call succeeded after {retry_count} retries", fg="green")
                    break

                except RateLimitError as e:
                    retry_count += 1

                    if retry_count > max_retries:
                        # Exceeded max retries - give up
                        click.echo()
                        click.secho("⚠ RATE LIMIT EXCEEDED", fg="red", bold=True)
                        click.echo("=" * 60)
                        click.echo(f"Provider: {self.provider_name}")
                        click.echo(f"Retries attempted: {retry_count - 1}")
                        click.echo()
                        click.echo("The API rate limit has been exceeded and automatic")
                        click.echo("retries have been exhausted. Please try again later.")
                        click.echo()
                        if e.retry_after:
                            click.echo(f"Provider suggests waiting {e.retry_after} seconds")
                        click.echo("=" * 60)

                        # Save state before exiting
                        from taskmaster.state import save_state

                        save_state(self.state)

                        raise  # Re-raise to be caught by outer exception handler

                    # Calculate backoff time
                    if e.retry_after:
                        # Respect Retry-After header from provider
                        wait_time = min(e.retry_after, max_backoff)
                        click.secho(
                            f"  ⚠ Rate limit hit. Retrying in {wait_time}s (from Retry-After header)",
                            fg="yellow",
                        )
                    else:
                        # Exponential backoff: 2, 4, 8, 16, 32, ... (capped at max_backoff)
                        wait_time = min(base_backoff * (2 ** (retry_count - 1)), max_backoff)
                        click.secho(
                            f"  ⚠ Rate limit hit. Retrying in {wait_time}s (attempt {retry_count}/{max_retries})",
                            fg="yellow",
                        )

                    time.sleep(wait_time)

            # Record usage after successful call
            if self.provider_name and response:
                # Estimate tokens used (rough estimate)
                tokens_used = len(request.prompt) // 4 + len(response.content) // 4
                self.state.record_usage(self.provider_name, tokens=tokens_used, requests=1)

            # Save response to log file
            self._save_response_log(task, prompt_components, response)

            # Display response summary
            if not self.quiet:
                click.echo(f"\n✓ Agent response received ({len(response.content)} chars)")
                click.echo(f"  Model: {response.model}")
            if not self.quiet and response.usage:
                click.echo(f"  Tokens: {response.usage.get('total_tokens', 'N/A')}")

            # Apply changes if auto-apply is enabled
            if self.auto_apply_changes:
                click.secho("\n⚙  Auto-applying changes from agent response...", fg="yellow")
                applier = ChangeApplier(dry_run=self.dry_run, working_dir=Path.cwd())
                success_count, fail_count = applier.apply_all_changes(response.content)

                if success_count > 0 or fail_count > 0:
                    click.echo(f"\n  Applied {success_count} changes, {fail_count} failed")
                else:
                    click.echo("  No code changes found in response")

            # Capture git diff after code application (for non-progress detection)
            diff_after = get_git_diff(Path.cwd())

            # Run post-hooks if configured
            post_hooks = task.post_hooks or (
                self.config.hook_defaults.post_hooks if self.config else []
            )

            if post_hooks and self.hook_runner:
                if not self.quiet:
                    click.secho(f"\n⚙  Running {len(post_hooks)} post-task hook(s)...", fg="yellow")

                try:
                    results = self.hook_runner.run_post_hooks(post_hooks)

                    # Display hook results
                    if not self.quiet:
                        for result in results:
                            if result.success:
                                click.secho(
                                    f"  ✓ {result.hook_id} ({result.duration:.1f}s)",
                                    fg="green",
                                )
                            else:
                                click.secho(f"  ✗ {result.hook_id} failed", fg="red")
                                if result.stderr:
                                    click.echo(f"    {result.stderr[:200]}")

                    # Save post-hook results
                    self.hook_runner.save_hook_results(task.id, results, "post")

                except HookExecutionError as e:
                    click.secho(f"\n✗ Post-hook failed: {e}", fg="red")
                    click.echo(f"  Hook: {e.hook_result.hook_id}")
                    click.echo(f"  Exit code: {e.hook_result.exit_code}")

                    if e.hook_result.stderr:
                        click.echo(f"  Error: {e.hook_result.stderr[:500]}")

                    # Save failed hook results
                    self.hook_runner.save_hook_results(task.id, [e.hook_result], "post")

                    # Detect non-progress: if no code changes were made but tests still fail
                    if not has_changes(diff_before, diff_after):
                        self.state.increment_non_progress_count(task.id)
                        non_progress = self.state.get_non_progress_count(task.id)
                        click.secho(
                            f"  ⚠ Non-progress detected: No code changes made (count: {non_progress})",
                            fg="yellow",
                        )

                    task.mark_failed()
                    return False

            # Mark task as completed (only if all hooks passed)
            task.mark_completed()
            click.secho(f"\n✓ Task completed: {task.title}", fg="green")

            return True

        except AgentError as e:
            # Handle agent-specific errors
            click.secho(f"\n✗ Agent error: {e}", fg="red")

            if e.is_retryable():
                click.secho("  → This error is retryable", fg="yellow")
            else:
                click.secho("  → This error is not retryable", fg="red")

            task.mark_failed()
            return False

        except Exception as e:
            # Handle unexpected errors
            click.secho(f"\n✗ Unexpected error: {e}", fg="red")
            task.mark_failed()
            return False

    def _prompt_user_intervention(self, task: Task, max_attempts: int) -> str:
        """
        Prompt user for intervention when task repeatedly fails.

        Args:
            task: The task that failed
            max_attempts: Maximum attempts configured

        Returns:
            User's choice: 'retry', 'skip', or 'abort'
        """
        click.echo("\n" + "=" * 60)
        click.secho("⚠ MANUAL INTERVENTION REQUIRED", fg="red", bold=True)
        click.echo("=" * 60)

        click.echo(f"\nTask: {task.title}")
        click.echo(f"ID: {task.id}")
        click.echo(f"Status: Failed after {max_attempts} attempts")

        # Display attempt summary
        click.echo("\nAttempt Summary:")
        click.echo(f"  Total attempts: {task.attempt_count}")
        click.echo(f"  Failures: {task.failure_count}")

        # Display non-progress count if any
        non_progress = self.state.get_non_progress_count(task.id)
        if non_progress > 0:
            click.secho(
                f"  Non-progress attempts: {non_progress} (no code changes made)",
                fg="yellow",
            )

        # Display last error if available
        last_error = self.state.get_last_error(task.id)
        if last_error:
            click.echo(f"\nLast error: {last_error}")

        # Display options
        click.echo("\n" + "-" * 60)
        click.echo("What would you like to do?")
        click.echo("  [R]etry - Try this task one more time")
        click.echo("  [S]kip  - Skip this task and continue with next task")
        click.echo("  [A]bort - Stop execution and exit")
        click.echo("-" * 60)

        # Get user input
        while True:
            choice = click.prompt(
                "\nYour choice",
                type=click.Choice(["R", "r", "S", "s", "A", "a"], case_sensitive=False),
                show_choices=False,
            ).upper()

            if choice == "R":
                return "retry"
            elif choice == "S":
                return "skip"
            elif choice == "A":
                return "abort"

    def _save_response_log(self, task: Task, prompt_components, response) -> None:
        """
        Save agent response to a log file.

        Args:
            task: The task that was executed
            prompt_components: The prompt components used
            response: The agent response
        """
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{task.id}_{timestamp}.json"
        log_path = self.log_dir / log_filename

        # Prepare log data
        log_data = {
            "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "path": task.path,
                "metadata": task.metadata,
            },
            "prompt": {
                "system_prompt": prompt_components.system_prompt,
                "task_description": prompt_components.task_description,
                "context": prompt_components.context,
                "constraints": prompt_components.constraints,
                "full_prompt": prompt_components.to_full_prompt(),
            },
            "response": {
                "content": response.content,
                "model": response.model,
                "usage": response.usage,
                "finish_reason": response.finish_reason,
                "metadata": response.metadata,
            },
            "execution": {
                "timestamp": timestamp,
                "provider": self.provider_name,
            },
        }

        # Write log file
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        click.echo(f"  Log saved: {log_path}")

    def get_summary(self) -> dict:
        """
        Get execution summary.

        Returns:
            Dictionary with execution statistics
        """
        completed = self.task_list.get_completed_tasks()
        pending = self.task_list.get_pending_tasks()
        failed = self.task_list.get_failed_tasks()

        return {
            "total": len(self.task_list.tasks),
            "completed": len(completed),
            "pending": len(pending),
            "failed": len(failed),
        }


def run_tasks(
    task_file: Path,
    dry_run: bool = False,
    stop_on_first_failure: bool = False,
    provider: Optional[str] = None,
    resume: bool = False,
    auto_apply: bool = False,
    ignore_config_limits: bool = False,
    quiet: bool = False,
) -> bool:
    """
    Run tasks from a task list file.

    Args:
        task_file: Path to task list file (YAML or JSON)
        dry_run: If True, preview execution without running
        stop_on_first_failure: If True, prompt user immediately on first post-hook failure (no retries)
        provider: Provider override (overrides active_provider from config)
        resume: If True, resume from saved state
        auto_apply: If True, automatically apply code changes from agent responses
        ignore_config_limits: If True, ignore configured rate limits (not recommended)
        quiet: If True, minimal output (useful for CI environments)

    Returns:
        True if execution completed successfully, False otherwise
    """
    # Load task list
    if not quiet:
        click.echo(f"Loading task list from: {task_file}")
    try:
        task_list = load_task_list(task_file)
        if not quiet:
            click.secho(f"✓ Loaded {len(task_list.tasks)} tasks", fg="green")
    except Exception as e:
        click.secho(f"✗ Failed to load task list: {e}", fg="red")
        return False

    # Load configuration and create agent client (unless dry run)
    agent_client = None
    provider_name = None
    config = None

    if not dry_run:
        try:
            from taskmaster.config_loader import load_config
            from taskmaster.provider_factory import ProviderError, get_agent_client

            # Load configuration
            config = load_config()

            # Validate configuration
            validation_errors = config.validate()
            if validation_errors:
                click.secho("✗ Configuration validation failed:", fg="red")
                for error in validation_errors:
                    click.secho(f"  - {error}", fg="red")
                return False

            # Get agent client for the specified provider
            try:
                provider_name, agent_client = get_agent_client(config, provider)
                if not quiet:
                    click.secho(f"✓ Initialized provider: {provider_name}", fg="green")
            except ProviderError as e:
                click.secho(f"✗ Provider configuration error: {e}", fg="red")
                return False

        except Exception as e:
            click.secho(f"✗ Failed to load configuration: {e}", fg="red")
            click.echo(
                "\nHint: Create a configuration file at ~/.taskmaster/config.yml or ./.taskmaster.yml"
            )
            return False

    # Load or create state
    state = None
    if resume or not dry_run:
        try:
            state = load_state()
            if state:
                # Verify state matches current task file
                if state.task_file != str(task_file):
                    click.secho(
                        f"⚠ Warning: Existing state is for {state.task_file}, "
                        f"but running {task_file}",
                        fg="yellow",
                    )
                    if not resume:
                        # Start fresh if not explicitly resuming
                        state = None
                else:
                    if not quiet:
                        click.secho("✓ Loaded existing state", fg="green")
        except Exception as e:
            click.secho(f"⚠ Warning: Failed to load state: {e}", fg="yellow")

    # Create and run task runner
    runner = TaskRunner(
        task_list,
        task_file,
        dry_run=dry_run,
        state=state,
        agent_client=agent_client,
        provider_name=provider_name,
        auto_apply_changes=auto_apply,
        stop_on_first_failure=stop_on_first_failure,
        ignore_config_limits=ignore_config_limits,
        config=config,
        quiet=quiet,
    )
    success = runner.run()

    # Display summary
    summary = runner.get_summary()
    click.echo("\nExecution Summary:")
    click.echo(f"  Total tasks: {summary['total']}")
    click.secho(f"  Completed: {summary['completed']}", fg="green")
    click.echo(f"  Pending: {summary['pending']}")
    if summary["failed"] > 0:
        click.secho(f"  Failed: {summary['failed']}", fg="red")

    return success
