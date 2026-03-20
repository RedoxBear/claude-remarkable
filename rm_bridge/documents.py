"""Document model — UUID structure, metadata, content, and pagedata helpers."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


XOCHITL_ROOT = "/home/root/.local/share/remarkable/xochitl"


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _now_ms() -> str:
    """Return current UTC time as millisecond epoch string (device format)."""
    ts = datetime.now(timezone.utc).timestamp()
    return str(int(ts * 1000))


@dataclass
class Document:
    """Represents a document on the device or in the cloud."""
    uuid: str
    title: str
    parent_id: str = ""
    modified_ms: str = field(default_factory=_now_ms)
    file_type: str = "pdf"      # "pdf" | "epub" | "notebook"
    page_count: int = 1
    pinned: bool = False
    deleted: bool = False

    @property
    def is_folder(self) -> bool:
        return self.file_type == "CollectionType"


@dataclass
class DocumentMetadata:
    """Maps to the {uuid}.metadata JSON file on device."""
    visible_name: str
    parent: str = ""
    last_modified: str = field(default_factory=_now_ms)
    type: str = "DocumentType"     # "DocumentType" | "CollectionType"
    version: int = 1
    pinned: bool = False
    synced: bool = False
    deleted: bool = False
    metadatamodified: bool = True
    modified: bool = True
    last_opened_page: int = 0

    def to_json(self) -> str:
        return json.dumps({
            "visibleName": self.visible_name,
            "parent": self.parent,
            "lastModified": self.last_modified,
            "type": self.type,
            "version": self.version,
            "pinned": self.pinned,
            "synced": self.synced,
            "deleted": self.deleted,
            "metadatamodified": self.metadatamodified,
            "modified": self.modified,
            "lastOpenedPage": self.last_opened_page,
        }, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "DocumentMetadata":
        d = json.loads(raw)
        return cls(
            visible_name=d.get("visibleName", "Untitled"),
            parent=d.get("parent", ""),
            last_modified=d.get("lastModified", _now_ms()),
            type=d.get("type", "DocumentType"),
            version=d.get("version", 1),
            pinned=d.get("pinned", False),
            synced=d.get("synced", False),
            deleted=d.get("deleted", False),
            metadatamodified=d.get("metadatamodified", False),
            modified=d.get("modified", False),
            last_opened_page=d.get("lastOpenedPage", 0),
        )


@dataclass
class DocumentContent:
    """Maps to the {uuid}.content JSON file on device."""
    file_type: str = "pdf"   # "pdf" | "epub" | ""
    page_count: int = 1
    pages: list[str] = field(default_factory=list)
    cover_page_number: int = 0
    line_height: int = -1
    margins: int = 180
    text_scale: int = 1

    def __post_init__(self) -> None:
        if not self.pages:
            self.pages = [generate_uuid() for _ in range(self.page_count)]

    def to_json(self) -> str:
        return json.dumps({
            "extraMetadata": {},
            "fileType": self.file_type,
            "fontName": "",
            "lastOpenedPage": 0,
            "lineHeight": self.line_height,
            "margins": self.margins,
            "pageCount": self.page_count,
            "pages": self.pages,
            "textScale": self.text_scale,
            "transform": {},
            "coverPageNumber": self.cover_page_number,
        }, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "DocumentContent":
        d = json.loads(raw)
        pages = d.get("pages", [])
        return cls(
            file_type=d.get("fileType", "pdf"),
            page_count=d.get("pageCount", len(pages)),
            pages=pages,
            cover_page_number=d.get("coverPageNumber", 0),
            line_height=d.get("lineHeight", -1),
            margins=d.get("margins", 180),
            text_scale=d.get("textScale", 1),
        )


def build_pagedata(page_count: int, template: str = "Blank") -> str:
    """Return the {uuid}.pagedata content: one template name per line."""
    return "\n".join([template] * page_count) + "\n"


def metadata_to_document(doc_uuid: str, meta: DocumentMetadata, content: DocumentContent | None = None) -> Document:
    return Document(
        uuid=doc_uuid,
        title=meta.visible_name,
        parent_id=meta.parent,
        modified_ms=meta.last_modified,
        file_type=content.file_type if content else "pdf",
        page_count=content.page_count if content else 1,
        pinned=meta.pinned,
        deleted=meta.deleted,
    )
