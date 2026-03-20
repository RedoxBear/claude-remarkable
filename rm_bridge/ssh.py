"""SSH transport — connect, list, push PDF, pull document + annotations, restart xochitl.

Uses SFTP (via paramiko) for all file transfers. See ADR-002.

Device facts:
  USB IP:  10.11.99.1 (always)
  WiFi IP: shown in Settings → Help → Copyrights
  SSH:     root@<ip>, port 22
  Docs:    /home/root/.local/share/remarkable/xochitl/
"""
from __future__ import annotations

import io
import stat
from pathlib import Path

import paramiko
from pypdf import PdfReader

from .documents import (
    XOCHITL_ROOT,
    Document,
    DocumentContent,
    DocumentMetadata,
    build_pagedata,
    generate_uuid,
    metadata_to_document,
)
from .transport import Transport


class SSHTransport(Transport):
    """Direct SSH/SFTP access to the Remarkable 2 device."""

    def __init__(
        self,
        host: str,
        username: str = "root",
        password: str | None = None,
        key_path: str | None = None,
        port: int = 22,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._key_path = key_path
        self._port = port
        self._timeout = timeout
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open SSH + SFTP connections to the device."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict = {
            "hostname": self._host,
            "port": self._port,
            "username": self._username,
            "timeout": self._timeout,
        }

        if self._key_path:
            connect_kwargs["key_filename"] = self._key_path
        elif self._password:
            connect_kwargs["password"] = self._password
        else:
            # Try agent / default key locations
            connect_kwargs["look_for_keys"] = True
            connect_kwargs["allow_agent"] = True

        client.connect(**connect_kwargs)
        self._client = client
        self._sftp = client.open_sftp()

    def close(self) -> None:
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SSHTransport":
        self.connect()
        return self

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise RuntimeError("Not connected. Call connect() first or use as context manager.")
        return self._sftp

    @property
    def ssh(self) -> paramiko.SSHClient:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first or use as context manager.")
        return self._client

    def _read_file(self, remote_path: str) -> str:
        buf = io.BytesIO()
        self.sftp.getfo(remote_path, buf)
        return buf.getvalue().decode("utf-8")

    def _write_text(self, remote_path: str, content: str) -> None:
        buf = io.BytesIO(content.encode("utf-8"))
        self.sftp.putfo(buf, remote_path)

    def _write_bytes(self, remote_path: str, data: bytes) -> None:
        buf = io.BytesIO(data)
        self.sftp.putfo(buf, remote_path)

    def _doc_path(self, filename: str) -> str:
        return f"{XOCHITL_ROOT}/{filename}"

    def _run(self, cmd: str) -> tuple[str, str]:
        """Run a shell command; return (stdout, stderr)."""
        _, stdout, stderr = self.ssh.exec_command(cmd)
        return stdout.read().decode(), stderr.read().decode()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_documents(self) -> list[Document]:
        """Return all non-deleted documents on the device."""
        docs: list[Document] = []

        try:
            entries = self.sftp.listdir(XOCHITL_ROOT)
        except FileNotFoundError as e:
            raise RuntimeError(f"xochitl directory not found: {XOCHITL_ROOT}") from e

        metadata_files = [e for e in entries if e.endswith(".metadata")]

        for filename in metadata_files:
            doc_uuid = filename[:-9]  # strip ".metadata"
            try:
                raw_meta = self._read_file(self._doc_path(filename))
                meta = DocumentMetadata.from_json(raw_meta)

                if meta.deleted:
                    continue

                content: DocumentContent | None = None
                content_path = self._doc_path(f"{doc_uuid}.content")
                try:
                    raw_content = self._read_file(content_path)
                    content = DocumentContent.from_json(raw_content)
                except FileNotFoundError:
                    pass  # .content may be absent on older documents

                docs.append(metadata_to_document(doc_uuid, meta, content))

            except Exception as e:
                # Log and skip corrupt entries rather than aborting the full list
                print(f"[warn] skipping {doc_uuid}: {e}")

        return sorted(docs, key=lambda d: d.modified_ms, reverse=True)

    def push_pdf(self, path: Path, title: str | None = None, parent_id: str = "") -> Document:
        """Push a PDF to the device and return the resulting Document.

        Per official reMarkable documentation: xochitl must NOT be running
        while files are written. We stop it, write atomically, then restart.

        Steps:
          1. Generate UUID and count pages
          2. Stop xochitl
          3. SFTP-put .pdf, .metadata, .content, .pagedata
          4. Restart xochitl (always — even on write failure)
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        doc_title = title or path.stem
        doc_uuid = generate_uuid()

        reader = PdfReader(str(path))
        page_count = len(reader.pages)

        meta = DocumentMetadata(visible_name=doc_title, parent=parent_id)
        content = DocumentContent(file_type="pdf", page_count=page_count)
        pagedata = build_pagedata(page_count)

        self.stop_xochitl()
        try:
            self._write_bytes(self._doc_path(f"{doc_uuid}.pdf"), path.read_bytes())
            self._write_text(self._doc_path(f"{doc_uuid}.metadata"), meta.to_json())
            self._write_text(self._doc_path(f"{doc_uuid}.content"), content.to_json())
            self._write_text(self._doc_path(f"{doc_uuid}.pagedata"), pagedata)
        finally:
            # Always restart — a stopped xochitl is a blank screen on the device
            self.restart_xochitl()

        return metadata_to_document(doc_uuid, meta, content)

    def pull_document(self, uuid: str) -> bytes:
        """Return the original PDF bytes for a document UUID."""
        for ext in (".pdf", ".epub"):
            path = self._doc_path(f"{uuid}{ext}")
            try:
                buf = io.BytesIO()
                self.sftp.getfo(path, buf)
                return buf.getvalue()
            except FileNotFoundError:
                continue
        raise FileNotFoundError(f"No PDF or epub found for UUID {uuid}")

    def pull_annotations(self, uuid: str) -> dict[str, bytes]:
        """Return {page_number: raw_rm_bytes} for all annotation pages.

        Annotation files live at: {uuid}/{pageNum}.rm
        Page numbers are zero-padded strings as returned by the device.
        """
        annotation_dir = self._doc_path(uuid)
        result: dict[str, bytes] = {}

        try:
            entries = self.sftp.listdir_attr(annotation_dir)
        except FileNotFoundError:
            return result  # No annotations — not an error

        for entry in entries:
            if entry.filename.endswith(".rm") and stat.S_ISREG(entry.st_mode):
                page_key = entry.filename[:-3]  # strip ".rm"
                buf = io.BytesIO()
                self.sftp.getfo(f"{annotation_dir}/{entry.filename}", buf)
                result[page_key] = buf.getvalue()

        return result

    def stop_xochitl(self) -> None:
        """Stop the xochitl UI process before writing document files.

        Required by official reMarkable documentation: xochitl must not be
        running when the document store is modified.
        """
        _, stderr = self._run("systemctl stop xochitl")
        if stderr and "Warning" not in stderr:
            raise RuntimeError(f"xochitl stop failed: {stderr.strip()}")

    def restart_xochitl(self) -> None:
        """Restart xochitl after document writes are complete."""
        _, stderr = self._run("systemctl restart xochitl")
        if stderr and "Warning" not in stderr:
            raise RuntimeError(f"xochitl restart failed: {stderr.strip()}")

    def device_info(self) -> dict[str, str]:
        """Return device serial, OS version, and firmware (official detection method)."""
        serial_out, _ = self._run("cat /sys/devices/soc0/serial_number 2>/dev/null || echo unknown")
        # Official method per developer.remarkable.com/documentation/sdk
        version_out, _ = self._run("cat /etc/os-release 2>/dev/null | grep ^VERSION= || echo unknown")
        config_out, _ = self._run("cat /home/root/.config/remarkable/xochitl.conf 2>/dev/null | head -5 || echo ''")
        return {
            "serial": serial_out.strip(),
            "os_version": version_out.strip().removeprefix("VERSION=").strip('"'),
            "host": self._host,
            "xochitl_conf_preview": config_out.strip(),
        }
