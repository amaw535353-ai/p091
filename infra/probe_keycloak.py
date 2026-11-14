#!/usr/bin/env python3
"""Real local Keycloak component checks; no token/credential output or retention.

Prerequisite: bootstrap_live.py prepare, then the documented standalone Keycloak
probe or core Keycloak service listening on loopback8081. This is not a full
Compose/PostgreSQL/assistant integration test.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from bootstrap_live import read_env  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from p091.auth import Authenticator  # noqa: E402
from p091.config import Settings  # noqa: E402

TOKEN_URL = "http://127.0.0.1:8081/realms/p091/protocol/openid-connect/token"


def token_request(fields: dict[str, str]) -> tuple[int, dict]:
    request = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(fields).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def main() -> None:
    values = read_env()
    settings = Settings(mode="live", database_url="postgresql://unused")
    results = []
    first_token = ""
    for client, secret_name, sub, tenant in [
        ("indexer", "INDEXER_CLIENT_SECRET", "nw-indexer", "northwind"),
        ("contoso-indexer", "CONTOSO_INDEXER_CLIENT_SECRET", "co-indexer", "contoso"),
    ]:
        status, data = token_request({"grant_type": "client_credentials", "client_id": client,
                                      "client_secret": values[secret_name]})
        if status != 200:
            raise SystemExit("Local service grant failed; HTTP status " + str(status))
        token = data["access_token"]
        first_token = first_token or token
        principal = Authenticator(settings).verify(token)
        observed = {"sub": principal.sub, "tenant": principal.tenant, "actor_type": principal.actor_type,
                    "scopes": sorted(principal.scopes)}
        passed = (principal.sub == sub and principal.tenant == tenant and principal.actor_type == "service"
                  and principal.scopes == frozenset({"ingest"}))
        results.append({"test_id": "LIVE-KC-SERVICE-" + tenant.upper(), "status": "PASS" if passed else "FAIL",
                        "observed": observed})
    for test_id, config, supplied in [
        ("LIVE-KC-WRONG-ISSUER", dataclasses.replace(settings, issuer="http://localhost:8081/realms/other"), first_token),
        ("LIVE-KC-WRONG-AUDIENCE", dataclasses.replace(settings, audience="other-api"), first_token),
    ]:
        try:
            Authenticator(config).verify(supplied)
            code = 200
        except HTTPException as exc:
            code = exc.status_code
        results.append({"test_id": test_id, "expected_http_status": 401, "observed_http_status": code,
                        "status": "PASS" if code == 401 else "FAIL"})
    pieces = first_token.split(".")
    pieces[2] = ("A" if pieces[2][0] != "A" else "B") + pieces[2][1:]
    try:
        Authenticator(settings).verify(".".join(pieces))
        code = 200
    except HTTPException as exc:
        code = exc.status_code
    results.append({"test_id": "LIVE-KC-INVALID-SIGNATURE", "expected_http_status": 401,
                    "observed_http_status": code, "status": "PASS" if code == 401 else "FAIL"})
    verifier = Authenticator(settings)
    verifier.verify(first_token)
    verifier.revoke(first_token)
    try:
        verifier.verify(first_token)
        code = 200
    except HTTPException as exc:
        code = exc.status_code
    results.append({"test_id": "LIVE-KC-APP-LOGOUT", "expected_http_status": 401,
                    "observed_http_status": code, "status": "PASS" if code == 401 else "FAIL",
                    "limitation": "Process-local application revocation only; not external Keycloak session revocation"})
    status, _ = token_request({"grant_type": "password", "client_id": "p091-web", "username": "nw-employee",
                               "password": values["LAB_USER_PASSWORD"]})
    results.append({"test_id": "LIVE-KC-PASSWORD-GRANT-DISABLED", "observed_http_status": status,
                    "status": "PASS" if status in (400, 401) else "FAIL"})
    artifact = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "command": ".venv/bin/python infra/probe_keycloak.py", "component": "Keycloak26.8.2",
        "configuration": "Real standalone Docker Keycloak with H2 dev-file, committed realm, local generated credentials",
        "boundary": "Real Keycloak grant -> signed JWT -> actual application Authenticator + live JWKS",
        "limitation": "Not PostgreSQL-backed Compose or full assistant end-to-end integration; human PKCE evidence is separate",
        "results": results,
    }
    output = ROOT / "docs/evidence/keycloak-component.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n")
    passed = sum(item["status"] == "PASS" for item in results)
    print(f"Real Keycloak component checks: {passed}/{len(results)} PASS; sanitized evidence {output.relative_to(ROOT)}")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
