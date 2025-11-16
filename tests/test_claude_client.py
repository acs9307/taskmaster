"""Tests for Claude client implementation."""

import os
from unittest.mock import Mock, patch

import pytest

from taskmaster.agent_client import (
    AuthenticationError,
    CodeChangeRequest,
    CompletionRequest,
    FatalError,
    RateLimitError,
    TransientError,
)


class TestClaudeClientImport:
    """Tests for importing Claude client."""

    def test_import_without_anthropic(self):
        """Test that importing module doesn't fail without anthropic installed."""
        # This test just verifies the module can be imported
        from taskmaster import claude_client

        assert claude_client is not None


class TestClaudeClientInitialization:
    """Tests for Claude client initialization."""

    @patch("taskmaster.claude_client.anthropic")
    def test_init_with_api_key(self, mock_anthropic):
        """Test initialization with API key."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model == "claude-3-5-sonnet-20241022"
        assert client.default_max_tokens == 4096
        assert client.default_temperature == 1.0

    @patch("taskmaster.claude_client.anthropic")
    def test_init_with_env_var(self, mock_anthropic):
        """Test initialization with environment variable."""
        from taskmaster.claude_client import ClaudeClient

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            client = ClaudeClient()
            assert client.api_key == "env-key"

    @patch("taskmaster.claude_client.anthropic")
    def test_init_without_api_key(self, mock_anthropic):
        """Test initialization fails without API key."""
        from taskmaster.claude_client import ClaudeClient

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="No API key provided"):
                ClaudeClient()

    @patch("taskmaster.claude_client.anthropic")
    def test_init_with_custom_model(self, mock_anthropic):
        """Test initialization with custom model."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key", model="claude-3-opus-20240229")
        assert client.model == "claude-3-opus-20240229"

    @patch("taskmaster.claude_client.anthropic")
    def test_init_with_custom_params(self, mock_anthropic):
        """Test initialization with custom parameters."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key", max_tokens=2048, temperature=0.5)
        assert client.default_max_tokens == 2048
        assert client.default_temperature == 0.5

    def test_init_without_anthropic_package(self):
        """Test initialization fails gracefully without anthropic package."""
        from taskmaster.claude_client import ClaudeClient

        with patch("taskmaster.claude_client.anthropic", None):
            with pytest.raises(FatalError, match="anthropic package not installed"):
                ClaudeClient(api_key="test-key")


@patch("taskmaster.claude_client.anthropic")
class TestClaudeClientCompletion:
    """Tests for Claude completion generation."""

    def test_generate_completion_basic(self, mock_anthropic):
        """Test basic completion generation."""
        from taskmaster.claude_client import ClaudeClient

        # Mock response
        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="Hello, world!")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Say hello")
        response = client.generate_completion(request)

        assert response.content == "Hello, world!"
        assert response.model == "claude-3-5-sonnet-20241022"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.usage["total_tokens"] == 15
        assert response.finish_reason == "end_turn"
        assert response.metadata["id"] == "msg_123"

    def test_generate_completion_with_system_prompt(self, mock_anthropic):
        """Test completion with system prompt."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Hello", system_prompt="You are a helpful assistant")
        client.generate_completion(request)

        # Verify system prompt was passed
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are a helpful assistant"

    def test_generate_completion_with_custom_params(self, mock_anthropic):
        """Test completion with custom parameters."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(
            prompt="Test",
            max_tokens=1000,
            temperature=0.7,
            stop_sequences=["STOP"],
        )
        client.generate_completion(request)

        # Verify parameters were passed
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["stop_sequences"] == ["STOP"]

    def test_generate_completion_multiple_content_blocks(self, mock_anthropic):
        """Test completion with multiple content blocks."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [
            Mock(text="Part 1 "),
            Mock(text="Part 2"),
        ]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")
        response = client.generate_completion(request)

        assert response.content == "Part 1 Part 2"


@patch("taskmaster.claude_client.anthropic")
class TestClaudeClientErrorHandling:
    """Tests for Claude error handling."""

    def test_rate_limit_error(self, mock_anthropic):
        """Test handling of rate limit errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's RateLimitError
        class AnthropicRateLimitError(Exception):
            pass

        AnthropicRateLimitError.__name__ = "RateLimitError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicRateLimitError("Rate limit exceeded")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(RateLimitError):
            client.generate_completion(request)

    def test_authentication_error(self, mock_anthropic):
        """Test handling of authentication errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's AuthenticationError
        class AnthropicAuthenticationError(Exception):
            pass

        AnthropicAuthenticationError.__name__ = "AuthenticationError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicAuthenticationError("Invalid API key")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(AuthenticationError):
            client.generate_completion(request)

    def test_bad_request_error(self, mock_anthropic):
        """Test handling of bad request errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's BadRequestError
        class AnthropicBadRequestError(Exception):
            pass

        AnthropicBadRequestError.__name__ = "BadRequestError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicBadRequestError("Invalid request")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(FatalError):
            client.generate_completion(request)

    def test_server_error(self, mock_anthropic):
        """Test handling of server errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's InternalServerError
        class AnthropicInternalServerError(Exception):
            pass

        AnthropicInternalServerError.__name__ = "InternalServerError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicInternalServerError(
            "Internal server error"
        )
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_connection_error(self, mock_anthropic):
        """Test handling of connection errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's APIConnectionError
        class AnthropicAPIConnectionError(Exception):
            pass

        AnthropicAPIConnectionError.__name__ = "APIConnectionError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicAPIConnectionError("Connection failed")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_timeout_error(self, mock_anthropic):
        """Test handling of timeout errors."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's APITimeoutError
        class AnthropicAPITimeoutError(Exception):
            pass

        AnthropicAPITimeoutError.__name__ = "APITimeoutError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicAPITimeoutError("Request timed out")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_unknown_error_with_rate_limit_message(self, mock_anthropic):
        """Test mapping of unknown errors with rate limit indicators."""
        from taskmaster.claude_client import ClaudeClient

        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("Error 429: rate limit")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(RateLimitError):
            client.generate_completion(request)

    def test_unknown_error_with_auth_message(self, mock_anthropic):
        """Test mapping of unknown errors with auth indicators."""
        from taskmaster.claude_client import ClaudeClient

        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("401 Unauthorized")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(AuthenticationError):
            client.generate_completion(request)

    def test_unknown_error_defaults_to_transient(self, mock_anthropic):
        """Test that unknown errors default to transient."""
        from taskmaster.claude_client import ClaudeClient

        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("Unknown error")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)


@patch("taskmaster.claude_client.anthropic")
class TestClaudeClientCodeChanges:
    """Tests for code change functionality."""

    def test_apply_code_changes(self, mock_anthropic):
        """Test applying code changes."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="Changes explained")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CodeChangeRequest(repo_path="/path/to/repo", instructions="Fix the bug")
        response = client.apply_code_changes(request)

        assert "Changes explained" in response.explanation
        assert response.metadata["model"] == "claude-3-5-sonnet-20241022"

    def test_apply_code_changes_dry_run(self, mock_anthropic):
        """Test code changes in dry run mode."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="Proposed changes")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=10, output_tokens=5)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        request = CodeChangeRequest(repo_path="/repo", instructions="Add feature", dry_run=True)
        client.apply_code_changes(request)

        # Verify dry run was mentioned in prompt
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "dry run" in call_kwargs["messages"][0]["content"].lower()


@patch("taskmaster.claude_client.anthropic")
class TestClaudeClientUtilities:
    """Tests for utility methods."""

    def test_get_model_name(self, mock_anthropic):
        """Test getting model name."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key", model="claude-3-opus-20240229")
        assert client.get_model_name() == "claude-3-opus-20240229"

    def test_validate_connection_success(self, mock_anthropic):
        """Test successful connection validation."""
        from taskmaster.claude_client import ClaudeClient

        mock_response = Mock()
        mock_response.id = "msg_123"
        mock_response.type = "message"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.content = [Mock(text="test")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock(input_tokens=1, output_tokens=1)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")
        assert client.validate_connection() is True

    def test_validate_connection_auth_failure(self, mock_anthropic):
        """Test connection validation with auth failure."""
        from taskmaster.claude_client import ClaudeClient

        # Create mock exception that looks like Anthropic's AuthenticationError
        class AnthropicAuthenticationError(Exception):
            pass

        AnthropicAuthenticationError.__name__ = "AuthenticationError"

        mock_client = Mock()
        mock_client.messages.create.side_effect = AnthropicAuthenticationError("Invalid API key")
        mock_anthropic.Anthropic.return_value = mock_client

        client = ClaudeClient(api_key="test-key")

        with pytest.raises(AuthenticationError):
            client.validate_connection()

    def test_get_rate_limits(self, mock_anthropic):
        """Test getting rate limits."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        limits = client.get_rate_limits()

        assert "requests_per_minute" in limits
        assert "tokens_per_minute" in limits
        assert isinstance(limits["requests_per_minute"], int)

    def test_supports_code_changes(self, mock_anthropic):
        """Test that code changes are supported."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        assert client.supports_code_changes() is True

    def test_estimate_tokens(self, mock_anthropic):
        """Test token estimation."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        # Inherited from AgentClient base class
        tokens = client.estimate_tokens("a" * 100)
        assert tokens == 25

    def test_repr(self, mock_anthropic):
        """Test string representation."""
        from taskmaster.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key", model="claude-3-opus-20240229")
        repr_str = repr(client)

        assert "ClaudeClient" in repr_str
        assert "claude-3-opus-20240229" in repr_str
