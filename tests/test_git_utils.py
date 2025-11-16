"""Tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from taskmaster.git_utils import get_git_diff, get_git_status, has_changes


class TestGetGitDiff:
    """Tests for get_git_diff function."""

    @patch("subprocess.run")
    def test_get_git_diff_success(self, mock_run):
        """Test getting git diff successfully."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="diff --git a/file.py b/file.py\n+new line",
        )

        result = get_git_diff(Path("/tmp/repo"))

        assert result == "diff --git a/file.py b/file.py\n+new line"
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "diff", "HEAD"]
        assert mock_run.call_args[1]["cwd"] == Path("/tmp/repo")

    @patch("subprocess.run")
    def test_get_git_diff_empty(self, mock_run):
        """Test getting git diff when there are no changes."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = get_git_diff(Path("/tmp/repo"))

        assert result == ""

    @patch("subprocess.run")
    def test_get_git_diff_not_git_repo(self, mock_run):
        """Test getting git diff in a non-git repository."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")

        result = get_git_diff(Path("/tmp/not-a-repo"))

        assert result is None

    @patch("subprocess.run")
    def test_get_git_diff_timeout(self, mock_run):
        """Test getting git diff with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git diff HEAD", 5)

        result = get_git_diff(Path("/tmp/repo"))

        assert result is None

    @patch("subprocess.run")
    def test_get_git_diff_command_not_found(self, mock_run):
        """Test getting git diff when git command not found."""
        mock_run.side_effect = FileNotFoundError()

        result = get_git_diff(Path("/tmp/repo"))

        assert result is None

    @patch("subprocess.run")
    def test_get_git_diff_custom_timeout(self, mock_run):
        """Test getting git diff with custom timeout."""
        mock_run.return_value = MagicMock(returncode=0, stdout="diff content")

        get_git_diff(Path("/tmp/repo"), timeout=10)

        assert mock_run.call_args[1]["timeout"] == 10


class TestGetGitStatus:
    """Tests for get_git_status function."""

    @patch("subprocess.run")
    def test_get_git_status_success(self, mock_run):
        """Test getting git status successfully."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="## main\n M file.py\n",
        )

        result = get_git_status(Path("/tmp/repo"))

        assert result == "## main\n M file.py"
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "status", "--short", "--branch"]

    @patch("subprocess.run")
    def test_get_git_status_clean(self, mock_run):
        """Test getting git status when repo is clean."""
        mock_run.return_value = MagicMock(returncode=0, stdout="## main\n")

        result = get_git_status(Path("/tmp/repo"))

        assert result == "## main"

    @patch("subprocess.run")
    def test_get_git_status_not_git_repo(self, mock_run):
        """Test getting git status in a non-git repository."""
        mock_run.return_value = MagicMock(returncode=128, stdout="")

        result = get_git_status(Path("/tmp/not-a-repo"))

        assert result is None

    @patch("subprocess.run")
    def test_get_git_status_timeout(self, mock_run):
        """Test getting git status with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git status", 5)

        result = get_git_status(Path("/tmp/repo"))

        assert result is None


class TestHasChanges:
    """Tests for has_changes function."""

    def test_has_changes_different_diffs(self):
        """Test has_changes with different diffs."""
        diff_before = "diff --git a/file.py b/file.py\n-old line"
        diff_after = "diff --git a/file.py b/file.py\n+new line"

        assert has_changes(diff_before, diff_after) is True

    def test_has_changes_same_diffs(self):
        """Test has_changes with same diffs."""
        diff = "diff --git a/file.py b/file.py\n M file.py"

        assert has_changes(diff, diff) is False

    def test_has_changes_both_empty(self):
        """Test has_changes when both diffs are empty."""
        assert has_changes("", "") is False

    def test_has_changes_both_none(self):
        """Test has_changes when both diffs are None."""
        assert has_changes(None, None) is False

    def test_has_changes_before_none_after_has_content(self):
        """Test has_changes when before is None and after has content."""
        assert has_changes(None, "diff content") is True

    def test_has_changes_before_has_content_after_none(self):
        """Test has_changes when before has content and after is None."""
        assert has_changes("diff content", None) is True

    def test_has_changes_before_empty_after_has_content(self):
        """Test has_changes when before is empty and after has content."""
        assert has_changes("", "diff content") is True

    def test_has_changes_before_has_content_after_empty(self):
        """Test has_changes when before has content and after is empty."""
        assert has_changes("diff content", "") is True

    def test_has_changes_whitespace_differences(self):
        """Test has_changes with whitespace differences."""
        diff_before = "diff content\n"
        diff_after = "diff content\n "

        # Exact string comparison - whitespace differences count as changes
        assert has_changes(diff_before, diff_after) is True
