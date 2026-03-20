"""Remarkable Connect cloud transport — device registration, token management, document API.

Auth flow:
  1. User visits https://my.remarkable.com/connect/desktop
  2. User gets a one-time 8-character alphanumeric code
  3. We POST that code + a generated deviceID to /token/json/2/device/new → device token (permanent JWT)
  4. We POST to /token/json/2/user/new with device token → user token (24h JWT)
  5. All subsequent API calls use the user token as Bearer

Token storage: ~/.rm_bridge/tokens.json
Service discovery: hit service-manager to get dynamic storage host before each session.

References:
  - https://akeil.de/posts/remarkable-cloud-api/
  - https://github.com/juruen/rmapi
  - ADR-003 (token storage strategy)
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .documents import (
    Document,
    DocumentContent,
    DocumentMetadata,
    build_pagedata,
    generate_uuid,
    metadata_to_document,
)
from .transport import Transport


# ------------------------------------------------------------------
# API constants
# ------------------------------------------------------------------

AUTH_HOST = "https://my.remarkable.com"
SERVICE_MANAGER_HOST = "https://service-manager-production-dot-remarkable-production.appspot.com"
DEVICE_DESC = "desktop-linux"
REGISTRATION_URL = "https://my.remarkable.com/connect/desktop"

DEFAULT_TOKEN_PATH = Path.home() / ".rm_bridge" / "tokens.json"


class ConnectTransport(Transport):
    """Remarkable Connect (cloud) transport.

    Usage — first-time setup:
        transport = ConnectTransport()
        transport.register("abc12345")   # code from my.remarkable.com/connect/desktop
        transport.connect()

    Usage — subsequent sessions:
        transport = ConnectTransport()
        transport.connect()              # loads stored tokens, refreshes user token
    """

    def __init__(self, token_path: Path | None = None) -> None:
        self._token_path = Path(token_path or DEFAULT_TOKEN_PATH)
        self._device_token: str | None = None
        self._user_token: str | None = None
        self._storage_host: str | None = None
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Registration (one-time)
    # ------------------------------------------------------------------

    def register(self, code: str) -> None:
        """Register this client with a one-time code from {REGISTRATION_URL}.

        The resulting device token is saved to disk and used for all future
        sessions. Call this once; subsequent sessions use connect() only.
        """
        device_id = generate_uuid()
        resp = httpx.post(
            f"{AUTH_HOST}/token/json/2/device/new",
            json={"code": code.strip(), "deviceID": device_id, "deviceDesc": DEVICE_DESC},
            timeout=15,
        )
        resp.raise_for_status()
        self._device_token = resp.text.strip()
        self._save_tokens()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Load stored tokens, refresh the user token, discover storage host."""
        self._load_tokens()
        if not self._device_token:
            raise RuntimeError(
                f"No device token found. Run register() first.\n"
                f"Get a one-time code at: {REGISTRATION_URL}"
            )
        self._refresh_user_token()
        self._discover_storage_host()
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {self._user_token}"},
            timeout=30,
        )

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ConnectTransport":
        self.connect()
        return self

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_user_token(self) -> None:
        resp = httpx.post(
            f"{AUTH_HOST}/token/json/2/user/new",
            headers={
                "Authorization": f"Bearer {self._device_token}",
                "Content-Length": "0",
            },
            content=b"",
            timeout=15,
        )
        resp.raise_for_status()
        self._user_token = resp.text.strip()

    def _discover_storage_host(self) -> None:
        """Hit the service manager to get the current storage host."""
        # Parse user ID from the user token (JWT middle segment)
        try:
            import base64
            payload_b64 = self._user_token.split(".")[1]  # type: ignore[union-attr]
            # Add padding
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            user_id = payload.get("sub", "")
        except Exception:
            user_id = ""

        resp = httpx.get(
            f"{SERVICE_MANAGER_HOST}/service/json/1/document-storage",
            params={"environment": "production", "group": user_id, "apiVer": "2"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        host = data.get("Host", "document-storage-production-dot-remarkable-production.appspot.com")
        self._storage_host = f"https://{host}"

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first or use as context manager.")
        return self._client

    @property
    def storage_base(self) -> str:
        if not self._storage_host:
            raise RuntimeError("Storage host not discovered. Call connect() first.")
        return f"{self._storage_host}/document-storage/json/2"

    def _storage_get(self, path: str, **kwargs) -> httpx.Response:
        resp = self.client.get(f"{self.storage_base}{path}", **kwargs)
        resp.raise_for_status()
        return resp

    def _storage_post(self, path: str, **kwargs) -> httpx.Response:
        resp = self.client.post(f"{self.storage_base}{path}", **kwargs)
        resp.raise_for_status()
        return resp

    def _load_tokens(self) -> None:
        if self._token_path.exists():
            data = json.loads(self._token_path.read_text())
            self._device_token = data.get("device_token")

    def _save_tokens(self) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(json.dumps({"device_token": self._device_token}, indent=2))

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_documents(self) -> list[Document]:
        """Return all documents in the cloud account."""
        resp = self._storage_get("/docs")
        items = resp.json() or []
        docs: list[Document] = []

        for item in items:
            if item.get("Type") != "DocumentType":
                continue
            docs.append(Document(
                uuid=item["ID"],
                title=item.get("VissibleName", "Untitled"),
                parent_id=item.get("Parent", ""),
                modified_ms=item.get("ModifiedClient", "0"),
                file_type=item.get("fileType", "pdf"),
                page_count=item.get("pageCount", 1),
            ))

        return sorted(docs, key=lambda d: d.modified_ms, reverse=True)

    def push_pdf(self, path: Path, title: str | None = None, parent_id: str = "") -> Document:
        """Push a PDF to the cloud via 3-step upload.

        Steps:
          1. POST /uploadRequest → get uploadUrl (pre-signed GCS URL)
          2. PUT the zip to uploadUrl
          3. POST /updateStatus with metadata
        """
        from pypdf import PdfReader

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

        # Build zip in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{doc_uuid}.pdf", path.read_bytes())
            zf.writestr(f"{doc_uuid}.content", content.to_json())
            zf.writestr(f"{doc_uuid}.pagedata", pagedata)
        zip_bytes = zip_buf.getvalue()

        # Step 1: request upload URL
        upload_req = self._storage_post(
            "/uploadRequest",
            json=[{"ID": doc_uuid, "Type": "DocumentType", "Version": 1}],
        )
        upload_info = upload_req.json()
        if not isinstance(upload_info, list) or not upload_info:
            raise RuntimeError(f"Unexpected uploadRequest response: {upload_info}")
        upload_url = upload_info[0].get("BlobURLPut")
        if not upload_url:
            raise RuntimeError("No BlobURLPut in uploadRequest response")

        # Step 2: PUT zip to GCS
        put_resp = httpx.put(upload_url, content=zip_bytes, timeout=60)
        put_resp.raise_for_status()

        # Step 3: update metadata
        status_resp = self._storage_post(
            "/updateStatus",
            json=[{
                "ID": doc_uuid,
                "Parent": parent_id,
                "VissibleName": doc_title,
                "Type": "DocumentType",
                "Version": 1,
                "ModifiedClient": self._now_iso(),
            }],
        )
        data = status_resp.json()
        if isinstance(data, list) and data and not data[0].get("Success", True):
            raise RuntimeError(f"updateStatus failed: {data[0].get('Message')}")

        return metadata_to_document(doc_uuid, meta, content)

    def pull_document(self, uuid: str) -> bytes:
        """Download the original PDF bytes for a document UUID."""
        resp = self._storage_get("/docs", params={"doc": uuid, "withBlob": "true"})
        items = resp.json() or []
        if not items:
            raise FileNotFoundError(f"Document not found in cloud: {uuid}")
        blob_url = items[0].get("BlobURLGet")
        if not blob_url:
            raise RuntimeError(f"No BlobURLGet for {uuid}")

        zip_resp = httpx.get(blob_url, timeout=60)
        zip_resp.raise_for_status()

        # Extract .pdf or .epub from the zip
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith((".pdf", ".epub")):
                    return zf.read(name)
        raise FileNotFoundError(f"No PDF/epub found in blob for {uuid}")

    def pull_annotations(self, uuid: str) -> dict[str, bytes]:
        """Download .rm annotation bytes per page from the cloud blob."""
        resp = self._storage_get("/docs", params={"doc": uuid, "withBlob": "true"})
        items = resp.json() or []
        if not items:
            return {}
        blob_url = items[0].get("BlobURLGet")
        if not blob_url:
            return {}

        zip_resp = httpx.get(blob_url, timeout=60)
        zip_resp.raise_for_status()

        result: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".rm"):
                    page_key = name.split("/")[-1][:-3]
                    result[page_key] = zf.read(name)
        return result
