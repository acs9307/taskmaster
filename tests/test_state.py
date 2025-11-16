"""Tests for state management."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from taskmaster.config import RateLimitConfig
from taskmaster.state import (
    RunState,
    calculate_next_reset,
    clear_state,
    get_state_file_path,
    load_state,
    save_state,
)


class TestCalculateNextReset:
    """Tests for calculate_next_reset utility function."""

    def test_next_minute_reset(self):
        """Test calculating next minute boundary."""
        next_reset = calculate_next_reset("minute")
        now = datetime.utcnow()

        # Should be in the future
        assert next_reset > now
        # Should be at second 0
        assert next_reset.second == 0
        assert next_reset.microsecond == 0
        # Should be within 60 seconds
        assert (next_reset - now).total_seconds() <= 60

    def test_next_hour_reset(self):
        """Test calculating next hour boundary."""
        next_reset = calculate_next_reset("hour")
        now = datetime.utcnow()

        # Should be in the future
        assert next_reset > now
        # Should be at minute 0, second 0
        assert next_reset.minute == 0
        assert next_reset.second == 0
        assert next_reset.microsecond == 0
        # Should be within 1 hour
        assert (next_reset - now).total_seconds() <= 3600

    def test_next_day_reset(self):
        """Test calculating next day boundary."""
        next_reset = calculate_next_reset("day")
        now = datetime.utcnow()

        # Should be in the future
        assert next_reset > now
        # Should be at midnight (hour 0, minute 0, second 0)
        assert next_reset.hour == 0
        assert next_reset.minute == 0
        assert next_reset.second == 0
        assert next_reset.microsecond == 0
        # Should be within 24 hours
        assert (next_reset - now).total_seconds() <= 86400

    def test_next_week_reset(self):
        """Test calculating next week boundary."""
        next_reset = calculate_next_reset("week")
        now = datetime.utcnow()

        # Should be in the future
        assert next_reset > now
        # Should be at Monday midnight
        assert next_reset.weekday() == 0  # Monday
        assert next_reset.hour == 0
        assert next_reset.minute == 0
        assert next_reset.second == 0
        # Should be within 7 days
        assert (next_reset - now).total_seconds() <= 7 * 86400

    def test_invalid_window_type(self):
        """Test that invalid window type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown window type"):
            calculate_next_reset("invalid")


class TestRunState:
    """Tests for RunState model."""

    def test_create_run_state(self):
        """Test creating a run state."""
        state = RunState(task_file="tasks.yml")
        assert state.task_file == "tasks.yml"
        assert state.completed_task_ids == []
        assert state.current_task_index == 0
        assert state.failure_counts == {}
        assert state.attempt_counts == {}
        assert state.non_progress_counts == {}
        assert state.user_interventions == {}
        assert state.last_errors == {}
        assert state.usage_records == []
        assert state.created_at is not None
        assert state.updated_at is not None

    def test_run_state_with_data(self):
        """Test creating run state with initial data."""
        state = RunState(
            task_file="tasks.yml",
            completed_task_ids=["T1", "T2"],
            current_task_index=2,
            failure_counts={"T3": 1},
            last_errors={"T3": "Some error"},
        )
        assert state.completed_task_ids == ["T1", "T2"]
        assert state.current_task_index == 2
        assert state.failure_counts == {"T3": 1}
        assert state.last_errors == {"T3": "Some error"}

    def test_mark_task_completed(self):
        """Test marking a task as completed."""
        state = RunState(task_file="tasks.yml")
        state.mark_task_completed("T1")

        assert "T1" in state.completed_task_ids
        assert len(state.completed_task_ids) == 1

    def test_mark_task_completed_no_duplicates(self):
        """Test that marking same task twice doesn't create duplicates."""
        state = RunState(task_file="tasks.yml")
        state.mark_task_completed("T1")
        state.mark_task_completed("T1")

        assert state.completed_task_ids.count("T1") == 1
        assert len(state.completed_task_ids) == 1

    def test_increment_failure_count(self):
        """Test incrementing failure count."""
        state = RunState(task_file="tasks.yml")
        state.increment_failure_count("T1", "Error 1")

        assert state.failure_counts["T1"] == 1
        assert state.last_errors["T1"] == "Error 1"

    def test_increment_failure_count_multiple_times(self):
        """Test incrementing failure count multiple times."""
        state = RunState(task_file="tasks.yml")
        state.increment_failure_count("T1", "Error 1")
        state.increment_failure_count("T1", "Error 2")
        state.increment_failure_count("T1", "Error 3")

        assert state.failure_counts["T1"] == 3
        assert state.last_errors["T1"] == "Error 3"

    def test_increment_failure_count_without_error(self):
        """Test incrementing failure count without error message."""
        state = RunState(task_file="tasks.yml")
        state.increment_failure_count("T1")

        assert state.failure_counts["T1"] == 1
        assert "T1" not in state.last_errors

    def test_advance_to_next_task(self):
        """Test advancing to next task."""
        state = RunState(task_file="tasks.yml")
        assert state.current_task_index == 0

        state.advance_to_next_task()
        assert state.current_task_index == 1

        state.advance_to_next_task()
        assert state.current_task_index == 2

    def test_is_task_completed(self):
        """Test checking if task is completed."""
        state = RunState(task_file="tasks.yml")
        state.mark_task_completed("T1")

        assert state.is_task_completed("T1") is True
        assert state.is_task_completed("T2") is False

    def test_get_failure_count(self):
        """Test getting failure count for a task."""
        state = RunState(task_file="tasks.yml")
        state.increment_failure_count("T1")
        state.increment_failure_count("T1")

        assert state.get_failure_count("T1") == 2
        assert state.get_failure_count("T2") == 0

    def test_get_last_error(self):
        """Test getting last error for a task."""
        state = RunState(task_file="tasks.yml")
        state.increment_failure_count("T1", "Test error")

        assert state.get_last_error("T1") == "Test error"
        assert state.get_last_error("T2") is None

    def test_increment_attempt_count(self):
        """Test incrementing attempt count."""
        state = RunState(task_file="tasks.yml")
        state.increment_attempt_count("T1")

        assert state.attempt_counts["T1"] == 1

    def test_increment_attempt_count_multiple_times(self):
        """Test incrementing attempt count multiple times."""
        state = RunState(task_file="tasks.yml")
        state.increment_attempt_count("T1")
        state.increment_attempt_count("T1")
        state.increment_attempt_count("T1")

        assert state.attempt_counts["T1"] == 3

    def test_get_attempt_count(self):
        """Test getting attempt count for a task."""
        state = RunState(task_file="tasks.yml")
        state.increment_attempt_count("T1")
        state.increment_attempt_count("T1")

        assert state.get_attempt_count("T1") == 2
        assert state.get_attempt_count("T2") == 0

    def test_attempt_count_independent_of_failure_count(self):
        """Test that attempt count and failure count are independent."""
        state = RunState(task_file="tasks.yml")

        # Three attempts, two failures
        state.increment_attempt_count("T1")
        state.increment_failure_count("T1", "First failure")

        state.increment_attempt_count("T1")
        state.increment_failure_count("T1", "Second failure")

        state.increment_attempt_count("T1")
        # Third attempt succeeds (no failure increment)

        assert state.get_attempt_count("T1") == 3
        assert state.get_failure_count("T1") == 2

    def test_increment_non_progress_count(self):
        """Test incrementing non-progress count."""
        state = RunState(task_file="tasks.yml")
        state.increment_non_progress_count("T1")

        assert state.non_progress_counts["T1"] == 1

    def test_increment_non_progress_count_multiple_times(self):
        """Test incrementing non-progress count multiple times."""
        state = RunState(task_file="tasks.yml")
        state.increment_non_progress_count("T1")
        state.increment_non_progress_count("T1")
        state.increment_non_progress_count("T1")

        assert state.non_progress_counts["T1"] == 3

    def test_get_non_progress_count(self):
        """Test getting non-progress count for a task."""
        state = RunState(task_file="tasks.yml")
        state.increment_non_progress_count("T1")
        state.increment_non_progress_count("T1")

        assert state.get_non_progress_count("T1") == 2
        assert state.get_non_progress_count("T2") == 0

    def test_non_progress_count_independent(self):
        """Test that non-progress count is independent of other counts."""
        state = RunState(task_file="tasks.yml")

        # Task with attempts, failures, and non-progress
        state.increment_attempt_count("T1")
        state.increment_failure_count("T1", "Error")
        state.increment_non_progress_count("T1")

        state.increment_attempt_count("T1")
        state.increment_failure_count("T1", "Error")
        # This attempt made progress

        state.increment_attempt_count("T1")
        state.increment_non_progress_count("T1")

        # Verify all counters are independent
        assert state.get_attempt_count("T1") == 3
        assert state.get_failure_count("T1") == 2
        assert state.get_non_progress_count("T1") == 2

    def test_record_user_intervention(self):
        """Test recording user intervention."""
        state = RunState(task_file="tasks.yml")
        state.record_user_intervention("T1", "retry")

        assert state.user_interventions["T1"] == "retry"

    def test_record_user_intervention_multiple(self):
        """Test recording multiple user interventions."""
        state = RunState(task_file="tasks.yml")
        state.record_user_intervention("T1", "retry")
        state.record_user_intervention("T2", "skip")
        state.record_user_intervention("T3", "abort")

        assert state.user_interventions["T1"] == "retry"
        assert state.user_interventions["T2"] == "skip"
        assert state.user_interventions["T3"] == "abort"

    def test_get_user_intervention(self):
        """Test getting user intervention."""
        state = RunState(task_file="tasks.yml")
        state.record_user_intervention("T1", "skip")

        assert state.get_user_intervention("T1") == "skip"
        assert state.get_user_intervention("T2") is None

    def test_record_user_intervention_updates_timestamp(self):
        """Test that recording intervention updates timestamp."""
        state = RunState(task_file="tasks.yml")
        initial_updated = state.updated_at

        import time

        time.sleep(0.01)

        state.record_user_intervention("T1", "retry")
        assert state.updated_at != initial_updated

    def test_to_dict(self):
        """Test converting state to dictionary."""
        state = RunState(
            task_file="tasks.yml",
            completed_task_ids=["T1"],
            current_task_index=1,
        )
        data = state.to_dict()

        assert data["task_file"] == "tasks.yml"
        assert data["completed_task_ids"] == ["T1"]
        assert data["current_task_index"] == 1
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        """Test creating state from dictionary."""
        data = {
            "task_file": "tasks.yml",
            "completed_task_ids": ["T1", "T2"],
            "current_task_index": 2,
            "failure_counts": {"T3": 1},
            "attempt_counts": {"T3": 2},
            "non_progress_counts": {"T3": 1},
            "user_interventions": {"T3": "retry"},
            "last_errors": {"T3": "Error"},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
        }
        state = RunState.from_dict(data)

        assert state.task_file == "tasks.yml"
        assert state.completed_task_ids == ["T1", "T2"]
        assert state.current_task_index == 2
        assert state.failure_counts == {"T3": 1}
        assert state.attempt_counts == {"T3": 2}
        assert state.non_progress_counts == {"T3": 1}
        assert state.user_interventions == {"T3": "retry"}
        assert state.last_errors == {"T3": "Error"}
        assert state.created_at == "2024-01-01T00:00:00"
        assert state.updated_at == "2024-01-01T01:00:00"

    def test_timestamps_auto_initialized(self):
        """Test that timestamps are auto-initialized."""
        state = RunState(task_file="tasks.yml")

        assert state.created_at is not None
        assert state.updated_at is not None
        # Both should be set to the same initial value
        assert state.created_at == state.updated_at

    def test_updated_at_changes_on_modifications(self):
        """Test that updated_at changes when state is modified."""
        state = RunState(task_file="tasks.yml")
        initial_updated = state.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        state.mark_task_completed("T1")
        assert state.updated_at != initial_updated

    def test_record_usage(self):
        """Test recording API usage."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)

        assert len(state.usage_records) == 1
        record = state.usage_records[0]
        assert record["provider"] == "claude"
        assert record["tokens"] == 1000
        assert record["requests"] == 1
        assert "timestamp" in record

    def test_record_usage_multiple(self):
        """Test recording multiple usage records."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("claude", tokens=500, requests=1)
        state.record_usage("openai", tokens=2000, requests=1)

        assert len(state.usage_records) == 3

    def test_get_usage_for_window_empty(self):
        """Test getting usage when no records exist."""
        state = RunState(task_file="tasks.yml")
        tokens, requests = state.get_usage_for_window("claude", 60)

        assert tokens == 0
        assert requests == 0

    def test_get_usage_for_window_single_provider(self):
        """Test getting usage for a single provider."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("claude", tokens=500, requests=1)
        state.record_usage("openai", tokens=2000, requests=1)

        tokens, requests = state.get_usage_for_window("claude", 60)
        assert tokens == 1500
        assert requests == 2

    def test_get_usage_for_window_filters_provider(self):
        """Test that usage filtering by provider works correctly."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("openai", tokens=2000, requests=1)

        tokens, requests = state.get_usage_for_window("claude", 60)
        assert tokens == 1000
        assert requests == 1

        tokens, requests = state.get_usage_for_window("openai", 60)
        assert tokens == 2000
        assert requests == 1

    def test_get_usage_for_window_time_filtering(self):
        """Test that usage filtering by time window works."""
        from datetime import datetime

        state = RunState(task_file="tasks.yml")

        # Add an old record (2 hours ago)
        old_time = datetime.utcnow() - timedelta(hours=2)
        old_record = {
            "timestamp": old_time.isoformat(),
            "provider": "claude",
            "tokens": 1000,
            "requests": 1,
        }
        state.usage_records.append(old_record)

        # Add a recent record
        state.record_usage("claude", tokens=500, requests=1)

        # Get usage for last hour (should only include recent)
        tokens, requests = state.get_usage_for_window("claude", 60)
        assert tokens == 500
        assert requests == 1

        # Get usage for last 3 hours (should include both)
        tokens, requests = state.get_usage_for_window("claude", 180)
        assert tokens == 1500
        assert requests == 2

    def test_get_hourly_usage(self):
        """Test getting hourly usage."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("claude", tokens=500, requests=1)

        tokens, requests = state.get_hourly_usage("claude")
        assert tokens == 1500
        assert requests == 2

    def test_get_daily_usage(self):
        """Test getting daily usage."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("claude", tokens=500, requests=1)

        tokens, requests = state.get_daily_usage("claude")
        assert tokens == 1500
        assert requests == 2

    def test_get_weekly_usage(self):
        """Test getting weekly usage."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("claude", tokens=500, requests=1)

        tokens, requests = state.get_weekly_usage("claude")
        assert tokens == 1500
        assert requests == 2

    def test_cleanup_old_usage_records(self):
        """Test cleaning up old usage records."""
        from datetime import datetime

        state = RunState(task_file="tasks.yml")

        # Add old records (8 days ago)
        old_time = datetime.utcnow() - timedelta(days=8)
        old_record = {
            "timestamp": old_time.isoformat(),
            "provider": "claude",
            "tokens": 1000,
            "requests": 1,
        }
        state.usage_records.append(old_record)

        # Add recent records
        state.record_usage("claude", tokens=500, requests=1)
        state.record_usage("openai", tokens=2000, requests=1)

        # Should have 3 records
        assert len(state.usage_records) == 3

        # Cleanup (keep 7 days)
        state.cleanup_old_usage_records(days_to_keep=7)

        # Should only have 2 recent records
        assert len(state.usage_records) == 2
        # Old record should be removed
        for record in state.usage_records:
            timestamp = datetime.fromisoformat(record["timestamp"])
            assert timestamp > datetime.utcnow() - timedelta(days=7)

    def test_cleanup_old_usage_records_custom_days(self):
        """Test cleaning up old records with custom retention period."""
        from datetime import datetime

        state = RunState(task_file="tasks.yml")

        # Add records at different times
        for days_ago in [15, 10, 5, 1]:
            old_time = datetime.utcnow() - timedelta(days=days_ago)
            record = {
                "timestamp": old_time.isoformat(),
                "provider": "claude",
                "tokens": 100,
                "requests": 1,
            }
            state.usage_records.append(record)

        # Keep only last 7 days
        state.cleanup_old_usage_records(days_to_keep=7)
        assert len(state.usage_records) == 2  # Only 5 and 1 day old records

        # Keep only last 3 days
        state.cleanup_old_usage_records(days_to_keep=3)
        assert len(state.usage_records) == 1  # Only 1 day old record

    def test_usage_records_persist_in_serialization(self):
        """Test that usage records are included in to_dict/from_dict."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)
        state.record_usage("openai", tokens=500, requests=1)

        # Convert to dict
        state_dict = state.to_dict()
        assert "usage_records" in state_dict
        assert len(state_dict["usage_records"]) == 2

        # Recreate from dict
        restored_state = RunState.from_dict(state_dict)
        assert len(restored_state.usage_records) == 2
        assert restored_state.usage_records[0]["provider"] == "claude"
        assert restored_state.usage_records[0]["tokens"] == 1000

    def test_check_rate_limit_no_limits(self):
        """Test check_rate_limit when no limits are configured."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=10000, requests=100)

        # No limits configured (all None)
        rate_limits = RateLimitConfig()
        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=1000, rate_limits=rate_limits
        )

        assert can_proceed is True
        assert limit_type is None
        assert next_reset is None

    def test_check_rate_limit_under_all_limits(self):
        """Test check_rate_limit when usage is under all limits."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=1000, requests=1)

        rate_limits = RateLimitConfig(
            max_tokens_hour=10000,
            max_tokens_day=50000,
            max_tokens_week=200000,
            max_requests_minute=10,
        )

        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=500, rate_limits=rate_limits
        )

        assert can_proceed is True
        assert limit_type is None
        assert next_reset is None

    def test_check_rate_limit_exceeds_hourly_tokens(self):
        """Test check_rate_limit when hourly token limit would be exceeded."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=9000, requests=1)

        rate_limits = RateLimitConfig(max_tokens_hour=10000)

        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=2000, rate_limits=rate_limits
        )

        assert can_proceed is False
        assert limit_type == "tokens_per_hour"
        assert next_reset is not None
        assert next_reset > datetime.utcnow()

    def test_check_rate_limit_exceeds_daily_tokens(self):
        """Test check_rate_limit when daily token limit would be exceeded."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=45000, requests=1)

        rate_limits = RateLimitConfig(max_tokens_day=50000)

        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=6000, rate_limits=rate_limits
        )

        assert can_proceed is False
        assert limit_type == "tokens_per_day"
        assert next_reset is not None

    def test_check_rate_limit_exceeds_weekly_tokens(self):
        """Test check_rate_limit when weekly token limit would be exceeded."""
        state = RunState(task_file="tasks.yml")
        state.record_usage("claude", tokens=190000, requests=1)

        rate_limits = RateLimitConfig(max_tokens_week=200000)

        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=15000, rate_limits=rate_limits
        )

        assert can_proceed is False
        assert limit_type == "tokens_per_week"
        assert next_reset is not None

    def test_check_rate_limit_exceeds_requests_per_minute(self):
        """Test check_rate_limit when requests per minute would be exceeded."""
        state = RunState(task_file="tasks.yml")
        # Add 10 requests in the last minute
        for _ in range(10):
            state.record_usage("claude", tokens=100, requests=1)

        rate_limits = RateLimitConfig(max_requests_minute=10)

        can_proceed, limit_type, next_reset = state.check_rate_limit(
            "claude", estimated_tokens=100, rate_limits=rate_limits
        )

        assert can_proceed is False
        assert limit_type == "requests_per_minute"
        assert next_reset is not None

    def test_check_rate_limit_different_providers(self):
        """Test that rate limits are checked per provider."""
        state = RunState(task_file="tasks.yml")
        # Claude has high usage
        state.record_usage("claude", tokens=9000, requests=1)
        # OpenAI has low usage
        state.record_usage("openai", tokens=100, requests=1)

        rate_limits = RateLimitConfig(max_tokens_hour=10000)

        # Claude should be blocked
        can_proceed, _, _ = state.check_rate_limit(
            "claude", estimated_tokens=2000, rate_limits=rate_limits
        )
        assert can_proceed is False

        # OpenAI should be allowed
        can_proceed, _, _ = state.check_rate_limit(
            "openai", estimated_tokens=2000, rate_limits=rate_limits
        )
        assert can_proceed is True

    def test_check_rate_limit_multiple_limits_first_fails(self):
        """Test that first exceeded limit is returned when multiple limits exist."""
        state = RunState(task_file="tasks.yml")
        # Add 10 requests (will hit requests/minute limit first)
        for _ in range(10):
            state.record_usage("claude", tokens=1000, requests=1)

        rate_limits = RateLimitConfig(
            max_requests_minute=10,
            max_tokens_hour=5000,  # This is also exceeded
        )

        can_proceed, limit_type, _ = state.check_rate_limit(
            "claude", estimated_tokens=100, rate_limits=rate_limits
        )

        assert can_proceed is False
        # requests_per_minute is checked first
        assert limit_type == "requests_per_minute"


class TestStateFileOperations:
    """Tests for state file operations."""

    def test_get_state_file_path(self):
        """Test getting state file path."""
        path = get_state_file_path()
        assert path.name == "state.json"
        assert path.parent.name == ".taskmaster"

    def test_save_and_load_state(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Create and save state
            original_state = RunState(
                task_file="tasks.yml",
                completed_task_ids=["T1", "T2"],
                current_task_index=2,
            )
            save_state(original_state, state_file)

            # Load state
            loaded_state = load_state(state_file)

            assert loaded_state is not None
            assert loaded_state.task_file == "tasks.yml"
            assert loaded_state.completed_task_ids == ["T1", "T2"]
            assert loaded_state.current_task_index == 2

    def test_load_nonexistent_state(self):
        """Test loading state when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"
            state = load_state(state_file)
            assert state is None

    def test_save_state_creates_directory(self):
        """Test that save_state creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "subdir" / "state.json"
            state = RunState(task_file="tasks.yml")

            save_state(state, state_file)

            assert state_file.exists()
            assert state_file.parent.exists()

    def test_save_state_atomic_write(self):
        """Test that save_state uses atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Save initial state
            state1 = RunState(task_file="tasks1.yml")
            save_state(state1, state_file)

            # Save updated state
            state2 = RunState(task_file="tasks2.yml")
            save_state(state2, state_file)

            # Load and verify it's the latest
            loaded = load_state(state_file)
            assert loaded.task_file == "tasks2.yml"

            # Verify no temp files left behind
            temp_files = list(Path(tmpdir).glob(".state_*"))
            assert len(temp_files) == 0

    def test_save_state_updates_timestamp(self):
        """Test that save_state updates the timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state = RunState(task_file="tasks.yml")
            original_updated = state.updated_at

            import time

            time.sleep(0.01)

            save_state(state, state_file)

            # Load and check timestamp was updated
            loaded = load_state(state_file)
            assert loaded.updated_at != original_updated

    def test_load_invalid_json(self):
        """Test loading state with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Write invalid JSON
            with open(state_file, "w") as f:
                f.write("invalid json [")

            # Should raise ValueError
            with pytest.raises(ValueError, match="Failed to load state file"):
                load_state(state_file)

    def test_clear_state(self):
        """Test clearing state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Create state
            state = RunState(task_file="tasks.yml")
            save_state(state, state_file)
            assert state_file.exists()

            # Clear state
            clear_state(state_file)
            assert not state_file.exists()

    def test_clear_nonexistent_state(self):
        """Test clearing state that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"

            # Should not raise error
            clear_state(state_file)

    def test_state_roundtrip_with_all_fields(self):
        """Test complete roundtrip with all fields populated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Create state with all fields
            original = RunState(
                task_file="tasks.yml",
                completed_task_ids=["T1", "T2", "T3"],
                current_task_index=3,
                failure_counts={"T4": 2, "T5": 1},
                attempt_counts={"T4": 3, "T5": 2},
                non_progress_counts={"T4": 1},
                user_interventions={"T4": "retry", "T5": "skip"},
                last_errors={"T4": "Error A", "T5": "Error B"},
            )

            # Save and load
            save_state(original, state_file)
            loaded = load_state(state_file)

            # Verify all fields
            assert loaded.task_file == original.task_file
            assert loaded.completed_task_ids == original.completed_task_ids
            assert loaded.current_task_index == original.current_task_index
            assert loaded.failure_counts == original.failure_counts
            assert loaded.attempt_counts == original.attempt_counts
            assert loaded.non_progress_counts == original.non_progress_counts
            assert loaded.user_interventions == original.user_interventions
            assert loaded.last_errors == original.last_errors

    def test_state_file_format(self):
        """Test that state file is properly formatted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state = RunState(
                task_file="tasks.yml",
                completed_task_ids=["T1"],
                current_task_index=1,
            )
            save_state(state, state_file)

            # Read and verify JSON is properly formatted
            with open(state_file) as f:
                data = json.load(f)

            assert "task_file" in data
            assert "completed_task_ids" in data
            assert "current_task_index" in data
            assert "failure_counts" in data
            assert "attempt_counts" in data
            assert "non_progress_counts" in data
            assert "user_interventions" in data
            assert "last_errors" in data
            assert "created_at" in data
            assert "updated_at" in data


class TestStateIntegration:
    """Integration tests for state management."""

    def test_multiple_task_execution_simulation(self):
        """Test simulating multiple task executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            # Start fresh
            state = RunState(task_file="tasks.yml")

            # Complete first task
            state.mark_task_completed("T1")
            state.current_task_index = 1
            save_state(state, state_file)

            # Reload and complete second task
            state = load_state(state_file)
            state.mark_task_completed("T2")
            state.current_task_index = 2
            save_state(state, state_file)

            # Reload and verify
            state = load_state(state_file)
            assert state.completed_task_ids == ["T1", "T2"]
            assert state.current_task_index == 2

    def test_failure_tracking_simulation(self):
        """Test simulating task failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state = RunState(task_file="tasks.yml")

            # Task T1 fails once
            state.increment_failure_count("T1", "First error")
            save_state(state, state_file)

            # Reload and fail again
            state = load_state(state_file)
            state.increment_failure_count("T1", "Second error")
            save_state(state, state_file)

            # Reload and verify
            state = load_state(state_file)
            assert state.get_failure_count("T1") == 2
            assert state.get_last_error("T1") == "Second error"
