"""Config management — load/save ~/.rm_bridge/config.json.

Shared by CLI (for defaults) and MCP server (for device selection at startup).

Schema:
    {
        "transport": "ssh" | "connect",          # which transport to use
        "ssh": {
            "host": "10.11.99.1",
            "username": "root",
            "key_path": null,
            "password": null,
            "port": 22
        },
        "connect": {
            "token_path": "~/.rm_bridge/tokens.json"
        }
    }

All fields are optional — defaults are applied for anything missing.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


CONFIG_PATH = Path.home() / ".rm_bridge" / "config.json"


@dataclass
class SSHConfig:
    host: str = "10.11.99.1"
    username: str = "root"
    key_path: str | None = None
    password: str | None = None
    port: int = 22


@dataclass
class ConnectConfig:
    token_path: str = str(Path.home() / ".rm_bridge" / "tokens.json")


@dataclass
class Config:
    transport: str = "ssh"          # "ssh" | "connect"
    ssh: SSHConfig = field(default_factory=SSHConfig)
    connect: ConnectConfig = field(default_factory=ConnectConfig)

    def token_path(self) -> Path:
        return Path(self.connect.token_path).expanduser()

    def validate(self) -> None:
        if self.transport not in ("ssh", "connect"):
            raise ValueError(f"transport must be 'ssh' or 'connect', got {self.transport!r}")
        if self.ssh.port < 1 or self.ssh.port > 65535:
            raise ValueError(f"ssh.port must be 1–65535, got {self.ssh.port}")


def load_config(path: Path | None = None) -> Config:
    """Load config from disk. Returns defaults if file does not exist."""
    config_path = Path(path or CONFIG_PATH).expanduser()

    if not config_path.exists():
        return Config()

    raw = json.loads(config_path.read_text())

    ssh_raw = raw.get("ssh", {})
    connect_raw = raw.get("connect", {})

    config = Config(
        transport=raw.get("transport", "ssh"),
        ssh=SSHConfig(
            host=ssh_raw.get("host", "10.11.99.1"),
            username=ssh_raw.get("username", "root"),
            key_path=ssh_raw.get("key_path"),
            password=ssh_raw.get("password"),
            port=ssh_raw.get("port", 22),
        ),
        connect=ConnectConfig(
            token_path=connect_raw.get(
                "token_path",
                str(Path.home() / ".rm_bridge" / "tokens.json"),
            ),
        ),
    )
    config.validate()
    return config


def save_config(config: Config, path: Path | None = None) -> None:
    """Save config to disk, creating directories as needed."""
    config.validate()
    config_path = Path(path or CONFIG_PATH).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "transport": config.transport,
        "ssh": {
            "host": config.ssh.host,
            "username": config.ssh.username,
            "key_path": config.ssh.key_path,
            "password": config.ssh.password,
            "port": config.ssh.port,
        },
        "connect": {
            "token_path": config.connect.token_path,
        },
    }
    config_path.write_text(json.dumps(data, indent=2))
