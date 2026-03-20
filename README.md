# claude-remarkable

Python library for Remarkable 2 — push PDFs, pull annotated documents, render annotation overlays. No cloud lock-in required.

## Transports

- **SSH** — direct device access over USB or WiFi, no account needed
- **Remarkable Connect** — cloud API for remote workflows (requires subscription)

## Status

Under active development. See [docs/adr/](docs/adr/) for architecture decisions.

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | SSH foundations + Connect auth | 🔧 In progress |
| 2 | Pull + annotation render | Planned |
| 3 | Package + CLI + MCP server | Planned |
| 4 | GitHub release | Planned |

## Quick Start (Phase 3+)

```bash
pip install claude-remarkable
rm-bridge push document.pdf
rm-bridge pull "My Document"
```

## Development

```bash
git clone https://github.com/bdcl/claude-remarkable
cd claude-remarkable
pip install -e ".[dev]"
pytest
```

## License

MIT
