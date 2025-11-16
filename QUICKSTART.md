# TaskMaster Quickstart Guide

This guide will walk you through setting up and running TaskMaster for the first time with a complete working example.

**Time to complete:** ~10 minutes

## Prerequisites

- Python 3.8 or higher
- pip package manager
- An API key from either:
  - [Anthropic](https://console.anthropic.com/) (for Claude)
  - [OpenAI](https://platform.openai.com/) (for GPT models)

## Step 1: Install TaskMaster

### Option A: From PyPI (when published)

```bash
pip install taskmaster
```

### Option B: From Source

```bash
git clone https://github.com/acs9307/taskmaster.git
cd taskmaster
pip install -e .
```

### Verify Installation

```bash
taskmaster --version
```

You should see output like:
```
taskmaster, version 0.1.0
```

## Step 2: Set Up Your API Key

Choose your preferred AI provider and set the corresponding environment variable:

### For Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

### For OpenAI

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

**Tip:** Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### Verify API Key

```bash
echo $ANTHROPIC_API_KEY
```

You should see your API key printed.

## Step 3: Create Your First Project

Let's create a simple Python project to demonstrate TaskMaster:

```bash
# Create project directory
mkdir my-first-taskmaster-project
cd my-first-taskmaster-project

# Create basic structure
mkdir -p src tests
```

## Step 4: Create a Task File

Create a file named `tasks.yml` with the following content:

```yaml
tasks:
  - id: task-1
    title: Create a calculator module
    description: |
      Create a Python module called calculator.py in the src/ directory.
      The module should have the following functions:
      - add(a, b) - returns the sum of two numbers
      - subtract(a, b) - returns the difference
      - multiply(a, b) - returns the product
      - divide(a, b) - returns the quotient (handle division by zero)

      Each function should:
      - Have type hints
      - Include a docstring
      - Handle edge cases appropriately
    path: src/
    post_hooks:
      - test

  - id: task-2
    title: Add advanced calculator functions
    description: |
      Extend the calculator module with:
      - power(base, exponent) - returns base raised to exponent
      - square_root(n) - returns the square root of n
      - factorial(n) - returns the factorial of n

      Include proper error handling and docstrings.
    path: src/
    post_hooks:
      - test
```

## Step 5: Create Configuration File

Create a file named `.taskmaster.yml` with the following content:

### For Claude Users

```yaml
# Provider configuration
provider_configs:
  claude:
    type: claude
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
    max_tokens: 4096

    rate_limits:
      max_requests_minute: 5
      max_tokens_hour: 50000

active_provider: claude

# Hook definitions
hooks:
  test:
    command: pytest tests/ -v --tb=short
    timeout: 120
    stop_on_failure: true
    description: Run test suite

# Default hooks for all tasks
hook_defaults:
  post_hooks:
    - test

# Failure handling
max_attempts_per_task: 3
max_consecutive_failures: 2
```

### For OpenAI Users

```yaml
# Provider configuration
provider_configs:
  openai:
    type: openai
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
    temperature: 0.7
    max_tokens: 4096

    rate_limits:
      max_requests_minute: 10
      max_tokens_hour: 50000

active_provider: openai

# Hook definitions
hooks:
  test:
    command: pytest tests/ -v --tb=short
    timeout: 120
    stop_on_failure: true
    description: Run test suite

# Default hooks for all tasks
hook_defaults:
  post_hooks:
    - test

# Failure handling
max_attempts_per_task: 3
max_consecutive_failures: 2
```

## Step 6: Install Test Dependencies

Since our tasks will run pytest tests, we need to install pytest:

```bash
pip install pytest
```

## Step 7: Create Initial Test File

Create a placeholder test file so pytest can run:

```bash
mkdir -p tests
cat > tests/test_calculator.py << 'EOF'
"""Tests for calculator module."""
import pytest

def test_placeholder():
    """Placeholder test - will be updated by AI."""
    assert True
EOF
```

## Step 8: Preview Execution (Dry Run)

Before running tasks, let's preview what TaskMaster will do:

```bash
taskmaster run tasks.yml --dry-run
```

You should see output like:

```
Starting TaskMaster Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task 1/2: Create a calculator module
ID: task-1
Description: Create a Python module called calculator.py...

📋 DRY RUN - Execution Plan:

  Post-hooks that would execute:
    • test: pytest tests/ -v --tb=short

  ✓ Would complete successfully

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task 2/2: Add advanced calculator functions
...
```

## Step 9: Run Your First Task

Now let's execute the tasks:

```bash
taskmaster run tasks.yml
```

You'll see output showing:

1. **Task execution**: TaskMaster calls the AI agent with your task description
2. **Code generation**: The AI creates the calculator module
3. **Test execution**: The test hook runs automatically
4. **Results**: Success or failure status

Expected output:

```
Starting TaskMaster Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task 1/2: Create a calculator module
ID: task-1
Description: Create a Python module called calculator.py in the src/ directory...
Path: src/

▶ Calling AI agent...
  Provider: claude
  Model: claude-3-5-sonnet-20241022

✓ Agent response received

Running post-hook: test
  Command: pytest tests/ -v --tb=short

✓ Hook 'test' passed (exit code 0)

✓ Task completed: Create a calculator module (12.3s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task 2/2: Add advanced calculator functions
...
```

## Step 10: Verify Results

Check the generated code:

```bash
# View the calculator module
cat src/calculator.py

# View the tests
cat tests/test_calculator.py

# Run tests manually
pytest tests/ -v
```

## Step 11: Check Task Status

View the current status and progress:

```bash
taskmaster status
```

Output:

```
Current Task Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task File: tasks.yml
Total Tasks: 2
Completed: 2
Current: None

✓ task-1: Create a calculator module
✓ task-2: Add advanced calculator functions

All tasks completed successfully!
```

## Next Steps

Congratulations! You've successfully run TaskMaster. Here's what to explore next:

### 1. Try Different Hooks

Add a linting hook to your `.taskmaster.yml`:

```yaml
hooks:
  lint:
    command: ruff check src/
    timeout: 60
    stop_on_failure: false
    description: Run linter

  test:
    command: pytest tests/ -v
    timeout: 120
    stop_on_failure: true
    description: Run test suite
```

Then use both hooks in tasks:

```yaml
tasks:
  - id: task-3
    title: Your new task
    description: ...
    path: src/
    pre_hooks:
      - lint
    post_hooks:
      - test
```

### 2. Explore Resume Functionality

If a task fails or you interrupt execution:

```bash
# Resume from where you left off
taskmaster run tasks.yml --resume
```

### 3. Use Quiet Mode for CI/CD

For cleaner output in CI pipelines:

```bash
taskmaster run tasks.yml --quiet
```

### 4. Debug Failed Tasks

If something goes wrong:

```bash
taskmaster debug
```

### 5. Check Out Examples

Explore the comprehensive examples:

```bash
# Navigate to examples directory
cd examples/small-project
cat README.md

# Try the small project example
taskmaster run tasks.yml --dry-run
```

## Common Issues & Solutions

### Issue: "taskmaster: command not found"

**Solution:**
```bash
# Verify installation
pip show taskmaster

# If installed but not in PATH, use:
python -m taskmaster run tasks.yml
```

### Issue: "API key not found"

**Solution:**
```bash
# Check if variable is set
echo $ANTHROPIC_API_KEY

# Set it if missing
export ANTHROPIC_API_KEY="your-key-here"
```

### Issue: "Hook command failed: pytest"

**Solution:**
```bash
# Install pytest
pip install pytest

# Or remove the hook temporarily by editing .taskmaster.yml:
hook_defaults:
  post_hooks: []  # Empty - no default hooks
```

### Issue: Rate limit errors

**Solution:**

TaskMaster automatically handles rate limits. If you hit them:

1. Wait for the reset window (TaskMaster will tell you when)
2. Or adjust limits in `.taskmaster.yml`:

```yaml
rate_limits:
  max_requests_minute: 3  # Lower limit
  max_tokens_hour: 30000
```

### Issue: Task fails repeatedly

**Solution:**

1. Check the debug output:
   ```bash
   taskmaster debug
   ```

2. Review the logs in `.taskmaster/logs/`

3. Modify the task description to be more specific

4. Skip the problematic task and continue:
   - When prompted, choose `[S]kip this task`

## Configuration Options Reference

### Minimal Configuration

The absolute minimum `.taskmaster.yml`:

```yaml
provider_configs:
  claude:
    api_key: ${ANTHROPIC_API_KEY}

active_provider: claude
```

### Recommended Configuration

For most projects:

```yaml
provider_configs:
  claude:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022

active_provider: claude

hooks:
  test:
    command: pytest tests/ -v
    timeout: 300
    stop_on_failure: true

hook_defaults:
  post_hooks:
    - test

max_attempts_per_task: 3
```

## Learning Resources

- **Full Documentation**: [README.md](README.md)
- **Examples**: [examples/](examples/)
  - [Small Project Example](examples/small-project/README.md)
  - [Monorepo Example](examples/monorepo/README.md)
- **Configuration Reference**: See README.md "Configuration Reference" section
- **Troubleshooting**: See README.md "Troubleshooting" section

## Getting Help

- **Command help**: `taskmaster --help` or `taskmaster run --help`
- **GitHub Issues**: [Report a bug or request a feature](https://github.com/acs9307/taskmaster/issues)
- **Examples**: Check the [examples/](examples/) directory
- **Debug mode**: `taskmaster debug` for detailed state information

## Summary

You've learned how to:

✅ Install TaskMaster
✅ Configure API keys
✅ Create a task file (`tasks.yml`)
✅ Configure TaskMaster (`.taskmaster.yml`)
✅ Run tasks with AI agents
✅ Use hooks for testing
✅ Check task status
✅ Troubleshoot common issues

**Ready to automate your development workflow? Start adding more tasks to your `tasks.yml` and let TaskMaster handle the implementation!**
