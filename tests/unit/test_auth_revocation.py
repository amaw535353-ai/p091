"""F-003 regression: logout revokes authenticated identity across JWT encodings."""

import json
import time

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from p091.auth import Authenticator
from p091.config import Settings
from p091.main import create_app


@pytest.mark.parametrize("padding", ["=", "==", "==="])
def test_api_logout_rejects_signature_padding_variants(padding):
    """AUTH-LOGOUT-001: revoked signature padding variants cannot regain access."""
    app = create_app(Settings(mode="offline", database_url="sqlite:///:memory:"))
    with TestClient(app) as client:
        response = client.post("/lab/login", json={"user_id": "nw-employee"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        original = {"Authorization": "Bearer " + token}
        variant = {"Authorization": "Bearer " + token + padding}
        assert client.get("/auth/me", headers=original).status_code == 200
        # PyJWT accepts this equivalent signature encoding. It remains the same
        # authenticated identity and must receive the same revocation decision.
        assert client.get("/auth/me", headers=variant).status_code == 200
        assert client.post("/auth/logout", headers=original).status_code == 200
        assert client.get("/auth/me", headers=original).status_code == 401
        assert client.get("/auth/me", headers=variant).status_code == 401
        assert client.get("/documents", headers=variant).status_code == 401


def test_api_forged_same_jti_cannot_authorize_or_revoke_valid_identity():
    """AUTH-LOGOUT-002: unverified jti cannot authorize or poison logout state."""
    config = Settings(mode="offline", database_url="sqlite:///:memory:")
    app = create_app(config)
    with TestClient(app) as client:
        token = client.post("/lab/login", json={"user_id": "nw-employee"}).json()["access_token"]
        # The test inspects synthetic fixture claims; the application never uses
        # unverified payload claims to make authorization/revocation decisions.
        claims = jwt.decode(token, options={"verify_signature": False})
        attacker = Authenticator(config)
        forged = attacker.issue_lab_token("nw-employee", "northwind", overrides=claims)
        original_headers = {"Authorization": "Bearer " + token}
        forged_headers = {"Authorization": "Bearer " + forged}
        assert client.get("/auth/me", headers=forged_headers).status_code == 401
        assert client.post("/auth/logout", headers=forged_headers).status_code == 401
        assert client.get("/auth/me", headers=original_headers).status_code == 200
        assert client.post("/auth/logout", headers=original_headers).status_code == 200
        assert client.get("/auth/me", headers=forged_headers).status_code == 401
        assert client.get("/auth/me", headers=original_headers).status_code == 401


def test_live_jwks_verified_identity_revocation_covers_equivalent_encodings():
    """AUTH-LOGOUT-003: mocked live-JWKS path shares the identity-based denylist."""
    config = Settings(mode="offline", database_url="sqlite:///:memory:")
    issuer = Authenticator(config)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(issuer.private_key.public_key()))
    public.update(kid="offline-lab", use="sig", alg="RS256")
    # Authenticator only uses identity settings here: no database is connected
    # and the mocked JWKS path does not claim that Keycloak ran.
    live_config = Settings(mode="live", database_url="postgresql://synthetic:synthetic@localhost/p091")
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"keys": [public]}))
    verifier = Authenticator(live_config, httpx.Client(transport=transport))
    token = issuer.issue_lab_token("nw-employee", "northwind")
    assert verifier.verify(token + "=").sub == "nw-employee"
    verifier.revoke(token + "==")
    for variant in (token, token + "=", token + "==", token + "==="):
        with pytest.raises(HTTPException) as result:
            verifier.verify(variant)
        assert result.value.status_code == 401


def test_expired_revocation_entries_are_pruned_without_affecting_active_identity():
    """AUTH-LOGOUT-004: identity denylist retains bounded expiry pruning."""
    config = Settings(mode="offline", database_url="sqlite:///:memory:")
    auth = Authenticator(config)
    token = auth.issue_lab_token("nw-employee", "northwind")
    auth._revoked["expired-synthetic-fixture"] = time.time() - 1
    assert auth.verify(token).sub == "nw-employee"
    assert "expired-synthetic-fixture" not in auth._revoked
