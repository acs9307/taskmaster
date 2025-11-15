"""Tests for configuration system."""

import os
import tempfile
from pathlib import Path

from taskmaster.config import (
    Config,
    HookDefaults,
    Provider,
    ProviderConfig,
    RateLimitConfig,
)
from taskmaster.config_loader import (
    ConfigLoadError,
    load_config,
    load_config_file,
    merge_configs,
    parse_config,
    validate_config_file,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_rate_limits(self):
        """Test default rate limit config (unlimited)."""
        config = RateLimitConfig()
        assert config.max_tokens_hour is None
        assert config.max_tokens_day is None
        assert config.max_tokens_week is None
        assert config.max_requests_minute is None

    def test_custom_rate_limits(self):
        """Test custom rate limit values."""
        config = RateLimitConfig(
            max_tokens_hour=100000,
            max_tokens_week=500000,
            max_requests_minute=50,
        )
        assert config.max_tokens_hour == 100000
        assert config.max_tokens_week == 500000
        assert config.max_requests_minute == 50


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_provider_config_creation(self):
        """Test creating a provider config."""
        config = ProviderConfig(
            provider=Provider.CLAUDE,
            api_key="test-key",
            model="claude-3",
        )
        assert config.provider == Provider.CLAUDE
        assert config.api_key == "test-key"
        assert config.model == "claude-3"

    def test_get_api_key_literal(self):
        """Test getting literal API key."""
        config = ProviderConfig(provider=Provider.CLAUDE, api_key="literal-key")
        assert config.get_api_key() == "literal-key"

    def test_get_api_key_from_env_var_syntax(self):
        """Test getting API key from $VAR syntax."""
        os.environ["TEST_API_KEY"] = "env-key-value"
        config = ProviderConfig(provider=Provider.CLAUDE, api_key="$TEST_API_KEY")
        assert config.get_api_key() == "env-key-value"
        del os.environ["TEST_API_KEY"]

    def test_get_api_key_from_api_key_env(self):
        """Test getting API key from api_key_env field."""
        os.environ["TEST_API_KEY_2"] = "env-key-value-2"
        config = ProviderConfig(
            provider=Provider.CLAUDE, api_key_env="TEST_API_KEY_2"
        )
        assert config.get_api_key() == "env-key-value-2"
        del os.environ["TEST_API_KEY_2"]

    def test_get_api_key_missing_env_var(self):
        """Test getting API key when env var doesn't exist."""
        config = ProviderConfig(
            provider=Provider.CLAUDE, api_key="$NONEXISTENT_KEY"
        )
        assert config.get_api_key() is None

    def test_get_api_key_none(self):
        """Test getting API key when none configured."""
        config = ProviderConfig(provider=Provider.CLAUDE)
        assert config.get_api_key() is None


class TestHookDefaults:
    """Tests for HookDefaults."""

    def test_empty_hook_defaults(self):
        """Test empty hook defaults."""
        defaults = HookDefaults()
        assert defaults.pre_hooks == []
        assert defaults.post_hooks == []
        assert defaults.test_command is None

    def test_hook_defaults_with_values(self):
        """Test hook defaults with values."""
        defaults = HookDefaults(
            pre_hooks=["install"],
            post_hooks=["test", "lint"],
            test_command="pytest",
            lint_command="ruff check .",
        )
        assert defaults.pre_hooks == ["install"]
        assert defaults.post_hooks == ["test", "lint"]
        assert defaults.test_command == "pytest"
        assert defaults.lint_command == "ruff check ."


class TestConfig:
    """Tests for Config model."""

    def test_default_config(self):
        """Test default config values."""
        config = Config()
        assert config.active_provider == "claude"
        assert config.state_dir == ".agent-runner"
        assert config.log_dir == "logs"
        assert config.max_attempts_per_task == 3
        assert config.max_consecutive_failures == 3

    def test_get_active_provider_config(self):
        """Test getting active provider config."""
        provider_config = ProviderConfig(provider=Provider.CLAUDE, api_key="test")
        config = Config(
            provider_configs={"claude": provider_config}, active_provider="claude"
        )
        assert config.get_active_provider_config() == provider_config

    def test_get_active_provider_config_missing(self):
        """Test getting active provider config when it doesn't exist."""
        config = Config(active_provider="nonexistent")
        assert config.get_active_provider_config() is None

    def test_validate_success(self):
        """Test validation with valid config."""
        os.environ["TEST_KEY"] = "test-value"
        provider_config = ProviderConfig(
            provider=Provider.CLAUDE, api_key="$TEST_KEY"
        )
        config = Config(
            provider_configs={"claude": provider_config}, active_provider="claude"
        )
        errors = config.validate()
        assert len(errors) == 0
        del os.environ["TEST_KEY"]

    def test_validate_missing_provider(self):
        """Test validation with missing active provider."""
        config = Config(active_provider="missing")
        errors = config.validate()
        assert any("not found in provider_configs" in e for e in errors)

    def test_validate_missing_api_key(self):
        """Test validation with missing API key."""
        provider_config = ProviderConfig(provider=Provider.CLAUDE)
        config = Config(
            provider_configs={"claude": provider_config}, active_provider="claude"
        )
        errors = config.validate()
        assert any("No API key configured" in e for e in errors)

    def test_validate_invalid_temperature(self):
        """Test validation with invalid temperature."""
        os.environ["TEST_KEY"] = "test"
        provider_config = ProviderConfig(
            provider=Provider.CLAUDE, api_key="$TEST_KEY", temperature=3.0
        )
        config = Config(
            provider_configs={"claude": provider_config}, active_provider="claude"
        )
        errors = config.validate()
        assert any("temperature must be between" in e for e in errors)
        del os.environ["TEST_KEY"]

    def test_validate_negative_rate_limits(self):
        """Test validation with negative rate limits."""
        os.environ["TEST_KEY"] = "test"
        rate_limits = RateLimitConfig(max_tokens_hour=-100)
        provider_config = ProviderConfig(
            provider=Provider.CLAUDE, api_key="$TEST_KEY", rate_limits=rate_limits
        )
        config = Config(
            provider_configs={"claude": provider_config}, active_provider="claude"
        )
        errors = config.validate()
        assert any("max_tokens_hour must be >= 0" in e for e in errors)
        del os.environ["TEST_KEY"]

    def test_validate_invalid_retry_settings(self):
        """Test validation with invalid retry settings."""
        config = Config(max_attempts_per_task=0)
        errors = config.validate()
        assert any("max_attempts_per_task must be >= 1" in e for e in errors)


class TestConfigLoader:
    """Tests for configuration loading."""

    def test_load_yaml_file(self):
        """Test loading YAML configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(
                """
active_provider: claude
providers:
  claude:
    provider: claude
    api_key: test-key
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            data = load_config_file(path)
            assert data["active_provider"] == "claude"
            assert data["providers"]["claude"]["api_key"] == "test-key"
        finally:
            path.unlink()

    def test_load_json_file(self):
        """Test loading JSON configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(
                """{
  "active_provider": "openai",
  "providers": {
    "openai": {
      "provider": "openai",
      "api_key": "test-key"
    }
  }
}"""
            )
            f.flush()
            path = Path(f.name)

        try:
            data = load_config_file(path)
            assert data["active_provider"] == "openai"
            assert data["providers"]["openai"]["api_key"] == "test-key"
        finally:
            path.unlink()

    def test_load_nonexistent_file(self):
        """Test loading non-existent file returns empty dict."""
        path = Path("/nonexistent/config.yml")
        data = load_config_file(path)
        assert data == {}

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            path = Path(f.name)

        try:
            raised = False
            try:
                load_config_file(path)
            except ConfigLoadError:
                raised = True
            assert raised, "Should have raised ConfigLoadError"
        finally:
            path.unlink()

    def test_parse_config(self):
        """Test parsing configuration from dict."""
        data = {
            "active_provider": "claude",
            "providers": {
                "claude": {
                    "provider": "claude",
                    "api_key": "test-key",
                    "model": "claude-3",
                    "max_tokens": 8000,
                    "rate_limits": {"max_tokens_hour": 50000},
                }
            },
            "hook_defaults": {
                "test_command": "pytest",
                "pre_hooks": ["install"],
            },
            "max_attempts_per_task": 5,
        }

        config = parse_config(data)
        assert config.active_provider == "claude"
        assert "claude" in config.provider_configs
        assert config.provider_configs["claude"].model == "claude-3"
        assert config.provider_configs["claude"].max_tokens == 8000
        assert config.provider_configs["claude"].rate_limits.max_tokens_hour == 50000
        assert config.hook_defaults.test_command == "pytest"
        assert config.hook_defaults.pre_hooks == ["install"]
        assert config.max_attempts_per_task == 5

    def test_merge_configs(self):
        """Test merging two configurations."""
        base = Config(
            provider_configs={
                "claude": ProviderConfig(provider=Provider.CLAUDE, api_key="base-key")
            },
            active_provider="claude",
            max_attempts_per_task=3,
        )

        override = Config(
            provider_configs={
                "openai": ProviderConfig(
                    provider=Provider.OPENAI, api_key="override-key"
                )
            },
            active_provider="openai",
            max_attempts_per_task=5,
        )

        merged = merge_configs(base, override)

        # Should have both providers
        assert "claude" in merged.provider_configs
        assert "openai" in merged.provider_configs

        # Override values should win
        assert merged.active_provider == "openai"
        assert merged.max_attempts_per_task == 5

    def test_merge_hook_defaults(self):
        """Test merging hook defaults."""
        base = Config(
            hook_defaults=HookDefaults(
                pre_hooks=["base-pre"],
                test_command="base-test",
            )
        )

        override = Config(
            hook_defaults=HookDefaults(
                post_hooks=["override-post"],
                lint_command="override-lint",
            )
        )

        merged = merge_configs(base, override)

        # Override hook lists replace base (not append)
        assert merged.hook_defaults.post_hooks == ["override-post"]
        # But base test_command is preserved when override doesn't set it
        assert merged.hook_defaults.test_command == "base-test"
        assert merged.hook_defaults.lint_command == "override-lint"

    def test_validate_config_file(self):
        """Test validating a config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(
                """
active_provider: claude
providers:
  claude:
    provider: claude
    api_key: test-key
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            is_valid, errors = validate_config_file(path)
            assert is_valid
            assert len(errors) == 0
        finally:
            path.unlink()

    def test_validate_config_file_with_errors(self):
        """Test validating a config file with errors."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(
                """
active_provider: nonexistent
providers:
  claude:
    provider: claude
"""
            )
            f.flush()
            path = Path(f.name)

        try:
            is_valid, errors = validate_config_file(path)
            assert not is_valid
            assert len(errors) > 0
        finally:
            path.unlink()

    def test_load_config_global_only(self):
        """Test loading config with only global config present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_config = Path(tmpdir) / "global.yml"
            global_config.write_text(
                """
active_provider: claude
providers:
  claude:
    provider: claude
    api_key: global-key
"""
            )

            project_config = Path(tmpdir) / "project.yml"
            # project_config doesn't exist

            config = load_config(global_config, project_config)
            assert config.active_provider == "claude"
            assert config.provider_configs["claude"].api_key == "global-key"

    def test_load_config_with_project_override(self):
        """Test loading config with project overriding global."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_config = Path(tmpdir) / "global.yml"
            global_config.write_text(
                """
active_provider: claude
max_attempts_per_task: 3
providers:
  claude:
    provider: claude
    api_key: global-key
"""
            )

            project_config = Path(tmpdir) / "project.yml"
            project_config.write_text(
                """
active_provider: openai
max_attempts_per_task: 5
providers:
  openai:
    provider: openai
    api_key: project-key
"""
            )

            config = load_config(global_config, project_config)
            assert config.active_provider == "openai"
            assert config.max_attempts_per_task == 5
            # Both providers should be present
            assert "claude" in config.provider_configs
            assert "openai" in config.provider_configs
