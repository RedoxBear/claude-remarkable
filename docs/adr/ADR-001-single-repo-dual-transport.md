# ADR-001: Single Repo, Dual Transport (SSH + Connect)

**Date:** 2026-03-19
**Status:** Accepted
**Deciders:** User (bdcl)

---

## Context

Building a Python library for Remarkable 2 that can move documents on and off the device and render annotations. Two transport mechanisms exist:

1. **SSH** — direct device access over USB (10.11.99.1) or WiFi. Root access. No account required. Works offline.
2. **Remarkable Connect** — cloud API. Requires subscription. Community-reverse-engineered auth flow (email → device token → bearer token). Works from anywhere.

The existing ecosystem is fragmented:
- `rmapi` — cloud only, Go binary, no Python
- `rmapy` — Python, abandoned, cloud only
- `rmscene` — parses .rm strokes, active but narrow scope
- No single library does SSH + cloud + annotation render

MCP server integration was also desired (for use with Claude Code and other MCP clients).

---

## Decision

**Single repo (`claude-remarkable`) containing:**

| Folder | Contents |
|--------|----------|
| `rm_bridge/` | Core Python library — SSH, Connect auth, document model, render |
| `mcp_server/` | MCP server — thin wrapper exposing rm_bridge as MCP tools |
| `docs/adr/` | Architecture Decision Records (this folder) |
| `tests/` | pytest test suite |

Both SSH and Connect are first-class transports. The public API exposes both:
```python
rm = ReMarkable(host="10.11.99.1")           # SSH
rm = ReMarkable.from_connect(email, pwd)     # Connect
```

The MCP server lives in the same repo (not a separate package) to keep the project navigable and avoid version drift between library and server.

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| SSH only | User has Connect subscription; cloud transport enables remote workflows |
| Connect only | Creates cloud dependency; SSH works offline and without account |
| Separate MCP repo | Added complexity without benefit at this scale |
| Wrap existing MCP server (mcpmarket.com/server/remarkable-1) | Unknown quality, unknown maintenance, no annotation render support |

---

## Consequences

- **Phase 1** implements SSH transport first (USB, reliable, no auth complexity)
- **Phase 1** also implements Connect auth so both transports are available together
- **Phase 3** adds MCP server after core library is stable
- Each subsequent design decision gets its own ADR (ADR-002, ADR-003, …)
- ADRs link to the git commit/tag at the time of the decision for full retraceability

---

## Linked Commits

- Initial scaffold: _(tag: v0.0.1-scaffold — to be created after first commit)_
