"""State management for task execution persistence."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def calculate_next_reset(window_type: str) -> datetime:
    """
    Calculate the next reset time for a given rate limit window.

    Args:
        window_type: Type of window - 'minute', 'hour', 'day', or 'week'

    Returns:
        datetime of next reset boundary (UTC)
    """
    now = datetime.utcnow()

    if window_type == "minute":
        # Next minute boundary
        next_reset = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    elif window_type == "hour":
        # Next hour boundary
        next_reset = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif window_type == "day":
        # Next day boundary (midnight UTC)
        next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif window_type == "week":
        # Next week boundary (Monday midnight UTC)
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=days_until_monday
        )
    else:
        raise ValueError(f"Unknown window type: {window_type}")

    return next_reset


@dataclass
class RunState:
    """
    Represents the execution state of a task run.

    This state can be persisted to disk and resumed later.
    """

    task_file: str
    completed_task_ids: list[str] = field(default_factory=list)
    current_task_index: int = 0
    failure_counts: dict[str, int] = field(default_factory=dict)
    attempt_counts: dict[str, int] = field(default_factory=dict)
    non_progress_counts: dict[str, int] = field(default_factory=dict)
    user_interventions: dict[str, str] = field(default_factory=dict)
    last_errors: dict[str, str] = field(default_factory=dict)
    usage_records: list[dict] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.utcnow().isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def mark_task_completed(self, task_id: str):
        """Mark a task as completed."""
        if task_id not in self.completed_task_ids:
            self.completed_task_ids.append(task_id)
        self.updated_at = datetime.utcnow().isoformat()

    def increment_failure_count(self, task_id: str, error_message: str = ""):
        """Increment failure count for a task."""
        self.failure_counts[task_id] = self.failure_counts.get(task_id, 0) + 1
        if error_message:
            self.last_errors[task_id] = error_message
        self.updated_at = datetime.utcnow().isoformat()

    def increment_attempt_count(self, task_id: str):
        """Increment attempt count for a task."""
        self.attempt_counts[task_id] = self.attempt_counts.get(task_id, 0) + 1
        self.updated_at = datetime.utcnow().isoformat()

    def advance_to_next_task(self):
        """Move to the next task."""
        self.current_task_index += 1
        self.updated_at = datetime.utcnow().isoformat()

    def is_task_completed(self, task_id: str) -> bool:
        """Check if a task has been completed."""
        return task_id in self.completed_task_ids

    def get_failure_count(self, task_id: str) -> int:
        """Get the failure count for a task."""
        return self.failure_counts.get(task_id, 0)

    def get_attempt_count(self, task_id: str) -> int:
        """Get the attempt count for a task."""
        return self.attempt_counts.get(task_id, 0)

    def increment_non_progress_count(self, task_id: str):
        """Increment non-progress count for a task (when no changes are made but tests fail)."""
        self.non_progress_counts[task_id] = self.non_progress_counts.get(task_id, 0) + 1
        self.updated_at = datetime.utcnow().isoformat()

    def get_non_progress_count(self, task_id: str) -> int:
        """Get the non-progress count for a task."""
        return self.non_progress_counts.get(task_id, 0)

    def record_user_intervention(self, task_id: str, action: str):
        """Record a user intervention action for a task (retry, skip, abort)."""
        self.user_interventions[task_id] = action
        self.updated_at = datetime.utcnow().isoformat()

    def get_user_intervention(self, task_id: str) -> Optional[str]:
        """Get the user intervention action for a task."""
        return self.user_interventions.get(task_id)

    def get_last_error(self, task_id: str) -> Optional[str]:
        """Get the last error message for a task."""
        return self.last_errors.get(task_id)

    def record_usage(self, provider: str, tokens: int = 0, requests: int = 0):
        """
        Record API usage for rate limit tracking.

        Args:
            provider: Provider name (e.g., 'claude', 'openai')
            tokens: Number of tokens used
            requests: Number of requests made
        """
        usage_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "tokens": tokens,
            "requests": requests,
        }
        self.usage_records.append(usage_record)
        self.updated_at = datetime.utcnow().isoformat()

    def get_usage_for_window(self, provider: str, window_minutes: int) -> tuple[int, int]:
        """
        Get total usage (tokens, requests) for a provider within a time window.

        Args:
            provider: Provider name to filter by
            window_minutes: Time window in minutes from now

        Returns:
            Tuple of (total_tokens, total_requests) within the window
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=window_minutes)

        total_tokens = 0
        total_requests = 0

        for record in self.usage_records:
            # Filter by provider
            if record.get("provider") != provider:
                continue

            # Parse timestamp and check if within window
            try:
                record_time = datetime.fromisoformat(record["timestamp"])
                if record_time >= cutoff:
                    total_tokens += record.get("tokens", 0)
                    total_requests += record.get("requests", 0)
            except (ValueError, KeyError):
                # Skip invalid records
                continue

        return total_tokens, total_requests

    def get_hourly_usage(self, provider: str) -> tuple[int, int]:
        """
        Get usage for the last hour.

        Args:
            provider: Provider name

        Returns:
            Tuple of (tokens, requests) used in last hour
        """
        return self.get_usage_for_window(provider, 60)

    def get_daily_usage(self, provider: str) -> tuple[int, int]:
        """
        Get usage for the last 24 hours.

        Args:
            provider: Provider name

        Returns:
            Tuple of (tokens, requests) used in last 24 hours
        """
        return self.get_usage_for_window(provider, 24 * 60)

    def get_weekly_usage(self, provider: str) -> tuple[int, int]:
        """
        Get usage for the last 7 days.

        Args:
            provider: Provider name

        Returns:
            Tuple of (tokens, requests) used in last 7 days
        """
        return self.get_usage_for_window(provider, 7 * 24 * 60)

    def cleanup_old_usage_records(self, days_to_keep: int = 7):
        """
        Remove usage records older than specified days.

        Args:
            days_to_keep: Number of days of records to keep (default 7)
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        # Filter to keep only recent records
        self.usage_records = [
            record
            for record in self.usage_records
            if datetime.fromisoformat(record["timestamp"]) >= cutoff
        ]
        self.updated_at = datetime.utcnow().isoformat()

    def check_rate_limit(
        self, provider: str, estimated_tokens: int, rate_limits
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Check if a new API call would exceed configured rate limits.

        Args:
            provider: Provider name (e.g., 'claude', 'openai')
            estimated_tokens: Estimated tokens for the upcoming call
            rate_limits: RateLimitConfig object with limit settings

        Returns:
            Tuple of (can_proceed, limit_type, next_reset):
            - can_proceed: True if call can be made without exceeding limits
            - limit_type: Type of limit that would be exceeded (or None)
            - next_reset: When the exceeded limit will reset (or None)
        """
        # Check requests per minute
        if rate_limits.max_requests_minute is not None:
            _, current_requests = self.get_usage_for_window(provider, 1)
            if current_requests + 1 > rate_limits.max_requests_minute:
                return False, "requests_per_minute", calculate_next_reset("minute")

        # Check tokens per hour
        if rate_limits.max_tokens_hour is not None:
            current_tokens, _ = self.get_hourly_usage(provider)
            if current_tokens + estimated_tokens > rate_limits.max_tokens_hour:
                return False, "tokens_per_hour", calculate_next_reset("hour")

        # Check tokens per day
        if rate_limits.max_tokens_day is not None:
            current_tokens, _ = self.get_daily_usage(provider)
            if current_tokens + estimated_tokens > rate_limits.max_tokens_day:
                return False, "tokens_per_day", calculate_next_reset("day")

        # Check tokens per week
        if rate_limits.max_tokens_week is not None:
            current_tokens, _ = self.get_weekly_usage(provider)
            if current_tokens + estimated_tokens > rate_limits.max_tokens_week:
                return False, "tokens_per_week", calculate_next_reset("week")

        # All checks passed
        return True, None, None

    def to_dict(self) -> dict:
        """Convert state to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        """Create RunState from dictionary."""
        return cls(**data)


def get_state_file_path(task_file: Optional[Path] = None) -> Path:
    """
    Get the path to the state file.

    Args:
        task_file: Optional task file path to use for state directory

    Returns:
        Path to state.json file
    """
    # Use .taskmaster directory in current working directory
    state_dir = Path.cwd() / ".taskmaster"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "state.json"


def save_state(state: RunState, state_file: Optional[Path] = None):
    """
    Save run state to disk using atomic write.

    Args:
        state: RunState to save
        state_file: Optional path to state file (uses default if not provided)
    """
    if state_file is None:
        state_file = get_state_file_path()

    # Ensure directory exists
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Update timestamp
    state.updated_at = datetime.utcnow().isoformat()

    # Atomic write: write to temp file, then rename
    # This prevents corruption if the process is interrupted
    fd, temp_path = tempfile.mkstemp(dir=state_file.parent, prefix=".state_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state.to_dict(), f, indent=2)

        # Atomic rename
        os.replace(temp_path, state_file)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load_state(state_file: Optional[Path] = None) -> Optional[RunState]:
    """
    Load run state from disk.

    Args:
        state_file: Optional path to state file (uses default if not provided)

    Returns:
        RunState if file exists, None otherwise
    """
    if state_file is None:
        state_file = get_state_file_path()

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            data = json.load(f)
        return RunState.from_dict(data)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to load state file: {e}") from e


def clear_state(state_file: Optional[Path] = None):
    """
    Clear the state file.

    Args:
        state_file: Optional path to state file (uses default if not provided)
    """
    if state_file is None:
        state_file = get_state_file_path()

    if state_file.exists():
        state_file.unlink()
