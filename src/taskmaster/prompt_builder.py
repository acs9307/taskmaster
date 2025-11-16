"""Prompt builder for constructing AI agent prompts from tasks."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from taskmaster.models import Task


@dataclass
class PromptContext:
    """
    Context information for building prompts.

    Attributes:
        task: The task to execute
        repo_path: Path to the repository root
        include_git_status: Whether to include git status in the prompt
        include_file_snippets: Whether to include file snippets in the prompt
        file_patterns: Patterns for files to include as snippets
        max_file_size: Maximum file size to include (in bytes)
        template_path: Optional path to custom prompt template file
    """

    task: Task
    repo_path: Path = field(default_factory=Path.cwd)
    include_git_status: bool = True
    include_file_snippets: bool = False
    file_patterns: list[str] = field(default_factory=list)
    max_file_size: int = 10000  # 10KB
    template_path: Optional[Path] = None


@dataclass
class PromptComponents:
    """
    Components of a constructed prompt.

    Attributes:
        system_prompt: System-level instructions for the agent
        task_description: The main task description
        context: Additional context (git status, files, etc.)
        constraints: Constraints and requirements (pre/post-conditions)
    """

    system_prompt: str
    task_description: str
    context: str = ""
    constraints: str = ""

    def to_full_prompt(self) -> str:
        """
        Combine all components into a single prompt.

        Returns:
            The complete prompt string
        """
        sections = [self.task_description]

        if self.context:
            sections.append(f"\n## Context\n\n{self.context}")

        if self.constraints:
            sections.append(f"\n## Requirements\n\n{self.constraints}")

        return "\n".join(sections)


class PromptBuilder:
    """
    Builder for constructing prompts from tasks.

    The PromptBuilder creates prompts that include task information,
    repository context, and constraints for AI agents to execute tasks.
    """

    DEFAULT_SYSTEM_PROMPT = """You are an AI coding assistant executing a task from a task orchestration system.

Your responsibilities:
- Understand the task description and requirements
- Consider the current repository state and context
- Execute the task according to the specified constraints
- Provide clear explanations of your changes
- Ensure all pre-conditions are met before starting
- Verify post-conditions are satisfied after completion

Be thorough, precise, and follow best practices for code quality and maintainability."""

    def __init__(
        self,
        default_template_path: Optional[Path] = None,
        enable_git_status: bool = True,
    ):
        """
        Initialize the prompt builder.

        Args:
            default_template_path: Default template file to use
            enable_git_status: Whether to enable git status by default
        """
        self.default_template_path = default_template_path
        self.enable_git_status = enable_git_status

    def build_prompt(self, context: PromptContext) -> PromptComponents:
        """
        Build a prompt from the given context.

        Args:
            context: The prompt context with task and configuration

        Returns:
            PromptComponents with all parts of the prompt
        """
        # Load template if specified
        template = self._load_template(context.template_path or self.default_template_path)

        # Build system prompt
        system_prompt = template.get("system", self.DEFAULT_SYSTEM_PROMPT)

        # Build task description
        task_description = self._build_task_description(context.task, template)

        # Build context section
        context_section = self._build_context_section(context)

        # Build constraints section
        constraints_section = self._build_constraints_section(context.task)

        return PromptComponents(
            system_prompt=system_prompt,
            task_description=task_description,
            context=context_section,
            constraints=constraints_section,
        )

    def _load_template(self, template_path: Optional[Path]) -> dict[str, str]:
        """
        Load a template file if specified.

        Args:
            template_path: Path to template file

        Returns:
            Dictionary with template sections
        """
        if not template_path or not template_path.exists():
            return {}

        # Simple template format: sections separated by --- markers
        # Format:
        # --- system ---
        # System prompt here
        # --- task ---
        # Task template here
        content = template_path.read_text()
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.strip().startswith("---") and line.strip().endswith("---"):
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                section_name = line.strip().strip("-").strip()
                current_section = section_name
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _build_task_description(self, task: Task, template: dict[str, str]) -> str:
        """
        Build the task description section.

        Args:
            task: The task to describe
            template: Template sections

        Returns:
            Formatted task description
        """
        # Use template if available, otherwise use default format
        task_template = template.get("task")

        if task_template:
            # Simple variable substitution
            description = task_template.replace("{title}", task.title)
            description = description.replace("{description}", task.description)
            description = description.replace("{id}", task.id)
            description = description.replace("{path}", task.path or ".")
            return description

        # Default format
        parts = [
            f"# Task: {task.title}",
            f"\n**Task ID:** {task.id}",
            f"\n**Description:**\n{task.description}",
        ]

        if task.path:
            parts.append(f"\n**Working Directory:** {task.path}")

        if task.metadata:
            metadata_str = "\n".join(f"- {k}: {v}" for k, v in task.metadata.items())
            parts.append(f"\n**Metadata:**\n{metadata_str}")

        return "\n".join(parts)

    def _build_context_section(self, context: PromptContext) -> str:
        """
        Build the context section with repository state.

        Args:
            context: The prompt context

        Returns:
            Formatted context section
        """
        parts = []

        # Add git status if enabled
        if context.include_git_status and self.enable_git_status:
            git_status = self._get_git_status(context.repo_path)
            if git_status:
                parts.append(f"### Git Status\n\n```\n{git_status}\n```")

        # Add file snippets if requested
        if context.include_file_snippets and context.file_patterns:
            file_snippets = self._get_file_snippets(
                context.repo_path, context.file_patterns, context.max_file_size
            )
            if file_snippets:
                parts.append(f"### Relevant Files\n\n{file_snippets}")

        return "\n\n".join(parts) if parts else ""

    def _build_constraints_section(self, task: Task) -> str:
        """
        Build the constraints section with pre/post-conditions.

        Args:
            task: The task with potential constraints

        Returns:
            Formatted constraints section
        """
        parts = []

        # Add pre-hooks as pre-conditions
        if task.pre_hooks:
            hooks_str = "\n".join(f"- `{hook}`" for hook in task.pre_hooks)
            parts.append(
                f"### Pre-conditions\n\nThe following checks must pass before starting:\n{hooks_str}"
            )

        # Add post-hooks as post-conditions
        if task.post_hooks:
            hooks_str = "\n".join(f"- `{hook}`" for hook in task.post_hooks)
            parts.append(
                f"### Post-conditions\n\nThe following checks must pass after completion:\n{hooks_str}"
            )

        # Add metadata-based constraints
        if task.metadata:
            if "test_command" in task.metadata:
                parts.append(f"\n### Testing\n\nRun tests with: `{task.metadata['test_command']}`")

            if "lint_command" in task.metadata:
                parts.append(
                    f"\n### Linting\n\nCheck code quality with: `{task.metadata['lint_command']}`"
                )

        return "\n\n".join(parts) if parts else ""

    def _get_git_status(self, repo_path: Path) -> str:
        """
        Get git status for the repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Git status output or empty string if not a git repo
        """
        try:
            result = subprocess.run(
                ["git", "status", "--short", "--branch"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return ""

    def _get_file_snippets(self, repo_path: Path, patterns: list[str], max_size: int) -> str:
        """
        Get file snippets matching the patterns.

        Args:
            repo_path: Path to the repository
            patterns: File patterns to match
            max_size: Maximum file size to include

        Returns:
            Formatted file snippets
        """
        snippets = []

        for pattern in patterns:
            # Use pathlib glob for pattern matching
            for file_path in repo_path.glob(pattern):
                if not file_path.is_file():
                    continue

                # Check file size
                try:
                    if file_path.stat().st_size > max_size:
                        snippets.append(
                            f"#### {file_path.relative_to(repo_path)}\n\n"
                            f"*File too large (>{max_size} bytes), skipped*"
                        )
                        continue

                    # Read file content
                    content = file_path.read_text()
                    rel_path = file_path.relative_to(repo_path)
                    snippets.append(f"#### {rel_path}\n\n```\n{content}\n```")
                except (OSError, UnicodeDecodeError):
                    # Skip files that can't be read
                    continue

        return "\n\n".join(snippets) if snippets else ""


def build_prompt_for_task(task: Task, repo_path: Optional[Path] = None) -> PromptComponents:
    """
    Convenience function to build a prompt for a task.

    Args:
        task: The task to build a prompt for
        repo_path: Optional repository path (defaults to current directory)

    Returns:
        PromptComponents with the constructed prompt
    """
    builder = PromptBuilder()
    context = PromptContext(task=task, repo_path=repo_path or Path.cwd())
    return builder.build_prompt(context)
