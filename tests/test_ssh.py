"""Tests for SSHTransport — all paramiko calls mocked, no device required."""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from rm_bridge.documents import DocumentContent, DocumentMetadata, XOCHITL_ROOT
from rm_bridge.ssh import SSHTransport


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def transport():
    """SSHTransport with mocked paramiko internals."""
    t = SSHTransport(host="10.11.99.1")
    t._client = MagicMock()
    t._sftp = MagicMock()
    return t


def _make_sftp_file(content: str) -> MagicMock:
    """Return a mock that writes content into the passed BytesIO on getfo."""
    def getfo_side_effect(path, buf):
        buf.write(content.encode())
    m = MagicMock()
    m.side_effect = getfo_side_effect
    return m


# ------------------------------------------------------------------
# list_documents
# ------------------------------------------------------------------

class TestListDocuments:
    def test_returns_empty_when_no_metadata_files(self, transport):
        transport._sftp.listdir.return_value = ["some.content", "other.pdf"]
        docs = transport.list_documents()
        assert docs == []

    def test_parses_single_document(self, transport):
        meta = DocumentMetadata(visible_name="Test Doc", parent="")
        content_obj = DocumentContent(file_type="pdf", page_count=2)

        def getfo(path, buf):
            if path.endswith(".metadata"):
                buf.write(meta.to_json().encode())
            elif path.endswith(".content"):
                buf.write(content_obj.to_json().encode())

        transport._sftp.listdir.return_value = ["abc123.metadata"]
        transport._sftp.getfo.side_effect = getfo

        docs = transport.list_documents()
        assert len(docs) == 1
        assert docs[0].title == "Test Doc"
        assert docs[0].uuid == "abc123"
        assert docs[0].page_count == 2

    def test_skips_deleted_documents(self, transport):
        meta = DocumentMetadata(visible_name="Deleted", deleted=True)

        def getfo(path, buf):
            if path.endswith(".metadata"):
                buf.write(meta.to_json().encode())

        transport._sftp.listdir.return_value = ["del123.metadata"]
        transport._sftp.getfo.side_effect = getfo

        docs = transport.list_documents()
        assert docs == []

    def test_skips_corrupt_entries(self, transport):
        def getfo(path, buf):
            buf.write(b"not valid json{{{")

        transport._sftp.listdir.return_value = ["bad.metadata"]
        transport._sftp.getfo.side_effect = getfo

        # Should not raise; just skip
        docs = transport.list_documents()
        assert docs == []


# ------------------------------------------------------------------
# push_pdf
# ------------------------------------------------------------------

class TestPushPdf:
    def test_push_creates_four_files(self, transport, tmp_path):
        pdf_path = tmp_path / "test.pdf"

        # Create a minimal valid PDF
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
                    b"xref\n0 2\n0000000000 65535 f\n0000000009 00000 n\n"
                    b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n")

        written_paths = []
        def putfo(buf, path):
            written_paths.append(path)

        transport._sftp.putfo.side_effect = putfo
        transport._client.exec_command.return_value = (
            MagicMock(), MagicMock(read=lambda: b""), MagicMock(read=lambda: b"")
        )

        with patch("rm_bridge.ssh.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock(), MagicMock()]
            doc = transport.push_pdf(pdf_path, title="My Paper")

        assert len(written_paths) == 4
        extensions = {p.split(".")[-1] for p in written_paths}
        assert extensions == {"pdf", "metadata", "content", "pagedata"}

    def test_push_uses_filename_as_default_title(self, transport, tmp_path):
        pdf_path = tmp_path / "my_paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

        transport._sftp.putfo.return_value = None
        transport._client.exec_command.return_value = (
            MagicMock(), MagicMock(read=lambda: b""), MagicMock(read=lambda: b"")
        )

        with patch("rm_bridge.ssh.PdfReader") as mock_reader:
            mock_reader.return_value.pages = [MagicMock()]
            doc = transport.push_pdf(pdf_path)

        assert doc.title == "my_paper"

    def test_push_raises_for_missing_file(self, transport):
        with pytest.raises(FileNotFoundError):
            transport.push_pdf(Path("/does/not/exist.pdf"))


# ------------------------------------------------------------------
# pull_document
# ------------------------------------------------------------------

class TestPullDocument:
    def test_pulls_pdf(self, transport):
        pdf_bytes = b"%PDF-1.4 content"

        def getfo(path, buf):
            if path.endswith(".pdf"):
                buf.write(pdf_bytes)
            else:
                raise FileNotFoundError

        transport._sftp.getfo.side_effect = getfo
        result = transport.pull_document("some-uuid")
        assert result == pdf_bytes

    def test_raises_when_no_file_found(self, transport):
        transport._sftp.getfo.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            transport.pull_document("no-such-uuid")


# ------------------------------------------------------------------
# pull_annotations
# ------------------------------------------------------------------

class TestPullAnnotations:
    def test_returns_empty_when_no_annotation_dir(self, transport):
        transport._sftp.listdir_attr.side_effect = FileNotFoundError
        result = transport.pull_annotations("some-uuid")
        assert result == {}

    def test_returns_rm_files(self, transport):
        import stat as stat_mod

        entry1 = MagicMock()
        entry1.filename = "0.rm"
        entry1.st_mode = stat_mod.S_IFREG | 0o644

        entry2 = MagicMock()
        entry2.filename = "1.rm"
        entry2.st_mode = stat_mod.S_IFREG | 0o644

        transport._sftp.listdir_attr.return_value = [entry1, entry2]

        def getfo(path, buf):
            buf.write(b"rm-stroke-data")

        transport._sftp.getfo.side_effect = getfo

        result = transport.pull_annotations("some-uuid")
        assert set(result.keys()) == {"0", "1"}
        assert result["0"] == b"rm-stroke-data"


# ------------------------------------------------------------------
# restart_xochitl
# ------------------------------------------------------------------

class TestRestartXochitl:
    def test_restart_calls_systemctl(self, transport):
        transport._client.exec_command.return_value = (
            MagicMock(), MagicMock(read=lambda: b""), MagicMock(read=lambda: b"")
        )
        transport.restart_xochitl()
        cmd = transport._client.exec_command.call_args[0][0]
        assert "xochitl" in cmd
        assert "restart" in cmd

    def test_restart_raises_on_stderr(self, transport):
        transport._client.exec_command.return_value = (
            MagicMock(),
            MagicMock(read=lambda: b""),
            MagicMock(read=lambda: b"Error: unit not found"),
        )
        with pytest.raises(RuntimeError, match="xochitl restart failed"):
            transport.restart_xochitl()
