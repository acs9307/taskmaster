"""OpenAI agent client implementation using OpenAI API."""

import os
from typing import Optional

try:
    import openai
except ImportError:
    openai = None  # type: ignore

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


class OpenAIClient(AgentClient):
    """
    Client for interacting with OpenAI API.

    Supports GPT-4, GPT-3.5-Turbo, and other OpenAI models with
    rate limiting, authentication, and error recovery.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model: OpenAI model to use (gpt-4, gpt-3.5-turbo, etc.)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature

        # Check if openai is available
        if openai is None:
            raise FatalError("openai package not installed. Run: pip install openai")

        self._openai = openai
        self.client = openai.OpenAI(api_key=self.api_key)

    def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Generate a completion using OpenAI.

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
            # Build messages for OpenAI API
            messages = []

            # Add system message if provided
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})

            # Add user message
            messages.append({"role": "user", "content": request.prompt})

            # Prepare API call parameters
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": request.max_tokens or self.default_max_tokens,
            }

            # Add optional parameters
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            else:
                kwargs["temperature"] = self.default_temperature

            if request.stop_sequences:
                kwargs["stop"] = request.stop_sequences

            # Make API call
            response = self.client.chat.completions.create(**kwargs)

            # Extract content from response
            content = response.choices[0].message.content or ""

            # Build usage dict
            usage = {}
            if hasattr(response, "usage") and response.usage:
                if hasattr(response.usage, "prompt_tokens"):
                    usage["prompt_tokens"] = response.usage.prompt_tokens
                if hasattr(response.usage, "completion_tokens"):
                    usage["completion_tokens"] = response.usage.completion_tokens
                if hasattr(response.usage, "total_tokens"):
                    usage["total_tokens"] = response.usage.total_tokens

            return CompletionResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                metadata={"id": response.id, "created": response.created},
            )

        except Exception as e:
            # Map OpenAI errors to our error types
            raise self._map_error(e) from e

    def apply_code_changes(self, request: CodeChangeRequest) -> CodeChangeResponse:
        """
        Apply code changes via OpenAI.

        This uses OpenAI's chat API to generate code change suggestions
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

        completion_request = CompletionRequest(prompt=user_prompt, system_prompt=system_prompt)

        # Get completion from OpenAI
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
        """Get the OpenAI model name."""
        return self.model

    def validate_connection(self) -> bool:
        """
        Validate connection to OpenAI API.

        Returns:
            True if connection is valid

        Raises:
            AuthenticationError: If API key is invalid
            TransientError: If connection cannot be established
        """
        try:
            # Try a minimal API call to validate credentials
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            raise self._map_error(e) from e

    def get_rate_limits(self) -> dict:
        """
        Get rate limit information for OpenAI API.

        Returns:
            Dictionary with rate limit info
        """
        # OpenAI's current limits (varies by tier and model)
        return {
            "requests_per_minute": 500,  # Varies by tier
            "tokens_per_minute": 10000,  # Varies by tier and model
            "note": "Actual limits depend on your API tier and model",
        }

    def _map_error(self, error: Exception):
        """
        Map OpenAI API errors to our error types.

        Args:
            error: Original exception from OpenAI SDK

        Returns:
            Mapped AgentError subclass
        """
        error_message = str(error)
        error_class_name = error.__class__.__name__

        # Check for OpenAI-specific errors by class name
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
                f"OpenAI API rate limit exceeded: {error_message}",
                retry_after=retry_after,
                original_error=error,
            )

        if error_class_name == "AuthenticationError":
            return AuthenticationError(
                f"OpenAI API authentication failed: {error_message}",
                original_error=error,
            )

        if error_class_name == "BadRequestError":
            return FatalError(
                f"Invalid request to OpenAI API: {error_message}",
                original_error=error,
            )

        if error_class_name == "InternalServerError":
            return TransientError(
                f"OpenAI API server error: {error_message}",
                original_error=error,
            )

        if error_class_name == "APIConnectionError":
            return TransientError(
                f"Failed to connect to OpenAI API: {error_message}",
                original_error=error,
            )

        if error_class_name == "APITimeoutError" or error_class_name == "Timeout":
            return TransientError(
                f"OpenAI API request timed out: {error_message}",
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
