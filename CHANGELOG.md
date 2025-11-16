# Changelog

All notable changes to TaskMaster will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-16

### Added

#### Core Features
- AI-powered task orchestration with Claude and OpenAI support
- Configurable pre- and post-task hooks for testing and validation
- Comprehensive state management and persistence
- Automatic resume capability after interruptions
- Intelligent failure handling with retry logic and escalation
- Multi-level rate limit management (per-minute, hourly, daily, weekly)
- Dry-run mode for previewing execution plans

#### CLI Commands
- `taskmaster run` - Execute tasks from a task file
- `taskmaster resume` - Resume interrupted runs
- `taskmaster status` - Show current run status
- `taskmaster debug` - Display detailed debug information
- `taskmaster config validate` - Validate configuration files

#### Configuration System
- Support for YAML, JSON, and TOML configuration formats
- Per-project and global configuration support
- Environment variable interpolation for API keys
- Comprehensive provider configuration (models, tokens, rate limits)
- Hook configuration with timeouts and failure policies
- Task file format with metadata and dependencies

#### Agent Integration
- Abstract agent client interface for pluggable providers
- Claude client with full Anthropic API support
- OpenAI client with GPT-4 and other model support
- Automatic prompt construction from task descriptions
- Optional code change application
- Provider selection via config or CLI flag

#### Failure Handling
- Per-task attempt tracking and retry limits
- Non-progress detection (no code changes)
- Automatic escalation to manual intervention
- User prompts for retry/skip/abort decisions
- Hard stop mode (`--stop-on-first-failure`)
- Detailed failure logging and reporting

#### Rate Limiting
- Local usage tracking with timestamps
- Pre-flight limit checking before API calls
- Automatic pause when limits approached
- Reset window calculations and notifications
- HTTP 429 handling with exponential backoff
- Per-provider rate limit configuration

#### State Management
- Durable state serialization to JSON
- Atomic file writes to prevent corruption
- Complete run state tracking (tasks, attempts, failures)
- API usage history tracking
- User intervention recording
- Automatic state cleanup

#### Hook System
- Pre-task hooks for setup and validation
- Post-task hooks for testing and quality checks
- Per-hook timeout configuration
- Stop-on-failure policy support
- Detailed hook output logging
- Hook execution timing and status tracking

#### CLI Features
- Color-coded status output (pending/running/passed/failed/skipped)
- Rich progress information with timing data
- Quiet mode for CI/CD integration
- Clear task separation and formatting
- Comprehensive help text
- Version information display

#### Testing
- 458 comprehensive unit and integration tests
- Test coverage for all major components
- Mock-based testing for API clients
- Temporary directory fixtures for file operations
- Configuration validation tests
- State management integration tests

#### Documentation
- Comprehensive README with features and usage
- Detailed QUICKSTART guide with step-by-step tutorial
- Advanced usage documentation covering all features
- Architecture documentation explaining system design
- Contributing guidelines for developers
- Two complete example projects (small-project, monorepo)
- API documentation in code comments

#### Development Tools
- Makefile with common commands (test, lint, format)
- Ruff configuration for linting and formatting
- Pytest configuration with coverage reporting
- Example configuration files
- Development dependency management
- MANIFEST.in for package distribution

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- Secure API key management via environment variables
- No sensitive data in logs or state files
- Atomic file writes prevent state corruption

## Release Links

[0.1.0]: https://github.com/acs9307/taskmaster/releases/tag/v0.1.0
