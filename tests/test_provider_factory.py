"""Tests for provider factory."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from taskmaster.config import Config, Provider, ProviderConfig
from taskmaster.provider_factory import (
    ProviderError,
    create_agent_client,
    get_agent_client,
    validate_provider,
)


class TestCreateAgentClient:
    """Test create_agent_client function."""

    def test_create_claude_client_success(self):
        """Test creating Claude client successfully."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
        )

        with patch("taskmaster.claude_client.ClaudeClient") as mock_claude:
            mock_client = MagicMock()
            mock_claude.return_value = mock_client

            client = create_agent_client("claude", config)

            assert client == mock_client
            mock_claude.assert_called_once_with(
                api_key="test-key",
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.7,
            )

    def test_create_claude_client_default_model(self):
        """Test creating Claude client with default model."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            api_key="test-key",
        )

        with patch("taskmaster.claude_client.ClaudeClient") as mock_claude:
            mock_client = MagicMock()
            mock_claude.return_value = mock_client

            client = create_agent_client("claude", config)

            assert client == mock_client
            # Should use default model
            assert mock_claude.call_args[1]["model"] == "claude-3-5-sonnet-20241022"

    def test_create_openai_client_success(self):
        """Test creating OpenAI client successfully."""
        config = ProviderConfig(
            provider=Provider.OPENAI,
            api_key="test-key",
            model="gpt-4-turbo",
            max_tokens=8000,
            temperature=0.5,
        )

        with patch("taskmaster.openai_client.OpenAIClient") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_agent_client("openai", config)

            assert client == mock_client
            mock_openai.assert_called_once_with(
                api_key="test-key",
                model="gpt-4-turbo",
                max_tokens=8000,
                temperature=0.5,
            )

    def test_create_openai_client_default_model(self):
        """Test creating OpenAI client with default model."""
        config = ProviderConfig(
            provider=Provider.OPENAI,
            api_key="test-key",
        )

        with patch("taskmaster.openai_client.OpenAIClient") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_agent_client("openai", config)

            assert client == mock_client
            # Should use default model
            assert mock_openai.call_args[1]["model"] == "gpt-4"

    def test_create_codex_client_success(self):
        """Test creating Codex client (uses OpenAI)."""
        config = ProviderConfig(
            provider=Provider.CODEX,
            api_key="test-key",
            model="gpt-4",
        )

        with patch("taskmaster.openai_client.OpenAIClient") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_agent_client("codex", config)

            assert client == mock_client

    def test_create_codex_client_default_model(self):
        """Test creating Codex client with default model."""
        config = ProviderConfig(
            provider=Provider.CODEX,
            api_key="test-key",
        )

        with patch("taskmaster.openai_client.OpenAIClient") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            _ = create_agent_client("codex", config)

            # Codex without model should default to gpt-4
            assert mock_openai.call_args[1]["model"] == "gpt-4"

    def test_missing_api_key(self):
        """Test error when API key is missing."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            # No API key
        )

        with pytest.raises(ProviderError) as exc_info:
            create_agent_client("claude", config)

        error_msg = str(exc_info.value).lower()
        assert "missing api key" in error_msg or "no api key" in error_msg
        assert "claude" in str(exc_info.value)

    def test_unsupported_provider_type(self):
        """Test error for unsupported provider type."""
        config = ProviderConfig(
            provider=Provider.OTHER,
            api_key="test-key",
        )

        with pytest.raises(ProviderError) as exc_info:
            create_agent_client("custom", config)

        assert "unsupported type" in str(exc_info.value).lower()
        assert "other" in str(exc_info.value).lower()

    def test_claude_import_error(self):
        """Test error when Claude client cannot be imported."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            api_key="test-key",
        )

        with patch(
            "taskmaster.claude_client.ClaudeClient",
            side_effect=ImportError("No module named 'anthropic'"),
        ):
            with pytest.raises(ProviderError) as exc_info:
                create_agent_client("claude", config)

            # The error may say "failed to create" or "not available"
            error_msg = str(exc_info.value).lower()
            assert "claude" in error_msg
            assert "anthropic" in error_msg or "failed" in error_msg

    def test_openai_import_error(self):
        """Test error when OpenAI client cannot be imported."""
        config = ProviderConfig(
            provider=Provider.OPENAI,
            api_key="test-key",
        )

        with patch(
            "taskmaster.openai_client.OpenAIClient",
            side_effect=ImportError("No module named 'openai'"),
        ):
            with pytest.raises(ProviderError) as exc_info:
                create_agent_client("openai", config)

            # The error may say "failed to create" or "not available"
            error_msg = str(exc_info.value).lower()
            assert "openai" in error_msg
            assert "openai" in error_msg or "failed" in error_msg

    def test_client_creation_failure(self):
        """Test error when client initialization fails."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            api_key="test-key",
        )

        with patch(
            "taskmaster.claude_client.ClaudeClient",
            side_effect=Exception("Invalid API key"),
        ):
            with pytest.raises(ProviderError) as exc_info:
                create_agent_client("claude", config)

            assert "failed to create" in str(exc_info.value).lower()
            assert "Invalid API key" in str(exc_info.value)


class TestGetAgentClient:
    """Test get_agent_client function."""

    def test_get_active_provider(self):
        """Test getting client for active provider."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    api_key="claude-key",
                ),
            },
            active_provider="claude",
        )

        with patch("taskmaster.claude_client.ClaudeClient") as mock_claude:
            mock_client = MagicMock()
            mock_claude.return_value = mock_client

            provider_name, client = get_agent_client(config)

            assert provider_name == "claude"
            assert client == mock_client

    def test_get_provider_with_override(self):
        """Test getting client with provider override."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    api_key="claude-key",
                ),
                "openai": ProviderConfig(
                    provider=Provider.OPENAI,
                    api_key="openai-key",
                ),
            },
            active_provider="claude",
        )

        with patch("taskmaster.openai_client.OpenAIClient") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Override to use openai instead of claude
            provider_name, client = get_agent_client(config, provider_override="openai")

            assert provider_name == "openai"
            assert client == mock_client

    def test_provider_not_found(self):
        """Test error when provider is not found in config."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    api_key="claude-key",
                ),
            },
            active_provider="claude",
        )

        with pytest.raises(ProviderError) as exc_info:
            get_agent_client(config, provider_override="nonexistent")

        assert "not found in configuration" in str(exc_info.value).lower()
        assert "nonexistent" in str(exc_info.value)
        assert "claude" in str(exc_info.value)  # Shows available providers

    def test_no_providers_configured(self):
        """Test error when no providers are configured."""
        config = Config(
            provider_configs={},
            active_provider="claude",
        )

        with pytest.raises(ProviderError) as exc_info:
            get_agent_client(config)

        assert "not found in configuration" in str(exc_info.value).lower()
        assert "none" in str(exc_info.value).lower()

    def test_active_provider_missing(self):
        """Test error when active provider doesn't exist in configs."""
        config = Config(
            provider_configs={
                "openai": ProviderConfig(
                    provider=Provider.OPENAI,
                    api_key="openai-key",
                ),
            },
            active_provider="claude",  # Not in provider_configs
        )

        with pytest.raises(ProviderError) as exc_info:
            get_agent_client(config)

        assert "not found in configuration" in str(exc_info.value).lower()
        assert "claude" in str(exc_info.value)


class TestValidateProvider:
    """Test validate_provider function."""

    def test_validate_success(self):
        """Test successful validation."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    api_key="test-key",
                ),
            },
        )

        # Mock that anthropic is installed
        with patch.dict(sys.modules, {"anthropic": MagicMock()}):
            errors = validate_provider(config, "claude")
            assert errors == []

    def test_validate_provider_not_found(self):
        """Test validation error when provider not found."""
        config = Config(provider_configs={})

        errors = validate_provider(config, "claude")

        assert len(errors) == 1
        assert "not found in configuration" in errors[0].lower()

    def test_validate_missing_api_key(self):
        """Test validation error for missing API key."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    # No API key
                ),
            },
        )

        errors = validate_provider(config, "claude")

        assert len(errors) >= 1
        assert any("api key" in error.lower() for error in errors)

    def test_validate_unsupported_provider_type(self):
        """Test validation error for unsupported provider type."""
        config = Config(
            provider_configs={
                "custom": ProviderConfig(
                    provider=Provider.OTHER,
                    api_key="test-key",
                ),
            },
        )

        errors = validate_provider(config, "custom")

        assert len(errors) >= 1
        assert any("unsupported" in error.lower() for error in errors)

    def test_validate_missing_anthropic_package(self):
        """Test validation error when anthropic package is not installed."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    api_key="test-key",
                ),
            },
        )

        # Block the import by setting anthropic to None in sys.modules
        # This causes the import to fail
        original = sys.modules.get("anthropic")
        sys.modules["anthropic"] = None

        try:
            errors = validate_provider(config, "claude")

            assert len(errors) >= 1
            assert any("anthropic package" in error.lower() for error in errors)
        finally:
            # Restore original state
            if original is None:
                sys.modules.pop("anthropic", None)
            else:
                sys.modules["anthropic"] = original

    def test_validate_missing_openai_package(self):
        """Test validation error when openai package is not installed."""
        config = Config(
            provider_configs={
                "openai": ProviderConfig(
                    provider=Provider.OPENAI,
                    api_key="test-key",
                ),
            },
        )

        # Block the import by setting openai to None in sys.modules
        original = sys.modules.get("openai")
        sys.modules["openai"] = None

        try:
            errors = validate_provider(config, "openai")

            assert len(errors) >= 1
            assert any("openai package" in error.lower() for error in errors)
        finally:
            # Restore original state
            if original is None:
                sys.modules.pop("openai", None)
            else:
                sys.modules["openai"] = original

    def test_validate_codex_package(self):
        """Test validation for codex provider (uses openai package)."""
        config = Config(
            provider_configs={
                "codex": ProviderConfig(
                    provider=Provider.CODEX,
                    api_key="test-key",
                ),
            },
        )

        # Block the import by setting openai to None in sys.modules
        original = sys.modules.get("openai")
        sys.modules["openai"] = None

        try:
            errors = validate_provider(config, "codex")

            assert len(errors) >= 1
            assert any("openai package" in error.lower() for error in errors)
        finally:
            # Restore original state
            if original is None:
                sys.modules.pop("openai", None)
            else:
                sys.modules["openai"] = original

    def test_validate_multiple_errors(self):
        """Test validation with multiple errors."""
        config = Config(
            provider_configs={
                "claude": ProviderConfig(
                    provider=Provider.CLAUDE,
                    # Missing API key
                ),
            },
        )

        # Block the import by setting anthropic to None in sys.modules
        original = sys.modules.get("anthropic")
        sys.modules["anthropic"] = None

        try:
            errors = validate_provider(config, "claude")

            # Should have both API key error and package import error
            assert len(errors) >= 2
            assert any("api key" in error.lower() for error in errors)
            assert any("anthropic package" in error.lower() for error in errors)
        finally:
            # Restore original state
            if original is None:
                sys.modules.pop("anthropic", None)
            else:
                sys.modules["anthropic"] = original
