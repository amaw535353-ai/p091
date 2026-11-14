"""Run `uvicorn p091.main:create_app --factory --host 127.0.0.1`. One worker."""
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from p091.auth import Authenticator, Principal
from p091.config import Settings
from p091.seed import ROOT, seed_store
from p091.services import Services
from p091.store import Store


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictBody):
    user_id: str = Field(min_length=1, max_length=128)


class Search(StrictBody):
    query: str = Field(min_length=1, max_length=1000)


class Question(StrictBody):
    question: str = Field(min_length=1, max_length=1000)


class Share(StrictBody):
    user_id: str = Field(min_length=1, max_length=128)


class Membership(StrictBody):
    member: bool


class Edit(StrictBody):
    body: str = Field(max_length=32768)
    title: str | None = Field(default=None, min_length=1, max_length=200)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    store = Store(config.database_url)
    if config.seed:
        seed_store(store)
    auth = Authenticator(config)
    service = Services(store, config)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        store.close()

    app = FastAPI(title="P-091 Synthetic Security Lab", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.auth, app.state.services = store, auth, service

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.headers.get("host", "").split(":")[0] not in {"localhost", "127.0.0.1", "testserver", "api"}:
            return JSONResponse({"detail": "Local lab host required"}, status_code=400)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 40000):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        # Count while receiving, before accumulation can exceed the bound.
        if request.method in {"POST", "PATCH", "PUT"}:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 40000:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
                body.extend(chunk)
            request._body = bytes(body)
        request.state.correlation_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers.update({
            "X-Correlation-ID": request.state.correlation_id,
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' http://localhost:8081; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        })
        return response

    @app.exception_handler(HTTPException)
    async def denied(request: Request, error: HTTPException):
        with store.lock:
            principal = getattr(request.state, "principal", None)
            store.audit(request.state.correlation_id, principal.sub if principal else "anonymous", principal.actor_type if principal else "unknown", "request", f"DENY_{error.status_code}")
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    def current(request: Request, authorization: Annotated[str | None, Header()] = None) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer credentials required")
        principal = auth.verify(authorization[7:])
        request.state.principal = principal
        return principal

    Identity = Annotated[Principal, Depends(current)]

    def record(request: Request, p: Principal, action: str, source_version: str | None = None):
        store.audit(request.state.correlation_id, p.sub, p.actor_type, action, "ALLOW", source_version)

    @app.get("/config")
    def public_config():
        return {"mode": config.mode, "oidc_issuer": config.issuer, "oidc_client_id": "p091-web", "redirect_uri": "http://localhost:8000/", "logout_url": config.issuer + "/protocol/openid-connect/logout"}

    @app.get("/health/live")
    def live():
        return {"status": "alive", "mode": config.mode}

    @app.get("/health/ready")
    def ready():
        with store.lock:
            store.execute("SELECT 1")
            service.fault("authz", "retrieval", "source", "identity")
            if service.fga and (not service.fga.health() or not config.fga_store_id or not config.fga_model_id):
                raise HTTPException(503, "Authorization service not ready")
            if service.vectors and not service.vectors.health():
                raise HTTPException(503, "Retrieval service not ready")
            if config.mode == "live":
                try:
                    response = auth.client.get(config.jwks_url)
                    response.raise_for_status()
                    if not response.json().get("keys"):
                        raise ValueError("No identity keys")
                except (httpx.HTTPError, ValueError, TypeError) as error:
                    raise HTTPException(503, "Identity service not ready") from error
            if service.source:
                candidate = next((d for d in store.documents() if not d["deleted"]), None)
                if not candidate:
                    raise HTTPException(503, "Source not seeded")
                service.source.fetch(candidate["source_path"])
            return {"status": "ready", "mode": config.mode, "source": "nextcloud" if service.source else "synthetic-fixture", "policy_version": "p091-policy-v1"}

    @app.post("/lab/login")
    def login(body: Login, request: Request):
        if config.mode != "offline" or not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(404, "Synthetic login unavailable")
        with store.lock:
            user = store.get_user(body.user_id)
            if not user or user["actor_type"] != "human":
                raise HTTPException(403, "Unknown synthetic user")
            token = auth.issue_lab_token(user["id"], user["tenant"], scopes="read admin" if user["admin"] else "read")
            return {"access_token": token, "token_type": "bearer", "expires_in": 900, "mode": "synthetic-offline"}

    @app.post("/auth/logout")
    def logout(p: Identity, authorization: Annotated[str, Header()]):
        auth.revoke(authorization[7:])
        return {"status": "signed-out"}

    @app.get("/auth/me")
    def me(p: Identity):
        with store.lock:
            user = service.user(p)
            return {"sub": p.sub, "tenant": user["tenant"], "groups": user["groups"], "scopes": sorted(p.scopes), "actor_type": p.actor_type, "admin": user["admin"]}

    @app.get("/documents")
    def documents(request: Request, p: Identity):
        with store.lock:
            values = service.documents(service.user(p))
            record(request, p, "list")
            return {"documents": values}

    @app.get("/documents/{doc_id}")
    @app.get("/documents/{doc_id}/export")
    def document(doc_id: str, request: Request, p: Identity):
        with store.lock:
            doc = service.document(service.user(p), doc_id)
            record(request, p, "document", doc["source_version"])
            return service.view(doc, detail=True)

    @app.get("/citations/{doc_id}/{version}")
    def citation(doc_id: str, version: int, request: Request, p: Identity):
        with store.lock:
            doc = service.document(service.user(p), doc_id, version)
            record(request, p, "citation", doc["source_version"])
            return service.view(doc, detail=True)

    @app.post("/search")
    def search(body: Search, request: Request, p: Identity):
        with store.lock:
            result = service.search(service.user(p), body.query)
            record(request, p, "search")
            return {"documents": result}

    @app.post("/chat")
    def chat(body: Question, request: Request, p: Identity):
        with store.lock:
            result = service.chat(service.user(p), body.question)
            record(request, p, "chat")
            return result

    @app.get("/history")
    def history(p: Identity):
        with store.lock:
            return service.history(service.user(p))

    @app.get("/history/{message_id}")
    @app.get("/history/{message_id}/export")
    @app.get("/summaries/{message_id}")
    def message(message_id: str, p: Identity):
        with store.lock:
            return service.history(service.user(p), message_id)

    @app.post("/admin/documents/{doc_id}/share")
    @app.post("/admin/documents/{doc_id}/unshare")
    def share(doc_id: str, body: Share, request: Request, p: Identity):
        with store.lock:
            user, doc = service.admin_document(p, doc_id)
            target = store.get_user(body.user_id)
            if not target or target["tenant"] != user["tenant"] or target["actor_type"] != "human":
                raise HTTPException(404, "User unavailable")
            grant = request.url.path.endswith("/share")
            # Persist restrictive decision first: partial remote failure denies.
            store.set_shared(doc_id, body.user_id, grant)
            service.sync_fga(doc_id)
            record(request, p, "share" if grant else "unshare", doc["source_version"])
            return {"status": "shared" if grant else "unshared"}

    @app.patch("/admin/groups/{group}/members/{user_id}")
    def membership(group: str, user_id: str, body: Membership, request: Request, p: Identity):
        with store.lock:
            user = service.user(p, admin=True)
            target = store.get_user(user_id)
            if not re.fullmatch(re.escape(user["tenant"]) + r"-(hr|finance)", group) or not target or target["tenant"] != user["tenant"]:
                raise HTTPException(404, "Group unavailable")
            store.set_membership(group, user_id, body.member)
            for doc in store.documents():
                if doc["tenant"] == user["tenant"]:
                    service.sync_fga(doc["id"])
            record(request, p, "membership")
            return {"status": "updated"}

    @app.delete("/admin/documents/{doc_id}")
    def delete(doc_id: str, request: Request, p: Identity):
        with store.lock:
            _, doc = service.admin_document(p, doc_id)
            store.update_document(doc_id, deleted=True)
            service.sync_fga(doc_id, force_remove=True)
            if service.vectors:
                service.vectors.delete(doc_id, doc["tenant"])
            record(request, p, "delete", doc["source_version"])
            return {"status": "deleted"}

    @app.patch("/admin/documents/{doc_id}")
    def edit(doc_id: str, body: Edit, request: Request, p: Identity):
        with store.lock:
            _, doc = service.admin_document(p, doc_id)
            if service.source:
                raise HTTPException(409, "Edit content in Nextcloud then reindex")
            version = doc["version"] + 1
            store.update_document(doc_id, body=body.body, title=body.title or doc["title"], version=version, source_version=str(version))
            record(request, p, "edit", str(version))
            return {"id": doc_id, "version": version, "state": "pending-reindex"}

    @app.post("/admin/documents/{doc_id}/reindex")
    def reindex(doc_id: str, request: Request, p: Identity):
        with store.lock:
            _, doc = service.admin_document(p, doc_id)
            result = service.reindex(doc)
            record(request, p, "reindex", doc["source_version"])
            return result

    @app.post("/ingestion/reindex/{doc_id}")
    def ingest(doc_id: str, request: Request, p: Identity):
        with store.lock:
            user = service.user(p, service=True)
            doc = store.get_document(doc_id)
            if not doc or doc["tenant"] != user["tenant"] or doc["deleted"]:
                raise HTTPException(404, "Document unavailable")
            result = service.reindex(doc)
            record(request, p, "ingest", doc["source_version"])
            return result

    @app.get("/dashboard")
    def dashboard(p: Identity):
        with store.lock:
            user = service.user(p)
            docs = [d for d in store.documents() if d["tenant"] == user["tenant"]]
            own_hash = __import__("hashlib").sha256(p.sub.encode()).hexdigest()[:16]
            failures = store.execute("SELECT count(*) AS n FROM audits WHERE actor_hash=? AND outcome LIKE 'DENY_%'", (own_hash,)).fetchone()["n"]
            evidence = ROOT / "docs/evidence/manifest.json"
            return {"mode": config.mode, "tenant": user["tenant"], "sync": {"pending": sum(d["source_version"] != d["synced_version"] for d in docs)} if user["admin"] else {"status": "restricted"}, "authorization_failures": failures, "evaluations": "see local evidence manifest", "evidence_ids": ["latest"] if evidence.exists() else [], "policy_version": "p091-policy-v1"}

    web = ROOT / "apps/web"
    if web.exists():
        app.mount("/assets", StaticFiles(directory=web), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        path = Path(web / "index.html")
        if not path.exists():
            return JSONResponse({"project": "P-091", "docs": "/docs"})
        return FileResponse(path)

    return app
