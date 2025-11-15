# TaskMaster Architecture

This document describes the core architecture and domain models of TaskMaster, an AI-powered task orchestration and automation tool.

## Overview

TaskMaster is designed to execute a series of tasks using AI agents (like Claude or OpenAI Codex), with support for pre/post-task hooks, dependency management, failure handling, and rate limiting.

## Core Domain Models

### Task

The `Task` model represents a single unit of work to be executed by an AI agent.

**Key Attributes:**
- `id`: Unique identifier (e.g., "T1", "setup-database")
- `title`: Short, human-readable title
- `description`: Detailed description of what needs to be accomplished
- `path`: Working directory where the task should be executed
- `metadata`: Extensible dictionary for task-specific data
- `pre_hooks`: List of hook IDs to execute before the agent runs
- `post_hooks`: List of hook IDs to execute after the agent completes
- `status`: Current state (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
- `failure_count`: Number of times the task has failed

**Methods:**
- `mark_completed()`: Marks task as successfully completed
- `mark_failed()`: Marks task as failed and increments failure count
- `mark_running()`: Marks task as currently in progress
- `mark_skipped()`: Marks task as skipped

**Example:**
```python
task = Task(
    id="T1",
    title="Setup database schema",
    description="Create initial database tables and indexes",
    path="./backend",
    pre_hooks=["install-deps"],
    post_hooks=["run-tests"],
    metadata={"priority": "high"}
)
```

### TaskList

The `TaskList` model manages an ordered collection of tasks with dependency tracking.

**Key Attributes:**
- `tasks`: Ordered list of Task objects
- `dependencies`: Map of task_id → list of dependency task_ids
- `current_index`: Index of the currently executing task

**Methods:**
- `add_task(task, depends_on)`: Add a task with optional dependencies
- `get_current_task()`: Get the task at current_index
- `advance()`: Move to the next task in the list
- `get_pending_tasks()`: Filter tasks by PENDING status
- `get_completed_tasks()`: Filter tasks by COMPLETED status
- `get_failed_tasks()`: Filter tasks by FAILED status

**Example:**
```python
task_list = TaskList()
task_list.add_task(task1)
task_list.add_task(task2, depends_on=["T1"])  # T2 depends on T1
```

### Hook

The `Hook` model represents shell commands executed before or after task execution (e.g., tests, linters, build steps).

**Key Attributes:**
- `id`: Unique identifier for referencing from tasks
- `name`: Human-readable name
- `command`: Shell command to execute
- `hook_type`: PRE_TASK or POST_TASK
- `working_dir`: Optional working directory override
- `timeout`: Optional timeout in seconds
- `continue_on_failure`: Whether to continue if the hook fails

**Example:**
```python
test_hook = Hook(
    id="run-tests",
    name="Run Test Suite",
    command="pytest tests/",
    hook_type=HookType.POST_TASK,
    timeout=300,
    continue_on_failure=False
)
```

### AgentRequest

The `AgentRequest` model encapsulates a request to an AI agent.

**Key Attributes:**
- `task`: The Task object to be executed
- `prompt`: Formatted prompt string for the agent
- `context`: Additional context (git status, file contents, etc.)
- `max_tokens`: Maximum tokens for the response
- `temperature`: Sampling temperature (0.0 - 1.0)

**Example:**
```python
request = AgentRequest(
    task=task,
    prompt="Implement the database schema as described...",
    context={"git_status": "clean", "current_branch": "main"},
    max_tokens=4000,
    temperature=0.7
)
```

### AgentResponse

The `AgentResponse` model captures the output from an AI agent.

**Key Attributes:**
- `task_id`: ID of the task this response is for
- `content`: Full text response from the agent
- `code_edits`: List of CodeEdit objects with suggested changes
- `commands`: List of shell commands suggested by the agent
- `logs`: Execution logs from the agent
- `success`: Boolean indicating successful completion
- `error`: Error message if the agent failed

**Example:**
```python
response = AgentResponse(
    task_id="T1",
    content="I have created the database schema...",
    code_edits=[edit1, edit2],
    commands=["alembic upgrade head"],
    success=True
)
```

### CodeEdit

The `CodeEdit` model represents a suggested code change.

**Key Attributes:**
- `file_path`: Path to the file to be modified
- `original`: Original content
- `modified`: Modified content
- `description`: Human-readable description of the change

## Architectural Flow

```
┌──────────────┐
│  Task List   │
│  (YAML/JSON) │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│   Task Runner    │ ◄─── Resume from state file
│   (Main Loop)    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   Pre-Hooks      │ ─── Execute shell commands
│   (Tests, Deps)  │     (install, lint, etc.)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Prompt Builder  │ ─── Construct agent prompt
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Agent Client    │ ─── Call Claude/Codex API
│  (Claude/Codex)  │     with rate limit checks
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Agent Response  │ ─── Parse code edits,
│   Processing     │     commands, logs
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   Post-Hooks     │ ─── Run tests, validation
│   (Tests, Build) │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Failure Check   │ ─── If failed, retry or
│  & Escalation    │     escalate to user
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   Save State     │ ─── Persist progress
│  (for resume)    │     for resumability
└──────────────────┘
```

## Key Design Principles

### 1. Separation of Concerns
Each model has a single, well-defined responsibility. Tasks describe work, Hooks describe validation, Agents execute, and TaskList manages orchestration.

### 2. Extensibility
The `metadata` field in Task and `context` field in AgentRequest allow for future extensions without breaking existing code.

### 3. Type Safety
All models use Python dataclasses with type hints for compile-time checking and better IDE support.

### 4. Immutability Where Possible
Models favor explicit state transitions (e.g., `mark_completed()`) rather than direct field manipulation.

### 5. Resumability
Task status and failure counts enable resuming from interruptions (rate limits, crashes, user abort).

## State Management

TaskMaster maintains a state file (`.agent-runner/state.json`) containing:
- Current task index
- Status of each task
- Failure counts
- Rate limit usage tracking
- Last known error per task

This enables safe resumption after any stopping condition.

## Future Considerations

- **Parallel Task Execution**: Currently sequential, could support parallel execution for independent tasks
- **Advanced Dependency Resolution**: More sophisticated DAG-based dependency handling
- **Plugin System**: Allow custom hooks, agents, and prompt templates
- **Distributed Execution**: Execute tasks across multiple machines
- **Rollback Support**: Ability to undo changes from failed tasks
