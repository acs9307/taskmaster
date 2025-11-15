"""Task runner for sequential task execution."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from taskmaster.agent_client import AgentClient, AgentError, CompletionRequest
from taskmaster.change_applier import ChangeApplier
from taskmaster.models import Task, TaskList
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
        """
        self.task_list = task_list
        self.task_file = task_file
        self.dry_run = dry_run
        self.agent_client = agent_client
        self.provider_name = provider_name
        self.log_dir = log_dir or Path(".taskmaster") / "logs"
        self.auto_apply_changes = auto_apply_changes
        self.prompt_builder = PromptBuilder()

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
        click.echo("\n" + "=" * 60)
        click.secho("Starting TaskMaster Execution", fg="cyan", bold=True)
        click.echo("=" * 60)

        total_tasks = len(self.task_list.tasks)
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

        # Start from the current task index (for resume support)
        start_index = self.state.current_task_index
        for i in range(start_index, len(self.task_list.tasks)):
            task = self.task_list.tasks[i]
            task_num = i + 1

            # Skip if already completed
            if self.state.is_task_completed(task.id):
                click.echo("-" * 60)
                click.secho(
                    f"\n[SKIPPED] Task {task_num}/{total_tasks}: {task.title}",
                    fg="yellow",
                )
                click.echo(f"ID: {task.id}")
                click.echo("Task already completed in previous run")
                continue

            click.echo("-" * 60)
            success = self._run_task(task, task_num, total_tasks)

            if success:
                # Mark task as completed in state and save
                self.state.mark_task_completed(task.id)
                self.state.current_task_index = i + 1
                if not self.dry_run:
                    save_state(self.state)
            else:
                all_successful = False
                # Save state even on failure
                if not self.dry_run:
                    save_state(self.state)
                break

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
        # Display task header
        click.secho(f"\nTask {task_num}/{total_tasks}: {task.title}", fg="cyan", bold=True)
        click.echo(f"ID: {task.id}")
        click.echo(f"Description: {task.description}")
        click.echo(f"Path: {task.path}")

        if task.metadata:
            click.echo(f"Metadata: {task.metadata}")

        if task.pre_hooks:
            click.echo(f"Pre-hooks: {', '.join(task.pre_hooks)}")

        if task.post_hooks:
            click.echo(f"Post-hooks: {', '.join(task.post_hooks)}")

        # Mark task as running
        task.mark_running()
        click.echo(f"\nStatus: {task.status.value}")

        # Execute task
        click.echo()
        if self.dry_run:
            click.secho("[DRY RUN] Would execute task", fg="yellow")
            task.mark_completed()
            click.secho(f"\n✓ Task completed: {task.title}", fg="green")
            return True

        # Execute with agent if available
        if self.agent_client:
            return self._execute_with_agent(task)
        else:
            # No agent available - just mark as completed
            click.secho("⚙  No agent configured - marking as completed", fg="yellow")
            task.mark_completed()
            click.secho(f"\n✓ Task completed: {task.title}", fg="green")
            return True

    def _execute_with_agent(self, task: Task) -> bool:
        """
        Execute a task using the AI agent.

        Args:
            task: Task to execute

        Returns:
            True if task completed successfully, False otherwise
        """
        try:
            # Build prompt for the task
            click.secho("⚙  Building prompt...", fg="yellow")
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

            # Call agent
            click.secho(f"⚙  Calling agent ({self.provider_name})...", fg="yellow")
            response = self.agent_client.generate_completion(request)

            # Save response to log file
            self._save_response_log(task, prompt_components, response)

            # Display response summary
            click.echo(f"\n✓ Agent response received ({len(response.content)} chars)")
            click.echo(f"  Model: {response.model}")
            if response.usage:
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

            # Mark task as completed
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
    stop_on_failure: bool = False,
    provider: Optional[str] = None,
    resume: bool = False,
    auto_apply: bool = False,
) -> bool:
    """
    Run tasks from a task list file.

    Args:
        task_file: Path to task list file (YAML or JSON)
        dry_run: If True, preview execution without running
        stop_on_failure: If True, stop on first failure (currently unused)
        provider: Provider override (overrides active_provider from config)
        resume: If True, resume from saved state
        auto_apply: If True, automatically apply code changes from agent responses

    Returns:
        True if execution completed successfully, False otherwise
    """
    # Load task list
    click.echo(f"Loading task list from: {task_file}")
    try:
        task_list = load_task_list(task_file)
        click.secho(f"✓ Loaded {len(task_list.tasks)} tasks", fg="green")
    except Exception as e:
        click.secho(f"✗ Failed to load task list: {e}", fg="red")
        return False

    # Load configuration and create agent client (unless dry run)
    agent_client = None
    provider_name = None

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
