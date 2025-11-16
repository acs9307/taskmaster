"""Git utilities for TaskMaster."""

import subprocess
from pathlib import Path
from typing import Optional


def get_git_diff(repo_path: Path, timeout: int = 5) -> Optional[str]:
    """
    Get git diff for the repository.

    Args:
        repo_path: Path to the repository
        timeout: Timeout in seconds for the git command

    Returns:
        Git diff output or None if not a git repo or on error
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


def get_git_status(repo_path: Path, timeout: int = 5) -> Optional[str]:
    """
    Get git status for the repository.

    Args:
        repo_path: Path to the repository
        timeout: Timeout in seconds for the git command

    Returns:
        Git status output or None if not a git repo or on error
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


def has_changes(diff_before: Optional[str], diff_after: Optional[str]) -> bool:
    """
    Check if there are changes between two git diffs.

    Args:
        diff_before: Git diff before an operation
        diff_after: Git diff after an operation

    Returns:
        True if changes were made (diffs are different), False otherwise
    """
    # Treat None as empty string
    before = diff_before or ""
    after = diff_after or ""

    # Compare the diffs
    return before != after
