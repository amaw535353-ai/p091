"""HTTP contract tests; mock results are not evidence of a live integration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import jwt
import pytest
from fastapi import HTTPException

from p091.adapters import NextcloudSource, OpenFGA, Qdrant, embed
from p091.auth import Authenticator


def settings(**overrides):
    values = dict(
        mode="offline", issuer="http://localhost:8081/realms/p091", audience="p091-api",
        jwks_url="http://localhost:8081/realms/p091/protocol/openid-connect/certs",
        openfga_url="http://localhost:8082", fga_store_id="store", fga_model_id="model",
        fga_token="synthetic-fga", qdrant_url="http://localhost:6333", qdrant_key="synthetic-qdrant",
        nextcloud_url="http://localhost:8083", nextcloud_user="indexer", nextcloud_password="synthetic",
    )
    return SimpleNamespace(**(values | overrides))


def test_offline_rsa_identity_and_process_logout():
    auth = Authenticator(settings())
    token = auth.issue_lab_token("nw-employee", "northwind")
    principal = auth.verify(token)
    assert principal.sub == "nw-employee" and principal.scopes == frozenset({"read"})
    auth.revoke(token)
    with pytest.raises(HTTPException) as result:
        auth.verify(token)
    assert result.value.status_code == 401


@pytest.mark.parametrize("overrides", [
    {"iss": "https://untrusted.invalid"}, {"aud": "another-api"}, {"exp": 1},
    {"iat": 9999999999}, {"nbf": 9999999999}, {"sub": "user:admin"},
    {"tenant": "northwind/contoso"}, {"scope": ["read"]}, {"actor_type": "admin"},
    {"jti": ""}, {"exp": "9999999999"}, {"exp": True}, {"exp": float("inf")},
])
def test_invalid_signed_claims_are_rejected(overrides):
    auth = Authenticator(settings())
    token = auth.issue_lab_token("nw-employee", "northwind", overrides=overrides)
    with pytest.raises(HTTPException) as result:
        auth.verify(token)
    assert result.value.status_code == 401
    assert result.value.detail == "Invalid credentials"


def test_signature_from_another_offline_issuer_is_rejected():
    auth = Authenticator(settings())
    other = Authenticator(settings())
    with pytest.raises(HTTPException) as result:
        auth.verify(other.issue_lab_token("nw-admin", "northwind"))
    assert result.value.status_code == 401


def test_live_jwks_verifier_uses_configured_url_and_fresh_key():
    issuer = Authenticator(settings())
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(issuer.private_key.public_key()))
    public.update(kid="offline-lab", use="sig", alg="RS256")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"keys": [public]})

    auth = Authenticator(settings(mode="live"), httpx.Client(transport=httpx.MockTransport(handler)))
    token = issuer.issue_lab_token("nw-employee", "northwind")
    assert auth.private_key is None
    assert auth.verify(token).sub == "nw-employee"
    assert auth.verify(token).sub == "nw-employee"
    assert calls == [settings().jwks_url] * 2
    with pytest.raises(HTTPException) as result:
        auth.issue_lab_token("nw-admin", "northwind")
    assert result.value.status_code == 404


@pytest.mark.parametrize("body,status", [({"keys": []}, 200), ({"keys": ["broken"]}, 200), ({}, 503)])
def test_live_jwks_outage_or_unknown_key_denies(body, status):
    issuer = Authenticator(settings())
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
    auth = Authenticator(settings(mode="live"), client)
    with pytest.raises(HTTPException) as result:
        auth.verify(issuer.issue_lab_token("nw-employee", "northwind"))
    assert result.value.status_code in (401, 503)


def test_openfga_requires_current_consistency_and_boolean_decision():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"allowed": True})

    adapter = OpenFGA(settings(), httpx.Client(transport=httpx.MockTransport(handler)))
    assert adapter.check("nw-employee", "doc-1") is True
    assert calls[0]["consistency"] == "HIGHER_CONSISTENCY"
    assert calls[0]["tuple_key"] == {"user": "user:nw-employee", "relation": "viewer", "object": "document:doc-1"}


def test_openfga_reads_exact_document_direct_viewers_with_pagination():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.path == "/stores/store/read"
        assert "authorization_model_id" not in body
        assert body["tuple_key"] == {"relation": "viewer", "object": "document:doc-1"}
        if len(calls) == 1:
            return httpx.Response(200, json={"tuples": [
                {"key": {"object": "document:doc-1", "relation": "viewer", "user": "user:nw-employee"}},
                {"key": {"object": "document:doc-1", "relation": "viewer", "user": "group:nw-hr#member"}},
            ], "continuation_token": "page-2"})
        assert body["continuation_token"] == "page-2"
        return httpx.Response(200, json={"tuples": [
            {"key": {"object": "document:doc-1", "relation": "viewer", "user": "user:nw-admin"}},
        ]})

    adapter = OpenFGA(settings(), httpx.Client(transport=httpx.MockTransport(handler)))
    assert adapter.read_document_viewers("doc-1") == {"user:nw-employee", "user:nw-admin"}
    assert len(calls) == 2


@pytest.mark.parametrize("body,status", [
    ({"tuples": "malformed"}, 200),
    ({"tuples": [{"key": {"object": "document:another", "relation": "viewer", "user": "user:nw-admin"}}]}, 200),
    ({"tuples": [{"key": {"object": "document:doc-1", "relation": "viewer", "user": "user:bad/id"}}]}, 200),
    ({"tuples": [], "continuation_token": ["broken"]}, 200),
    ({"error": "private detail"}, 500),
])
def test_openfga_read_errors_fail_closed(body, status):
    adapter = OpenFGA(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))))
    with pytest.raises(HTTPException) as result:
        adapter.read_document_viewers("doc-1")
    assert result.value.status_code == 503
    assert "private detail" not in result.value.detail


def test_openfga_read_repeated_continuation_fails_closed():
    adapter = OpenFGA(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"tuples": [], "continuation_token": "loop"}))))
    with pytest.raises(HTTPException) as result:
        adapter.read_document_viewers("doc-1")
    assert result.value.status_code == 503


@pytest.mark.parametrize("body,status", [({"allowed": "true"}, 200), ({}, 200), ({"error": "do not expose"}, 500)])
def test_openfga_unavailable_or_malformed_fails_closed(body, status):
    adapter = OpenFGA(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))))
    with pytest.raises(HTTPException) as result:
        adapter.check("nw-employee", "doc-1")
    assert result.value.status_code == 503
    assert "do not expose" not in result.value.detail


def test_qdrant_tenant_scoped_filter_and_content_free_payload():
    calls = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, str(request.url), body))
        if request.url.path == "/collections":
            return httpx.Response(200, json={"result": {"collections": [{"name": "p091_northwind"}]}})
        if request.url.path.endswith("/points/query"):
            return httpx.Response(200, json={"result": {"points": [
                {"payload": {"tenant": "northwind", "doc_id": "doc-1"}},
                {"payload": {"tenant": "contoso", "doc_id": "doc-2"}},
            ]}})
        return httpx.Response(200, json={"result": {"status": "completed"}})

    adapter = Qdrant(settings(), httpx.Client(transport=httpx.MockTransport(handler)))
    adapter.index("doc-1", "northwind", "synthetic confidential content", "v1")
    payload = calls[1][2]["points"][0]["payload"]
    assert payload == {"tenant": "northwind", "doc_id": "doc-1", "version": "v1"}
    assert adapter.query("northwind", "question") == ["doc-1"]
    assert calls[-1][2]["filter"] == {"must": [{"key": "tenant", "match": {"value": "northwind"}}]}
    assert "/collections/p091_northwind/" in calls[-1][1]
    assert len(embed("question")) == 64 and embed("question") == embed("question")


@pytest.mark.parametrize("payload", [None, {}, {"result": {"points": "bad"}}, {"result": {"points": [None]}}])
def test_qdrant_malformed_result_denies(payload):
    adapter = Qdrant(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))))
    with pytest.raises(HTTPException) as result:
        adapter.query("northwind", "question")
    assert result.value.status_code == 503


def dav(permissions="G", length="12", content_type="text/plain", etag='&quot;v1&quot;'):
    return f'''<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:response><d:propstat><d:prop><d:getetag>{etag}</d:getetag><d:getcontentlength>{length}</d:getcontentlength><d:getcontenttype>{content_type}</d:getcontenttype><oc:permissions>{permissions}</oc:permissions></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>'''.encode()


def test_nextcloud_bounded_fetch_uses_read_metadata_and_if_match():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "PROPFIND":
            assert request.headers["depth"] == "0"
            return httpx.Response(207, content=dav())
        assert request.headers["if-match"] == '"v1"'
        return httpx.Response(200, content=b"safe content")

    source = NextcloudSource(settings(), httpx.Client(transport=httpx.MockTransport(handler)))
    assert source.fetch("northwind/doc.txt") == {"text": "safe content", "version": '"v1"', "permissions": "G"}
    assert len(calls) == 2


@pytest.mark.parametrize("path", ["../secret.txt", "/secret.txt", "https://evil.invalid/a.txt", "a%2fb.txt", "a/../b.txt", "a\\b.txt", "a.txt?x", "a.txt#x"])
def test_nextcloud_traversal_and_destinations_are_rejected(path):
    source = NextcloudSource(settings())
    with pytest.raises(HTTPException) as result:
        source.fetch(path)
    assert result.value.status_code == 400


@pytest.mark.parametrize("metadata,status", [(dav(permissions="W"), 503), (dav(length="999999"), 413), (dav(content_type="text/html"), 415)])
def test_nextcloud_unknown_permissions_size_and_type_denied(metadata, status):
    source = NextcloudSource(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(207, content=metadata))))
    with pytest.raises(HTTPException) as result:
        source.fetch("doc.txt")
    assert result.value.status_code == status


def test_nextcloud_chunked_oversize_is_bounded():
    def handler(request):
        if request.method == "PROPFIND":
            return httpx.Response(207, content=dav())
        return httpx.Response(200, content=b"x" * (NextcloudSource.MAX_BYTES + 1))

    source = NextcloudSource(settings(), httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(HTTPException) as result:
        source.fetch("doc.txt")
    assert result.value.status_code == 413


def test_nextcloud_xml_external_entities_denied_without_dereference():
    malicious = b'<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><x>&xxe;</x>'
    source = NextcloudSource(settings(), httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(207, content=malicious))))
    with pytest.raises(HTTPException) as result:
        source.fetch("doc.txt")
    assert result.value.status_code == 503
