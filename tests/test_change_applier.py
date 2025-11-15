"""Tests for code change applier."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from taskmaster.change_applier import (
    ChangeApplier,
    CodeBlock,
    CommandExecution,
    FileChange,
    apply_agent_changes,
)


class TestCodeBlock:
    """Tests for CodeBlock dataclass."""

    def test_creation(self):
        """Test creating a code block."""
        block = CodeBlock(
            content="print('hello')",
            language="python",
            file_path="test.py",
            start_line=5,
        )

        assert block.content == "print('hello')"
        assert block.language == "python"
        assert block.file_path == "test.py"
        assert block.start_line == 5

    def test_creation_minimal(self):
        """Test creating a minimal code block."""
        block = CodeBlock(content="echo test", language="bash")

        assert block.content == "echo test"
        assert block.language == "bash"
        assert block.file_path is None
        assert block.start_line == 0


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_creation(self):
        """Test creating a file change."""
        change = FileChange(
            path=Path("test.py"),
            operation="create",
            content="print('hello')",
            is_diff=False,
        )

        assert change.path == Path("test.py")
        assert change.operation == "create"
        assert change.content == "print('hello')"
        assert change.is_diff is False

    def test_creation_diff(self):
        """Test creating a diff change."""
        change = FileChange(
            path=Path("test.py"),
            operation="update",
            content="@@ -1,1 +1,1 @@",
            is_diff=True,
        )

        assert change.is_diff is True


class TestCommandExecution:
    """Tests for CommandExecution dataclass."""

    def test_creation(self):
        """Test creating a command execution."""
        cmd = CommandExecution(
            command="pytest",
            working_dir=Path("/tmp"),
            description="Run tests",
        )

        assert cmd.command == "pytest"
        assert cmd.working_dir == Path("/tmp")
        assert cmd.description == "Run tests"


class TestChangeApplierParsing:
    """Tests for parsing agent responses."""

    def test_parse_response_simple_code_block(self):
        """Test parsing a simple code block."""
        response = """
Here is some code:

```python
print('hello world')
```
"""
        applier = ChangeApplier()
        blocks = applier.parse_response(response)

        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].content == "print('hello world')"
        assert blocks[0].file_path is None

    def test_parse_response_code_block_with_file_path(self):
        """Test parsing a code block with file path."""
        response = """
Update the main file:

```python:src/main.py
def main():
    print('updated')
```
"""
        applier = ChangeApplier()
        blocks = applier.parse_response(response)

        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].file_path == "src/main.py"
        assert "def main():" in blocks[0].content

    def test_parse_response_multiple_blocks(self):
        """Test parsing multiple code blocks."""
        response = """
Update these files:

```python:src/foo.py
def foo():
    pass
```

```python:src/bar.py
def bar():
    pass
```

```bash
pytest
```
"""
        applier = ChangeApplier()
        blocks = applier.parse_response(response)

        assert len(blocks) == 3
        assert blocks[0].language == "python"
        assert blocks[0].file_path == "src/foo.py"
        assert blocks[1].language == "python"
        assert blocks[1].file_path == "src/bar.py"
        assert blocks[2].language == "bash"
        assert blocks[2].file_path is None

    def test_parse_response_diff_block(self):
        """Test parsing a diff block."""
        response = """
Apply this patch:

```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old line
+new line
```
"""
        applier = ChangeApplier()
        blocks = applier.parse_response(response)

        assert len(blocks) == 1
        assert blocks[0].language == "diff"
        assert "--- a/file.py" in blocks[0].content

    def test_parse_response_no_blocks(self):
        """Test parsing response with no code blocks."""
        response = "This is just plain text with no code blocks."
        applier = ChangeApplier()
        blocks = applier.parse_response(response)

        assert len(blocks) == 0


class TestChangeApplierExtraction:
    """Tests for extracting changes from code blocks."""

    def test_extract_file_changes_create(self):
        """Test extracting file change for creation."""
        blocks = [
            CodeBlock(
                content="print('hello')",
                language="python",
                file_path="new_file.py",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            applier = ChangeApplier(working_dir=Path(tmpdir))
            changes = applier.extract_file_changes(blocks)

            assert len(changes) == 1
            assert changes[0].operation == "create"
            assert changes[0].content == "print('hello')"
            assert changes[0].path.name == "new_file.py"

    def test_extract_file_changes_update(self):
        """Test extracting file change for update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing file
            existing_file = Path(tmpdir) / "existing.py"
            existing_file.write_text("old content")

            blocks = [
                CodeBlock(
                    content="new content",
                    language="python",
                    file_path="existing.py",
                )
            ]

            applier = ChangeApplier(working_dir=Path(tmpdir))
            changes = applier.extract_file_changes(blocks)

            assert len(changes) == 1
            assert changes[0].operation == "update"
            assert changes[0].content == "new content"

    def test_extract_file_changes_skip_commands(self):
        """Test that shell commands are not treated as file changes."""
        blocks = [
            CodeBlock(content="pytest", language="bash"),
            CodeBlock(content="npm install", language="sh"),
        ]

        applier = ChangeApplier()
        changes = applier.extract_file_changes(blocks)

        assert len(changes) == 0

    def test_extract_file_changes_skip_diffs(self):
        """Test that diffs are not treated as regular file changes."""
        blocks = [
            CodeBlock(
                content="--- a/file.py\n+++ b/file.py",
                language="diff",
            )
        ]

        applier = ChangeApplier()
        changes = applier.extract_file_changes(blocks)

        assert len(changes) == 0

    def test_extract_file_changes_only_with_path(self):
        """Test that only blocks with file paths are extracted."""
        blocks = [
            CodeBlock(content="print('hello')", language="python"),  # No path
            CodeBlock(content="print('world')", language="python", file_path="test.py"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            applier = ChangeApplier(working_dir=Path(tmpdir))
            changes = applier.extract_file_changes(blocks)

            # Only the one with file_path should be extracted
            assert len(changes) == 1
            assert changes[0].path.name == "test.py"

    def test_extract_diffs(self):
        """Test extracting diff changes."""
        blocks = [
            CodeBlock(
                content="""--- a/file.py
+++ b/file.py
@@ -1,1 +1,1 @@
-old
+new""",
                language="diff",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            applier = ChangeApplier(working_dir=Path(tmpdir))
            changes = applier.extract_diffs(blocks)

            assert len(changes) == 1
            assert changes[0].is_diff is True
            assert changes[0].operation == "update"
            assert changes[0].path.name == "file.py"

    def test_extract_diffs_no_path(self):
        """Test extracting diff without recognizable path."""
        blocks = [
            CodeBlock(
                content="@@ -1,1 +1,1 @@\n-old\n+new",
                language="diff",
            )
        ]

        applier = ChangeApplier()
        changes = applier.extract_diffs(blocks)

        # Should not extract if path can't be determined
        assert len(changes) == 0

    def test_extract_commands(self):
        """Test extracting shell commands."""
        blocks = [
            CodeBlock(content="pytest\nruff check", language="bash"),
            CodeBlock(content="npm install", language="sh"),
        ]

        applier = ChangeApplier()
        commands = applier.extract_commands(blocks)

        # pytest, ruff check, npm install
        assert len(commands) == 3
        assert commands[0].command == "pytest"
        assert commands[1].command == "ruff check"
        assert commands[2].command == "npm install"

    def test_extract_commands_skip_comments(self):
        """Test that comments are skipped in command extraction."""
        blocks = [
            CodeBlock(
                content="# This is a comment\npytest\n# Another comment\nruff check",
                language="bash",
            )
        ]

        applier = ChangeApplier()
        commands = applier.extract_commands(blocks)

        assert len(commands) == 2
        assert commands[0].command == "pytest"
        assert commands[1].command == "ruff check"

    def test_extract_commands_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        blocks = [CodeBlock(content="pytest\n\n\nruff check\n\n", language="bash")]

        applier = ChangeApplier()
        commands = applier.extract_commands(blocks)

        assert len(commands) == 2


class TestChangeApplierApplication:
    """Tests for applying changes."""

    def test_apply_file_change_create(self):
        """Test applying a file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            change = FileChange(
                path=file_path,
                operation="create",
                content="print('hello')",
            )

            applier = ChangeApplier(working_dir=Path(tmpdir))
            success = applier.apply_file_change(change)

            assert success is True
            assert file_path.exists()
            assert file_path.read_text() == "print('hello')"

    def test_apply_file_change_update(self):
        """Test applying a file update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            file_path.write_text("old content")

            change = FileChange(
                path=file_path,
                operation="update",
                content="new content",
            )

            applier = ChangeApplier(working_dir=Path(tmpdir))
            success = applier.apply_file_change(change)

            assert success is True
            assert file_path.read_text() == "new content"

    def test_apply_file_change_delete(self):
        """Test applying a file deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            file_path.write_text("content")

            change = FileChange(
                path=file_path,
                operation="delete",
            )

            applier = ChangeApplier(working_dir=Path(tmpdir))
            success = applier.apply_file_change(change)

            assert success is True
            assert not file_path.exists()

    def test_apply_file_change_create_subdirs(self):
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "subdir" / "nested" / "test.py"
            change = FileChange(
                path=file_path,
                operation="create",
                content="content",
            )

            applier = ChangeApplier(working_dir=Path(tmpdir))
            success = applier.apply_file_change(change)

            assert success is True
            assert file_path.exists()
            assert file_path.parent.exists()

    def test_apply_file_change_dry_run(self):
        """Test that dry run doesn't actually apply changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            change = FileChange(
                path=file_path,
                operation="create",
                content="content",
            )

            applier = ChangeApplier(dry_run=True, working_dir=Path(tmpdir))
            success = applier.apply_file_change(change)

            # Should report success but not create file
            assert success is True
            assert not file_path.exists()

    @patch("subprocess.run")
    def test_apply_command_success(self, mock_run):
        """Test applying a shell command successfully."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

        command = CommandExecution(command="pytest")
        applier = ChangeApplier()
        success = applier.apply_command(command)

        assert success is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == "pytest"

    @patch("subprocess.run")
    def test_apply_command_failure(self, mock_run):
        """Test handling command failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error occurred")

        command = CommandExecution(command="failing-command")
        applier = ChangeApplier()
        success = applier.apply_command(command)

        assert success is False

    @patch("subprocess.run")
    def test_apply_command_timeout(self, mock_run):
        """Test handling command timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

        command = CommandExecution(command="slow-command")
        applier = ChangeApplier()
        success = applier.apply_command(command)

        assert success is False

    def test_apply_command_dry_run(self):
        """Test that dry run doesn't execute commands."""
        command = CommandExecution(command="rm -rf /")
        applier = ChangeApplier(dry_run=True)
        success = applier.apply_command(command)

        # Should report success but not actually run
        assert success is True


class TestChangeApplierIntegration:
    """Integration tests for applying all changes."""

    def test_apply_all_changes_mixed(self):
        """Test applying mixed file changes and commands."""
        response = """
Create a new file:

```python:src/new.py
def new_function():
    pass
```

And run tests:

```bash
pytest
```
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                applier = ChangeApplier(working_dir=Path(tmpdir))
                success_count, fail_count = applier.apply_all_changes(response)

                # Should have 1 file change and 1 command
                assert success_count == 2
                assert fail_count == 0

                # Check file was created
                new_file = Path(tmpdir) / "src" / "new.py"
                assert new_file.exists()

                # Check command was executed
                mock_run.assert_called_once()

    def test_apply_all_changes_dry_run(self):
        """Test dry run mode for all changes."""
        response = """
```python:test.py
print('hello')
```

```bash
pytest
```
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = ChangeApplier(dry_run=True, working_dir=Path(tmpdir))
            success_count, fail_count = applier.apply_all_changes(response)

            # Should report success
            assert success_count == 2
            assert fail_count == 0

            # But no actual changes
            test_file = Path(tmpdir) / "test.py"
            assert not test_file.exists()

    def test_apply_all_changes_no_changes(self):
        """Test response with no code changes."""
        response = "This is just a text response with no code blocks."

        applier = ChangeApplier()
        success_count, fail_count = applier.apply_all_changes(response)

        assert success_count == 0
        assert fail_count == 0


class TestApplyAgentChanges:
    """Tests for convenience function."""

    def test_apply_agent_changes(self):
        """Test convenience function."""
        response = """
```python:test.py
print('hello')
```
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            success_count, fail_count = apply_agent_changes(response, working_dir=Path(tmpdir))

            assert success_count == 1
            assert fail_count == 0

            test_file = Path(tmpdir) / "test.py"
            assert test_file.exists()

    def test_apply_agent_changes_dry_run(self):
        """Test convenience function with dry run."""
        response = """
```python:test.py
print('hello')
```
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            success_count, fail_count = apply_agent_changes(
                response, dry_run=True, working_dir=Path(tmpdir)
            )

            assert success_count == 1
            assert fail_count == 0

            # No actual file created
            test_file = Path(tmpdir) / "test.py"
            assert not test_file.exists()
