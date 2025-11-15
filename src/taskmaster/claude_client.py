"""Claude AI agent client implementation using Anthropic API."""

import os
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

from taskmaster.agent_client import (
    AgentClient,
    AuthenticationError,
    CodeChangeRequest,
    CodeChangeResponse,
    CompletionRequest,
    CompletionResponse,
    FatalError,
    RateLimitError,
    TransientError,
)


class ClaudeClient(AgentClient):
    """
    Client for interacting with Claude via the Anthropic API.

    Supports Claude 3 models (Opus, Sonnet, Haiku) and handles
    rate limiting, authentication, and error recovery.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature

        # Check if anthropic is available
        if anthropic is None:
            raise FatalError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Generate a completion using Claude.

        Args:
            request: Completion request with prompt and parameters

        Returns:
            CompletionResponse with generated content

        Raises:
            RateLimitError: Rate limit exceeded
            AuthenticationError: Invalid API key
            TransientError: Temporary failure
            FatalError: Non-recoverable error
        """
        try:
            # Build messages for Claude API
            messages = [{"role": "user", "content": request.prompt}]

            # Prepare API call parameters
            kwargs = {
                "model": self.model,
                "max_tokens": request.max_tokens or self.default_max_tokens,
                "messages": messages,
            }

            # Add optional parameters
            if request.system_prompt:
                kwargs["system"] = request.system_prompt

            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            else:
                kwargs["temperature"] = self.default_temperature

            if request.stop_sequences:
                kwargs["stop_sequences"] = request.stop_sequences

            # Make API call
            response = self.client.messages.create(**kwargs)

            # Extract content from response
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # Build usage dict
            usage = {}
            if hasattr(response, "usage"):
                if hasattr(response.usage, "input_tokens"):
                    usage["prompt_tokens"] = response.usage.input_tokens
                if hasattr(response.usage, "output_tokens"):
                    usage["completion_tokens"] = response.usage.output_tokens
                usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get(
                    "completion_tokens", 0
                )

            return CompletionResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=getattr(response, "stop_reason", None),
                metadata={"id": response.id, "type": response.type},
            )

        except Exception as e:
            # Map anthropic errors to our error types
            raise self._map_error(e) from e

    def apply_code_changes(
        self, request: CodeChangeRequest
    ) -> CodeChangeResponse:
        """
        Apply code changes via Claude.

        This uses Claude's completion API to generate code change suggestions
        based on natural language instructions.

        Args:
            request: Code change request with instructions

        Returns:
            CodeChangeResponse with proposed changes

        Raises:
            RateLimitError: Rate limit exceeded
            AuthenticationError: Invalid API key
            TransientError: Temporary failure
            FatalError: Non-recoverable error
        """
        # Build a prompt for code changes
        system_prompt = (
            "You are a code modification assistant. Given a repository path and "
            "instructions, analyze the code and propose specific changes. "
            "Format your response as structured change descriptions."
        )

        user_prompt = f"""
Repository: {request.repo_path}
Instructions: {request.instructions}

Please propose specific code changes to implement these instructions.
For each change, specify:
- File path
- Operation (create, modify, delete)
- Content or description of the change
"""

        if request.context:
            user_prompt += f"\n\nContext: {request.context}"

        if request.dry_run:
            user_prompt += "\n\n(This is a dry run - propose changes but don't apply)"

        completion_request = CompletionRequest(
            prompt=user_prompt, system_prompt=system_prompt
        )

        # Get completion from Claude
        response = self.generate_completion(completion_request)

        # For now, return the response as explanation
        # In a real implementation, this would parse the response
        # into structured CodeChange objects
        return CodeChangeResponse(
            changes=[],  # Would parse from response.content
            explanation=response.content,
            metadata={"model": response.model, "usage": response.usage},
        )

    def get_model_name(self) -> str:
        """Get the Claude model name."""
        return self.model

    def validate_connection(self) -> bool:
        """
        Validate connection to Anthropic API.

        Returns:
            True if connection is valid

        Raises:
            AuthenticationError: If API key is invalid
            TransientError: If connection cannot be established
        """
        try:
            # Try a minimal API call to validate credentials
            self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception as e:
            raise self._map_error(e) from e

    def get_rate_limits(self) -> dict:
        """
        Get rate limit information for Claude API.

        Returns:
            Dictionary with rate limit info
        """
        # Anthropic's current limits (as of API v1)
        return {
            "requests_per_minute": 50,  # Varies by tier
            "tokens_per_minute": 40000,  # Varies by tier
            "note": "Actual limits depend on your API tier",
        }

    def _map_error(self, error: Exception):
        """
        Map Anthropic API errors to our error types.

        Args:
            error: Original exception from Anthropic SDK

        Returns:
            Mapped AgentError subclass
        """
        error_message = str(error)
        error_class_name = error.__class__.__name__

        # Check for anthropic-specific errors by class name
        if error_class_name == "RateLimitError":
            retry_after = None
            # Try to extract retry-after from error
            if hasattr(error, "response") and hasattr(error.response, "headers"):
                retry_after = error.response.headers.get("retry-after")
                if retry_after:
                    try:
                        retry_after = int(retry_after)
                    except (ValueError, TypeError):
                        retry_after = None

            return RateLimitError(
                f"Claude API rate limit exceeded: {error_message}",
                retry_after=retry_after,
                original_error=error,
            )

        if error_class_name == "AuthenticationError":
            return AuthenticationError(
                f"Claude API authentication failed: {error_message}",
                original_error=error,
            )

        if error_class_name == "BadRequestError":
            return FatalError(
                f"Invalid request to Claude API: {error_message}",
                original_error=error,
            )

        if error_class_name == "InternalServerError":
            return TransientError(
                f"Claude API server error: {error_message}",
                original_error=error,
            )

        if error_class_name == "APIConnectionError":
            return TransientError(
                f"Failed to connect to Claude API: {error_message}",
                original_error=error,
            )

        if error_class_name == "APITimeoutError":
            return TransientError(
                f"Claude API request timed out: {error_message}",
                original_error=error,
            )

        # Fallback for unknown errors
        # Check error message for common patterns
        error_lower = error_message.lower()

        if "rate limit" in error_lower or "429" in error_lower:
            return RateLimitError(error_message, original_error=error)

        if "auth" in error_lower or "401" in error_lower or "403" in error_lower:
            return AuthenticationError(error_message, original_error=error)

        if "timeout" in error_lower or "connection" in error_lower:
            return TransientError(error_message, original_error=error)

        if "500" in error_lower or "502" in error_lower or "503" in error_lower:
            return TransientError(error_message, original_error=error)

        if "400" in error_lower or "404" in error_lower:
            return FatalError(error_message, original_error=error)

        # Default to transient for unknown errors (safer to retry)
        return TransientError(f"Unknown error: {error_message}", original_error=error)
