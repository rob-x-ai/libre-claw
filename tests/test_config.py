"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from libre_claw.config import Config, BackendConfig, WorkspaceConfig, HeartbeatConfig


class TestConfig:
    """Test configuration loading."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.backend.type == "claude_code"
        assert config.backend.claude_path == "/opt/homebrew/bin/claude"
        assert config.heartbeat.enabled is True
        assert config.heartbeat.interval_seconds == 30
        assert config.memory.enabled is True

    def test_backend_config(self):
        """Test backend configuration."""
        config = BackendConfig()
        assert config.type == "claude_code"
        assert config.ollama_url == "http://localhost:11434"
        assert config.anthropic_api_key is None

    def test_workspace_config(self):
        """Test workspace configuration."""
        config = WorkspaceConfig()
        assert config.path == "~/.openclaw/workspace"

    def test_heartbeat_config(self):
        """Test heartbeat configuration."""
        config = HeartbeatConfig()
        assert config.enabled is True
        assert config.interval_seconds == 30
        assert "HEARTBEAT.md" in config.prompt

    def test_from_yaml(self, tmp_path):
        """Test loading config from YAML."""
        config_data = {
            "backend": {
                "type": "ollama",
                "ollama_url": "http://stargate.local:11434",
                "ollama_model": "qwen2.5",
            },
            "heartbeat": {
                "enabled": False,
                "interval_seconds": 60,
            },
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config.from_yaml(config_file)
        assert config.backend.type == "ollama"
        assert config.backend.ollama_url == "http://stargate.local:11434"
        assert config.heartbeat.enabled is False
        assert config.heartbeat.interval_seconds == 60

    def test_from_yaml_missing_file(self, tmp_path):
        """Test loading config from non-existent file returns defaults."""
        config = Config.from_yaml(tmp_path / "nonexistent.yaml")
        assert config.backend.type == "claude_code"

    def test_save_config(self, tmp_path):
        """Test saving config to YAML."""
        config = Config()
        save_path = tmp_path / "saved_config.yaml"
        config.save(save_path)

        assert save_path.exists()

        loaded = Config.from_yaml(save_path)
        assert loaded.backend.type == config.backend.type
