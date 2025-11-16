"""Command-line interface for TaskMaster."""

from pathlib import Path
from typing import Optional

import click

from taskmaster.config_loader import load_config, validate_config_file
from taskmaster.runner import run_tasks
from taskmaster.state import load_state


@click.group()
@click.version_option(version="0.1.0", prog_name="taskmaster")
@click.pass_context
def main(ctx):
    """
    TaskMaster - AI-powered task orchestration and automation tool.

    Execute tasks using AI agents with support for hooks, dependencies,
    failure handling, and rate limiting.

    \b
    Common Commands:
      taskmaster run <task-file>     Run tasks from a task list file
      taskmaster status              Show current queue and progress
      taskmaster resume              Resume interrupted task execution
      taskmaster config validate     Validate configuration

    \b
    Examples:
      taskmaster run tasks.yml       Execute tasks from tasks.yml
      taskmaster run tasks.json      Execute tasks from tasks.json
      taskmaster status              Check current task progress
      taskmaster resume              Continue from where you left off
    """
    # Ensure context object exists for subcommands
    ctx.ensure_object(dict)


@main.command()
@click.argument("task_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be executed without running tasks",
)
@click.option(
    "--stop-on-first-failure",
    is_flag=True,
    help="Stop and prompt user on first post-hook failure (no automatic retries)",
)
@click.option(
    "--provider",
    "-p",
    help="Override the active provider from config",
)
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    help="Resume from saved state if available",
)
@click.option(
    "--auto-apply",
    "-a",
    is_flag=True,
    help="Automatically apply code changes from agent responses",
)
@click.option(
    "--ignore-config-limits",
    is_flag=True,
    help="Ignore configured rate limits (not recommended)",
)
@click.pass_context
def run(
    ctx,
    task_file: Path,
    dry_run: bool,
    stop_on_first_failure: bool,
    provider: Optional[str],
    resume: bool,
    auto_apply: bool,
    ignore_config_limits: bool,
) -> None:
    """
    Run tasks from a task list file.

    Executes tasks sequentially from the specified YAML or JSON file.
    Tasks are run using the configured AI agent provider with support
    for pre/post hooks, dependency checking, and failure handling.

    \b
    TASK_FILE: Path to YAML or JSON file containing task list

    \b
    Examples:
      taskmaster run tasks.yml
      taskmaster run tasks.json --dry-run
      taskmaster run tasks.yml --stop-on-first-failure
      taskmaster run tasks.yml --provider openai
    """
    # Run tasks using the task runner
    success = run_tasks(
        task_file=task_file,
        dry_run=dry_run,
        stop_on_first_failure=stop_on_first_failure,
        provider=provider,
        resume=resume,
        auto_apply=auto_apply,
        ignore_config_limits=ignore_config_limits,
    )

    # Exit with appropriate code
    if not success:
        raise click.exceptions.Exit(1)


@main.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed task information",
)
@click.pass_context
def status(ctx, verbose: bool) -> None:
    """
    Show current task queue and progress.

    Displays the status of all tasks including completed, running,
    pending, and failed tasks. Also shows progress statistics and
    any error messages.

    \b
    Examples:
      taskmaster status           Show basic status
      taskmaster status -v        Show detailed status with logs
    """
    click.echo("TaskMaster Status")
    click.echo("=" * 50)

    # Load state
    state = load_state()

    if state is None:
        click.echo("\nNo active task execution found.")
        click.secho("Run 'taskmaster run <task-file>' to start.", fg="cyan")
        return

    # Display basic information
    click.echo(f"\nTask File: {state.task_file}")
    click.echo(f"Created: {state.created_at}")
    click.echo(f"Updated: {state.updated_at}")

    # Load task list to get total count
    try:
        from taskmaster.task_parser import load_task_list

        task_list = load_task_list(Path(state.task_file))
        total_tasks = len(task_list.tasks)
        completed_count = len(state.completed_task_ids)
        pending_count = total_tasks - completed_count

        click.echo(f"\nProgress: {completed_count}/{total_tasks} tasks completed")
        click.echo(f"  Completed: {completed_count}")
        click.echo(f"  Pending: {pending_count}")

        if state.current_task_index < total_tasks:
            current_task = task_list.tasks[state.current_task_index]
            click.echo(f"\nCurrent/Next Task: {current_task.title} (ID: {current_task.id})")
        else:
            click.secho("\n✓ All tasks completed!", fg="green")

        # Show failures if any
        if state.failure_counts:
            click.echo("\nFailure Counts:")
            for task_id, count in state.failure_counts.items():
                click.secho(f"  {task_id}: {count} failure(s)", fg="red")

        # Verbose mode
        if verbose:
            click.echo("\nCompleted Tasks:")
            for task_id in state.completed_task_ids:
                # Find task by ID
                task = next((t for t in task_list.tasks if t.id == task_id), None)
                if task:
                    click.secho(f"  ✓ {task.title} (ID: {task_id})", fg="green")
                else:
                    click.secho(f"  ✓ {task_id}", fg="green")

            if state.last_errors:
                click.echo("\nLast Errors:")
                for task_id, error in state.last_errors.items():
                    click.echo(f"  {task_id}:")
                    click.secho(f"    {error}", fg="red")

    except Exception as e:
        click.secho(f"\n⚠ Warning: Could not load task list: {e}", fg="yellow")
        click.echo("\nRaw state information:")
        click.echo(f"  Completed task IDs: {', '.join(state.completed_task_ids)}")
        click.echo(f"  Current task index: {state.current_task_index}")
        if state.failure_counts:
            click.echo(f"  Failure counts: {state.failure_counts}")


@main.command()
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force resume even if state appears inconsistent",
)
@click.option(
    "--provider",
    "-p",
    help="Override the active provider from config",
)
@click.pass_context
def resume(ctx, force: bool, provider: Optional[str]) -> None:
    """
    Resume task execution after interruption.

    Continues executing tasks from where the last run stopped.
    This works after rate limit pauses, user interruptions (Ctrl+C),
    failures requiring manual intervention, or system crashes.

    The resume command uses the saved state file to determine which
    task to continue from and preserves all failure counts and
    progress information.

    \b
    Examples:
      taskmaster resume           Resume from saved state
      taskmaster resume --force   Resume even with inconsistent state
      taskmaster resume -p claude Override provider for this run
    """
    click.echo("Resuming task execution...")

    if force:
        click.secho("Force mode enabled - ignoring state warnings", fg="yellow")

    # Load state
    state = load_state()

    if state is None:
        click.secho("\n✗ No saved state found", fg="red")
        click.echo("Nothing to resume. Run 'taskmaster run <task-file>' to start a new execution.")
        raise click.exceptions.Exit(1)

    # Get task file from state
    task_file = Path(state.task_file)

    if not task_file.exists():
        click.secho(f"\n✗ Task file not found: {task_file}", fg="red")
        if not force:
            click.echo("The task file from the saved state doesn't exist.")
            click.echo(
                "Use --force to ignore this error, or run 'taskmaster run' with a new task file."
            )
            raise click.exceptions.Exit(1)
        else:
            click.secho("Continuing anyway due to --force flag", fg="yellow")

    click.secho(f"✓ Found saved state for: {task_file}", fg="green")
    click.echo(f"Completed: {len(state.completed_task_ids)} tasks")
    click.echo(f"Resuming from task index: {state.current_task_index}")

    # Resume execution
    success = run_tasks(
        task_file=task_file,
        dry_run=False,
        stop_on_failure=False,
        provider=provider,
        resume=True,
    )

    # Exit with appropriate code
    if not success:
        raise click.exceptions.Exit(1)


@main.group()
def config():
    """Manage TaskMaster configuration."""
    pass


@config.command("validate")
@click.option(
    "--global-config",
    "-g",
    type=click.Path(exists=True, path_type=Path),
    help="Path to global config file (default: ~/.taskmaster/config.yml)",
)
@click.option(
    "--project-config",
    "-p",
    type=click.Path(exists=True, path_type=Path),
    help="Path to project config file (default: ./.taskmaster.yml)",
)
def validate_config(global_config: Optional[Path], project_config: Optional[Path]) -> None:
    """
    Validate configuration files.

    Checks global and/or project configuration for errors.
    """
    from taskmaster.config import get_default_config_path, get_project_config_path

    # Determine which configs to validate
    if global_config is None:
        global_config = get_default_config_path()
    if project_config is None:
        project_config = get_project_config_path()

    has_errors = False

    # Validate global config
    if global_config.exists():
        click.echo(f"Validating global config: {global_config}")
        is_valid, errors = validate_config_file(global_config)
        if is_valid:
            click.secho("  ✓ Global config is valid", fg="green")
        else:
            click.secho("  ✗ Global config has errors:", fg="red")
            for error in errors:
                click.secho(f"    - {error}", fg="red")
            has_errors = True
    else:
        click.secho(f"  ⚠ Global config not found: {global_config}", fg="yellow")

    # Validate project config
    if project_config.exists():
        click.echo(f"\nValidating project config: {project_config}")
        is_valid, errors = validate_config_file(project_config)
        if is_valid:
            click.secho("  ✓ Project config is valid", fg="green")
        else:
            click.secho("  ✗ Project config has errors:", fg="red")
            for error in errors:
                click.secho(f"    - {error}", fg="red")
            has_errors = True
    else:
        click.secho(f"  ⚠ Project config not found: {project_config}", fg="yellow")

    # Try to load merged config
    click.echo("\nLoading merged configuration...")
    try:
        merged_config = load_config(global_config, project_config)
        validation_errors = merged_config.validate()

        if validation_errors:
            click.secho("  ✗ Merged config has errors:", fg="red")
            for error in validation_errors:
                click.secho(f"    - {error}", fg="red")
            has_errors = True
        else:
            click.secho("  ✓ Merged config is valid", fg="green")
            click.echo(f"\nActive provider: {merged_config.active_provider}")

            provider_config = merged_config.get_active_provider_config()
            if provider_config:
                api_key = provider_config.get_api_key()
                if api_key:
                    click.secho("  ✓ API key is configured", fg="green")
                else:
                    click.secho("  ✗ API key is not configured", fg="red")
                    has_errors = True

    except Exception as e:
        click.secho(f"  ✗ Failed to load merged config: {e}", fg="red")
        has_errors = True

    # Exit with appropriate code
    if has_errors:
        click.echo("\n" + "=" * 50)
        click.secho("Configuration validation FAILED", fg="red", bold=True)
        raise click.exceptions.Exit(1)
    else:
        click.echo("\n" + "=" * 50)
        click.secho("Configuration validation PASSED", fg="green", bold=True)


@config.command("show")
@click.option(
    "--global-config",
    "-g",
    type=click.Path(exists=True, path_type=Path),
    help="Path to global config file",
)
@click.option(
    "--project-config",
    "-p",
    type=click.Path(exists=True, path_type=Path),
    help="Path to project config file",
)
def show_config(global_config: Optional[Path], project_config: Optional[Path]) -> None:
    """Display the current merged configuration."""
    try:
        merged_config = load_config(global_config, project_config)

        click.echo("Current TaskMaster Configuration")
        click.echo("=" * 50)
        click.echo(f"Active Provider: {merged_config.active_provider}")
        click.echo(f"State Directory: {merged_config.state_dir}")
        click.echo(f"Log Directory: {merged_config.log_dir}")
        click.echo(f"Max Attempts Per Task: {merged_config.max_attempts_per_task}")
        click.echo(f"Max Consecutive Failures: {merged_config.max_consecutive_failures}")

        click.echo("\nConfigured Providers:")
        for name, provider_cfg in merged_config.provider_configs.items():
            active = " (active)" if name == merged_config.active_provider else ""
            click.echo(f"  - {name}{active}")
            click.echo(f"      Type: {provider_cfg.provider.value}")
            if provider_cfg.model:
                click.echo(f"      Model: {provider_cfg.model}")
            api_key = provider_cfg.get_api_key()
            if api_key:
                # Mask the API key for security
                masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
                click.echo(f"      API Key: {masked}")

        if merged_config.hook_defaults.test_command:
            click.echo(f"\nDefault Test Command: {merged_config.hook_defaults.test_command}")
        if merged_config.hook_defaults.lint_command:
            click.echo(f"Default Lint Command: {merged_config.hook_defaults.lint_command}")

    except Exception as e:
        click.secho(f"Error loading configuration: {e}", fg="red")
        raise click.exceptions.Exit(1) from e


if __name__ == "__main__":
    main()
