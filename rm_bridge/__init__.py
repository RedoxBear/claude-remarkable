"""
claude-remarkable — SSH + cloud library for Remarkable 2.

Quick start:

    # SSH (USB cable, device at 10.11.99.1)
    from rm_bridge import ReMarkable
    with ReMarkable(host="10.11.99.1") as rm:
        docs = rm.list_documents()
        rm.push_pdf("paper.pdf", title="My Paper")

    # Remarkable Connect (cloud, first-time setup)
    from rm_bridge import ReMarkable
    rm = ReMarkable.from_connect()
    rm.register("abc12345")   # one-time code from my.remarkable.com/connect/desktop
    with rm:
        docs = rm.list_documents()

    # Remarkable Connect (subsequent sessions)
    with ReMarkable.from_connect() as rm:
        docs = rm.list_documents()
"""
from __future__ import annotations

from pathlib import Path

from .connect import ConnectTransport
from .documents import Document
from .ssh import SSHTransport
from .transport import Transport

__version__ = "0.1.0"
__all__ = ["ReMarkable", "Document"]


class ReMarkable:
    """Facade over SSH and Connect transports.

    Use ReMarkable(host=...) for SSH or ReMarkable.from_connect() for cloud.
    Supports context manager usage; connect() is called automatically on __enter__.
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def over_ssh(
        cls,
        host: str = "10.11.99.1",
        username: str = "root",
        password: str | None = None,
        key_path: str | None = None,
        port: int = 22,
    ) -> "ReMarkable":
        """Create an SSH-backed instance. Alias: ReMarkable(host=...)."""
        return cls(SSHTransport(host, username, password, key_path, port))

    @classmethod
    def from_connect(cls, token_path: Path | None = None) -> "ReMarkable":
        """Create a Remarkable Connect (cloud) backed instance."""
        return cls(ConnectTransport(token_path))

    # Convenience: ReMarkable(host="10.11.99.1") → SSH
    def __class_getitem__(cls, _):  # type: ignore[override]
        return cls

    # ------------------------------------------------------------------
    # Registration (Connect only)
    # ------------------------------------------------------------------

    def register(self, code: str) -> None:
        """Register with a one-time code (Connect transport only)."""
        if not isinstance(self._transport, ConnectTransport):
            raise TypeError("register() is only available for Connect transport")
        self._transport.register(code)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def connect(self) -> "ReMarkable":
        if isinstance(self._transport, SSHTransport):
            self._transport.connect()
        elif isinstance(self._transport, ConnectTransport):
            self._transport.connect()
        return self

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "ReMarkable":
        return self.connect()

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Document API (delegates to transport)
    # ------------------------------------------------------------------

    def list_documents(self) -> list[Document]:
        """List all documents."""
        return self._transport.list_documents()

    def push_pdf(self, path: str | Path, title: str | None = None, parent_id: str = "") -> Document:
        """Push a PDF file to the device or cloud."""
        return self._transport.push_pdf(Path(path), title, parent_id)

    def pull_document(self, uuid: str) -> bytes:
        """Pull the original PDF bytes for a document."""
        return self._transport.pull_document(uuid)

    def pull_annotations(self, uuid: str) -> dict[str, bytes]:
        """Pull raw .rm annotation bytes keyed by page number."""
        return self._transport.pull_annotations(uuid)

    # SSH-only convenience
    def device_info(self) -> dict[str, str]:
        if not isinstance(self._transport, SSHTransport):
            raise TypeError("device_info() is only available for SSH transport")
        return self._transport.device_info()

    def restart_xochitl(self) -> None:
        if not isinstance(self._transport, SSHTransport):
            raise TypeError("restart_xochitl() is only available for SSH transport")
        self._transport.restart_xochitl()
