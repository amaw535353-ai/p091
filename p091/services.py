"""Deterministic authorization and read-time provenance gates outside generation.

All HTTP operations acquire Store.lock. This lab deliberately runs one worker:
multi-replica serializability and durable session revocation are not claimed.
"""
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException

from p091.adapters import NextcloudSource, OpenFGA, Qdrant
from p091.auth import Principal
from p091.config import Settings
from p091.store import Store


def policy_allows(user: dict, doc: dict) -> bool:
    return bool(
        user["actor_type"] == "human" and user["tenant"] == doc["tenant"]
        and not doc["deleted"] and doc["acl_known"]
        and (user["admin"] or doc["visibility"] in {"tenant", "public"}
             or doc["owner"] == user["id"] or user["id"] in doc["readers"]
             or (doc["visibility"] == "group" and doc["group"] in user["groups"]))
    )


class Services:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings
        self.fga = OpenFGA(settings) if settings.mode == "live" else None
        self.vectors = Qdrant(settings) if settings.mode == "live" else None
        self.source = NextcloudSource(settings) if settings.nextcloud_enabled else None

    def fault(self, *names: str) -> None:
        if any(n in self.store.faults for n in names):
            raise HTTPException(503, "Required dependency unavailable")

    def user(self, principal: Principal, *, admin: bool = False, service: bool = False) -> dict:
        self.fault("identity", "keycloak")
        user = self.store.get_user(principal.sub)
        actor = "service" if service else "human"
        scope = "ingest" if service else "read"
        if not user or user["tenant"] != principal.tenant or user["actor_type"] != actor or principal.actor_type != actor or scope not in principal.scopes:
            raise HTTPException(403, "Access denied")
        if admin and (not user["admin"] or "admin" not in principal.scopes):
            raise HTTPException(403, "Access denied")
        return user

    def allowed(self, user: dict, doc: dict | None) -> bool:
        self.fault("authz", "openfga", "source", "nextcloud")
        if not doc or not policy_allows(user, doc):
            return False
        if doc["source_version"] != doc["synced_version"]:
            return False
        if self.fga and not self.fga.check(user["id"], doc["id"]):
            return False
        if self.source:
            if not doc.get("source_path"):
                return False
            fresh = self.source.fetch(doc["source_path"])
            if fresh["version"] != doc["source_version"] or fresh["text"] != doc["body"]:
                return False
        return True

    def document(self, user: dict, doc_id: str, version: int | None = None) -> dict:
        doc = self.store.get_document(doc_id)
        if doc is None or not self.allowed(user, doc) or (version is not None and doc["version"] != version):
            raise HTTPException(404, "Document unavailable")
        return doc

    @staticmethod
    def view(doc: dict, detail: bool = False) -> dict:
        result = {key: doc[key] for key in ("id", "title", "version")}
        result["body" if detail else "snippet"] = doc["body"] if detail else doc["body"][:180]
        return result

    def documents(self, user: dict) -> list[dict]:
        return [self.view(doc) for doc in self.store.documents() if self.allowed(user, doc)]

    def search(self, user: dict, query: str) -> list[dict]:
        self.fault("retrieval", "qdrant")
        candidates = self.vectors.query(user["tenant"], query) if self.vectors else [d["id"] for d in self.store.documents()]
        terms = set(re.findall(r"\w+", query.casefold()))
        ranked: list[tuple[int, dict]] = []
        for doc_id in dict.fromkeys(candidates):
            doc = self.store.get_document(doc_id)
            if doc is not None and self.allowed(user, doc):
                words = set(re.findall(r"\w+", (doc["title"] + " " + doc["body"]).casefold()))
                score = len(words & terms)
                if score:
                    ranked.append((score, doc))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        # Candidate identity and text are canonical SQL, never vector payload.
        return [self.view(self.document(user, d["id"])) for _, d in ranked[:5]]

    def render(self, user: dict, refs: list[dict], message_id: str = "") -> dict:
        self.fault("model")
        citations = []
        for ref in refs:
            doc = self.document(user, ref["document_id"], ref["version"])
            citations.append({"document_id": doc["id"], "chunk_id": str(uuid5(NAMESPACE_URL, f"p091:{doc['id']}:{doc['version']}:0")), "version": doc["version"], "title": doc["title"], "quote": doc["body"][:320]})
        answer = "\n\n".join(c["quote"] for c in citations) if citations else "No authorized matching documents found."
        return {"id": message_id, "answer": answer, "citations": citations, "mode": "extractive"}

    def chat(self, user: dict, question: str) -> dict:
        candidates = self.search(user, question)[:3]
        refs = [{"document_id": doc["id"], "version": doc["version"]} for doc in candidates]
        result = self.render(user, refs)
        result["id"] = self.store.save_message(user["id"], question, refs)
        return result

    def history(self, user: dict, message_id: str | None = None) -> Any:
        values = []
        for message in self.store.messages(user["id"]):
            if message_id and message["id"] != message_id:
                continue
            try:
                values.append(self.render(user, message["refs"], message["id"]))
            except HTTPException as error:
                if error.status_code != 404:
                    raise
                # Drop the entire dependent answer, including title/question.
                if message_id:
                    raise HTTPException(404, "Message unavailable") from error
        if message_id:
            if not values:
                raise HTTPException(404, "Message unavailable")
            return values[0]
        return {"messages": values}

    def admin_document(self, principal: Principal, doc_id: str) -> tuple[dict, dict]:
        user = self.user(principal, admin=True)
        doc = self.store.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, "Document unavailable")
        if not doc or doc["tenant"] != user["tenant"] or doc["deleted"]:
            raise HTTPException(404, "Document unavailable")
        self.fault("authz", "openfga")
        return user, doc

    def sync_fga(self, doc_id: str, *, force_remove: bool = False) -> None:
        if not self.fga:
            return
        doc = self.store.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, "Document unavailable")
        # Reconcile exact direct tuples, including removals. A failed remote
        # update cannot bypass the restrictive current SQL gate.
        wanted = {f"user:{u['id']}" for u in self.store.users() if not force_remove and policy_allows(u, doc)}
        current = self.fga.read_document_viewers(doc_id)
        def key(user_id: str) -> dict[str, str]:
            return {"user": user_id, "relation": "viewer", "object": f"document:{doc_id}"}
        self.fga.write([key(u) for u in sorted(wanted - current)], [key(u) for u in sorted(current - wanted)])

    def reindex(self, doc: dict) -> dict:
        self.fault("source", "nextcloud", "retrieval", "qdrant")
        if self.source:
            source = self.source.fetch(doc["source_path"])
            body, source_version = source["text"], source["version"]
            version = doc["version"] + int(body != doc["body"])
            # Content ingestion is not a human ACL reconciliation authority.
            self.store.update_document(doc["id"], body=body, version=version, source_version=source_version)
            refreshed = self.store.get_document(doc["id"])
            if refreshed is None:
                raise HTTPException(404, "Document unavailable")
            doc = refreshed
        if self.vectors:
            self.vectors.index(doc["id"], doc["tenant"], doc["title"] + " " + doc["body"], str(doc["version"]))
        self.sync_fga(doc["id"])
        self.store.update_document(doc["id"], synced_version=doc["source_version"])
        return {"id": doc["id"], "version": doc["version"], "state": "synced"}
