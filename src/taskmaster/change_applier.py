"""Code change applier for applying agent-suggested changes."""

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CodeBlock:
    """
    Represents a code block from agent response.

    Attributes:
        content: The code content
        language: Programming language or block type (python, bash, diff, etc.)
        file_path: Optional file path if specified in code block
        start_line: Line number where this block starts in the response
    """

    content: str
    language: str
    file_path: Optional[str] = None
    start_line: int = 0


@dataclass
class FileChange:
    """
    Represents a file change operation.

    Attributes:
        path: Path to the file
        operation: Type of operation (create, update, delete)
        content: New content for the file (for create/update)
        is_diff: Whether the content is a diff/patch
    """

    path: Path
    operation: str  # 'create', 'update', 'delete'
    content: Optional[str] = None
    is_diff: bool = False


@dataclass
class CommandExecution:
    """
    Represents a shell command to execute.

    Attributes:
        command: The command to execute
        working_dir: Working directory for command execution
        description: Optional description of what the command does
    """

    command: str
    working_dir: Optional[Path] = None
    description: Optional[str] = None


class ChangeApplier:
    """
    Parses and applies code changes from agent responses.

    This class handles extracting code blocks, diffs, and commands from
    agent responses and applying them to the repository.
    """

    # Regex pattern for markdown code blocks with optional file path
    # Matches: ```language:path/to/file or ```language
    CODE_BLOCK_PATTERN = re.compile(r"```(\w+)(?::([^\n]+))?\n(.*?)```", re.DOTALL | re.MULTILINE)

    # Common languages that indicate shell commands
    SHELL_LANGUAGES = {"bash", "sh", "shell", "zsh", "fish"}

    # Languages that indicate diffs
    DIFF_LANGUAGES = {"diff", "patch"}

    def __init__(self, dry_run: bool = False, working_dir: Optional[Path] = None):
        """
        Initialize the change applier.

        Args:
            dry_run: If True, only show what would be changed without applying
            working_dir: Working directory for file operations (defaults to cwd)
        """
        self.dry_run = dry_run
        self.working_dir = working_dir or Path.cwd()

    def parse_response(self, response_content: str) -> list[CodeBlock]:
        """
        Parse agent response to extract code blocks.

        Args:
            response_content: The agent's response text

        Returns:
            List of CodeBlock objects found in the response
        """
        code_blocks = []

        for match in self.CODE_BLOCK_PATTERN.finditer(response_content):
            language = match.group(1).lower()
            file_path = match.group(2)  # May be None
            content = match.group(3).strip()
            start_line = response_content[: match.start()].count("\n")

            # Clean up file path if present
            if file_path:
                file_path = file_path.strip()

            code_blocks.append(
                CodeBlock(
                    content=content,
                    language=language,
                    file_path=file_path,
                    start_line=start_line,
                )
            )

        return code_blocks

    def extract_file_changes(self, code_blocks: list[CodeBlock]) -> list[FileChange]:
        """
        Extract file change operations from code blocks.

        Args:
            code_blocks: List of code blocks from agent response

        Returns:
            List of FileChange objects
        """
        changes = []

        for block in code_blocks:
            # Skip shell commands and diffs (handled separately)
            if block.language in self.SHELL_LANGUAGES or block.language in self.DIFF_LANGUAGES:
                continue

            # Only process blocks with explicit file paths
            if block.file_path:
                file_path = self.working_dir / block.file_path

                # Determine operation based on file existence
                if file_path.exists():
                    operation = "update"
                else:
                    operation = "create"

                changes.append(
                    FileChange(
                        path=file_path,
                        operation=operation,
                        content=block.content,
                        is_diff=False,
                    )
                )

        return changes

    def extract_diffs(self, code_blocks: list[CodeBlock]) -> list[FileChange]:
        """
        Extract diff/patch operations from code blocks.

        Args:
            code_blocks: List of code blocks from agent response

        Returns:
            List of FileChange objects for diffs
        """
        changes = []

        for block in code_blocks:
            if block.language in self.DIFF_LANGUAGES:
                # Try to extract file path from diff content
                # Look for lines like: --- a/path/to/file or +++ b/path/to/file
                file_path = self._extract_path_from_diff(block.content)

                if file_path:
                    changes.append(
                        FileChange(
                            path=self.working_dir / file_path,
                            operation="update",
                            content=block.content,
                            is_diff=True,
                        )
                    )

        return changes

    def extract_commands(self, code_blocks: list[CodeBlock]) -> list[CommandExecution]:
        """
        Extract shell commands from code blocks.

        Args:
            code_blocks: List of code blocks from agent response

        Returns:
            List of CommandExecution objects
        """
        commands = []

        for block in code_blocks:
            if block.language in self.SHELL_LANGUAGES:
                # Split multiple commands if they exist
                for line in block.content.split("\n"):
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith("#"):
                        commands.append(
                            CommandExecution(
                                command=line,
                                working_dir=self.working_dir,
                            )
                        )

        return commands

    def apply_file_change(self, change: FileChange) -> bool:
        """
        Apply a file change operation.

        Args:
            change: The file change to apply

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            self._print_dry_run_file_change(change)
            return True

        try:
            if change.operation == "delete":
                if change.path.exists():
                    change.path.unlink()
                return True

            elif change.operation in ("create", "update"):
                if change.is_diff:
                    return self._apply_diff(change.path, change.content)
                else:
                    # Ensure parent directory exists
                    change.path.parent.mkdir(parents=True, exist_ok=True)
                    # Write content to file
                    change.path.write_text(change.content)
                    return True

        except (OSError, subprocess.SubprocessError) as e:
            print(f"Error applying change to {change.path}: {e}")
            return False

        return False

    def apply_command(self, command: CommandExecution) -> bool:
        """
        Execute a shell command.

        Args:
            command: The command to execute

        Returns:
            True if command succeeded, False otherwise
        """
        if self.dry_run:
            self._print_dry_run_command(command)
            return True

        try:
            result = subprocess.run(
                command.command,
                shell=True,
                cwd=command.working_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                if result.stdout:
                    print(result.stdout)
                return True
            else:
                print(f"Command failed with exit code {result.returncode}")
                if result.stderr:
                    print(result.stderr)
                return False

        except subprocess.TimeoutExpired:
            print(f"Command timed out: {command.command}")
            return False
        except Exception as e:
            print(f"Error executing command: {e}")
            return False

    def apply_all_changes(self, response_content: str) -> tuple[int, int]:
        """
        Parse and apply all changes from an agent response.

        Args:
            response_content: The agent's response text

        Returns:
            Tuple of (successful_changes, failed_changes)
        """
        # Parse code blocks
        code_blocks = self.parse_response(response_content)

        # Extract changes and commands
        file_changes = self.extract_file_changes(code_blocks)
        diff_changes = self.extract_diffs(code_blocks)
        commands = self.extract_commands(code_blocks)

        all_changes = file_changes + diff_changes
        success_count = 0
        fail_count = 0

        # Apply file changes
        for change in all_changes:
            if self.apply_file_change(change):
                success_count += 1
            else:
                fail_count += 1

        # Execute commands
        for command in commands:
            if self.apply_command(command):
                success_count += 1
            else:
                fail_count += 1

        return success_count, fail_count

    def _extract_path_from_diff(self, diff_content: str) -> Optional[str]:
        """
        Extract file path from diff content.

        Args:
            diff_content: The diff/patch content

        Returns:
            File path if found, None otherwise
        """
        # Look for +++ b/path/to/file or --- a/path/to/file
        for line in diff_content.split("\n"):
            if line.startswith("+++") or line.startswith("---"):
                # Extract path after a/ or b/
                match = re.search(r"[ab]/(.+)$", line)
                if match:
                    return match.group(1).strip()
        return None

    def _apply_diff(self, file_path: Path, diff_content: str) -> bool:
        """
        Apply a diff/patch to a file.

        Args:
            file_path: Path to the file to patch
            diff_content: The diff/patch content

        Returns:
            True if successful, False otherwise
        """
        # Write diff to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(diff_content)
            patch_file = Path(f.name)

        try:
            # Try to apply patch
            result = subprocess.run(
                ["patch", "-u", str(file_path), str(patch_file)],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            return result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # patch command not available or timed out
            return False
        finally:
            # Clean up temporary patch file
            patch_file.unlink(missing_ok=True)

    def _print_dry_run_file_change(self, change: FileChange) -> None:
        """Print what would be changed in dry-run mode."""
        operation_str = change.operation.upper()
        print(f"\n[DRY RUN] {operation_str}: {change.path}")

        if change.is_diff:
            print("  (Would apply diff/patch)")
            print(f"  Diff preview:\n{change.content[:200]}...")
        elif change.content and change.operation in ("create", "update"):
            lines = change.content.split("\n")
            preview_lines = lines[:5]
            print(f"  Content preview ({len(lines)} lines):")
            for line in preview_lines:
                print(f"    {line}")
            if len(lines) > 5:
                print(f"    ... ({len(lines) - 5} more lines)")

    def _print_dry_run_command(self, command: CommandExecution) -> None:
        """Print what command would be executed in dry-run mode."""
        print(f"\n[DRY RUN] EXECUTE: {command.command}")
        if command.working_dir:
            print(f"  Working directory: {command.working_dir}")
        if command.description:
            print(f"  Description: {command.description}")


def apply_agent_changes(
    response_content: str,
    dry_run: bool = False,
    working_dir: Optional[Path] = None,
) -> tuple[int, int]:
    """
    Convenience function to apply changes from an agent response.

    Args:
        response_content: The agent's response text
        dry_run: If True, only show what would be changed
        working_dir: Working directory for changes (defaults to cwd)

    Returns:
        Tuple of (successful_changes, failed_changes)
    """
    applier = ChangeApplier(dry_run=dry_run, working_dir=working_dir)
    return applier.apply_all_changes(response_content)
