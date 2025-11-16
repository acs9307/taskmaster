# TaskMaster

An AI-powered task orchestration and automation tool that helps you systematically execute development tasks with integrated testing, quality checks, and intelligent failure handling.

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

TaskMaster is a command-line tool that orchestrates AI agents (Claude, OpenAI) to execute development tasks while ensuring code quality through configurable hooks for testing, linting, and validation. It provides robust state management, automatic retry logic, rate limiting, and resumable execution for reliable automation.

### Key Features

- **AI-Powered Task Execution**: Leverage Claude or OpenAI agents to implement tasks automatically
- **Configurable Hooks**: Run tests, linters, and custom validation before/after each task
- **Robust Failure Handling**: Automatic retries with intelligent failure escalation
- **Rate Limit Management**: Respects API rate limits with automatic scheduling
- **Resumable Execution**: Safely resume after interruptions, failures, or rate limits
- **State Persistence**: Track progress, failures, and attempts across sessions
- **Dry-Run Mode**: Preview execution plans without making changes
- **Rich CLI Output**: Color-coded status, timing information, and progress tracking
- **Quiet Mode**: Minimal output for CI/CD integration

## Installation

### From PyPI (when published)

```bash
pip install taskmaster
```

### From Source (Development)

1. Clone the repository:
```bash
git clone https://github.com/acs9307/taskmaster.git
cd taskmaster
```

2. Install in development mode:
```bash
pip install -e .
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

### Verify Installation

```bash
taskmaster --version
taskmaster --help
```

## Quick Start

### 1. Set Up API Keys

TaskMaster requires API keys for AI providers:

```bash
# For Claude (Anthropic)
export ANTHROPIC_API_KEY="your-api-key-here"

# OR for OpenAI
export OPENAI_API_KEY="your-api-key-here"
```

### 2. Create a Task File

Create `tasks.yml` with your tasks:

```yaml
tasks:
  - id: task-1
    title: Implement user authentication
    description: |
      Create a User model with email and password fields.
      Add password hashing and JWT token generation.
    path: src/auth/
    post_hooks:
      - test
```

### 3. Create Configuration File

Create `.taskmaster.yml` in your project:

```yaml
# Provider configuration
provider_configs:
  claude:
    type: claude
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022

    rate_limits:
      max_requests_minute: 10
      max_tokens_hour: 100000

active_provider: claude

# Hook definitions
hooks:
  test:
    command: pytest tests/ -v
    timeout: 300
    stop_on_failure: true
    description: Run test suite

# Default hooks for all tasks
hook_defaults:
  post_hooks:
    - test
```

### 4. Run Tasks

```bash
# Preview execution (dry-run)
taskmaster run tasks.yml --dry-run

# Execute tasks
taskmaster run tasks.yml

# Resume after interruption
taskmaster run tasks.yml --resume
```

## Usage Examples

### Basic Commands

```bash
# Run tasks from a file
taskmaster run tasks.yml

# Run with specific provider
taskmaster run tasks.yml --provider openai

# Dry-run mode (preview only)
taskmaster run tasks.yml --dry-run

# Stop on first failure
taskmaster run tasks.yml --stop-on-first-failure

# Quiet mode for CI/CD
taskmaster run tasks.yml --quiet

# Resume from last position
taskmaster run tasks.yml --resume
```

### State Management

```bash
# Check current status
taskmaster status

# View detailed debug information
taskmaster debug

# Resume interrupted run
taskmaster resume
```

### Configuration Validation

```bash
# Validate configuration file
taskmaster config validate
```

## Project Structure

```
taskmaster/
├── src/
│   └── taskmaster/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point
│       ├── models.py           # Data models (Task, Config, etc.)
│       ├── task_parser.py      # Task file parser
│       ├── config_parser.py    # Config file parser
│       ├── runner.py           # Task execution engine
│       ├── hooks.py            # Hook execution system
│       ├── state.py            # State persistence
│       ├── agent_client.py     # Agent provider abstraction
│       ├── claude_client.py    # Claude API integration
│       ├── openai_client.py    # OpenAI API integration
│       ├── prompt_builder.py   # Prompt construction
│       └── rate_limiter.py     # Rate limit management
├── tests/                      # Unit and integration tests
├── examples/                   # Example configurations
│   ├── small-project/          # Simple project example
│   └── monorepo/               # Monorepo example
├── pyproject.toml              # Package configuration
└── README.md                   # This file
```

## Dependencies

### Core Dependencies

- **Python**: 3.8 or higher
- **PyYAML**: 6.0+ (configuration parsing)
- **Click**: 8.0+ (CLI framework)
- **anthropic**: 0.18.0+ (Claude API client)
- **openai**: 1.0.0+ (OpenAI API client)

### Development Dependencies

- **pytest**: 7.0+ (testing framework)
- **pytest-cov**: 4.0+ (test coverage)
- **ruff**: 0.1.0+ (linting and formatting)

All dependencies are automatically installed with `pip install taskmaster` or `pip install -e ".[dev]"` for development.

## Configuration Reference

### Provider Configuration

```yaml
provider_configs:
  claude:
    type: claude
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
    max_tokens: 4096

    rate_limits:
      max_requests_minute: 10
      max_tokens_hour: 100000
      max_tokens_day: 500000

  openai:
    type: openai
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
    temperature: 0.7
    max_tokens: 4096

active_provider: claude
```

### Hook Configuration

```yaml
hooks:
  test:
    command: pytest tests/ -v
    timeout: 300
    stop_on_failure: true
    description: Run test suite

  lint:
    command: ruff check src/
    timeout: 60
    stop_on_failure: false
    description: Run linter

  build:
    command: npm run build
    timeout: 600
    stop_on_failure: true
    description: Build project

hook_defaults:
  post_hooks:
    - test
```

### Task File Format

```yaml
tasks:
  - id: unique-task-id
    title: Task Title
    description: |
      Detailed description of what the AI should implement.
      Include specific requirements, constraints, and examples.
    path: path/to/code/directory
    pre_hooks:
      - lint
    post_hooks:
      - test
      - build
    metadata:
      priority: high
      team: backend
```

## Examples

TaskMaster includes comprehensive examples:

### Small Project Example
Simple Python project with 3 tasks demonstrating basic usage.

```bash
cd examples/small-project
taskmaster run tasks.yml --dry-run
```

See [examples/small-project/README.md](examples/small-project/README.md)

### Monorepo Example
Complex monorepo with multiple services (API, Frontend, Workers) showing advanced hook configurations.

```bash
cd examples/monorepo
taskmaster run tasks.yml --dry-run
```

See [examples/monorepo/README.md](examples/monorepo/README.md)

### More Examples

- [All Examples Overview](examples/README.md)

## Advanced Features

### Failure Handling

TaskMaster provides intelligent failure handling:

- **Automatic Retries**: Configurable retry attempts per task
- **Non-Progress Detection**: Detects when agent makes no changes
- **Failure Escalation**: Prompts user after threshold exceeded
- **Hard Stop Mode**: `--stop-on-first-failure` for critical workflows

Configure in `.taskmaster.yml`:

```yaml
max_attempts_per_task: 3
max_consecutive_failures: 2
```

### Rate Limiting

Automatic rate limit management prevents API quota exhaustion:

- Tracks token and request usage per hour/day/week
- Automatically pauses execution when limits approached
- Displays time until next reset window
- Handles 429 responses with exponential backoff

```yaml
rate_limits:
  max_requests_minute: 10
  max_tokens_hour: 100000
  max_tokens_day: 500000
```

### State Persistence

All execution state is preserved in `.taskmaster/state.json`:

- Completed tasks
- Current task index
- Failure counts and attempts
- Rate limit usage
- User interventions

Resume any time with:

```bash
taskmaster run tasks.yml --resume
# or
taskmaster resume
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=taskmaster --cov-report=html

# Run specific test file
pytest tests/test_runner.py

# Run specific test
pytest tests/test_runner.py::TestTaskRunner::test_basic_task_execution
```

## Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/acs9307/taskmaster.git
cd taskmaster

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Format code
ruff format src/ tests/
```

### Code Quality

```bash
# Lint code
make lint  # or: ruff check src/ tests/

# Format code
make format  # or: ruff format src/ tests/

# Run tests
make test  # or: pytest

# Run all quality checks
make lint && make test
```

## Troubleshooting

### Common Issues

**Issue**: `taskmaster: command not found`

**Solution**: Ensure pip installation directory is in PATH, or use `python -m taskmaster` instead.

---

**Issue**: `API key not found`

**Solution**: Set environment variable:
```bash
export ANTHROPIC_API_KEY="your-key"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

---

**Issue**: `Rate limit exceeded`

**Solution**: TaskMaster auto-pauses. Wait for reset window or adjust `rate_limits` in config.

---

**Issue**: `Hook command failed`

**Solution**:
1. Run hook command manually to diagnose
2. Check timeout settings in `.taskmaster.yml`
3. Verify command is in PATH
4. Check working directory

---

**Issue**: `State file corrupted`

**Solution**:
```bash
rm -rf .taskmaster/  # Remove state
taskmaster run tasks.yml  # Start fresh
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI
- Powered by [Anthropic Claude](https://www.anthropic.com/) and [OpenAI](https://openai.com/) APIs
- Inspired by modern DevOps automation tools

## Links

- **Documentation**: [GitHub Wiki](https://github.com/acs9307/taskmaster/wiki) (coming soon)
- **Issue Tracker**: [GitHub Issues](https://github.com/acs9307/taskmaster/issues)
- **Examples**: [examples/](examples/)
- **PyPI Package**: [pypi.org/project/taskmaster](https://pypi.org/project/taskmaster/) (coming soon)

## Support

- Report bugs via [GitHub Issues](https://github.com/acs9307/taskmaster/issues)
- Ask questions in [Discussions](https://github.com/acs9307/taskmaster/discussions)
- See [examples/](examples/) for usage patterns

---

**Note**: TaskMaster is under active development. Features and APIs may change. For production use, pin to a specific version.
