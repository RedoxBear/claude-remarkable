"""Abstract transport interface — implemented by SSHTransport and ConnectTransport."""
from abc import ABC, abstractmethod
from pathlib import Path

from .documents import Document


class Transport(ABC):
    """Common interface for SSH and Remarkable Connect transports."""

    @abstractmethod
    def list_documents(self) -> list[Document]:
        """Return all documents visible to this transport."""

    @abstractmethod
    def push_pdf(self, path: Path, title: str, parent_id: str = "") -> Document:
        """Push a PDF file and return the resulting Document."""

    @abstractmethod
    def pull_document(self, uuid: str) -> bytes:
        """Return the original PDF/epub bytes for a document UUID."""

    @abstractmethod
    def pull_annotations(self, uuid: str) -> dict[str, bytes]:
        """Return a mapping of page_number → raw .rm annotation bytes."""

    @abstractmethod
    def close(self) -> None:
        """Release any open connections or resources."""

    def __enter__(self) -> "Transport":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
