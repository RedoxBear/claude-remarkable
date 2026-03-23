"""Tests for config module — no device or network required."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rm_bridge.config import Config, ConnectConfig, SSHConfig, load_config, save_config


class TestDefaults:
    def test_default_transport_is_ssh(self):
        assert Config().transport == "ssh"

    def test_default_ssh_host(self):
        assert Config().ssh.host == "10.11.99.1"

    def test_default_ssh_port(self):
        assert Config().ssh.port == 22

    def test_default_ssh_username(self):
        assert Config().ssh.username == "root"

    def test_default_ssh_no_password(self):
        assert Config().ssh.password is None

    def test_default_ssh_no_key(self):
        assert Config().ssh.key_path is None

    def test_default_token_path_contains_rm_bridge(self):
        assert ".rm_bridge" in Config().connect.token_path


class TestValidation:
    def test_valid_config_passes(self):
        Config().validate()  # should not raise

    def test_invalid_transport_raises(self):
        c = Config(transport="ftp")
        with pytest.raises(ValueError, match="transport must be"):
            c.validate()

    def test_invalid_port_too_low(self):
        c = Config(ssh=SSHConfig(port=0))
        with pytest.raises(ValueError, match="ssh.port"):
            c.validate()

    def test_invalid_port_too_high(self):
        c = Config(ssh=SSHConfig(port=99999))
        with pytest.raises(ValueError, match="ssh.port"):
            c.validate()

    def test_valid_connect_transport(self):
        c = Config(transport="connect")
        c.validate()  # should not raise


class TestSaveLoad:
    def test_round_trip_ssh(self, tmp_path):
        path = tmp_path / "config.json"
        original = Config(
            transport="ssh",
            ssh=SSHConfig(host="192.168.1.10", port=2222, username="admin"),
        )
        save_config(original, path)
        loaded = load_config(path)

        assert loaded.transport == "ssh"
        assert loaded.ssh.host == "192.168.1.10"
        assert loaded.ssh.port == 2222
        assert loaded.ssh.username == "admin"

    def test_round_trip_connect(self, tmp_path):
        path = tmp_path / "config.json"
        original = Config(
            transport="connect",
            connect=ConnectConfig(token_path="/tmp/tokens.json"),
        )
        save_config(original, path)
        loaded = load_config(path)

        assert loaded.transport == "connect"
        assert loaded.connect.token_path == "/tmp/tokens.json"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        config = load_config(path)
        assert config.transport == "ssh"
        assert config.ssh.host == "10.11.99.1"

    def test_save_creates_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "config.json"
        save_config(Config(), path)
        assert path.exists()

    def test_saved_file_is_valid_json(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(Config(), path)
        data = json.loads(path.read_text())
        assert "transport" in data
        assert "ssh" in data
        assert "connect" in data

    def test_partial_config_file_uses_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"transport": "connect"}))
        config = load_config(path)
        assert config.transport == "connect"
        assert config.ssh.host == "10.11.99.1"  # default preserved

    def test_unknown_fields_ignored(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "transport": "ssh",
            "future_field": "ignored",
            "ssh": {"host": "10.11.99.1"},
        }))
        config = load_config(path)  # should not raise
        assert config.ssh.host == "10.11.99.1"


class TestTokenPath:
    def test_token_path_returns_path_object(self):
        config = Config()
        assert isinstance(config.token_path(), Path)

    def test_token_path_expands_home(self):
        config = Config(connect=ConnectConfig(token_path="~/.rm_bridge/tokens.json"))
        result = config.token_path()
        assert "~" not in str(result)
