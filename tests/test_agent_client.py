"""Tests for agent client interface and error handling."""

import pytest

from taskmaster.agent_client import (
    AgentClient,
    AgentError,
    AuthenticationError,
    CodeChange,
    CodeChangeRequest,
    CodeChangeResponse,
    CompletionRequest,
    CompletionResponse,
    ErrorType,
    FatalError,
    RateLimitError,
    TransientError,
)


class TestErrorTypes:
    """Tests for error type enum."""

    def test_error_types_exist(self):
        """Test that all expected error types exist."""
        assert ErrorType.RATE_LIMIT.value == "rate_limit"
        assert ErrorType.AUTHENTICATION.value == "authentication"
        assert ErrorType.TRANSIENT.value == "transient"
        assert ErrorType.FATAL.value == "fatal"
        assert ErrorType.UNKNOWN.value == "unknown"


class TestAgentError:
    """Tests for base AgentError class."""

    def test_basic_error(self):
        """Test creating a basic error."""
        error = AgentError("Test error")
        assert str(error) == "Test error"
        assert error.error_type == ErrorType.UNKNOWN
        assert error.original_error is None
        assert error.retry_after is None

    def test_error_with_type(self):
        """Test error with specific type."""
        error = AgentError("Test", error_type=ErrorType.TRANSIENT)
        assert error.error_type == ErrorType.TRANSIENT

    def test_error_with_original(self):
        """Test error with original exception."""
        original = ValueError("Original")
        error = AgentError("Wrapped", original_error=original)
        assert error.original_error is original

    def test_error_with_retry_after(self):
        """Test error with retry_after."""
        error = AgentError("Test", retry_after=60)
        assert error.retry_after == 60

    def test_is_retryable_rate_limit(self):
        """Test that rate limit errors are retryable."""
        error = AgentError("Test", error_type=ErrorType.RATE_LIMIT)
        assert error.is_retryable() is True

    def test_is_retryable_transient(self):
        """Test that transient errors are retryable."""
        error = AgentError("Test", error_type=ErrorType.TRANSIENT)
        assert error.is_retryable() is True

    def test_is_not_retryable_fatal(self):
        """Test that fatal errors are not retryable."""
        error = AgentError("Test", error_type=ErrorType.FATAL)
        assert error.is_retryable() is False

    def test_is_not_retryable_auth(self):
        """Test that auth errors are not retryable."""
        error = AgentError("Test", error_type=ErrorType.AUTHENTICATION)
        assert error.is_retryable() is False


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_error_basic(self):
        """Test creating a rate limit error."""
        error = RateLimitError("Rate limited")
        assert str(error) == "Rate limited"
        assert error.error_type == ErrorType.RATE_LIMIT
        assert error.is_retryable() is True

    def test_rate_limit_error_with_retry_after(self):
        """Test rate limit error with retry_after."""
        error = RateLimitError("Rate limited", retry_after=120)
        assert error.retry_after == 120

    def test_rate_limit_error_with_original(self):
        """Test rate limit error with original exception."""
        original = Exception("429 Too Many Requests")
        error = RateLimitError("Rate limited", original_error=original)
        assert error.original_error is original


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_authentication_error(self):
        """Test creating an authentication error."""
        error = AuthenticationError("Invalid API key")
        assert str(error) == "Invalid API key"
        assert error.error_type == ErrorType.AUTHENTICATION
        assert error.is_retryable() is False

    def test_authentication_error_with_original(self):
        """Test auth error with original exception."""
        original = Exception("401 Unauthorized")
        error = AuthenticationError("Auth failed", original_error=original)
        assert error.original_error is original


class TestTransientError:
    """Tests for TransientError."""

    def test_transient_error(self):
        """Test creating a transient error."""
        error = TransientError("Network timeout")
        assert str(error) == "Network timeout"
        assert error.error_type == ErrorType.TRANSIENT
        assert error.is_retryable() is True

    def test_transient_error_with_original(self):
        """Test transient error with original exception."""
        original = TimeoutError("Connection timed out")
        error = TransientError("Timeout", original_error=original)
        assert error.original_error is original


class TestFatalError:
    """Tests for FatalError."""

    def test_fatal_error(self):
        """Test creating a fatal error."""
        error = FatalError("Invalid request")
        assert str(error) == "Invalid request"
        assert error.error_type == ErrorType.FATAL
        assert error.is_retryable() is False

    def test_fatal_error_with_original(self):
        """Test fatal error with original exception."""
        original = ValueError("Bad input")
        error = FatalError("Fatal", original_error=original)
        assert error.original_error is original


class TestCompletionRequest:
    """Tests for CompletionRequest."""

    def test_minimal_request(self):
        """Test creating a minimal completion request."""
        request = CompletionRequest(prompt="Hello")
        assert request.prompt == "Hello"
        assert request.system_prompt is None
        assert request.context == {}
        assert request.max_tokens is None
        assert request.temperature is None
        assert request.stop_sequences == []

    def test_full_request(self):
        """Test creating a full completion request."""
        request = CompletionRequest(
            prompt="Test prompt",
            system_prompt="You are a helpful assistant",
            context={"task_id": "T1"},
            max_tokens=1000,
            temperature=0.7,
            stop_sequences=["END", "STOP"],
        )
        assert request.prompt == "Test prompt"
        assert request.system_prompt == "You are a helpful assistant"
        assert request.context == {"task_id": "T1"}
        assert request.max_tokens == 1000
        assert request.temperature == 0.7
        assert request.stop_sequences == ["END", "STOP"]


class TestCompletionResponse:
    """Tests for CompletionResponse."""

    def test_minimal_response(self):
        """Test creating a minimal completion response."""
        response = CompletionResponse(content="Hello!", model="claude-3")
        assert response.content == "Hello!"
        assert response.model == "claude-3"
        assert response.usage == {}
        assert response.finish_reason is None
        assert response.metadata == {}

    def test_full_response(self):
        """Test creating a full completion response."""
        response = CompletionResponse(
            content="Generated text",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
            metadata={"request_id": "123"},
        )
        assert response.content == "Generated text"
        assert response.model == "gpt-4"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
        assert response.metadata["request_id"] == "123"


class TestCodeChange:
    """Tests for CodeChange."""

    def test_create_file_change(self):
        """Test creating a file creation change."""
        change = CodeChange(
            file_path="test.py",
            operation="create",
            content="print('hello')",
            description="Create test file",
        )
        assert change.file_path == "test.py"
        assert change.operation == "create"
        assert change.content == "print('hello')"
        assert change.description == "Create test file"

    def test_modify_file_change(self):
        """Test creating a file modification change."""
        change = CodeChange(
            file_path="existing.py",
            operation="modify",
            content="new content",
            line_start=10,
            line_end=20,
        )
        assert change.operation == "modify"
        assert change.line_start == 10
        assert change.line_end == 20

    def test_delete_file_change(self):
        """Test creating a file deletion change."""
        change = CodeChange(
            file_path="old.py",
            operation="delete",
            description="Remove deprecated file",
        )
        assert change.operation == "delete"
        assert change.content is None


class TestCodeChangeRequest:
    """Tests for CodeChangeRequest."""

    def test_basic_request(self):
        """Test creating a basic code change request."""
        request = CodeChangeRequest(
            repo_path="/path/to/repo", instructions="Fix the bug"
        )
        assert request.repo_path == "/path/to/repo"
        assert request.instructions == "Fix the bug"
        assert request.context == {}
        assert request.dry_run is False

    def test_request_with_context(self):
        """Test code change request with context."""
        request = CodeChangeRequest(
            repo_path="/repo",
            instructions="Add feature",
            context={"task_id": "T1", "branch": "main"},
            dry_run=True,
        )
        assert request.context["task_id"] == "T1"
        assert request.dry_run is True


class TestCodeChangeResponse:
    """Tests for CodeChangeResponse."""

    def test_response_with_changes(self):
        """Test code change response with changes."""
        changes = [
            CodeChange("file1.py", "create", "content1"),
            CodeChange("file2.py", "modify", "content2"),
        ]
        response = CodeChangeResponse(
            changes=changes, explanation="Made two changes"
        )
        assert len(response.changes) == 2
        assert response.explanation == "Made two changes"
        assert response.metadata == {}

    def test_response_with_metadata(self):
        """Test response with metadata."""
        response = CodeChangeResponse(
            changes=[],
            explanation="No changes needed",
            metadata={"confidence": 0.95},
        )
        assert len(response.changes) == 0
        assert response.metadata["confidence"] == 0.95


class MockAgentClient(AgentClient):
    """Mock implementation of AgentClient for testing."""

    def __init__(self, model: str = "mock-model"):
        self.model = model
        self._should_fail = False
        self._fail_with = None

    def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Mock completion generation."""
        if self._should_fail:
            raise self._fail_with

        return CompletionResponse(
            content=f"Response to: {request.prompt}",
            model=self.model,
            usage={"total_tokens": 100},
        )

    def apply_code_changes(
        self, request: CodeChangeRequest
    ) -> CodeChangeResponse:
        """Mock code change application."""
        if self._should_fail:
            raise self._fail_with

        changes = [
            CodeChange(
                file_path="test.py",
                operation="modify",
                content="# Modified",
                description=request.instructions,
            )
        ]
        return CodeChangeResponse(changes=changes, explanation="Applied changes")

    def get_model_name(self) -> str:
        """Get mock model name."""
        return self.model

    def validate_connection(self) -> bool:
        """Mock connection validation."""
        if self._should_fail:
            raise self._fail_with
        return True


class TestAgentClient:
    """Tests for AgentClient interface."""

    def test_mock_client_creation(self):
        """Test creating a mock client."""
        client = MockAgentClient()
        assert client.get_model_name() == "mock-model"

    def test_generate_completion(self):
        """Test generating a completion."""
        client = MockAgentClient()
        request = CompletionRequest(prompt="Hello")
        response = client.generate_completion(request)

        assert "Hello" in response.content
        assert response.model == "mock-model"

    def test_apply_code_changes(self):
        """Test applying code changes."""
        client = MockAgentClient()
        request = CodeChangeRequest(repo_path="/repo", instructions="Fix bug")
        response = client.apply_code_changes(request)

        assert len(response.changes) > 0
        assert response.changes[0].operation == "modify"

    def test_validate_connection(self):
        """Test validating connection."""
        client = MockAgentClient()
        assert client.validate_connection() is True

    def test_supports_code_changes(self):
        """Test that code changes are supported by default."""
        client = MockAgentClient()
        assert client.supports_code_changes() is True

    def test_get_rate_limits(self):
        """Test getting rate limits."""
        client = MockAgentClient()
        limits = client.get_rate_limits()
        assert isinstance(limits, dict)

    def test_estimate_tokens(self):
        """Test estimating tokens."""
        client = MockAgentClient()
        # Rough estimation: ~4 chars per token
        tokens = client.estimate_tokens("a" * 100)
        assert tokens == 25

    def test_repr(self):
        """Test string representation."""
        client = MockAgentClient(model="test-model")
        repr_str = repr(client)
        assert "MockAgentClient" in repr_str
        assert "test-model" in repr_str

    def test_completion_raises_rate_limit(self):
        """Test completion raises rate limit error."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = RateLimitError("Too many requests", retry_after=60)

        with pytest.raises(RateLimitError) as exc_info:
            client.generate_completion(CompletionRequest(prompt="Test"))

        assert exc_info.value.retry_after == 60
        assert exc_info.value.is_retryable()

    def test_completion_raises_auth_error(self):
        """Test completion raises authentication error."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError) as exc_info:
            client.generate_completion(CompletionRequest(prompt="Test"))

        assert not exc_info.value.is_retryable()

    def test_completion_raises_transient_error(self):
        """Test completion raises transient error."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = TransientError("Network timeout")

        with pytest.raises(TransientError) as exc_info:
            client.generate_completion(CompletionRequest(prompt="Test"))

        assert exc_info.value.is_retryable()

    def test_completion_raises_fatal_error(self):
        """Test completion raises fatal error."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = FatalError("Invalid request")

        with pytest.raises(FatalError) as exc_info:
            client.generate_completion(CompletionRequest(prompt="Test"))

        assert not exc_info.value.is_retryable()

    def test_validate_connection_raises_auth_error(self):
        """Test validate_connection can raise authentication error."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = AuthenticationError("Bad credentials")

        with pytest.raises(AuthenticationError):
            client.validate_connection()

    def test_code_changes_raises_errors(self):
        """Test that apply_code_changes can raise errors."""
        client = MockAgentClient()
        client._should_fail = True
        client._fail_with = RateLimitError("Rate limited")

        with pytest.raises(RateLimitError):
            client.apply_code_changes(
                CodeChangeRequest(repo_path="/repo", instructions="Fix")
            )
