"""Tests for domain models."""


from taskmaster.models import (
    AgentRequest,
    AgentResponse,
    CodeEdit,
    Hook,
    HookType,
    Task,
    TaskList,
    TaskStatus,
)


class TestTask:
    """Tests for the Task model."""

    def test_task_creation(self):
        """Test creating a basic task."""
        task = Task(
            id="T1",
            title="Setup project",
            description="Create initial project structure",
            path="/tmp/project",
        )
        assert task.id == "T1"
        assert task.title == "Setup project"
        assert task.description == "Create initial project structure"
        assert task.path == "/tmp/project"
        assert task.status == TaskStatus.PENDING
        assert task.failure_count == 0

    def test_task_with_hooks(self):
        """Test task with pre and post hooks."""
        task = Task(
            id="T2",
            title="Run tests",
            description="Execute test suite",
            pre_hooks=["install-deps"],
            post_hooks=["cleanup"],
        )
        assert task.pre_hooks == ["install-deps"]
        assert task.post_hooks == ["cleanup"]

    def test_task_with_metadata(self):
        """Test task with custom metadata."""
        task = Task(
            id="T3",
            title="Deploy",
            description="Deploy to production",
            metadata={"env": "production", "version": "1.0.0"},
        )
        assert task.metadata["env"] == "production"
        assert task.metadata["version"] == "1.0.0"

    def test_mark_completed(self):
        """Test marking a task as completed."""
        task = Task(id="T4", title="Test", description="Test task")
        task.mark_completed()
        assert task.status == TaskStatus.COMPLETED

    def test_mark_failed(self):
        """Test marking a task as failed."""
        task = Task(id="T5", title="Test", description="Test task")
        task.mark_failed()
        assert task.status == TaskStatus.FAILED
        assert task.failure_count == 1

        task.mark_failed()
        assert task.failure_count == 2

    def test_mark_running(self):
        """Test marking a task as running."""
        task = Task(id="T6", title="Test", description="Test task")
        task.mark_running()
        assert task.status == TaskStatus.RUNNING

    def test_mark_skipped(self):
        """Test marking a task as skipped."""
        task = Task(id="T7", title="Test", description="Test task")
        task.mark_skipped()
        assert task.status == TaskStatus.SKIPPED


class TestTaskList:
    """Tests for the TaskList model."""

    def test_empty_task_list(self):
        """Test creating an empty task list."""
        task_list = TaskList()
        assert len(task_list.tasks) == 0
        assert task_list.current_index == 0
        assert task_list.get_current_task() is None

    def test_add_task(self):
        """Test adding tasks to the list."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task_list.add_task(task1)
        task_list.add_task(task2)

        assert len(task_list.tasks) == 2
        assert task_list.tasks[0].id == "T1"
        assert task_list.tasks[1].id == "T2"

    def test_add_task_with_dependencies(self):
        """Test adding tasks with dependencies."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task_list.add_task(task1)
        task_list.add_task(task2, depends_on=["T1"])

        assert "T2" in task_list.dependencies
        assert task_list.dependencies["T2"] == ["T1"]

    def test_get_current_task(self):
        """Test getting the current task."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task_list.add_task(task1)
        task_list.add_task(task2)

        assert task_list.get_current_task().id == "T1"

    def test_advance(self):
        """Test advancing to the next task."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task_list.add_task(task1)
        task_list.add_task(task2)

        assert task_list.advance() is True
        assert task_list.get_current_task().id == "T2"

        # At end of list
        assert task_list.advance() is False

    def test_get_pending_tasks(self):
        """Test getting pending tasks."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")
        task3 = Task(id="T3", title="Third", description="Third task")

        task1.mark_completed()
        task2.status = TaskStatus.PENDING
        task3.status = TaskStatus.PENDING

        task_list.add_task(task1)
        task_list.add_task(task2)
        task_list.add_task(task3)

        pending = task_list.get_pending_tasks()
        assert len(pending) == 2
        assert pending[0].id == "T2"
        assert pending[1].id == "T3"

    def test_get_completed_tasks(self):
        """Test getting completed tasks."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task1.mark_completed()

        task_list.add_task(task1)
        task_list.add_task(task2)

        completed = task_list.get_completed_tasks()
        assert len(completed) == 1
        assert completed[0].id == "T1"

    def test_get_failed_tasks(self):
        """Test getting failed tasks."""
        task_list = TaskList()
        task1 = Task(id="T1", title="First", description="First task")
        task2 = Task(id="T2", title="Second", description="Second task")

        task1.mark_failed()

        task_list.add_task(task1)
        task_list.add_task(task2)

        failed = task_list.get_failed_tasks()
        assert len(failed) == 1
        assert failed[0].id == "T1"
        assert failed[0].failure_count == 1


class TestHook:
    """Tests for the Hook model."""

    def test_pre_task_hook(self):
        """Test creating a pre-task hook."""
        hook = Hook(
            id="install-deps",
            name="Install Dependencies",
            command="pip install -r requirements.txt",
            hook_type=HookType.PRE_TASK,
        )
        assert hook.id == "install-deps"
        assert hook.name == "Install Dependencies"
        assert hook.command == "pip install -r requirements.txt"
        assert hook.hook_type == HookType.PRE_TASK
        assert hook.continue_on_failure is False

    def test_post_task_hook(self):
        """Test creating a post-task hook."""
        hook = Hook(
            id="run-tests",
            name="Run Tests",
            command="pytest",
            hook_type=HookType.POST_TASK,
            timeout=300,
        )
        assert hook.hook_type == HookType.POST_TASK
        assert hook.timeout == 300

    def test_hook_with_working_dir(self):
        """Test hook with custom working directory."""
        hook = Hook(
            id="build",
            name="Build Project",
            command="make build",
            hook_type=HookType.POST_TASK,
            working_dir="/tmp/project",
        )
        assert hook.working_dir == "/tmp/project"

    def test_hook_continue_on_failure(self):
        """Test hook that continues on failure."""
        hook = Hook(
            id="optional-lint",
            name="Optional Linting",
            command="pylint src/",
            hook_type=HookType.PRE_TASK,
            continue_on_failure=True,
        )
        assert hook.continue_on_failure is True


class TestAgentRequest:
    """Tests for the AgentRequest model."""

    def test_agent_request_creation(self):
        """Test creating an agent request."""
        task = Task(id="T1", title="Test", description="Test task")
        request = AgentRequest(
            task=task,
            prompt="Please implement the following task...",
        )
        assert request.task.id == "T1"
        assert request.prompt == "Please implement the following task..."
        assert request.temperature == 0.7

    def test_agent_request_with_context(self):
        """Test agent request with context."""
        task = Task(id="T2", title="Test", description="Test task")
        request = AgentRequest(
            task=task,
            prompt="Implement feature X",
            context={"git_status": "clean", "files": ["main.py"]},
            max_tokens=2000,
        )
        assert request.context["git_status"] == "clean"
        assert request.max_tokens == 2000


class TestAgentResponse:
    """Tests for the AgentResponse model."""

    def test_successful_response(self):
        """Test creating a successful agent response."""
        response = AgentResponse(
            task_id="T1",
            content="I have completed the task successfully.",
            success=True,
        )
        assert response.task_id == "T1"
        assert response.success is True
        assert response.error is None

    def test_failed_response(self):
        """Test creating a failed agent response."""
        response = AgentResponse(
            task_id="T2",
            content="Failed to complete task",
            success=False,
            error="Rate limit exceeded",
        )
        assert response.success is False
        assert response.error == "Rate limit exceeded"

    def test_response_with_code_edits(self):
        """Test response with code edits."""
        edit1 = CodeEdit(
            file_path="src/main.py",
            original="def old():",
            modified="def new():",
            description="Renamed function",
        )
        edit2 = CodeEdit(
            file_path="src/utils.py",
            original="x = 1",
            modified="x = 2",
            description="Updated value",
        )
        response = AgentResponse(
            task_id="T3",
            content="Made code changes",
            code_edits=[edit1, edit2],
        )
        assert len(response.code_edits) == 2
        assert response.code_edits[0].file_path == "src/main.py"
        assert response.code_edits[1].file_path == "src/utils.py"

    def test_response_with_commands(self):
        """Test response with suggested commands."""
        response = AgentResponse(
            task_id="T4",
            content="Please run these commands",
            commands=["git add .", "git commit -m 'Update'"],
        )
        assert len(response.commands) == 2
        assert response.commands[0] == "git add ."

    def test_response_with_logs(self):
        """Test response with execution logs."""
        response = AgentResponse(
            task_id="T5",
            content="Task completed",
            logs="Starting task...\nProcessing...\nCompleted successfully",
        )
        assert "Starting task" in response.logs
        assert "Completed successfully" in response.logs


class TestCodeEdit:
    """Tests for the CodeEdit model."""

    def test_code_edit_creation(self):
        """Test creating a code edit."""
        edit = CodeEdit(
            file_path="/tmp/test.py",
            original="print('old')",
            modified="print('new')",
            description="Updated print statement",
        )
        assert edit.file_path == "/tmp/test.py"
        assert edit.original == "print('old')"
        assert edit.modified == "print('new')"
        assert edit.description == "Updated print statement"

    def test_code_edit_without_description(self):
        """Test code edit without description."""
        edit = CodeEdit(
            file_path="main.py",
            original="a = 1",
            modified="a = 2",
        )
        assert edit.description == ""
