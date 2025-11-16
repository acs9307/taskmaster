"""Tests for prompt builder."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from taskmaster.models import Task
from taskmaster.prompt_builder import (
    PromptBuilder,
    PromptComponents,
    PromptContext,
    build_prompt_for_task,
)


class TestPromptComponents:
    """Tests for PromptComponents."""

    def test_to_full_prompt_basic(self):
        """Test converting components to full prompt with basic content."""
        components = PromptComponents(
            system_prompt="System instructions",
            task_description="Do something",
        )

        full_prompt = components.to_full_prompt()

        assert "Do something" in full_prompt
        # System prompt is separate, not in full prompt
        assert "System instructions" not in full_prompt

    def test_to_full_prompt_with_context(self):
        """Test full prompt with context section."""
        components = PromptComponents(
            system_prompt="System instructions",
            task_description="Do something",
            context="Git status here",
        )

        full_prompt = components.to_full_prompt()

        assert "Do something" in full_prompt
        assert "## Context" in full_prompt
        assert "Git status here" in full_prompt

    def test_to_full_prompt_with_constraints(self):
        """Test full prompt with constraints section."""
        components = PromptComponents(
            system_prompt="System instructions",
            task_description="Do something",
            constraints="Must pass tests",
        )

        full_prompt = components.to_full_prompt()

        assert "Do something" in full_prompt
        assert "## Requirements" in full_prompt
        assert "Must pass tests" in full_prompt

    def test_to_full_prompt_complete(self):
        """Test full prompt with all sections."""
        components = PromptComponents(
            system_prompt="System instructions",
            task_description="Do something",
            context="Git status",
            constraints="Must pass tests",
        )

        full_prompt = components.to_full_prompt()

        assert "Do something" in full_prompt
        assert "## Context" in full_prompt
        assert "Git status" in full_prompt
        assert "## Requirements" in full_prompt
        assert "Must pass tests" in full_prompt


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    def test_initialization(self):
        """Test builder initialization."""
        builder = PromptBuilder()

        assert builder.default_template_path is None
        assert builder.enable_git_status is True

    def test_initialization_with_params(self):
        """Test builder initialization with parameters."""
        template_path = Path("template.txt")
        builder = PromptBuilder(default_template_path=template_path, enable_git_status=False)

        assert builder.default_template_path == template_path
        assert builder.enable_git_status is False

    def test_build_prompt_basic_task(self):
        """Test building prompt for basic task."""
        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert components.system_prompt
        assert "coding assistant" in components.system_prompt.lower()
        assert "Test task" in components.task_description
        assert "Do something" in components.task_description
        assert "T1" in components.task_description

    def test_build_prompt_with_metadata(self):
        """Test building prompt with task metadata."""
        task = Task(
            id="T1",
            title="Test task",
            description="Do something",
            metadata={"priority": "high", "category": "bugfix"},
        )
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "priority" in components.task_description.lower()
        assert "high" in components.task_description
        assert "category" in components.task_description.lower()
        assert "bugfix" in components.task_description

    def test_build_prompt_with_path(self):
        """Test building prompt with working directory path."""
        task = Task(id="T1", title="Test task", description="Do something", path="/app/src")
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "/app/src" in components.task_description

    def test_build_prompt_with_pre_hooks(self):
        """Test building prompt with pre-hooks."""
        task = Task(
            id="T1",
            title="Test task",
            description="Do something",
            pre_hooks=["pytest", "ruff check"],
        )
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "pre-condition" in components.constraints.lower()
        assert "pytest" in components.constraints
        assert "ruff check" in components.constraints

    def test_build_prompt_with_post_hooks(self):
        """Test building prompt with post-hooks."""
        task = Task(
            id="T1",
            title="Test task",
            description="Do something",
            post_hooks=["pytest", "ruff check"],
        )
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "post-condition" in components.constraints.lower()
        assert "pytest" in components.constraints
        assert "ruff check" in components.constraints

    def test_build_prompt_with_test_command(self):
        """Test building prompt with test command in metadata."""
        task = Task(
            id="T1",
            title="Test task",
            description="Do something",
            metadata={"test_command": "pytest tests/"},
        )
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "testing" in components.constraints.lower()
        assert "pytest tests/" in components.constraints

    def test_build_prompt_with_lint_command(self):
        """Test building prompt with lint command in metadata."""
        task = Task(
            id="T1",
            title="Test task",
            description="Do something",
            metadata={"lint_command": "ruff check src/"},
        )
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "linting" in components.constraints.lower()
        assert "ruff check src/" in components.constraints


class TestPromptBuilderGitStatus:
    """Tests for git status integration."""

    @patch("subprocess.run")
    def test_build_prompt_with_git_status(self, mock_run):
        """Test building prompt with git status."""
        # Mock git status output
        mock_run.return_value = MagicMock(returncode=0, stdout="## main\n M file.py\n")

        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=True)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        assert "git status" in components.context.lower()
        assert "M file.py" in components.context

    @patch("subprocess.run")
    def test_build_prompt_git_status_disabled(self, mock_run):
        """Test building prompt with git status disabled."""
        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=False)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        # Git command should not be called
        mock_run.assert_not_called()
        assert "git status" not in components.context.lower()

    @patch("subprocess.run")
    def test_build_prompt_git_status_builder_disabled(self, mock_run):
        """Test building prompt with git status disabled in builder."""
        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=True)

        builder = PromptBuilder(enable_git_status=False)
        components = builder.build_prompt(context)

        # Git command should not be called
        mock_run.assert_not_called()
        assert "git status" not in components.context.lower()

    @patch("subprocess.run")
    def test_build_prompt_git_status_not_git_repo(self, mock_run):
        """Test building prompt when not in a git repo."""
        # Mock git command failure
        mock_run.return_value = MagicMock(returncode=128, stdout="")

        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=True)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        # Should handle gracefully with empty context
        assert "M file.py" not in components.context

    @patch("subprocess.run")
    def test_build_prompt_git_status_timeout(self, mock_run):
        """Test building prompt when git command times out."""
        import subprocess

        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(task=task, include_git_status=True)

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        # Should handle gracefully with empty context
        assert components.context == ""


class TestPromptBuilderFileSnippets:
    """Tests for file snippet integration."""

    def test_build_prompt_with_file_snippets(self):
        """Test building prompt with file snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create test files
            (repo_path / "test.py").write_text("print('hello')")
            (repo_path / "test2.py").write_text("print('world')")

            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task,
                repo_path=repo_path,
                include_git_status=False,
                include_file_snippets=True,
                file_patterns=["*.py"],
            )

            builder = PromptBuilder()
            components = builder.build_prompt(context)

            assert "relevant files" in components.context.lower()
            assert "test.py" in components.context
            assert "print('hello')" in components.context

    def test_build_prompt_file_snippets_disabled(self):
        """Test building prompt with file snippets disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "test.py").write_text("print('hello')")

            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task,
                repo_path=repo_path,
                include_git_status=False,
                include_file_snippets=False,
                file_patterns=["*.py"],
            )

            builder = PromptBuilder()
            components = builder.build_prompt(context)

            assert "test.py" not in components.context

    def test_build_prompt_file_snippets_size_limit(self):
        """Test building prompt with file size limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create a large file
            large_content = "x" * 20000
            (repo_path / "large.py").write_text(large_content)

            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task,
                repo_path=repo_path,
                include_git_status=False,
                include_file_snippets=True,
                file_patterns=["*.py"],
                max_file_size=10000,
            )

            builder = PromptBuilder()
            components = builder.build_prompt(context)

            assert "large.py" in components.context
            assert "too large" in components.context.lower()
            assert large_content not in components.context

    def test_build_prompt_file_snippets_no_match(self):
        """Test building prompt when no files match patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task,
                repo_path=repo_path,
                include_git_status=False,
                include_file_snippets=True,
                file_patterns=["*.nonexistent"],
            )

            builder = PromptBuilder()
            components = builder.build_prompt(context)

            # Context should be empty
            assert components.context == ""


class TestPromptBuilderTemplate:
    """Tests for template customization."""

    def test_build_prompt_with_custom_template(self):
        """Test building prompt with custom template."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(
                """--- system ---
Custom system prompt
--- task ---
Custom Task: {title}
ID: {id}
Details: {description}
"""
            )
            f.flush()
            template_path = Path(f.name)

        try:
            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task, include_git_status=False, template_path=template_path
            )

            builder = PromptBuilder()
            components = builder.build_prompt(context)

            assert components.system_prompt == "Custom system prompt"
            assert "Custom Task: Test task" in components.task_description
            assert "ID: T1" in components.task_description
            assert "Details: Do something" in components.task_description
        finally:
            template_path.unlink()

    def test_build_prompt_with_default_template(self):
        """Test building prompt with default template from builder."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("--- system ---\nDefault template system prompt")
            f.flush()
            template_path = Path(f.name)

        try:
            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(task=task, include_git_status=False)

            builder = PromptBuilder(default_template_path=template_path)
            components = builder.build_prompt(context)

            assert components.system_prompt == "Default template system prompt"
        finally:
            template_path.unlink()

    def test_build_prompt_template_override(self):
        """Test that context template overrides builder default template."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("--- system ---\nDefault template")
            f1.flush()
            default_template = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            f2.write("--- system ---\nOverride template")
            f2.flush()
            override_template = Path(f2.name)

        try:
            task = Task(id="T1", title="Test task", description="Do something")
            context = PromptContext(
                task=task, include_git_status=False, template_path=override_template
            )

            builder = PromptBuilder(default_template_path=default_template)
            components = builder.build_prompt(context)

            assert components.system_prompt == "Override template"
        finally:
            default_template.unlink()
            override_template.unlink()

    def test_build_prompt_template_not_found(self):
        """Test building prompt when template file doesn't exist."""
        task = Task(id="T1", title="Test task", description="Do something")
        context = PromptContext(
            task=task,
            include_git_status=False,
            template_path=Path("/nonexistent/template.txt"),
        )

        builder = PromptBuilder()
        components = builder.build_prompt(context)

        # Should fall back to default system prompt
        assert "coding assistant" in components.system_prompt.lower()


class TestBuildPromptForTask:
    """Tests for convenience function."""

    def test_build_prompt_for_task(self):
        """Test convenience function."""
        task = Task(id="T1", title="Test task", description="Do something")

        components = build_prompt_for_task(task)

        assert components.system_prompt
        assert "Test task" in components.task_description
        assert "Do something" in components.task_description

    def test_build_prompt_for_task_with_repo_path(self):
        """Test convenience function with custom repo path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            task = Task(id="T1", title="Test task", description="Do something")

            components = build_prompt_for_task(task, repo_path=repo_path)

            assert components.system_prompt
            assert "Test task" in components.task_description
