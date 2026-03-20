# ADR-003: Stop Xochitl Before Writing Document Files

**Date:** 2026-03-20
**Status:** Accepted
**Deciders:** User (bdcl)
**Triggered by:** Official reMarkable developer documentation review

---

## Context

During Phase 1 development, the initial `push_pdf` implementation restarted
xochitl *after* writing files but did not stop it *before*. The assumption was
that a restart would be sufficient for the device to pick up new documents.

Review of the official reMarkable developer documentation revealed:

> "Xochitl should **not** be running when accessing and/or changing the stored documents."
> — developer.remarkable.com/documentation/xochitl

Writing document files while xochitl is running risks:
- Data corruption (xochitl may be mid-write to the same directory)
- Silent document loss (xochitl may overwrite or ignore newly appeared files)
- Inconsistent device state (partial document visible in UI)

---

## Decision

`push_pdf` (and any future write operations) must:
1. **Stop** xochitl (`systemctl stop xochitl`) before any file writes
2. Write all files
3. **Restart** xochitl (`systemctl restart xochitl`) after all files are written

The restart is wrapped in a `finally` block — xochitl is always restarted,
even if a write fails. A stopped xochitl leaves the device showing a blank
screen, which is unacceptable as an error state.

```python
self.stop_xochitl()
try:
    # write .pdf, .metadata, .content, .pagedata
finally:
    self.restart_xochitl()  # always runs
```

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| Restart only (original approach) | Not safe per official docs; risk of corruption |
| Write without stopping | Same risk, no restart benefit |
| DBUS/IPC notification instead of stop/start | No public IPC API documented; xochitl is proprietary |

---

## Additional Findings from Official Docs

- **OS version detection**: `cat /etc/os-release | grep ^VERSION=` (not `/etc/version`)
- **xochitl config**: `/home/root/.config/remarkable/xochitl.conf`
- **rM2 touch coordinates**: rotated 180° + inverted X — relevant for Phase 2 annotation rendering
- **No developer mode** required for rM1/rM2 SSH access (unlike Paper Pro)
- No guarantees of compatibility between xochitl versions — defensive parsing in place

---

## Linked Commits

- Bug fix applied: `0cb0f06` (tag: `v0.1.1`)
