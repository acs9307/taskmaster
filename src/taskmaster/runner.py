"""Task runner for sequential task execution."""

from pathlib import Path
from typing import Optional

import click

from taskmaster.models import TaskList
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
    ):
        """
        Initialize task runner.

        Args:
            task_list: TaskList to execute
            task_file: Path to task list file (for state tracking)
            dry_run: If True, don't actually execute tasks
            state: Optional existing state to resume from
        """
        self.task_list = task_list
        self.task_file = task_file
        self.dry_run = dry_run

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

    def _run_task(self, task, task_num: int, total_tasks: int) -> bool:
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

        # Simulate task execution
        click.echo()
        if not self.dry_run:
            click.secho("⚙  Executing task...", fg="yellow")
            # TODO: In Task 2.x and 3.x, this will call the actual agent
            click.echo("   → Would call AI agent to execute this task")
            click.echo("   → Agent would receive task description and context")
            click.echo("   → Agent would perform the required work")
        else:
            click.secho("[DRY RUN] Would execute task", fg="yellow")

        # For now, always succeed (no actual execution yet)
        task.mark_completed()
        click.secho(f"\n✓ Task completed: {task.title}", fg="green")

        return True

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
) -> bool:
    """
    Run tasks from a task list file.

    Args:
        task_file: Path to task list file (YAML or JSON)
        dry_run: If True, preview execution without running
        stop_on_failure: If True, stop on first failure (currently unused)
        provider: Provider override (currently unused)
        resume: If True, resume from saved state

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
    runner = TaskRunner(task_list, task_file, dry_run=dry_run, state=state)
    success = runner.run()

    # Display summary
    summary = runner.get_summary()
    click.echo("\nExecution Summary:")
    click.echo(f"  Total tasks: {summary['total']}")
    click.secho(f"  Completed: {summary['completed']}", fg="green")
    click.echo(f"  Pending: {summary['pending']}")
    if summary['failed'] > 0:
        click.secho(f"  Failed: {summary['failed']}", fg="red")

    return success
