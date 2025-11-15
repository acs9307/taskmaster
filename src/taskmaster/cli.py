"""Command-line interface for TaskMaster."""

from pathlib import Path
from typing import Optional

import click

from taskmaster.config_loader import load_config, validate_config_file


@click.group()
@click.version_option(version="0.1.0", prog_name="taskmaster")
def main():
    """
    TaskMaster - AI-powered task orchestration and automation tool.

    Execute tasks using AI agents with support for hooks, dependencies,
    failure handling, and rate limiting.
    """
    pass


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
