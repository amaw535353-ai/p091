"""Observed offline end-to-end workflows; these do not attest to Docker services."""

import pytest
from fastapi.testclient import TestClient

from p091.config import Settings
from p091.main import create_app


@pytest.fixture
def lab():
    app = create_app(Settings(mode="offline", database_url="sqlite:///:memory:"))
    with TestClient(app) as client:
        yield app, client


def login(client, user):
    response = client.post("/lab/login", json={"user_id": user})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def select(app, **conditions):
    for doc in app.state.store.documents():
        if not doc.get("deleted") and all(doc.get(key) == value for key, value in conditions.items()):
            if conditions.get("visibility") == "private" and doc.get("readers"):
                continue
            return doc
    raise AssertionError(f"No synthetic document for {conditions}")


@pytest.mark.parametrize("user,tenant", [("nw-employee", "northwind"), ("nw-manager", "northwind"), ("co-employee", "contoso"), ("co-manager", "contoso")])
def test_permitted_login_search_chat_and_citation(lab, user, tenant):
    """FLOW-001: permitted users obtain grounded answers and verifiable citations."""
    app, client = lab
    headers = login(client, user)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["sub"] == user
    assert me.json()["tenant"] == tenant
    doc = select(app, tenant=tenant, visibility="tenant")
    listed = client.get("/documents", headers=headers)
    assert listed.status_code == 200
    assert doc["id"] in {d["id"] for d in listed.json()["documents"]}
    search = client.post("/search", headers=headers, json={"query": doc["title"]})
    assert search.status_code == 200
    assert doc["id"] in {d["id"] for d in search.json()["documents"]}
    answer = client.post("/chat", headers=headers, json={"question": doc["title"]})
    assert answer.status_code == 200, answer.text
    result = answer.json()
    assert result["mode"] == "extractive"
    assert result["citations"]
    assert result["answer"]
    for citation in result["citations"]:
        verified = client.get(f"/citations/{citation['document_id']}/{citation['version']}", headers=headers)
        assert verified.status_code == 200
        assert citation["quote"] in verified.json()["body"]
    history = client.get(f"/history/{result['id']}", headers=headers)
    assert history.status_code == 200
    assert history.json()["answer"] == result["answer"]


def test_share_unshare_invalidates_all_derivative_paths(lab):
    """FLOW-002: explicit grant followed by revoke prevents cached/history reuse."""
    app, client = lab
    user_headers = login(client, "nw-employee")
    admin_headers = login(client, "nw-admin")
    doc = select(app, tenant="northwind", visibility="private", owner="nw-manager")
    base = f"/admin/documents/{doc['id']}"
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code in (403, 404)
    grant = client.post(base + "/share", headers=admin_headers, json={"user_id": "nw-employee"})
    assert grant.status_code in (200, 204), grant.text
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code == 200
    answer = client.post("/chat", headers=user_headers, json={"question": doc["title"]})
    assert answer.status_code == 200
    result = answer.json()
    assert doc["id"] in {c["document_id"] for c in result["citations"]}
    revoke = client.post(base + "/unshare", headers=admin_headers, json={"user_id": "nw-employee"})
    assert revoke.status_code in (200, 204), revoke.text
    version = next(c["version"] for c in result["citations"] if c["document_id"] == doc["id"])
    for path in [f"/documents/{doc['id']}", f"/documents/{doc['id']}/export", f"/citations/{doc['id']}/{version}", f"/history/{result['id']}", f"/history/{result['id']}/export", f"/summaries/{result['id']}"]:
        denied = client.get(path, headers=user_headers)
        assert denied.status_code in (403, 404, 503), (path, denied.text)
        assert doc["title"] not in denied.text
        assert doc["body"] not in denied.text
    history = client.get("/history", headers=user_headers)
    assert history.status_code == 200
    assert result["id"] not in {m["id"] for m in history.json()["messages"]}
    assert doc["title"] not in history.text
    assert doc["body"] not in history.text


def test_edit_requires_reindex_and_invalidates_prior_citations(lab):
    """FLOW-003: source edits cannot be silently served under old citations."""
    app, client = lab
    user_headers = login(client, "nw-employee")
    admin_headers = login(client, "nw-admin")
    doc = select(app, tenant="northwind", group="northwind-hr")
    old = client.get(f"/documents/{doc['id']}", headers=user_headers)
    assert old.status_code == 200
    old_version = old.json()["version"]
    base = f"/admin/documents/{doc['id']}"
    marker = "HR_UPDATED_BENIGN_MARKER_3917"
    edit = client.patch(base, headers=admin_headers, json={"body": "Updated synthetic HR leave policy. " + marker})
    assert edit.status_code in (200, 204), edit.text
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code in (403, 404, 503)
    reindex = client.post(base + "/reindex", headers=admin_headers)
    assert reindex.status_code in (200, 204), reindex.text
    current = client.get(f"/documents/{doc['id']}", headers=user_headers)
    assert current.status_code == 200
    assert marker in current.json()["body"]
    assert current.json()["version"] != old_version
    assert client.get(f"/citations/{doc['id']}/{old_version}", headers=user_headers).status_code in (403, 404, 409)


def test_health_and_readiness_report_mode(lab):
    """FLOW-004: local liveness/readiness are executable checks."""
    _, client = lab
    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert "offline" in ready.text


def test_no_retrieval_returns_grounded_empty_answer(lab):
    """FLOW-005: empty retrieval is a safe, usable outcome."""
    _, client = lab
    response = client.post("/chat", headers=login(client, "nw-employee"), json={"question": "zzzzunmatchableterm493816"})
    assert response.status_code == 200
    assert response.json()["citations"] == []
    assert response.json()["answer"]


def test_scoped_workload_can_reindex_own_tenant(lab):
    """FLOW-006: least-privileged workload credentials retain indexing utility."""
    app, client = lab
    doc = select(app, tenant="northwind", group="northwind-hr")
    token = app.state.auth.issue_lab_token("nw-indexer", "northwind", actor_type="service", scopes="ingest")
    response = client.post(f"/ingestion/reindex/{doc['id']}", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == doc["id"]
    assert "body" not in response.json()
    assert "title" not in response.json()


def test_group_addition_grants_only_current_authorized_department(lab):
    """FLOW-007: intentional current group grants preserve normal utility."""
    app, client = lab
    doc = select(app, tenant="northwind", group="northwind-finance")
    user_headers = login(client, "nw-employee")
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code in (403, 404)
    response = client.patch("/admin/groups/northwind-finance/members/nw-employee", headers=login(client, "nw-admin"), json={"member": True})
    assert response.status_code == 200, response.text
    assert "northwind-finance" in client.get("/auth/me", headers=user_headers).json()["groups"]
    allowed = client.get(f"/documents/{doc['id']}", headers=user_headers)
    assert allowed.status_code == 200
    assert allowed.json()["body"] == doc["body"]


def test_reindex_resolves_simulated_stale_source_window(lab):
    """FLOW-008: a simulated sync delay denies until the new source is indexed."""
    app, client = lab
    doc = select(app, tenant="northwind", group="northwind-hr")
    user_headers = login(client, "nw-employee")
    app.state.store.update_document(doc["id"], source_version="synthetic-source-v2")
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code in (403, 404, 503)
    sync = client.post(f"/admin/documents/{doc['id']}/reindex", headers=login(client, "nw-admin"))
    assert sync.status_code == 200, sync.text
    current = app.state.store.get_document(doc["id"])
    assert current["source_version"] == current["synced_version"]
    assert client.get(f"/documents/{doc['id']}", headers=user_headers).status_code == 200
