# ADR-002: SFTP over SCP for SSH File Transfer

**Date:** 2026-03-19
**Status:** Accepted
**Deciders:** User (bdcl)

---

## Context

The SSH transport needs to move files between the Mac and the Remarkable 2 device. Two common approaches exist over an SSH connection:

1. **SFTP** — SSH File Transfer Protocol. A subsystem of SSH, fully supported by paramiko natively via `client.open_sftp()`. Bidirectional, supports stat/listdir/put/get in a single session.
2. **SCP** — Secure Copy Protocol. Requires either a separate `scp` binary on the host or a third-party Python library (`scp`, `paramiko-expect`). Simpler for one-off copies but less capable.

---

## Decision

Use **SFTP via paramiko's native `SFTPClient`**.

---

## Reasons

| Criterion | SFTP | SCP |
|-----------|------|-----|
| paramiko native support | Yes (`open_sftp()`) | No (requires extra library) |
| Bidirectional (get + put) | Yes | Yes |
| Directory listing | Yes (`listdir_attr`) | No |
| In-memory transfer (BytesIO) | Yes (`putfo`/`getfo`) | No |
| Single session (no reconnect) | Yes | No |
| External binary dependency | None | `scp` binary |

SFTP lets us list the xochitl directory, read `.metadata` files, push the PDF + companions, and pull `.rm` annotation files — all over one open session without spawning subprocesses.

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| `scp` Python library | Extra dependency, no directory listing, subprocess overhead |
| `rsync` over SSH | Overkill; requires rsync on device (not guaranteed) |
| SFTP with temp files on disk | Unnecessary; `putfo`/`getfo` work with `io.BytesIO` directly |

---

## Consequences

- All file I/O in `SSHTransport` uses `self._sftp.putfo` / `getfo` / `listdir_attr`
- No files are written to the local filesystem as intermediaries
- The `paramiko` dependency covers both SSH exec (for `systemctl restart xochitl`) and SFTP — no additional libraries needed

---

## Linked Commits

- Phase 1 implementation: `2dce608` (tag: `v0.1.0`)
