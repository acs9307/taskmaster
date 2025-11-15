# Contributing to TaskMaster

Thank you for your interest in contributing to TaskMaster! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment for all contributors.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior vs actual behavior
- Your environment (OS, Python version, etc.)
- Any relevant logs or error messages

### Suggesting Enhancements

We welcome suggestions for new features or improvements! Please create an issue with:
- A clear description of the enhancement
- Use cases and benefits
- Any potential implementation approaches you've considered

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following the coding standards below
3. **Add tests** for any new functionality
4. **Ensure all tests pass** by running `make test`
5. **Run the linter** with `make lint` and fix any issues
6. **Update documentation** as needed
7. **Submit a pull request** with a clear description of the changes

## Development Setup

1. Clone your fork of the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/taskmaster.git
   cd taskmaster
   ```

2. Install development dependencies:
   ```bash
   pip install -e .[dev]
   ```

3. Run tests to verify your setup:
   ```bash
   make test
   ```

## Coding Standards

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Write docstrings for all public functions and classes
- Keep functions focused and reasonably sized
- Add type hints where appropriate

## Testing

- Write unit tests for new functionality
- Ensure all tests pass before submitting a PR
- Aim for high test coverage
- Test edge cases and error conditions

## Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in the present tense (e.g., "Add", "Fix", "Update")
- Keep the first line under 72 characters
- Add additional context in the commit body if needed

Example:
```
Add rate limit tracking for Claude API

Implements hourly and weekly token tracking to prevent
exceeding API quotas. Includes tests and configuration
options for customizing limits.
```

## Definition of Done

For any contribution to be considered complete, it must meet the following criteria:

- New behavior has automated test coverage (unit and/or integration)
- All tests pass locally and in CI
- CLI help text (--help) remains accurate and up-to-date
- Any new config options are documented in README and example configs
- No obvious regressions in existing flows

## Questions?

If you have questions about contributing, feel free to create an issue with the "question" label.

Thank you for contributing to TaskMaster!
