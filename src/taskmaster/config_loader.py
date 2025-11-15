"""Configuration file loading and merging."""

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from taskmaster.config import (
    Config,
    HookDefaults,
    Provider,
    ProviderConfig,
    RateLimitConfig,
    get_default_config_path,
    get_project_config_path,
)


class ConfigLoadError(Exception):
    """Raised when configuration cannot be loaded."""

    pass


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load a YAML configuration file.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed configuration dictionary

    Raises:
        ConfigLoadError: If the file cannot be loaded
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise ConfigLoadError(f"{path}: Root element must be a dictionary")
            return data
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Failed to parse YAML file {path}: {e}") from e
    except Exception as e:
        raise ConfigLoadError(f"Failed to load config file {path}: {e}") from e


def load_json_file(path: Path) -> dict[str, Any]:
    """
    Load a JSON configuration file.

    Args:
        path: Path to the JSON file

    Returns:
        Parsed configuration dictionary

    Raises:
        ConfigLoadError: If the file cannot be loaded
    """
    try:
        with open(path) as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ConfigLoadError(f"{path}: Root element must be a dictionary")
            return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ConfigLoadError(f"Failed to parse JSON file {path}: {e}") from e
    except Exception as e:
        raise ConfigLoadError(f"Failed to load config file {path}: {e}") from e


def load_config_file(path: Path) -> dict[str, Any]:
    """
    Load a configuration file (YAML or JSON based on extension).

    Args:
        path: Path to the config file

    Returns:
        Parsed configuration dictionary

    Raises:
        ConfigLoadError: If the file cannot be loaded
    """
    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    if suffix in [".yml", ".yaml"]:
        return load_yaml_file(path)
    elif suffix == ".json":
        return load_json_file(path)
    else:
        raise ConfigLoadError(
            f"Unsupported config file format: {suffix}. Use .yml, .yaml, or .json"
        )


def parse_rate_limits(data: dict[str, Any]) -> RateLimitConfig:
    """Parse rate limit configuration from dictionary."""
    return RateLimitConfig(
        max_tokens_hour=data.get("max_tokens_hour"),
        max_tokens_day=data.get("max_tokens_day"),
        max_tokens_week=data.get("max_tokens_week"),
        max_requests_minute=data.get("max_requests_minute"),
    )


def parse_provider_config(name: str, data: dict[str, Any]) -> ProviderConfig:
    """
    Parse provider configuration from dictionary.

    Args:
        name: Provider name
        data: Configuration dictionary

    Returns:
        ProviderConfig object

    Raises:
        ConfigLoadError: If configuration is invalid
    """
    # Parse provider type
    provider_str = data.get("provider", name)
    try:
        provider = Provider(provider_str.lower())
    except ValueError:
        provider = Provider.OTHER

    # Parse rate limits if present
    rate_limits_data = data.get("rate_limits", {})
    rate_limits = parse_rate_limits(rate_limits_data)

    return ProviderConfig(
        provider=provider,
        api_key=data.get("api_key"),
        api_key_env=data.get("api_key_env"),
        model=data.get("model"),
        base_url=data.get("base_url"),
        rate_limits=rate_limits,
        max_tokens=data.get("max_tokens", 4000),
        temperature=data.get("temperature", 0.7),
    )


def parse_hook_defaults(data: dict[str, Any]) -> HookDefaults:
    """Parse hook defaults from dictionary."""
    return HookDefaults(
        pre_hooks=data.get("pre_hooks", []),
        post_hooks=data.get("post_hooks", []),
        test_command=data.get("test_command"),
        lint_command=data.get("lint_command"),
        format_command=data.get("format_command"),
    )


def parse_config(data: dict[str, Any]) -> Config:
    """
    Parse configuration from dictionary.

    Args:
        data: Configuration dictionary

    Returns:
        Config object

    Raises:
        ConfigLoadError: If configuration is invalid
    """
    # Parse provider configs
    provider_configs = {}
    providers_data = data.get("providers", {})
    for name, provider_data in providers_data.items():
        provider_configs[name] = parse_provider_config(name, provider_data)

    # Parse hook defaults
    hook_defaults_data = data.get("hook_defaults", {})
    hook_defaults = parse_hook_defaults(hook_defaults_data)

    return Config(
        provider_configs=provider_configs,
        active_provider=data.get("active_provider", "claude"),
        hook_defaults=hook_defaults,
        state_dir=data.get("state_dir", ".agent-runner"),
        log_dir=data.get("log_dir", "logs"),
        max_attempts_per_task=data.get("max_attempts_per_task", 3),
        max_consecutive_failures=data.get("max_consecutive_failures", 3),
        metadata=data.get("metadata", {}),
    )


def merge_configs(base: Config, override: Config) -> Config:
    """
    Merge two configurations, with override taking precedence.

    Args:
        base: Base configuration (e.g., global config)
        override: Override configuration (e.g., project config)

    Returns:
        Merged configuration
    """
    # Start with base config
    merged_provider_configs = dict(base.provider_configs)

    # Merge provider configs
    for name, provider_config in override.provider_configs.items():
        merged_provider_configs[name] = provider_config

    # Merge hook defaults
    merged_hook_defaults = HookDefaults(
        pre_hooks=(
            override.hook_defaults.pre_hooks
            if override.hook_defaults.pre_hooks
            else base.hook_defaults.pre_hooks
        ),
        post_hooks=(
            override.hook_defaults.post_hooks
            if override.hook_defaults.post_hooks
            else base.hook_defaults.post_hooks
        ),
        test_command=override.hook_defaults.test_command or base.hook_defaults.test_command,
        lint_command=override.hook_defaults.lint_command or base.hook_defaults.lint_command,
        format_command=(override.hook_defaults.format_command or base.hook_defaults.format_command),
    )

    # Merge metadata
    merged_metadata = {**base.metadata, **override.metadata}

    return Config(
        provider_configs=merged_provider_configs,
        active_provider=override.active_provider,
        hook_defaults=merged_hook_defaults,
        state_dir=override.state_dir,
        log_dir=override.log_dir,
        max_attempts_per_task=override.max_attempts_per_task,
        max_consecutive_failures=override.max_consecutive_failures,
        metadata=merged_metadata,
    )


def load_config(
    global_config_path: Optional[Path] = None,
    project_config_path: Optional[Path] = None,
) -> Config:
    """
    Load configuration from global and project config files.

    Project config takes precedence over global config.

    Args:
        global_config_path: Path to global config (default: ~/.taskmaster/config.yml)
        project_config_path: Path to project config (default: ./.taskmaster.yml)

    Returns:
        Merged configuration

    Raises:
        ConfigLoadError: If configuration cannot be loaded or parsed
    """
    if global_config_path is None:
        global_config_path = get_default_config_path()
    if project_config_path is None:
        project_config_path = get_project_config_path()

    # Load global config
    global_data = load_config_file(global_config_path)
    global_config = parse_config(global_data) if global_data else Config()

    # Load project config
    project_data = load_config_file(project_config_path)
    if not project_data:
        # No project config, return global config
        return global_config

    project_config = parse_config(project_data)

    # Merge configs (project overrides global)
    return merge_configs(global_config, project_config)


def validate_config_file(config_path: Path) -> tuple[bool, list[str]]:
    """
    Validate a configuration file.

    Args:
        config_path: Path to the config file

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Try to load the file
    try:
        data = load_config_file(config_path)
        if not data:
            errors.append(f"Config file {config_path} not found or empty")
            return False, errors

        config = parse_config(data)
    except ConfigLoadError as e:
        errors.append(str(e))
        return False, errors
    except Exception as e:
        errors.append(f"Unexpected error loading config: {e}")
        return False, errors

    # Validate the parsed config
    validation_errors = config.validate()
    errors.extend(validation_errors)

    return len(errors) == 0, errors
