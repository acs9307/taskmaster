# Advanced Usage Guide

This guide covers advanced TaskMaster features for power users and production deployments.

## Table of Contents

- [Rate Limiting](#rate-limiting)
- [Fail-Safe Behavior](#fail-safe-behavior)
- [State Management & Resume](#state-management--resume)
- [Custom Prompt Templates](#custom-prompt-templates)
- [Hook Configuration](#hook-configuration)
- [CI/CD Integration](#cicd-integration)
- [Performance Tuning](#performance-tuning)

---

## Rate Limiting

TaskMaster includes sophisticated rate limiting to prevent API quota exhaustion and manage costs.

### Overview

Rate limiting operates at multiple levels:
- **Per-minute limits**: Prevent bursts of requests
- **Hourly limits**: Manage token consumption
- **Daily/Weekly limits**: Control long-term usage

### Configuration

Configure rate limits in `.taskmaster.yml`:

```yaml
provider_configs:
  claude:
    type: claude
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022

    rate_limits:
      max_requests_minute: 10    # Maximum 10 requests per minute
      max_tokens_hour: 100000     # Maximum 100k tokens per hour
      max_tokens_day: 500000      # Maximum 500k tokens per day
```

### How It Works

1. **Tracking**: TaskMaster tracks usage in `.taskmaster/state.json`
2. **Pre-flight checks**: Before each API call, usage is checked against limits
3. **Automatic pause**: If limit would be exceeded, execution pauses
4. **Resume notification**: TaskMaster displays when to resume:

```
⚠ Rate limit reached!

Current usage:
  - Requests this minute: 10/10
  - Tokens this hour: 100,000/100,000

Next reset: 2025-11-16 15:30:00 UTC (in 15 minutes)

Safe to resume after reset. Run:
  taskmaster resume
```

### Provider-Specific Limits

#### Anthropic Claude

```yaml
provider_configs:
  claude:
    rate_limits:
      max_requests_minute: 10
      max_tokens_hour: 100000
      max_tokens_day: 1000000
```

Typical limits by tier:
- **Free tier**: 5 RPM, 40k TPH
- **Build tier**: 50 RPM, 100k TPH
- **Scale tier**: Custom limits

#### OpenAI

```yaml
provider_configs:
  openai:
    rate_limits:
      max_requests_minute: 60
      max_tokens_hour: 200000
      max_requests_day: 10000
```

Typical limits by tier:
- **Free tier**: 3 RPM, 40k TPM
- **Pay-as-you-go**: 60 RPM, 200k TPM
- **Tier 4+**: Higher limits

### Handling 429 Errors

When the API returns rate limit errors:

1. **Retry-After header**: TaskMaster respects provider's suggested wait time
2. **Exponential backoff**: Automatic retry with increasing delays (2s, 4s, 8s, 16s)
3. **Maximum retries**: After 5 attempts, execution pauses for user intervention

Example output:

```
⚠ API rate limit error (HTTP 429)
Retry-After: 60 seconds

Attempt 1/5: Waiting 2 seconds...
Attempt 2/5: Waiting 4 seconds...
...
```

### Overriding Limits (Not Recommended)

For testing or emergency use:

```bash
taskmaster run tasks.yml --ignore-config-limits
```

**Warning**: This can lead to:
- Unexpected API bills
- Account suspension
- Service degradation

### Best Practices

1. **Set conservative limits**: Start lower than your tier allows
2. **Monitor usage**: Check `.taskmaster/state.json` regularly
3. **Use dry-run**: Preview token usage before actual run:
   ```bash
   taskmaster run tasks.yml --dry-run
   ```
4. **Rate limit per project**: Different projects can have different limits
5. **Schedule long runs**: Use cron for off-peak execution

### Troubleshooting Rate Limits

**Issue**: Hitting limits too frequently

**Solutions**:
```yaml
# Option 1: Reduce task complexity
- Use smaller, more focused tasks
- Split large tasks into smaller ones

# Option 2: Lower rate limits
rate_limits:
  max_requests_minute: 5  # More conservative

# Option 3: Use resume strategically
# Let TaskMaster pause, resume later
taskmaster run tasks.yml  # Pauses at limit
# Wait for reset window...
taskmaster resume         # Continues automatically
```

---

## Fail-Safe Behavior

TaskMaster includes multiple layers of failure handling to prevent infinite loops and wasted API calls.

### Failure Detection

TaskMaster tracks three types of failures:

1. **Hook failures**: Pre/post-hook commands exit with non-zero code
2. **Agent failures**: API errors, invalid responses
3. **Non-progress**: Agent makes changes but tests still fail

### Configuration

```yaml
# Maximum attempts before giving up on a task
max_attempts_per_task: 3

# Maximum consecutive failures before stopping entirely
max_consecutive_failures: 2

# Per-hook failure behavior
hooks:
  test:
    command: pytest tests/ -v
    stop_on_failure: true   # Stop immediately if this fails

  lint:
    command: ruff check src/
    stop_on_failure: false  # Continue even if this fails
```

### Failure Escalation Workflow

When a task fails:

```
Task execution
  ↓
Post-hook fails
  ↓
Attempt 1: Auto-retry (include error in prompt)
  ↓ (still fails)
Attempt 2: Auto-retry with more context
  ↓ (still fails)
Attempt 3: Auto-retry (last attempt)
  ↓ (still fails)
User intervention prompt
```

### User Intervention Prompt

After max attempts exceeded:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ Task has failed multiple times

Task: Implement user authentication
Attempts: 3/3
Last error: test hook failed (exit code 1)

Recent failures:
  Attempt 1: AssertionError in test_login
  Attempt 2: ImportError: cannot import 'User'
  Attempt 3: TypeError: missing required argument

What would you like to do?

  [R] Retry once more
  [S] Skip this task and continue
  [A] Abort entire run

Choice: _
```

### Non-Progress Detection

TaskMaster detects when the agent isn't making meaningful changes:

```yaml
# Enable non-progress detection
detect_non_progress: true  # Default: true
```

How it works:
1. Before agent call: Capture git diff hash
2. After agent call: Check if diff changed
3. If no change but tests fail: Increment non-progress counter
4. After 2 non-progress attempts: Escalate to user

Example:

```
⚠ Non-progress detected!

The agent made no code changes, but tests still fail.
This may indicate:
  - Task description is unclear
  - Tests are flaky
  - Environment issue

Non-progress count: 2/2

Escalating to user intervention...
```

### Override Flags

#### Stop on First Failure

```bash
taskmaster run tasks.yml --stop-on-first-failure
```

Stops immediately on any failure, useful for:
- High-risk production deployments
- Critical infrastructure changes
- When manual review is required

#### Auto-Apply Changes

```bash
taskmaster run tasks.yml --auto-apply
```

Automatically apply agent-suggested code changes (experimental).

**Warning**: Only use with:
- Version control (git)
- Comprehensive test coverage
- Trusted codebases

### Failure Logs

All failures are logged to `.taskmaster/logs/`:

```
.taskmaster/logs/
├── task-1/
│   ├── pre.log          # Pre-hook output
│   ├── post.log         # Post-hook output
│   ├── agent.log        # Agent response
│   └── error.log        # Error details
└── task-2/
    └── ...
```

View logs:

```bash
# View specific task logs
cat .taskmaster/logs/task-1/error.log

# View all errors
grep -r "ERROR" .taskmaster/logs/

# Get summary
taskmaster debug
```

### Best Practices

1. **Set realistic attempt limits**: 3-5 attempts usually sufficient
2. **Use stop_on_failure wisely**: Critical hooks → true, nice-to-have → false
3. **Review failure logs**: Understand why tasks fail
4. **Improve task descriptions**: Clear descriptions reduce failures
5. **Test hooks locally**: Ensure hooks work before TaskMaster run

---

## State Management & Resume

TaskMaster maintains comprehensive state to enable reliable resumption after any interruption.

### State File Location

```
.taskmaster/
├── state.json           # Main state file
└── logs/                # Per-task logs
    └── task-id/
        ├── pre.log
        ├── post.log
        └── agent.log
```

### State Contents

The state file tracks:

```json
{
  "task_file": "tasks.yml",
  "completed_task_ids": ["task-1", "task-2"],
  "current_task_index": 2,
  "created_at": "2025-11-16T10:00:00",
  "updated_at": "2025-11-16T10:15:00",

  "failure_counts": {
    "task-1": 0,
    "task-3": 2
  },

  "attempt_counts": {
    "task-1": 1,
    "task-3": 3
  },

  "non_progress_counts": {
    "task-3": 1
  },

  "user_interventions": {
    "task-5": "skip"
  },

  "last_errors": {
    "task-3": "test hook failed: pytest exited with code 1"
  },

  "rate_limit_usage": {
    "claude": {
      "requests_minute": 5,
      "tokens_hour": 45000,
      "tokens_day": 120000,
      "window_start_minute": "2025-11-16T10:15:00",
      "window_start_hour": "2025-11-16T10:00:00",
      "window_start_day": "2025-11-16T00:00:00"
    }
  }
}
```

### Resume Behavior

TaskMaster can resume from:

1. **Rate limit pause**
2. **User abort (Ctrl+C)**
3. **System crash**
4. **Network failure**
5. **Manual stop**

#### Automatic Resume

When you re-run a task file:

```bash
# Initial run
taskmaster run tasks.yml

# Interrupted at task 3...

# Resume automatically
taskmaster run tasks.yml  # Starts from task 3
```

TaskMaster detects existing state and asks:

```
Found existing run state:
  Task file: tasks.yml
  Completed: 2/5 tasks
  Last updated: 2 minutes ago

Resume from task 3? [Y/n]: _
```

#### Explicit Resume

```bash
# Resume without prompting
taskmaster resume

# Or use the run command with --resume flag
taskmaster run tasks.yml --resume
```

### State Inspection

View current state:

```bash
taskmaster status
```

Output:

```
Current Task Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task File: tasks.yml
Total Tasks: 5
Completed: 2
Current: 3 (Implement login endpoint)

Progress:
✓ task-1: Setup project structure
✓ task-2: Create database models
→ task-3: Implement login endpoint (2 attempts, 1 failure)
○ task-4: Add password reset
○ task-5: Implement 2FA
```

Detailed debug info:

```bash
taskmaster debug
```

Output:

```
TaskMaster Debug State
============================================================

Task File: tasks.yml
Created: 2025-11-16 10:00:00
Updated: 2025-11-16 10:15:00
Current Task Index: 2

============================================================
PER-TASK STATUS
============================================================

Task 1/5: Setup project structure
  ID: task-1
  Status: ✓ COMPLETED
  Failures: 0
  Attempts: 1

Task 2/5: Create database models
  ID: task-2
  Status: ✓ COMPLETED
  Failures: 0
  Attempts: 1

Task 3/5: Implement login endpoint
  ID: task-3
  Status: → CURRENT/NEXT
  Failures: 1
  Attempts: 2
  Last error: test hook failed: AssertionError in test_login

Task 4/5: Add password reset
  ID: task-4
  Status: ○ PENDING

Task 5/5: Implement 2FA
  ID: task-5
  Status: ○ PENDING

============================================================
RATE LIMIT USAGE
============================================================

Provider: claude
  Requests (current minute): 5 / 10
  Tokens (current hour): 45,000 / 100,000
  Tokens (current day): 120,000 / 500,000

Next reset:
  Minute: 2025-11-16 10:16:00 (in 45s)
  Hour: 2025-11-16 11:00:00 (in 45m)
```

### State Reset

Clear state to start fresh:

```bash
# Remove state file
rm -rf .taskmaster/

# Next run starts from beginning
taskmaster run tasks.yml
```

Or use a different state directory:

```bash
# Use custom state directory
TASKMASTER_STATE_DIR=/tmp/my-run taskmaster run tasks.yml
```

### State Corruption Recovery

If state file becomes corrupted:

```
Error: Failed to load state: Invalid JSON

To recover:
  1. Backup corrupted file: cp .taskmaster/state.json state.backup
  2. Remove state: rm -rf .taskmaster/
  3. Start fresh: taskmaster run tasks.yml
```

### Concurrent Runs

**Warning**: Don't run multiple TaskMaster instances on the same task file simultaneously.

For parallel execution:

```bash
# Option 1: Separate task files
taskmaster run backend-tasks.yml &
taskmaster run frontend-tasks.yml &

# Option 2: Separate state directories
TASKMASTER_STATE_DIR=.taskmaster-1 taskmaster run tasks.yml &
TASKMASTER_STATE_DIR=.taskmaster-2 taskmaster run tasks.yml &
```

### Best Practices

1. **Commit state periodically**: In long runs, backup `.taskmaster/state.json`
2. **Use git**: Track state file changes to understand progress
3. **Don't manually edit state**: Use TaskMaster commands instead
4. **Resume promptly**: Don't wait too long (rate limit windows expire)
5. **Check status often**: `taskmaster status` shows current progress

---

## Custom Prompt Templates

TaskMaster uses customizable prompt templates to control how tasks are presented to AI agents.

### Default Prompt Structure

The default prompt includes:

1. **System prompt**: Role and instructions
2. **Task information**: Title, description, path
3. **Repository context**: Git status, file snippets
4. **Hook expectations**: What tests/checks will run
5. **Previous attempts**: If retrying, includes past errors

### Custom Template Location

Create custom templates in `.taskmaster/prompts/`:

```
.taskmaster/prompts/
├── system.txt           # System prompt template
├── task.txt             # Task prompt template
└── retry.txt            # Retry prompt template
```

### System Prompt Template

`.taskmaster/prompts/system.txt`:

```
You are an expert software engineer working on {{project_name}}.

Your role is to implement the given task following these guidelines:
- Write clean, maintainable code
- Include comprehensive tests
- Follow {{language}} best practices
- Add clear documentation

Technology stack: {{tech_stack}}
Coding style: {{coding_style}}
```

Variables available:
- `{{project_name}}`: From config metadata
- `{{language}}`: Detected from task path
- `{{tech_stack}}`: From config metadata
- `{{coding_style}}`: From config metadata

### Task Prompt Template

`.taskmaster/prompts/task.txt`:

```
# Task: {{task_title}}

## Description
{{task_description}}

## Requirements
{{task_requirements}}

## Working Directory
{{task_path}}

## Current Repository State
```
{{git_status}}
```

## Files in Working Directory
{{file_list}}

## Post-Task Validation
After you complete this task, the following commands will run:
{{post_hooks}}

Ensure your implementation passes all validations.

## Implementation
Please implement this task now.
```

Variables available:
- `{{task_title}}`: Task title
- `{{task_description}}`: Task description
- `{{task_requirements}}`: Extracted requirements
- `{{task_path}}`: Working directory
- `{{git_status}}`: Current git status
- `{{file_list}}`: Files in task path
- `{{post_hooks}}`: List of validation commands

### Retry Prompt Template

`.taskmaster/prompts/retry.txt`:

```
# Retry: {{task_title}}

The previous attempt failed. Please review the error and try again.

## Previous Attempt {{attempt_number}}

### Agent Response
{{previous_response}}

### Validation Error
```
{{error_output}}
```

### Failure Analysis
{{failure_reason}}

## What to Fix
{{fix_suggestions}}

Please implement a corrected version that addresses these issues.
```

Variables available:
- `{{task_title}}`: Task title
- `{{attempt_number}}`: Current attempt number
- `{{previous_response}}`: Last agent response
- `{{error_output}}`: Hook failure output
- `{{failure_reason}}`: Analysis of failure
- `{{fix_suggestions}}`: Suggested fixes

### Configuration

Enable custom templates in `.taskmaster.yml`:

```yaml
prompt_templates:
  system: .taskmaster/prompts/system.txt
  task: .taskmaster/prompts/task.txt
  retry: .taskmaster/prompts/retry.txt

  # Template variables
  variables:
    project_name: "My Awesome Project"
    language: "Python"
    tech_stack: "FastAPI, PostgreSQL, React"
    coding_style: "PEP 8, type hints required"
```

### Advanced: Context Inclusion

Control what context is included:

```yaml
prompt_context:
  include_git_status: true
  include_file_list: true
  include_file_contents: false  # Can be expensive

  max_files_listed: 20
  max_file_size: 10000  # bytes

  # File patterns to include in context
  include_patterns:
    - "*.py"
    - "*.yml"
    - "README.md"

  # File patterns to exclude
  exclude_patterns:
    - "*.pyc"
    - "__pycache__"
    - ".git"
```

### Example: Python Project Template

`.taskmaster/prompts/system.txt`:

```
You are an expert Python developer implementing features for a production FastAPI application.

Code Requirements:
- Follow PEP 8 style guide strictly
- Use type hints for all functions
- Write comprehensive docstrings (Google style)
- Handle errors explicitly (no bare except:)
- Log important operations
- Write unit tests for all new functions

Testing Requirements:
- Use pytest for all tests
- Aim for >90% code coverage
- Include both positive and negative test cases
- Mock external dependencies

The codebase uses:
- Python 3.11+
- FastAPI for REST API
- SQLAlchemy for database ORM
- Pytest for testing
- Ruff for linting
```

### Example: Code Review Template

`.taskmaster/prompts/task.txt`:

```
# Task: {{task_title}}

{{task_description}}

## Pre-Implementation Checklist
Before writing code, consider:
- [ ] Do I understand all requirements?
- [ ] What edge cases exist?
- [ ] What errors might occur?
- [ ] How will this be tested?
- [ ] Does this affect existing functionality?

## Implementation
Working directory: {{task_path}}

Current files:
{{file_list}}

## Validation
Your code will be validated with:
{{post_hooks}}

Ensure all validations pass before considering the task complete.

## Code Quality Standards
- Type hints required
- Docstrings for all public functions
- Error handling for failure cases
- Logging for important operations
- Tests with >80% coverage
```

### Best Practices

1. **Keep prompts focused**: Clear, specific instructions work best
2. **Include examples**: Show desired code style
3. **Set expectations**: List validation criteria upfront
4. **Iterate templates**: Refine based on agent performance
5. **Version control**: Track template changes in git

### Debugging Templates

View the actual prompt sent to the agent:

```bash
# Enable verbose mode
taskmaster run tasks.yml --verbose

# Prompt will be logged to .taskmaster/logs/task-id/prompt.txt
cat .taskmaster/logs/task-1/prompt.txt
```

---

## Hook Configuration

Hooks are the backbone of TaskMaster's quality assurance system.

### Hook Types

1. **Pre-hooks**: Run before agent generates code
2. **Post-hooks**: Run after agent generates code

### Basic Hook Definition

```yaml
hooks:
  test:
    command: pytest tests/ -v
    timeout: 300
    stop_on_failure: true
    description: Run test suite
```

### Advanced Hook Options

```yaml
hooks:
  comprehensive-test:
    command: pytest tests/ -v --cov=src --cov-report=html
    timeout: 600
    stop_on_failure: true
    description: Run tests with coverage

    # Working directory for command
    working_dir: ./backend

    # Environment variables
    env:
      TESTING: "1"
      DATABASE_URL: "postgresql://localhost/test_db"

    # Retry configuration
    retry_count: 2
    retry_delay: 5  # seconds

    # Output handling
    capture_output: true
    log_output: true
    quiet: false
```

### Hook Patterns

#### Linting Hook

```yaml
hooks:
  lint:
    command: ruff check src/ --fix
    timeout: 60
    stop_on_failure: false  # Don't stop on lint errors
    description: Auto-fix linting issues
```

#### Multi-Step Hook

```yaml
hooks:
  full-validation:
    command: |
      ruff check src/ &&
      mypy src/ &&
      pytest tests/ --cov=src --cov-fail-under=80
    timeout: 900
    stop_on_failure: true
    description: Complete validation suite
```

#### Conditional Hook

```yaml
hooks:
  integration-test:
    command: |
      if [ "$CI" = "true" ]; then
        pytest tests/integration/ -v
      else
        echo "Skipping integration tests in local environment"
      fi
    timeout: 600
    stop_on_failure: false
```

### Hook Composition

Combine multiple hooks:

```yaml
hooks:
  # Individual hooks
  format:
    command: ruff format src/
    stop_on_failure: false

  lint:
    command: ruff check src/
    stop_on_failure: false

  type-check:
    command: mypy src/
    stop_on_failure: true

  unit-test:
    command: pytest tests/unit/ -v
    stop_on_failure: true

  integration-test:
    command: pytest tests/integration/ -v
    stop_on_failure: true

# Use in tasks
tasks:
  - id: task-1
    title: Implement feature
    pre_hooks:
      - format
      - lint
    post_hooks:
      - type-check
      - unit-test
      - integration-test
```

### Service-Specific Hooks (Monorepo)

```yaml
hooks:
  # Backend hooks
  backend-lint:
    command: cd services/backend && ruff check src/
    description: Lint backend service

  backend-test:
    command: cd services/backend && pytest tests/
    description: Test backend service

  # Frontend hooks
  frontend-lint:
    command: cd services/frontend && npm run lint
    description: Lint frontend service

  frontend-test:
    command: cd services/frontend && npm test
    description: Test frontend service

  # Shared hooks
  docker-build:
    command: docker-compose build
    timeout: 1200
    description: Build all services

tasks:
  - id: backend-task
    title: Backend feature
    path: services/backend/
    post_hooks:
      - backend-lint
      - backend-test

  - id: frontend-task
    title: Frontend feature
    path: services/frontend/
    post_hooks:
      - frontend-lint
      - frontend-test
```

### Hook Defaults

Set default hooks for all tasks:

```yaml
hook_defaults:
  pre_hooks:
    - format  # Format before AI changes

  post_hooks:
    - lint
    - test

# Tasks automatically get these hooks
tasks:
  - id: task-1
    title: Feature A
    # Inherits default hooks

  - id: task-2
    title: Feature B
    # Override defaults
    post_hooks:
      - lint
      - test
      - integration-test
```

### Best Practices

1. **Fast hooks first**: Run quick checks before slow ones
2. **stop_on_failure wisely**: Critical → true, informational → false
3. **Set generous timeouts**: Account for slow CI environments
4. **Log everything**: Keep logs for debugging
5. **Test hooks locally**: Verify commands work before TaskMaster run

---

## CI/CD Integration

TaskMaster integrates seamlessly with CI/CD pipelines.

### GitHub Actions

`.github/workflows/taskmaster.yml`:

```yaml
name: TaskMaster Automation

on:
  workflow_dispatch:  # Manual trigger
    inputs:
      task_file:
        description: 'Task file to run'
        required: true
        default: 'tasks.yml'

jobs:
  run-tasks:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install TaskMaster
        run: pip install taskmaster

      - name: Run TaskMaster
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          taskmaster run ${{ github.event.inputs.task_file }} \
            --quiet \
            --stop-on-first-failure

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: taskmaster-logs
          path: .taskmaster/logs/

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: 'TaskMaster run completed! Check the logs artifact for details.'
            })
```

### GitLab CI

`.gitlab-ci.yml`:

```yaml
taskmaster:
  image: python:3.11

  before_script:
    - pip install taskmaster

  script:
    - taskmaster run tasks.yml --quiet --stop-on-first-failure

  artifacts:
    when: always
    paths:
      - .taskmaster/logs/
    expire_in: 1 week

  only:
    - main
    - /^feature\/.*$/

  variables:
    ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
```

### Jenkins

`Jenkinsfile`:

```groovy
pipeline {
    agent any

    environment {
        ANTHROPIC_API_KEY = credentials('anthropic-api-key')
    }

    stages {
        stage('Setup') {
            steps {
                sh 'pip install taskmaster'
            }
        }

        stage('Run TaskMaster') {
            steps {
                sh '''
                    taskmaster run tasks.yml \
                        --quiet \
                        --stop-on-first-failure
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: '.taskmaster/logs/**/*', allowEmptyArchive: true
        }
        failure {
            emailext (
                subject: "TaskMaster Failed: ${env.JOB_NAME}",
                body: "Check logs at ${env.BUILD_URL}",
                to: 'team@example.com'
            )
        }
    }
}
```

### CI/CD Best Practices

1. **Use --quiet flag**: Cleaner logs
2. **Use --stop-on-first-failure**: Fail fast
3. **Archive logs**: Always save `.taskmaster/logs/`
4. **Secure API keys**: Use secrets management
5. **Set timeouts**: Prevent hanging jobs
6. **Use resume**: For long-running tasks, split into stages

---

## Performance Tuning

Optimize TaskMaster for speed and efficiency.

### Task Granularity

**Too Large** (slow, expensive):
```yaml
- id: big-task
  title: Build entire authentication system
  description: User model, login, logout, password reset, 2FA, sessions...
```

**Optimal** (fast, focused):
```yaml
- id: auth-1
  title: Create User model
  description: SQLAlchemy User model with email, password hash

- id: auth-2
  title: Implement login
  description: Login endpoint with JWT token generation

- id: auth-3
  title: Add password reset
  description: Password reset flow with email tokens
```

### Parallel Hook Execution

Currently, hooks run sequentially. For faster execution, use shell parallelization:

```yaml
hooks:
  parallel-tests:
    command: |
      pytest tests/unit/ -v & PID1=$!
      pytest tests/integration/ -v & PID2=$!
      wait $PID1 && wait $PID2
    timeout: 600
```

### Caching

Use hooks to leverage caching:

```yaml
hooks:
  cached-test:
    command: |
      # Use pytest-cache to skip successful tests
      pytest tests/ -v --lf --ff
    description: Run tests with last-failed optimization
```

### Resource Management

```yaml
hooks:
  resource-limited-test:
    command: pytest tests/ -v -n 4  # 4 parallel workers
    env:
      PYTEST_XDIST_AUTO_NUM_WORKERS: "4"
```

### Best Practices

1. **Small, focused tasks**: 5-20 minute tasks optimal
2. **Fast hooks**: Optimize test suite performance
3. **Conservative rate limits**: Prevent API throttling
4. **Use dry-run**: Preview before expensive runs
5. **Monitor token usage**: Check `.taskmaster/state.json`

---

For more information, see:
- [README.md](../README.md) - Main documentation
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
- [Examples](../examples/) - Sample configurations
