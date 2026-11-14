"""Small bounded REST adapters. Retrieved/vector metadata never grants access."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any
from urllib.parse import quote, unquote
from uuid import NAMESPACE_URL, uuid5

import httpx
from defusedxml import ElementTree
from fastapi import HTTPException


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value):
        raise HTTPException(400, "Invalid resource identifier")
    return value


class OpenFGA:
    def __init__(self, settings: Any, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=5, follow_redirects=False)

    def _post(self, operation: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.fga_store_id or not self.settings.fga_model_id:
            raise HTTPException(503, "Authorization service unconfigured")
        store = _identifier(self.settings.fga_store_id)
        headers = {"Authorization": f"Bearer {self.settings.fga_token}"}
        try:
            payload = data if operation == "read" else {
                "authorization_model_id": self.settings.fga_model_id, **data
            }
            response = self.client.post(
                f"{self.settings.openfga_url.rstrip('/')}/stores/{store}/{operation}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            body = response.json() if response.content else {}
            if not isinstance(body, dict):
                raise ValueError("Malformed response")
            return body
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise HTTPException(503, "Authorization service unavailable") from error

    def check(self, user_id: str, doc_id: str) -> bool:
        result = self._post(
            "check",
            {
                "tuple_key": {
                    "user": f"user:{_identifier(user_id)}",
                    "relation": "viewer",
                    "object": f"document:{_identifier(doc_id)}",
                },
                "consistency": "HIGHER_CONSISTENCY",
            },
        )
        if not isinstance(result.get("allowed"), bool):
            raise HTTPException(503, "Authorization service unavailable")
        return result["allowed"]

    def write(self, writes: list[dict[str, str]], deletes: list[dict[str, str]]) -> None:
        data: dict[str, Any] = {}
        if writes:
            data["writes"] = {"tuple_keys": writes}
        if deletes:
            data["deletes"] = {"tuple_keys": deletes}
        if data:
            self._post("write", data)

    def read_document_viewers(self, doc_id: str) -> set[str]:
        """Read exact stored direct-user tuples, never expand inherited access.

        Intended for reconciliation while the canonical policy is quarantined.
        This is not an authorization check and cannot replace `check` at egress.
        Bounded pagination rejects loops/oversized responses rather than silently
        treating a partial tuple set as complete.
        """
        object_id = f"document:{_identifier(doc_id)}"
        viewers: set[str] = set()
        continuation = ""
        seen: set[str] = set()
        try:
            for _ in range(100):
                data: dict[str, Any] = {
                    "tuple_key": {"relation": "viewer", "object": object_id},
                    "page_size": 100,
                    "consistency": "HIGHER_CONSISTENCY",
                }
                if continuation:
                    data["continuation_token"] = continuation
                result = self._post("read", data)
                tuples = result.get("tuples", [])
                if not isinstance(tuples, list) or len(tuples) > 100:
                    raise ValueError("Malformed tuple page")
                for item in tuples:
                    key = item["key"]
                    if key.get("object") != object_id or key.get("relation") != "viewer":
                        raise ValueError("Unexpected tuple")
                    user = key["user"]
                    if not isinstance(user, str):
                        raise ValueError("Malformed user")
                    if user.startswith("user:") and "#" not in user:
                        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", user.removeprefix("user:")):
                            raise ValueError("Malformed direct user")
                        viewers.add(user)
                continuation = result.get("continuation_token", "")
                if not isinstance(continuation, str) or len(continuation) > 8192:
                    raise ValueError("Malformed continuation")
                if not continuation:
                    return viewers
                if continuation in seen:
                    raise ValueError("Pagination loop")
                seen.add(continuation)
            raise ValueError("Pagination limit exceeded")
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise HTTPException(503, "Authorization service unavailable") from error

    def health(self) -> bool:
        try:
            response = self.client.get(self.settings.openfga_url.rstrip('/') + "/healthz")
            return response.is_success
        except httpx.HTTPError:
            return False


def embed(text: str) -> list[float]:
    """Deterministic hash bag-of-words, suitable for a lab, not semantic quality."""
    vector = [0.0] * 64
    for word in re.findall(r"\w+", text.casefold())[:8192]:
        hashed = hashlib.sha256(word.encode()).digest()
        index = int.from_bytes(hashed[:2], "big") % len(vector)
        vector[index] += 1.0 if hashed[2] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else [1.0] + [0.0] * 63


class Qdrant:
    def __init__(self, settings: Any, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=5, follow_redirects=False)

    def _request(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.client.request(
                method,
                self.settings.qdrant_url.rstrip("/") + path,
                headers={"api-key": self.settings.qdrant_key},
                json=data,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Malformed response")
            return result
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise HTTPException(503, "Retrieval service unavailable") from error

    @staticmethod
    def _collection(tenant: str) -> str:
        return "p091_" + _identifier(tenant)

    def ensure_collection(self, tenant: str) -> None:
        collection = self._collection(tenant)
        result = self._request("GET", "/collections")
        try:
            existing = result["result"]["collections"]
            if not isinstance(existing, list) or not all(isinstance(item, dict) for item in existing):
                raise ValueError("Malformed collections")
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(503, "Retrieval service unavailable") from error
        if not any(item.get("name") == collection for item in existing):
            self._request(
                "PUT", f"/collections/{collection}",
                {"vectors": {"size": 64, "distance": "Cosine"}},
            )

    def index(self, doc_id: str, tenant: str, text: str, version: str) -> None:
        doc_id = _identifier(doc_id)
        collection = self._collection(tenant)
        self.ensure_collection(tenant)
        self._request(
            "PUT", f"/collections/{collection}/points?wait=true",
            {"points": [{
                "id": str(uuid5(NAMESPACE_URL, f"p091:{tenant}:{doc_id}")),
                "vector": embed(text),
                "payload": {"tenant": tenant, "doc_id": doc_id, "version": version},
            }]},
        )

    def query(self, tenant: str, query: str) -> list[str]:
        collection = self._collection(tenant)
        result = self._request(
            "POST", f"/collections/{collection}/points/query",
            {
                "query": embed(query), "limit": 64, "with_payload": True,
                "with_vector": False,
                "filter": {"must": [{"key": "tenant", "match": {"value": tenant}}]},
            },
        )
        try:
            points = result["result"]["points"]
            if not isinstance(points, list) or len(points) > 64:
                raise ValueError("Malformed points")
            # Metadata is not authoritative: identifiers are only candidates.
            # Root must recheck canonical tenant, source version and ACL for each.
            return [
                _identifier(point["payload"]["doc_id"])
                for point in points
                if point.get("payload", {}).get("tenant") == tenant
            ]
        except (KeyError, TypeError, ValueError, HTTPException, AttributeError) as error:
            raise HTTPException(503, "Retrieval service unavailable") from error

    def delete(self, doc_id: str, tenant: str) -> None:
        collection = self._collection(tenant)
        self._request(
            "POST", f"/collections/{collection}/points/delete?wait=true",
            {"points": [str(uuid5(NAMESPACE_URL, f"p091:{tenant}:{_identifier(doc_id)}"))]},
        )

    def health(self) -> bool:
        try:
            self._request("GET", "/collections")
            return True
        except HTTPException:
            return False


class NextcloudSource:
    MAX_BYTES = 32768

    def __init__(self, settings: Any, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=5, follow_redirects=False)

    def _url(self, source_path: str) -> str:
        decoded = unquote(source_path)
        parts = decoded.split("/")
        if (
            not source_path or len(source_path) > 512 or decoded != source_path
            or source_path.startswith("/") or any(part in ("", ".", "..") for part in parts)
            or any(char in source_path for char in ("\\", ":", "?", "#", "\x00"))
            or any(ord(char) < 32 for char in source_path)
        ):
            raise HTTPException(400, "Invalid source path")
        if not source_path.casefold().endswith((".txt", ".md")):
            raise HTTPException(415, "Only UTF-8 plain-text source files are supported")
        user = quote(self.settings.nextcloud_user, safe="")
        path = "/".join(quote(part, safe="") for part in parts)
        return f"{self.settings.nextcloud_url.rstrip('/')}/remote.php/dav/files/{user}/{path}"

    def _bounded(self, method: str, url: str, headers: dict[str, str], content: bytes | None = None) -> bytes:
        auth = (self.settings.nextcloud_user, self.settings.nextcloud_password)
        with self.client.stream(method, url, headers=headers, content=content, auth=auth) as response:
            response.raise_for_status()
            length = response.headers.get("content-length")
            if length and int(length) > self.MAX_BYTES:
                raise HTTPException(413, "Source exceeds lab size limit")
            chunks = bytearray()
            for chunk in response.iter_bytes(chunk_size=4096):
                if len(chunks) + len(chunk) > self.MAX_BYTES:
                    raise HTTPException(413, "Source exceeds lab size limit")
                chunks.extend(chunk)
            return bytes(chunks)

    def fetch(self, source_path: str) -> dict[str, str]:
        url = self._url(source_path)
        try:
            xml = self._bounded(
                "PROPFIND", url, {"Depth": "0", "Content-Type": "application/xml"},
                b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><d:getetag/><d:getcontentlength/><d:getcontenttype/><oc:permissions/></d:prop></d:propfind>',
            )
            root = ElementTree.fromstring(xml)
            namespace = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
            successful = [
                propstat.find("d:prop", namespace)
                for propstat in root.findall(".//d:propstat", namespace)
                if " 200 " in (propstat.findtext("d:status", default="", namespaces=namespace))
            ]
            if len(successful) != 1 or successful[0] is None:
                raise ValueError("Unknown source metadata")
            props = successful[0]
            etag = props.findtext("d:getetag", default="", namespaces=namespace)
            permissions = props.findtext("oc:permissions", default="", namespaces=namespace)
            content_type = props.findtext("d:getcontenttype", default="", namespaces=namespace)
            length = props.findtext("d:getcontentlength", default="", namespaces=namespace)
            if "G" not in permissions or not etag or not length:
                raise HTTPException(503, "Source permissions or version unknown")
            if int(length) > self.MAX_BYTES or int(length) < 0:
                raise HTTPException(413, "Source exceeds lab size limit")
            if content_type.split(";", 1)[0] not in ("text/plain", "text/markdown", "text/x-markdown"):
                raise HTTPException(415, "Only UTF-8 plain-text source files are supported")
            if "\r" in etag or "\n" in etag or len(etag) > 256:
                raise ValueError("Malformed version")
            body = self._bounded("GET", url, {"If-Match": etag})
            return {"text": body.decode("utf-8", errors="strict"), "version": etag, "permissions": permissions}
        except HTTPException:
            raise
        except Exception as error:
            # XML/entity failures, network errors, missing metadata and invalid
            # text are deliberately indistinguishable to callers.
            raise HTTPException(503, "Source unavailable or unverified") from error
