"""Command-line interface for TaskMaster."""

from pathlib import Path
from typing import Optional

import click

from taskmaster.config_loader import load_config, validate_config_file


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
    "--stop-on-failure",
    is_flag=True,
    help="Stop immediately on first task failure",
)
@click.option(
    "--provider",
    "-p",
    help="Override the active provider from config",
)
@click.pass_context
def run(
    ctx, task_file: Path, dry_run: bool, stop_on_failure: bool, provider: Optional[str]
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
      taskmaster run tasks.yml --stop-on-failure
      taskmaster run tasks.yml --provider openai
    """
    click.echo(f"Running tasks from: {task_file}")

    if dry_run:
        click.secho("DRY RUN MODE - No tasks will be executed", fg="yellow", bold=True)

    if provider:
        click.echo(f"Using provider: {provider}")

    # TODO: Implement task runner (Task 1.3)
    # For now, just acknowledge the command
    click.secho(
        "\n⚠ Task runner not yet implemented (coming in Task 1.3)", fg="yellow"
    )
    click.echo("\nPlanned execution flow:")
    click.echo("  1. Load and parse task file")
    click.echo("  2. Load configuration")
    click.echo("  3. Initialize state tracking")
    click.echo("  4. Execute tasks sequentially")
    click.echo("  5. Run pre/post hooks")
    click.echo("  6. Handle failures and retries")
    click.echo("  7. Save progress state")


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

    # TODO: Implement status display (Task 1.4)
    # For now, show placeholder
    click.secho("\n⚠ Status tracking not yet implemented (coming in Task 1.4)", fg="yellow")
    click.echo("\nPlanned status display:")
    click.echo("  • Total tasks: 0")
    click.echo("  • Completed: 0")
    click.echo("  • Pending: 0")
    click.echo("  • Failed: 0")
    click.echo("  • Current task: None")
    click.echo("\nNo active task execution found.")

    if verbose:
        click.echo("\nVerbose mode would show:")
        click.echo("  - Full task details")
        click.echo("  - Execution logs")
        click.echo("  - Failure messages")
        click.echo("  - Hook output")


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

    if provider:
        click.echo(f"Using provider: {provider}")

    # TODO: Implement resume logic (Task 1.4 + Task 7.2)
    # For now, show placeholder
    click.secho(
        "\n⚠ Resume functionality not yet implemented (coming in Task 7.2)", fg="yellow"
    )
    click.echo("\nPlanned resume flow:")
    click.echo("  1. Load saved state from .agent-runner/state.json")
    click.echo("  2. Validate state consistency")
    click.echo("  3. Load task list and configuration")
    click.echo("  4. Continue from last incomplete task")
    click.echo("  5. Preserve failure counts and metadata")
    click.echo("\nNo saved state found.")


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
def validate_config(
    global_config: Optional[Path], project_config: Optional[Path]
) -> None:
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
        click.echo(
            f"Max Consecutive Failures: {merged_config.max_consecutive_failures}"
        )

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
            click.echo(
                f"\nDefault Test Command: {merged_config.hook_defaults.test_command}"
            )
        if merged_config.hook_defaults.lint_command:
            click.echo(
                f"Default Lint Command: {merged_config.hook_defaults.lint_command}"
            )

    except Exception as e:
        click.secho(f"Error loading configuration: {e}", fg="red")
        raise click.exceptions.Exit(1) from e


if __name__ == "__main__":
    main()
