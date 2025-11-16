"""Provider factory for creating agent clients based on configuration."""

from typing import Optional

from taskmaster.agent_client import AgentClient
from taskmaster.config import Config, Provider, ProviderConfig


class ProviderError(Exception):
    """Raised when provider configuration or creation fails."""

    pass


def create_agent_client(provider_name: str, provider_config: ProviderConfig) -> AgentClient:
    """
    Create an agent client instance from provider configuration.

    Args:
        provider_name: Name of the provider (e.g., "claude", "openai")
        provider_config: Provider configuration

    Returns:
        AgentClient instance

    Raises:
        ProviderError: If provider cannot be created or is misconfigured
    """
    # Validate API key is available
    api_key = provider_config.get_api_key()
    if not api_key:
        raise ProviderError(
            f"Provider '{provider_name}' is missing API key. "
            f"Set 'api_key', 'api_key_env' in config, or provide environment variable."
        )

    # Create client based on provider type
    provider_type = provider_config.provider

    if provider_type == Provider.CLAUDE:
        return _create_claude_client(provider_name, provider_config, api_key)
    elif provider_type == Provider.OPENAI or provider_type == Provider.CODEX:
        return _create_openai_client(provider_name, provider_config, api_key)
    else:
        raise ProviderError(
            f"Provider '{provider_name}' has unsupported type: {provider_type.value}. "
            f"Supported types: claude, openai, codex"
        )


def _create_claude_client(provider_name: str, config: ProviderConfig, api_key: str) -> AgentClient:
    """Create a Claude client instance."""
    try:
        from taskmaster.claude_client import ClaudeClient
    except ImportError as e:
        raise ProviderError(
            f"Provider '{provider_name}': Claude client is not available. "
            f"Install with: pip install anthropic"
        ) from e

    # Determine model
    model = config.model or "claude-3-5-sonnet-20241022"

    try:
        client = ClaudeClient(
            api_key=api_key,
            model=model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        return client
    except Exception as e:
        raise ProviderError(
            f"Provider '{provider_name}': Failed to create Claude client: {e}"
        ) from e


def _create_openai_client(provider_name: str, config: ProviderConfig, api_key: str) -> AgentClient:
    """Create an OpenAI client instance."""
    try:
        from taskmaster.openai_client import OpenAIClient
    except ImportError as e:
        raise ProviderError(
            f"Provider '{provider_name}': OpenAI client is not available. "
            f"Install with: pip install openai"
        ) from e

    # Determine model
    # For codex provider type, default to a codex model if not specified
    if config.provider == Provider.CODEX and not config.model:
        model = "gpt-4"  # Codex models are deprecated, use GPT-4 as fallback
    else:
        model = config.model or "gpt-4"

    try:
        client = OpenAIClient(
            api_key=api_key,
            model=model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        return client
    except Exception as e:
        raise ProviderError(
            f"Provider '{provider_name}': Failed to create OpenAI client: {e}"
        ) from e


def get_agent_client(
    config: Config, provider_override: Optional[str] = None
) -> tuple[str, AgentClient]:
    """
    Get an agent client from configuration.

    Args:
        config: TaskMaster configuration
        provider_override: Optional provider name to override config.active_provider

    Returns:
        Tuple of (provider_name, AgentClient instance)

    Raises:
        ProviderError: If provider cannot be created or is misconfigured
    """
    # Determine which provider to use
    provider_name = provider_override or config.active_provider

    # Check if provider exists in config
    if provider_name not in config.provider_configs:
        available = ", ".join(config.provider_configs.keys())
        raise ProviderError(
            f"Provider '{provider_name}' not found in configuration. "
            f"Available providers: {available if available else 'none'}"
        )

    # Get provider configuration
    provider_config = config.provider_configs[provider_name]

    # Create and return client
    client = create_agent_client(provider_name, provider_config)

    return provider_name, client


def validate_provider(config: Config, provider_name: str) -> list[str]:
    """
    Validate a specific provider configuration.

    Args:
        config: TaskMaster configuration
        provider_name: Name of provider to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check if provider exists
    if provider_name not in config.provider_configs:
        errors.append(f"Provider '{provider_name}' not found in configuration")
        return errors

    provider_config = config.provider_configs[provider_name]

    # Check API key
    api_key = provider_config.get_api_key()
    if not api_key:
        errors.append(
            f"Provider '{provider_name}': No API key configured. "
            f"Set 'api_key' or 'api_key_env' in config, or provide environment variable."
        )

    # Check provider type is supported
    if provider_config.provider not in [Provider.CLAUDE, Provider.OPENAI, Provider.CODEX]:
        errors.append(
            f"Provider '{provider_name}': Unsupported provider type '{provider_config.provider.value}'"
        )

    # Try to import required modules
    if provider_config.provider == Provider.CLAUDE:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            errors.append(
                f"Provider '{provider_name}': anthropic package not installed. "
                f"Install with: pip install anthropic"
            )

    if provider_config.provider in [Provider.OPENAI, Provider.CODEX]:
        try:
            import openai  # noqa: F401
        except ImportError:
            errors.append(
                f"Provider '{provider_name}': openai package not installed. "
                f"Install with: pip install openai"
            )

    return errors
