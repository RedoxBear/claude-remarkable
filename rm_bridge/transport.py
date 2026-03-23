"""Abstract transport interface — implemented by SSHTransport and ConnectTransport."""
from abc import ABC, abstractmethod
from pathlib import Path

from .documents import Document, DocumentContent


class Transport(ABC):
    """Common interface for SSH and Remarkable Connect transports."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection. Must be called before any document operations."""

    @abstractmethod
    def close(self) -> None:
        """Release any open connections or resources."""

    @abstractmethod
    def list_documents(self) -> list[Document]:
        """Return all documents visible to this transport."""

    @abstractmethod
    def push_pdf(self, path: Path, title: str | None, parent_id: str = "") -> Document:
        """Push a PDF file and return the resulting Document."""

    @abstractmethod
    def pull_document(self, uuid: str) -> bytes:
        """Return the original PDF/epub bytes for a document UUID."""

    @abstractmethod
    def pull_annotations(self, uuid: str) -> dict[str, bytes]:
        """Return a mapping of page_uuid → raw .rm annotation bytes."""

    def pull_content(self, uuid: str) -> DocumentContent:
        """Return DocumentContent (page order) for a document UUID.

        Optional — not all transports support this. Raises NotImplementedError
        if the transport cannot provide page ordering (e.g., Connect API
        does not expose page order separately from the document blob).
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support pull_content(). "
            "Annotation rendering will fall back to integer page index ordering."
        )

    def __enter__(self) -> "Transport":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
