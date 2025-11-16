# Monorepo Example

This example demonstrates how to use TaskMaster in a monorepo environment with multiple services. Each service has its own testing framework, linting rules, and build process.

## Overview

**Scenario:** Building an analytics feature across a microservices monorepo

**Services:**
- **API** (Python/FastAPI): REST API with database operations
- **Frontend** (React/TypeScript): Web dashboard
- **Workers** (Python/Celery): Background job processing
- **Infrastructure**: Monitoring and metrics

**Features demonstrated:**
- Service-specific hooks (different test commands per service)
- Multiple hook types (lint, test, integration-test, build, benchmark)
- Pre-hooks and post-hooks
- Monorepo path handling
- Complex workflows across services

## Project Structure

```
monorepo/
├── services/
│   ├── api/
│   │   ├── src/
│   │   └── tests/
│   ├── frontend/
│   │   ├── src/
│   │   └── tests/
│   └── workers/
│       ├── src/
│       └── tests/
├── tasks.yml              # TaskMaster task definitions
└── .taskmaster.yml        # TaskMaster configuration
```

## Task Breakdown

### API Tasks (Python)
1. **api-1:** Create analytics endpoint
   - Pre: Lint with ruff
   - Post: Unit tests + Integration tests
2. **api-2:** Optimize database queries
   - Post: Unit tests + Performance benchmarks

### Frontend Tasks (React/TypeScript)
3. **frontend-1:** Create analytics dashboard
   - Pre: ESLint
   - Post: Jest tests + Production build
4. **frontend-2:** Add real-time updates
   - Post: Jest tests

### Worker Tasks (Python)
5. **worker-1:** Daily aggregation job
   - Post: Pytest tests
6. **worker-2:** Data cleanup job
   - Post: Pytest tests

### Infrastructure Tasks
7. **infra-1:** Add Prometheus metrics
   - No automated tests (infrastructure)

## Prerequisites

- Python 3.8+ (for API and Workers)
- Node.js 16+ (for Frontend)
- Docker (optional, for integration tests)
- TaskMaster installed
- Anthropic API key or OpenAI API key

## Setup

### 1. Set API keys

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
# OR
export OPENAI_API_KEY="your-openai-key"
```

### 2. Install dependencies (if running hooks)

```bash
# API
cd services/api && pip install -r requirements.txt

# Frontend
cd services/frontend && npm install

# Workers
cd services/workers && pip install -r requirements.txt
```

### 3. Review configuration

The `.taskmaster.yml` defines separate hooks for each service:

```yaml
hooks:
  # API hooks
  api-lint: cd services/api && ruff check src/
  api-test: cd services/api && pytest tests/unit -v
  api-integration-test: cd services/api && pytest tests/integration -v

  # Frontend hooks
  frontend-lint: cd services/frontend && npm run lint
  frontend-test: cd services/frontend && npm test -- --coverage
  frontend-build: cd services/frontend && npm run build

  # Worker hooks
  worker-test: cd services/workers && pytest tests/ -v
```

Each task specifies which hooks to run based on the service it modifies.

## Running

### Dry run

```bash
taskmaster run tasks.yml --dry-run
```

Shows the execution plan:
```
Task 1/7: Add user analytics endpoint
  📋 DRY RUN - Execution Plan:

  Pre-hooks that would execute:
    • api-lint: cd services/api && ruff check src/

  Agent call that would be made:
    • Provider: claude
    • Model: claude-3-5-sonnet-20241022
    • Task: Add user analytics endpoint

  Post-hooks that would execute:
    • api-test: cd services/api && pytest tests/unit -v
    • api-integration-test: cd services/api && pytest tests/integration -v

  ✓ Would complete successfully
```

### Run all tasks

```bash
taskmaster run tasks.yml
```

### Run specific tasks

You can filter by creating a custom task file:

```bash
# Only API tasks
taskmaster run tasks.yml --dry-run | grep api

# Create filtered task file
# (manually extract api tasks to api-only.yml)
taskmaster run api-only.yml
```

### Run with different provider

```bash
# Override to use OpenAI instead of Claude
taskmaster run tasks.yml --provider openai
```

## Service-Specific Workflows

### API Service (Python)

API tasks use:
- **Pre-hooks:** Linting to ensure code quality before changes
- **Post-hooks:** Unit tests + Integration tests to verify functionality
- **Benchmarks:** Performance tests for optimization tasks

Example flow:
```
1. Run ruff linter (pre-hook)
2. Call AI agent to generate code
3. Run pytest unit tests (post-hook)
4. Run pytest integration tests (post-hook)
5. If all pass, move to next task
```

### Frontend Service (React)

Frontend tasks use:
- **Pre-hooks:** ESLint for code quality
- **Post-hooks:** Jest tests + TypeScript checks + Production build
- Ensures code compiles and passes tests

Example flow:
```
1. Run ESLint (pre-hook)
2. Call AI agent to generate React components
3. Run Jest tests (post-hook)
4. Build for production (post-hook)
5. Verify successful build
```

### Worker Service (Python)

Worker tasks use:
- **Post-hooks:** Pytest tests to verify job logic
- Tests include scheduling, error handling, and side effects

## Advanced Features

### Parallel Development

Different team members can work on different services:

```bash
# Backend team
taskmaster run tasks.yml --resume  # Continues from last API task

# Frontend team
# (create frontend-tasks.yml with only frontend tasks)
taskmaster run frontend-tasks.yml
```

### CI/CD Integration

Run in CI pipeline with quiet mode:

```bash
# .github/workflows/taskmaster.yml
- name: Run TaskMaster
  run: taskmaster run tasks.yml --quiet --stop-on-first-failure
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Debugging Failed Tasks

If a task fails:

```bash
taskmaster debug
```

Shows which service's tests failed and the error:
```
Task 3/7: Create analytics dashboard component
  Status: ✗ FAILED
  Failures: 2
  Attempts: 3
  Last error: frontend-test hook failed: npm test exited with code 1
```

## Hook Management

### Adding New Hooks

To add a new hook (e.g., security scanning):

```yaml
hooks:
  api-security:
    command: cd services/api && bandit -r src/
    timeout: 120
    stop_on_failure: false
    description: Security scan with bandit
```

Then add to task:
```yaml
- id: api-3
  title: Add authentication
  post_hooks:
    - api-test
    - api-security  # New security hook
```

### Skip Failing Hooks

If a hook consistently fails (e.g., flaky test):

```yaml
hooks:
  e2e-test:
    stop_on_failure: false  # Don't stop execution if this fails
```

## Performance Tips

1. **Order tasks by dependency** - Put prerequisite tasks first
2. **Use pre-hooks sparingly** - They run before AI generation
3. **Separate unit and integration tests** - Run fast tests first
4. **Set appropriate timeouts** - Prevent hanging on slow tests
5. **Use benchmarks selectively** - Only for performance-critical tasks

## Common Issues

### Hook Command Fails

**Problem:** `cd services/api && pytest` fails

**Solution:** Ensure working directory is monorepo root when running taskmaster

### Different Node/Python Versions

**Problem:** Frontend uses Node 18 but system has Node 16

**Solution:** Use Docker or specify version in hook:
```yaml
frontend-test:
  command: nvm use 18 && cd services/frontend && npm test
```

### Rate Limits

**Problem:** Hit rate limits with many tasks

**Solution:** Adjust rate limits or use --resume:
```yaml
rate_limits:
  max_requests_minute: 20  # Increase limit
```

## Customization Ideas

- Add database migration tasks
- Include Docker build steps
- Add deployment tasks
- Integrate with monitoring (Datadog, Sentry)
- Add code coverage requirements
- Include accessibility testing (a11y)

## Next Steps

- Adapt this example for your monorepo structure
- Add service-specific hooks for your tech stack
- Integrate with your CI/CD pipeline
- Set up team-specific task files
- Configure rate limits based on your API tier
