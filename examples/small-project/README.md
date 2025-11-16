# Small Project Example

This example demonstrates how to use TaskMaster for a small Python project. It implements a simple user authentication feature across 3 tasks, with automated testing after each task.

## Overview

**Scenario:** Building user authentication for a Python web application

**Tasks:**
1. Implement user authentication (User model, password hashing, JWT tokens)
2. Add user registration endpoint (REST API with validation)
3. Add password reset functionality (Reset tokens and email flow)

**Features demonstrated:**
- Sequential task execution
- AI-powered code generation with Claude
- Automated testing with pytest after each task
- Simple hook configuration
- Rate limiting

## Prerequisites

- Python 3.8+
- TaskMaster installed
- Anthropic API key (for Claude)

## Setup

### 1. Set your API key

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### 2. Review the configuration

The `.taskmaster.yml` file configures:
- **Provider:** Claude 3.5 Sonnet for code generation
- **Test hook:** Runs `pytest tests/ -v` after each task
- **Lint hook:** Runs `ruff check src/` (used in task 3)
- **Rate limits:** Conservative limits to prevent excessive API usage

### 3. Review the tasks

The `tasks.yml` file defines 3 tasks that build a complete auth system:
- Each task has a clear description of what to implement
- Each task specifies the path where code should be created
- Each task runs tests automatically via post_hooks

## Running

### Dry run (preview what will happen)

```bash
taskmaster run tasks.yml --dry-run
```

This shows you:
- Which tasks will run
- Which hooks will execute
- What agent calls will be made

### Run all tasks

```bash
taskmaster run tasks.yml
```

TaskMaster will:
1. Execute each task sequentially
2. Call Claude to generate the code
3. Run pytest after each task
4. Stop if tests fail (and let you fix it)
5. Continue to the next task on success

### Run with resume support

If execution is interrupted (Ctrl+C, rate limits, failures):

```bash
taskmaster run tasks.yml --resume
```

This continues from where you left off.

### Quiet mode (for CI/CD)

```bash
taskmaster run tasks.yml --quiet
```

Minimal output, perfect for automated pipelines.

## Expected Flow

```
Task 1/3: Implement user authentication
  ✓ Pre-hooks: (none)
  ⚙ Calling agent...
  ✓ Agent response received
  ⚙ Running post-hooks: test
  ✓ test (2.3s)
  ✓ Task completed (15.2s)

Task 2/3: Add user registration endpoint
  ⚙ Calling agent...
  ✓ Agent response received
  ⚙ Running post-hooks: test
  ✓ test (2.5s)
  ✓ Task completed (12.8s)

Task 3/3: Add password reset functionality
  ⚙ Calling agent...
  ✓ Agent response received
  ⚙ Running post-hooks: test, lint
  ✓ test (2.4s)
  ✓ lint (0.8s)
  ✓ Task completed (14.1s)

✓ All tasks completed successfully!
```

## Debugging

If something goes wrong:

```bash
taskmaster debug
```

This shows:
- Current task progress
- Failure counts and error messages
- Rate limit usage
- State of each task

## Customization

You can modify this example for your needs:

### Change the AI provider

Edit `.taskmaster.yml` to use OpenAI instead:

```yaml
provider_configs:
  openai:
    type: openai
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
```

### Add more hooks

Add linting or formatting hooks:

```yaml
hooks:
  format:
    command: black src/
    stop_on_failure: false

hook_defaults:
  pre_hooks:
    - format  # Format before each task
  post_hooks:
    - test    # Test after each task
```

### Adjust retry behavior

```yaml
max_attempts_per_task: 5  # Try each task up to 5 times
max_consecutive_failures: 3  # Allow 3 failures before requiring user intervention
```

## Tips

1. **Start with dry-run** - Always preview with `--dry-run` first
2. **Review agent responses** - Check generated code before running tests
3. **Use --resume** - If interrupted, resume instead of starting over
4. **Monitor rate limits** - Use `taskmaster debug` to check usage
5. **Iterate on prompts** - Refine task descriptions if code quality isn't good

## Next Steps

Once you're comfortable with this example:
- Try the monorepo example for more complex projects
- Add your own custom hooks
- Integrate with your CI/CD pipeline
- Experiment with different AI models
