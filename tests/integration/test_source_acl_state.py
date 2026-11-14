"""F-004: content ingestion cannot certify an unknown human authorization policy."""

import httpx
import pytest
from fastapi.testclient import TestClient

from p091.adapters import NextcloudSource
from p091.config import Settings
from p091.main import create_app


@pytest.mark.parametrize("acl_known", [False, True])
def test_content_reindex_preserves_independent_acl_state(acl_known):
    """SOURCE-ACL-001: indexer may refresh content without changing ACL certainty."""
    settings = Settings(
        database_url="sqlite:///:memory:", nextcloud_enabled=True, nextcloud_user="connector"
    )
    app = create_app(settings)
    doc = next(
        d for d in app.state.store.documents()
        if d["group"] == "northwind-hr" and d["owner"] != "nw-employee" and not d["deleted"]
    )
    app.state.store.update_document(
        doc["id"], source_version='"v1"', synced_version='"v1"', acl_known=acl_known
    )
    source_body = doc["body"].encode()
    # G establishes connector readability only; this response contains no
    # authoritative end-user/group ACL mapping or reconciliation proof.
    metadata = (
        '<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        '<d:response><d:propstat><d:prop><d:getetag>"v1"</d:getetag>'
        f"<d:getcontentlength>{len(source_body)}</d:getcontentlength>"
        "<d:getcontenttype>text/plain</d:getcontenttype><oc:permissions>G</oc:permissions>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    ).encode()
    source_requests = []

    def source_response(request):
        source_requests.append(request.method)
        if request.method == "PROPFIND":
            return httpx.Response(207, content=metadata)
        assert request.method == "GET"
        assert request.headers["If-Match"] == '"v1"'
        return httpx.Response(200, content=source_body)

    app.state.services.source = NextcloudSource(
        settings, httpx.Client(transport=httpx.MockTransport(source_response))
    )
    with TestClient(app) as client:
        employee = {
            "Authorization": "Bearer "
            + client.post("/lab/login", json={"user_id": "nw-employee"}).json()["access_token"]
        }
        workload = {
            "Authorization": "Bearer "
            + app.state.auth.issue_lab_token(
                "nw-indexer", "northwind", actor_type="service", scopes="ingest"
            )
        }
        expected_status = 200 if acl_known else 404
        assert client.get("/documents/" + doc["id"], headers=employee).status_code == expected_status
        reindexed = client.post("/ingestion/reindex/" + doc["id"], headers=workload)
        assert reindexed.status_code == 200
        assert "body" not in reindexed.json()
        assert "title" not in reindexed.json()
        current = app.state.store.get_document(doc["id"])
        assert current["acl_known"] is acl_known
        assert current["source_version"] == current["synced_version"]
        assert client.get("/documents/" + doc["id"], headers=employee).status_code == expected_status
        assert source_requests
        assert set(source_requests) == {"PROPFIND", "GET"}
