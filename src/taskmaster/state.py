"""State management for task execution persistence."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


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
    last_errors: dict[str, str] = field(default_factory=dict)
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

    def get_last_error(self, task_id: str) -> Optional[str]:
        """Get the last error message for a task."""
        return self.last_errors.get(task_id)

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
