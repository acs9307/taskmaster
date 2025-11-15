"""Configuration management for TaskMaster."""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Provider(Enum):
    """Supported AI agent providers."""

    CLAUDE = "claude"
    OPENAI = "openai"
    CODEX = "codex"
    OTHER = "other"


@dataclass
class RateLimitConfig:
    """
    Rate limit configuration for an agent provider.

    Attributes:
        max_tokens_hour: Maximum tokens per hour (None = unlimited)
        max_tokens_day: Maximum tokens per day (None = unlimited)
        max_tokens_week: Maximum tokens per week (None = unlimited)
        max_requests_minute: Maximum requests per minute (None = unlimited)
    """

    max_tokens_hour: Optional[int] = None
    max_tokens_day: Optional[int] = None
    max_tokens_week: Optional[int] = None
    max_requests_minute: Optional[int] = None


@dataclass
class ProviderConfig:
    """
    Configuration for an AI agent provider.

    Attributes:
        provider: The provider type
        api_key: API key (can be literal or env var name like $ANTHROPIC_API_KEY)
        api_key_env: Explicit environment variable name for API key
        model: Model name/identifier
        base_url: Optional base URL for API endpoint
        rate_limits: Rate limit configuration
        max_tokens: Default max tokens for requests
        temperature: Default temperature for requests
    """

    provider: Provider
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    rate_limits: RateLimitConfig = field(default_factory=RateLimitConfig)
    max_tokens: int = 4000
    temperature: float = 0.7

    def get_api_key(self) -> Optional[str]:
        """
        Get the API key, resolving environment variables if needed.

        Returns:
            The resolved API key or None
        """
        # First try explicit env var
        if self.api_key_env:
            return os.getenv(self.api_key_env)

        # Then try api_key field (may contain $VAR syntax)
        if self.api_key:
            if self.api_key.startswith("$"):
                env_var = self.api_key[1:]
                return os.getenv(env_var)
            return self.api_key

        return None


@dataclass
class HookDefaults:
    """
    Default hook configuration.

    Attributes:
        pre_hooks: Default pre-task hooks to run
        post_hooks: Default post-task hooks to run
        test_command: Default test command
        lint_command: Default lint command
        format_command: Default format command
    """

    pre_hooks: list[str] = field(default_factory=list)
    post_hooks: list[str] = field(default_factory=list)
    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    format_command: Optional[str] = None


@dataclass
class Config:
    """
    Main configuration for TaskMaster.

    Attributes:
        provider_configs: Map of provider name to configuration
        active_provider: Name of the currently active provider
        hook_defaults: Default hook configuration
        state_dir: Directory for state files (.agent-runner/)
        log_dir: Directory for log files
        max_attempts_per_task: Maximum retry attempts per task
        max_consecutive_failures: Maximum consecutive failures before escalation
        metadata: Additional user-defined metadata
    """

    provider_configs: dict[str, ProviderConfig] = field(default_factory=dict)
    active_provider: str = "claude"
    hook_defaults: HookDefaults = field(default_factory=HookDefaults)
    state_dir: str = ".agent-runner"
    log_dir: str = "logs"
    max_attempts_per_task: int = 3
    max_consecutive_failures: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_active_provider_config(self) -> Optional[ProviderConfig]:
        """Get the configuration for the active provider."""
        return self.provider_configs.get(self.active_provider)

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check if active provider exists
        if self.active_provider not in self.provider_configs:
            errors.append(f"Active provider '{self.active_provider}' not found in provider_configs")

        # Validate each provider config
        for name, provider_config in self.provider_configs.items():
            # Check if API key is available
            api_key = provider_config.get_api_key()
            if not api_key:
                errors.append(
                    f"Provider '{name}': No API key configured. "
                    f"Set 'api_key' or 'api_key_env' in config, or provide environment variable."
                )

            # Validate rate limits are non-negative
            rate_limits = provider_config.rate_limits
            if rate_limits.max_tokens_hour is not None and rate_limits.max_tokens_hour < 0:
                errors.append(f"Provider '{name}': max_tokens_hour must be >= 0")
            if rate_limits.max_tokens_day is not None and rate_limits.max_tokens_day < 0:
                errors.append(f"Provider '{name}': max_tokens_day must be >= 0")
            if rate_limits.max_tokens_week is not None and rate_limits.max_tokens_week < 0:
                errors.append(f"Provider '{name}': max_tokens_week must be >= 0")
            if rate_limits.max_requests_minute is not None and rate_limits.max_requests_minute < 0:
                errors.append(f"Provider '{name}': max_requests_minute must be >= 0")

            # Validate temperature
            if not 0.0 <= provider_config.temperature <= 2.0:
                errors.append(f"Provider '{name}': temperature must be between 0.0 and 2.0")

        # Validate paths
        if not self.state_dir:
            errors.append("state_dir cannot be empty")
        if not self.log_dir:
            errors.append("log_dir cannot be empty")

        # Validate retry settings
        if self.max_attempts_per_task < 1:
            errors.append("max_attempts_per_task must be >= 1")
        if self.max_consecutive_failures < 1:
            errors.append("max_consecutive_failures must be >= 1")

        return errors


def get_default_config_path() -> Path:
    """Get the default global config file path."""
    return Path.home() / ".taskmaster" / "config.yml"


def get_project_config_path() -> Path:
    """Get the project-local config file path."""
    return Path.cwd() / ".taskmaster.yml"
