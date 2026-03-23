# ADR-006: Config Schema — ~/.rm_bridge/config.json

**Date:** 2026-03-20
**Status:** Accepted
**Deciders:** User (bdcl)

---

## Context

Both the CLI and the MCP server need to know which transport to use (SSH or Connect)
and its connection parameters (host, key, token path). Without a shared config, every
CLI invocation requires repeating `--host`, `--key`, etc., and the MCP server has no
way to know which device to connect to at startup.

---

## Decision

A JSON config file at `~/.rm_bridge/config.json` shared by CLI and MCP server.

### Schema

```json
{
  "transport": "ssh",
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
```

### Rules

- All fields optional — defaults applied for anything missing
- `load_config()` returns `Config` with defaults if file does not exist
- `save_config()` creates parent directories as needed
- Validation runs on load and save: `transport` must be `"ssh"` or `"connect"`, port must be 1–65535
- Unknown fields in the file are silently ignored (forward compatibility)

### Transport selection

| `transport` value | Effect |
|---|---|
| `"ssh"` | Uses SSHTransport with `ssh.*` fields |
| `"connect"` | Uses ConnectTransport with `connect.token_path` |

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| Environment variables only | No persistence; awkward for multi-device setups |
| TOML or YAML | Extra dependency; JSON readable and stdlib-supported |
| Per-project config | Users typically have one device; home dir is appropriate |
| Pydantic models | Added dependency without benefit at this scale |

---

## Security Note

`ssh.password` is stored in plaintext. Users should prefer `key_path` (SSH key auth)
over `password`. The token file at `connect.token_path` should have restricted
permissions (`chmod 600`). Both are documented in the README.

---

## Linked Commits

- Implementation: _(tag: v0.2.1 — to be created after pre-fixes pass)_
