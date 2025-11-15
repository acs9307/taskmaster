"""Tests for OpenAI client implementation."""

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


class TestOpenAIClientImport:
    """Tests for importing OpenAI client."""

    def test_import_without_openai(self):
        """Test that importing module doesn't fail without openai installed."""
        from taskmaster import openai_client

        assert openai_client is not None


class TestOpenAIClientInitialization:
    """Tests for OpenAI client initialization."""

    @patch("taskmaster.openai_client.openai")
    def test_init_with_api_key(self, mock_openai):
        """Test initialization with API key."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model == "gpt-4"
        assert client.default_max_tokens == 4096
        assert client.default_temperature == 1.0

    @patch("taskmaster.openai_client.openai")
    def test_init_with_env_var(self, mock_openai):
        """Test initialization with environment variable."""
        from taskmaster.openai_client import OpenAIClient

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            client = OpenAIClient()
            assert client.api_key == "env-key"

    @patch("taskmaster.openai_client.openai")
    def test_init_without_api_key(self, mock_openai):
        """Test initialization fails without API key."""
        from taskmaster.openai_client import OpenAIClient

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="No API key provided"):
                OpenAIClient()

    @patch("taskmaster.openai_client.openai")
    def test_init_with_custom_model(self, mock_openai):
        """Test initialization with custom model."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key", model="gpt-3.5-turbo")
        assert client.model == "gpt-3.5-turbo"

    @patch("taskmaster.openai_client.openai")
    def test_init_with_custom_params(self, mock_openai):
        """Test initialization with custom parameters."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(
            api_key="test-key", max_tokens=2048, temperature=0.5
        )
        assert client.default_max_tokens == 2048
        assert client.default_temperature == 0.5

    def test_init_without_openai_package(self):
        """Test initialization fails gracefully without openai package."""
        from taskmaster.openai_client import OpenAIClient

        with patch("taskmaster.openai_client.openai", None):
            with pytest.raises(FatalError, match="openai package not installed"):
                OpenAIClient(api_key="test-key")


@patch("taskmaster.openai_client.openai")
class TestOpenAIClientCompletion:
    """Tests for OpenAI completion generation."""

    def test_generate_completion_basic(self, mock_openai):
        """Test basic completion generation."""
        from taskmaster.openai_client import OpenAIClient

        # Mock response
        mock_choice = Mock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Say hello")
        response = client.generate_completion(request)

        assert response.content == "Hello, world!"
        assert response.model == "gpt-4"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.usage["total_tokens"] == 15
        assert response.finish_reason == "stop"
        assert response.metadata["id"] == "chatcmpl-123"

    def test_generate_completion_with_system_prompt(self, mock_openai):
        """Test completion with system prompt."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(
            prompt="Hello", system_prompt="You are a helpful assistant"
        )
        response = client.generate_completion(request)

        # Verify system prompt was passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "You are a helpful assistant"
        assert call_kwargs["messages"][1]["role"] == "user"

    def test_generate_completion_with_custom_params(self, mock_openai):
        """Test completion with custom parameters."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(
            prompt="Test",
            max_tokens=1000,
            temperature=0.7,
            stop_sequences=["STOP"],
        )
        response = client.generate_completion(request)

        # Verify parameters were passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["stop"] == ["STOP"]

    def test_generate_completion_empty_content(self, mock_openai):
        """Test completion with empty content."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = None  # OpenAI can return None
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=0, total_tokens=10)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")
        response = client.generate_completion(request)

        assert response.content == ""


@patch("taskmaster.openai_client.openai")
class TestOpenAIClientErrorHandling:
    """Tests for OpenAI error handling."""

    def test_rate_limit_error(self, mock_openai):
        """Test handling of rate limit errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's RateLimitError
        class OpenAIRateLimitError(Exception):
            pass

        OpenAIRateLimitError.__name__ = "RateLimitError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIRateLimitError(
            "Rate limit exceeded"
        )
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(RateLimitError):
            client.generate_completion(request)

    def test_authentication_error(self, mock_openai):
        """Test handling of authentication errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's AuthenticationError
        class OpenAIAuthenticationError(Exception):
            pass

        OpenAIAuthenticationError.__name__ = "AuthenticationError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIAuthenticationError("Invalid API key")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(AuthenticationError):
            client.generate_completion(request)

    def test_bad_request_error(self, mock_openai):
        """Test handling of bad request errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's BadRequestError
        class OpenAIBadRequestError(Exception):
            pass

        OpenAIBadRequestError.__name__ = "BadRequestError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIBadRequestError("Invalid request")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(FatalError):
            client.generate_completion(request)

    def test_server_error(self, mock_openai):
        """Test handling of server errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's InternalServerError
        class OpenAIInternalServerError(Exception):
            pass

        OpenAIInternalServerError.__name__ = "InternalServerError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIInternalServerError("Internal server error")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_connection_error(self, mock_openai):
        """Test handling of connection errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's APIConnectionError
        class OpenAIAPIConnectionError(Exception):
            pass

        OpenAIAPIConnectionError.__name__ = "APIConnectionError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIAPIConnectionError("Connection failed")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_timeout_error(self, mock_openai):
        """Test handling of timeout errors."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's Timeout
        class OpenAITimeout(Exception):
            pass

        OpenAITimeout.__name__ = "Timeout"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAITimeout("Request timed out")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)

    def test_unknown_error_with_rate_limit_message(self, mock_openai):
        """Test mapping of unknown errors with rate limit indicators."""
        from taskmaster.openai_client import OpenAIClient

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Error 429: rate limit")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(RateLimitError):
            client.generate_completion(request)

    def test_unknown_error_with_auth_message(self, mock_openai):
        """Test mapping of unknown errors with auth indicators."""
        from taskmaster.openai_client import OpenAIClient

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("401 Unauthorized")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(AuthenticationError):
            client.generate_completion(request)

    def test_unknown_error_defaults_to_transient(self, mock_openai):
        """Test that unknown errors default to transient."""
        from taskmaster.openai_client import OpenAIClient

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Unknown error")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CompletionRequest(prompt="Test")

        with pytest.raises(TransientError):
            client.generate_completion(request)


@patch("taskmaster.openai_client.openai")
class TestOpenAIClientCodeChanges:
    """Tests for code change functionality."""

    def test_apply_code_changes(self, mock_openai):
        """Test applying code changes."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = "Changes explained"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CodeChangeRequest(
            repo_path="/path/to/repo", instructions="Fix the bug"
        )
        response = client.apply_code_changes(request)

        assert "Changes explained" in response.explanation
        assert response.metadata["model"] == "gpt-4"

    def test_apply_code_changes_dry_run(self, mock_openai):
        """Test code changes in dry run mode."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = "Proposed changes"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        request = CodeChangeRequest(
            repo_path="/repo", instructions="Add feature", dry_run=True
        )
        response = client.apply_code_changes(request)

        # Verify dry run was mentioned in prompt
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "dry run" in user_message["content"].lower()


@patch("taskmaster.openai_client.openai")
class TestOpenAIClientUtilities:
    """Tests for utility methods."""

    def test_get_model_name(self, mock_openai):
        """Test getting model name."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key", model="gpt-3.5-turbo")
        assert client.get_model_name() == "gpt-3.5-turbo"

    def test_validate_connection_success(self, mock_openai):
        """Test successful connection validation."""
        from taskmaster.openai_client import OpenAIClient

        mock_choice = Mock()
        mock_choice.message.content = "test"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")
        assert client.validate_connection() is True

    def test_validate_connection_auth_failure(self, mock_openai):
        """Test connection validation with auth failure."""
        from taskmaster.openai_client import OpenAIClient

        # Create mock exception that looks like OpenAI's AuthenticationError
        class OpenAIAuthenticationError(Exception):
            pass

        OpenAIAuthenticationError.__name__ = "AuthenticationError"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = OpenAIAuthenticationError("Invalid API key")
        mock_openai.OpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key")

        with pytest.raises(AuthenticationError):
            client.validate_connection()

    def test_get_rate_limits(self, mock_openai):
        """Test getting rate limits."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key")
        limits = client.get_rate_limits()

        assert "requests_per_minute" in limits
        assert "tokens_per_minute" in limits
        assert isinstance(limits["requests_per_minute"], int)

    def test_supports_code_changes(self, mock_openai):
        """Test that code changes are supported."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key")
        assert client.supports_code_changes() is True

    def test_estimate_tokens(self, mock_openai):
        """Test token estimation."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key")
        # Inherited from AgentClient base class
        tokens = client.estimate_tokens("a" * 100)
        assert tokens == 25

    def test_repr(self, mock_openai):
        """Test string representation."""
        from taskmaster.openai_client import OpenAIClient

        client = OpenAIClient(api_key="test-key", model="gpt-3.5-turbo")
        repr_str = repr(client)

        assert "OpenAIClient" in repr_str
        assert "gpt-3.5-turbo" in repr_str
