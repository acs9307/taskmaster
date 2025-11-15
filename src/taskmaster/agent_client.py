"""Abstract base class and interfaces for AI agent providers.

This module defines the interface that all AI agent providers must implement,
along with common error types and utilities for agent interaction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ErrorType(Enum):
    """Types of errors that can occur during agent interactions."""

    RATE_LIMIT = "rate_limit"  # Hit rate limit (HTTP 429 or quota exceeded)
    AUTHENTICATION = "authentication"  # Auth failure (invalid API key, etc.)
    TRANSIENT = "transient"  # Temporary failure (network, timeout, server error)
    FATAL = "fatal"  # Non-recoverable error (invalid request, not found, etc.)
    UNKNOWN = "unknown"  # Unknown error type


class AgentError(Exception):
    """Base exception for all agent-related errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        original_error: Optional[Exception] = None,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize agent error.

        Args:
            message: Human-readable error message
            error_type: Type of error that occurred
            original_error: Original exception that caused this error
            retry_after: Seconds to wait before retrying (for rate limits)
        """
        super().__init__(message)
        self.error_type = error_type
        self.original_error = original_error
        self.retry_after = retry_after

    def is_retryable(self) -> bool:
        """Check if this error is retryable."""
        return self.error_type in (ErrorType.RATE_LIMIT, ErrorType.TRANSIENT)


class RateLimitError(AgentError):
    """Error raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            error_type=ErrorType.RATE_LIMIT,
            original_error=original_error,
            retry_after=retry_after,
        )


class AuthenticationError(AgentError):
    """Error raised when authentication fails."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(
            message, error_type=ErrorType.AUTHENTICATION, original_error=original_error
        )


class TransientError(AgentError):
    """Error raised for temporary failures."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, error_type=ErrorType.TRANSIENT, original_error=original_error)


class FatalError(AgentError):
    """Error raised for non-recoverable failures."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, error_type=ErrorType.FATAL, original_error=original_error)


@dataclass
class CompletionRequest:
    """Request to generate a completion from an AI agent."""

    prompt: str
    system_prompt: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stop_sequences: list[str] = field(default_factory=list)


@dataclass
class CompletionResponse:
    """Response from an AI agent completion request."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeChange:
    """Represents a code change to be applied."""

    file_path: str
    operation: str  # "create", "modify", "delete"
    content: Optional[str] = None
    description: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class CodeChangeRequest:
    """Request to apply code changes via an AI agent."""

    repo_path: str
    instructions: str
    context: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False


@dataclass
class CodeChangeResponse:
    """Response from a code change request."""

    changes: list[CodeChange]
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentClient(ABC):
    """
    Abstract base class for AI agent providers.

    All agent provider implementations (Claude, OpenAI, etc.) must inherit
    from this class and implement the required methods.
    """

    @abstractmethod
    def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Generate a completion from the AI agent.

        Args:
            request: Completion request with prompt and parameters

        Returns:
            CompletionResponse with generated content

        Raises:
            RateLimitError: Rate limit exceeded
            AuthenticationError: Authentication failed
            TransientError: Temporary failure (network, timeout, etc.)
            FatalError: Non-recoverable error
        """
        pass

    @abstractmethod
    def apply_code_changes(self, request: CodeChangeRequest) -> CodeChangeResponse:
        """
        Apply code changes via the AI agent.

        This is an optional feature that allows the agent to propose
        and optionally apply code changes based on natural language
        instructions.

        Args:
            request: Code change request with instructions

        Returns:
            CodeChangeResponse with proposed changes

        Raises:
            RateLimitError: Rate limit exceeded
            AuthenticationError: Authentication failed
            TransientError: Temporary failure (network, timeout, etc.)
            FatalError: Non-recoverable error
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.

        Returns:
            Model name (e.g., "claude-3-opus-20240229")
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Validate that the client can connect to the API.

        Returns:
            True if connection is valid, False otherwise

        Raises:
            AuthenticationError: If credentials are invalid
            TransientError: If connection cannot be established
        """
        pass

    def supports_code_changes(self) -> bool:
        """
        Check if this agent supports automated code changes.

        Returns:
            True if apply_code_changes is supported
        """
        return True

    def get_rate_limits(self) -> dict[str, Any]:
        """
        Get current rate limit information.

        Returns:
            Dictionary with rate limit info (requests per minute, tokens per hour, etc.)
        """
        return {}

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text.

        This is a rough estimate and may not match the actual tokenization
        used by the model.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        # Rough estimation: ~4 characters per token on average
        return len(text) // 4

    def __repr__(self) -> str:
        """String representation of the agent client."""
        return f"{self.__class__.__name__}(model={self.get_model_name()})"
