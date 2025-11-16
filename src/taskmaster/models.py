"""Domain models for TaskMaster."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(Enum):
    """Status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """
    Represents a single task to be executed by an agent.

    Attributes:
        id: Unique identifier for the task
        title: Short, descriptive title
        description: Detailed description of what the task should accomplish
        path: Working directory path for the task execution
        metadata: Additional task-specific metadata
        pre_hooks: List of hook IDs to run before agent execution
        post_hooks: List of hook IDs to run after agent execution
        status: Current status of the task
        failure_count: Number of times this task has failed
        attempt_count: Number of times this task has been attempted
    """

    id: str
    title: str
    description: str
    path: str = "."
    metadata: dict[str, Any] = field(default_factory=dict)
    pre_hooks: list[str] = field(default_factory=list)
    post_hooks: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    failure_count: int = 0
    attempt_count: int = 0

    def mark_completed(self) -> None:
        """Mark the task as completed."""
        self.status = TaskStatus.COMPLETED

    def mark_failed(self) -> None:
        """Mark the task as failed and increment failure count."""
        self.status = TaskStatus.FAILED
        self.failure_count += 1

    def mark_running(self) -> None:
        """Mark the task as currently running."""
        self.status = TaskStatus.RUNNING

    def mark_skipped(self) -> None:
        """Mark the task as skipped."""
        self.status = TaskStatus.SKIPPED

    def increment_attempt(self) -> None:
        """Increment the attempt counter for this task."""
        self.attempt_count += 1

    def reset_for_retry(self) -> None:
        """Reset task status to pending for retry (preserves failure/attempt counts)."""
        self.status = TaskStatus.PENDING


@dataclass
class TaskList:
    """
    Represents an ordered list of tasks with dependency tracking.

    Attributes:
        tasks: Ordered list of Task objects
        dependencies: Map of task_id -> list of dependency task_ids
        current_index: Index of the currently active task
    """

    tasks: list[Task] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    current_index: int = 0

    def add_task(self, task: Task, depends_on: Optional[list[str]] = None) -> None:
        """
        Add a task to the list.

        Args:
            task: The task to add
            depends_on: Optional list of task IDs this task depends on
        """
        self.tasks.append(task)
        if depends_on:
            self.dependencies[task.id] = depends_on

    def get_current_task(self) -> Optional[Task]:
        """Get the currently active task."""
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None

    def advance(self) -> bool:
        """
        Move to the next task.

        Returns:
            True if advanced to next task, False if at end of list
        """
        if self.current_index < len(self.tasks) - 1:
            self.current_index += 1
            return True
        return False

    def get_pending_tasks(self) -> list[Task]:
        """Get all tasks that are still pending."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def get_completed_tasks(self) -> list[Task]:
        """Get all tasks that have been completed."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> list[Task]:
        """Get all tasks that have failed."""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]


class HookType(Enum):
    """Type of hook."""

    PRE_TASK = "pre_task"
    POST_TASK = "post_task"


@dataclass
class Hook:
    """
    Represents a pre- or post-task command hook.

    Attributes:
        id: Unique identifier for the hook
        name: Human-readable name
        command: Shell command to execute
        hook_type: Whether this is a pre-task or post-task hook
        working_dir: Optional working directory for command execution
        timeout: Optional timeout in seconds
        continue_on_failure: Whether to continue if this hook fails
    """

    id: str
    name: str
    command: str
    hook_type: HookType
    working_dir: Optional[str] = None
    timeout: Optional[int] = None
    continue_on_failure: bool = False


@dataclass
class AgentRequest:
    """
    Represents a request to an AI agent.

    Attributes:
        task: The task to be executed
        prompt: The formatted prompt for the agent
        context: Additional context (repo state, file contents, etc.)
        max_tokens: Maximum tokens for the response
        temperature: Sampling temperature for the agent
    """

    task: Task
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    max_tokens: Optional[int] = None
    temperature: float = 0.7


@dataclass
class CodeEdit:
    """
    Represents a code edit suggestion from an agent.

    Attributes:
        file_path: Path to the file to edit
        original: Original content
        modified: Modified content
        description: Description of the change
    """

    file_path: str
    original: str
    modified: str
    description: str = ""


@dataclass
class AgentResponse:
    """
    Represents a response from an AI agent.

    Attributes:
        task_id: ID of the task this response is for
        content: The full text response from the agent
        code_edits: List of code edits suggested by the agent
        commands: List of shell commands suggested by the agent
        logs: Agent execution logs
        success: Whether the agent completed successfully
        error: Error message if the agent failed
    """

    task_id: str
    content: str
    code_edits: list[CodeEdit] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    logs: str = ""
    success: bool = True
    error: Optional[str] = None
