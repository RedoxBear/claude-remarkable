"""Tests for the document model — no device or network required."""
import json

import pytest

from rm_bridge.documents import (
    DocumentContent,
    DocumentMetadata,
    build_pagedata,
    generate_uuid,
    metadata_to_document,
)


def test_generate_uuid_format():
    uid = generate_uuid()
    parts = uid.split("-")
    assert len(parts) == 5
    assert len(uid) == 36


def test_generate_uuid_unique():
    uuids = {generate_uuid() for _ in range(100)}
    assert len(uuids) == 100


class TestDocumentMetadata:
    def test_to_json_round_trip(self):
        meta = DocumentMetadata(visible_name="Test Doc", parent="parent-uuid")
        raw = meta.to_json()
        restored = DocumentMetadata.from_json(raw)

        assert restored.visible_name == "Test Doc"
        assert restored.parent == "parent-uuid"
        assert restored.type == "DocumentType"
        assert restored.version == 1

    def test_json_contains_required_fields(self):
        meta = DocumentMetadata(visible_name="Hello")
        data = json.loads(meta.to_json())

        for key in ("visibleName", "parent", "lastModified", "type", "version", "pinned",
                    "synced", "deleted", "metadatamodified", "modified", "lastOpenedPage"):
            assert key in data, f"Missing key: {key}"

    def test_from_json_unknown_fields_ignored(self):
        raw = json.dumps({
            "visibleName": "Test",
            "parent": "",
            "lastModified": "1000000000000",
            "type": "DocumentType",
            "version": 2,
            "unknownField": "ignored",
        })
        meta = DocumentMetadata.from_json(raw)
        assert meta.version == 2

    def test_defaults_are_sensible(self):
        meta = DocumentMetadata(visible_name="X")
        assert meta.deleted is False
        assert meta.pinned is False
        assert meta.type == "DocumentType"


class TestDocumentContent:
    def test_pages_auto_generated(self):
        content = DocumentContent(page_count=3)
        assert len(content.pages) == 3
        assert all(len(p) == 36 for p in content.pages)  # UUID format

    def test_explicit_pages_not_overwritten(self):
        pages = ["page-a", "page-b"]
        content = DocumentContent(page_count=2, pages=pages)
        assert content.pages == pages

    def test_to_json_round_trip(self):
        content = DocumentContent(file_type="pdf", page_count=2)
        raw = content.to_json()
        restored = DocumentContent.from_json(raw)

        assert restored.file_type == "pdf"
        assert restored.page_count == 2
        assert len(restored.pages) == 2

    def test_json_structure(self):
        content = DocumentContent(file_type="epub", page_count=1)
        data = json.loads(content.to_json())

        assert data["fileType"] == "epub"
        assert data["pageCount"] == 1
        assert isinstance(data["pages"], list)
        assert "extraMetadata" in data


class TestBuildPagedata:
    def test_correct_line_count(self):
        result = build_pagedata(3)
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_default_template(self):
        result = build_pagedata(2)
        assert all(line == "Blank" for line in result.strip().split("\n"))

    def test_custom_template(self):
        result = build_pagedata(2, template="Lined")
        assert all(line == "Lined" for line in result.strip().split("\n"))

    def test_ends_with_newline(self):
        assert build_pagedata(1).endswith("\n")


class TestMetadataToDocument:
    def test_basic_conversion(self):
        meta = DocumentMetadata(visible_name="My Doc", parent="folder-uuid")
        content = DocumentContent(file_type="pdf", page_count=5)
        doc = metadata_to_document("test-uuid", meta, content)

        assert doc.uuid == "test-uuid"
        assert doc.title == "My Doc"
        assert doc.parent_id == "folder-uuid"
        assert doc.file_type == "pdf"
        assert doc.page_count == 5

    def test_without_content(self):
        meta = DocumentMetadata(visible_name="Doc")
        doc = metadata_to_document("uid", meta, None)
        assert doc.file_type == "pdf"
        assert doc.page_count == 1
