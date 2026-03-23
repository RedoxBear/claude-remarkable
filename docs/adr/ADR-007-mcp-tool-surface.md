# ADR-007: MCP Server Tool Surface

**Date:** 2026-03-20
**Status:** Accepted
**Deciders:** User (bdcl)

---

## Context

Phase 3 adds an MCP server so Claude Code (and any other MCP-compatible client) can
interact with the reMarkable 2 programmatically. The server wraps `rm_bridge` and
exposes document operations as MCP tools.

The server must decide: which tools to expose, what parameters each takes, what
it returns, and how errors are communicated.

---

## Decision

### 6 tools

| Tool | Parameters | Returns | Transport |
|------|-----------|---------|-----------|
| `list_documents` | _(none)_ | JSON list of documents | SSH + Connect |
| `push_pdf` | `path: str`, `title?: str` | Document JSON | SSH + Connect |
| `pull_document` | `uuid: str`, `out_path?: str` | Saved file path | SSH + Connect |
| `render_document` | `uuid: str`, `out_path?: str` | Saved annotated PDF path | SSH + Connect |
| `device_info` | _(none)_ | Device JSON | SSH only |
| `push_to_miro` | `uuid: str`, `board_id: str` | Miro board URL | SSH + Connect |

### Transport selection

The MCP server loads `~/.rm_bridge/config.json` at startup and creates a single
`ReMarkable` instance. All tool calls share that instance. No per-call transport
switching.

### Error handling

MCP tools return either a result or a structured error. Errors include:
- `connection_error` — device unreachable
- `not_found` — UUID does not exist
- `auth_error` — Connect token invalid or expired
- `render_error` — annotation parsing failed
- `config_error` — config file missing or invalid

All errors include a human-readable `message` field.

### File paths

`pull_document` and `render_document` save files to a local path and return
the path string. Default: current working directory. The MCP client (Claude)
can then read the file or pass the path to other tools.

### Miro integration

`push_to_miro` renders annotations, converts to PNG, and uploads to the
specified Miro board via the Miro REST API. Requires a `MIRO_ACCESS_TOKEN`
environment variable (not stored in config — kept out of plaintext files).

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| Return raw bytes from pull/render | MCP tools return text/JSON; binary blobs require base64 which is impractical for large PDFs |
| One tool per transport | Doubles surface area; config selects transport at startup |
| Expose all SSH-only methods as tools | `device_info`, `restart_xochitl` are useful; `stop_xochitl` alone is dangerous without restart — not exposed |

---

## MCP Server Entry Point

```bash
rm-bridge-mcp          # uses ~/.rm_bridge/config.json
```

Claude Code config:
```json
{
  "mcpServers": {
    "remarkable": {
      "command": "rm-bridge-mcp"
    }
  }
}
```

---

## Linked Commits

- Implementation: _(Phase 3 — to be implemented after pre-fixes)_
