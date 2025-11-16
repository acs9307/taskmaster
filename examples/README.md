# TaskMaster Examples

This directory contains example configurations demonstrating how to use TaskMaster in different scenarios.

## Available Examples

### 1. [Small Project](./small-project/)
**Best for:** Simple projects, learning TaskMaster basics

A straightforward example showing how to use TaskMaster for a small Python project with 3 tasks that build a user authentication system.

**Features:**
- Simple sequential task execution
- Pytest test integration
- Basic hook configuration
- Rate limiting setup
- Perfect for getting started

**Use this example if you:**
- Are new to TaskMaster
- Have a single-service project
- Want a simple, clear configuration
- Need a quick start guide

### 2. [Monorepo](./monorepo/)
**Best for:** Multi-service projects, complex workflows

A comprehensive example demonstrating TaskMaster in a monorepo with multiple services (API, Frontend, Workers), each with different testing frameworks and build processes.

**Features:**
- Service-specific hooks
- Multiple test types (unit, integration, e2e)
- Pre-hooks and post-hooks
- Different tech stacks (Python, TypeScript)
- Complex workflow orchestration

**Use this example if you:**
- Work with a monorepo or microservices
- Have multiple services with different tech stacks
- Need service-specific testing strategies
- Want to see advanced hook configurations

## Quick Start

### 1. Choose an example

Pick the example that matches your project:

```bash
cd examples/small-project     # For simple projects
# OR
cd examples/monorepo          # For complex projects
```

### 2. Set up your API key

```bash
# For Claude (Anthropic)
export ANTHROPIC_API_KEY="your-key-here"

# OR for OpenAI
export OPENAI_API_KEY="your-key-here"
```

### 3. Preview the execution plan

```bash
taskmaster run tasks.yml --dry-run
```

This shows you what will happen without actually running anything.

### 4. Run tasks

```bash
taskmaster run tasks.yml
```

## Example Comparison

| Feature | Small Project | Monorepo |
|---------|--------------|----------|
| **Complexity** | Simple | Advanced |
| **Services** | 1 (Python API) | 3 (API, Frontend, Workers) |
| **Tasks** | 3 | 7 |
| **Hook Types** | test, lint | test, lint, integration-test, build, benchmark |
| **Tech Stack** | Python | Python, TypeScript, React |
| **Best For** | Learning, small projects | Production, complex projects |
| **Setup Time** | 5 minutes | 15 minutes |

## Common Use Cases

### Learning TaskMaster
→ Start with **small-project** example
- Clear, simple configuration
- Easy to understand
- Quick to run

### Production Deployment
→ Use **monorepo** example as template
- Comprehensive hook setup
- Service isolation
- CI/CD ready

### Experimentation
→ Both examples work well
- Copy example directory
- Modify tasks and hooks
- Test different configurations

## Configuration Files

Both examples include:

### `tasks.yml`
Defines the tasks to execute:
```yaml
tasks:
  - id: task-1
    title: Task title
    description: What the AI should implement
    path: where/to/create/code
    pre_hooks: [hooks-to-run-before]
    post_hooks: [hooks-to-run-after]
```

### `.taskmaster.yml`
Configures TaskMaster:
```yaml
provider_configs:  # AI provider setup
  claude:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-5-sonnet-20241022

hooks:  # Command definitions
  test:
    command: pytest tests/ -v
    stop_on_failure: true

hook_defaults:  # Default hooks for all tasks
  post_hooks: [test]
```

## Adapting Examples

### For Your Tech Stack

**Python projects:**
- Use small-project as base
- Modify test commands for your framework (pytest, unittest, etc.)

**JavaScript/TypeScript projects:**
- Use monorepo frontend hooks
- Change to npm test, jest, vitest, etc.

**Go/Rust/Other:**
- Copy hook structure
- Replace commands with your test runner
- Adjust paths and timeouts

### For Your Workflow

**Add more hooks:**
```yaml
hooks:
  format:
    command: black src/
  security:
    command: bandit -r src/
  coverage:
    command: pytest --cov=src tests/
```

**Customize task flow:**
```yaml
tasks:
  - id: prep
    pre_hooks: [format]  # Format before AI changes
    post_hooks: [test]    # Test after AI changes

  - id: deploy
    post_hooks: [test, security, build]  # Multiple validations
```

## Best Practices

From these examples:

1. **Always use dry-run first**
   ```bash
   taskmaster run tasks.yml --dry-run
   ```

2. **Set appropriate timeouts**
   - Fast tests: 60-120s
   - Integration tests: 300-600s
   - Builds: 300-900s

3. **Use stop_on_failure wisely**
   - `true` for critical hooks (tests)
   - `false` for nice-to-have hooks (linting)

4. **Configure rate limits**
   - Prevents accidental excessive API usage
   - Matches your API tier limits

5. **Use resume for reliability**
   ```bash
   taskmaster run tasks.yml --resume
   ```

## Troubleshooting

### Example doesn't run

**Check:**
- API key is set: `echo $ANTHROPIC_API_KEY`
- TaskMaster is installed: `taskmaster --version`
- Working directory: `pwd` (should be in example directory)

### Hooks fail

**Common issues:**
- Dependencies not installed
- Wrong working directory
- Timeout too short
- Command not in PATH

**Solution:**
```bash
# Run hook manually to diagnose
cd examples/small-project
pytest tests/ -v  # Test the command directly
```

### Rate limits hit

**Increase limits or add delays:**
```yaml
rate_limits:
  max_requests_minute: 20  # Increase
```

### Want to skip a task

**Use task IDs:**
```yaml
# Comment out tasks you don't want
tasks:
  - id: task-1
    # ...
  # - id: task-2  # Skipped
  #   # ...
  - id: task-3
    # ...
```

## Further Learning

After exploring these examples:

1. **Customize for your project**
   - Copy an example
   - Modify tasks for your requirements
   - Adjust hooks for your tools

2. **Explore TaskMaster features**
   ```bash
   taskmaster --help
   taskmaster debug          # View state
   taskmaster status         # Check progress
   ```

3. **Integrate with CI/CD**
   - Use `--quiet` flag
   - Use `--stop-on-first-failure`
   - Set up proper API key secrets

4. **Join the community**
   - Report issues on GitHub
   - Share your configurations
   - Contribute examples

## Contributing Examples

Have a great example for a specific use case? Contribute it!

**Good example ideas:**
- Mobile app development
- Data science / ML projects
- DevOps / Infrastructure as Code
- Documentation generation
- Database migrations
- Specific frameworks (Django, Rails, Next.js, etc.)

Submit a PR with:
- New directory under `examples/`
- `tasks.yml` and `.taskmaster.yml`
- Comprehensive README
- Clear use case description

## Additional Resources

- [TaskMaster Documentation](https://github.com/yourorg/taskmaster)
- [Configuration Reference](../docs/configuration.md)
- [Hook System Guide](../docs/hooks.md)
- [Best Practices](../docs/best-practices.md)
