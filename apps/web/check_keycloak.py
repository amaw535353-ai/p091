#!/usr/bin/env python3
"""Use real Chromium authorization-code PKCE login against the local lab realm."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import HTTPException
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from p091.auth import Authenticator  # noqa: E402
from p091.config import Settings  # noqa: E402

ISSUER = "http://localhost:8081/realms/p091"
REDIRECT = "http://localhost:8000/"


@contextmanager
def callback_listener() -> Iterator[None]:
    """A real loopback origin avoids Chromium synthetic-origin LNA denial."""
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>Local PKCE callback</title>")

        def log_message(self, _format, *_args):
            pass  # Authorization codes in the callback URL must never be logged.

    server = ThreadingHTTPServer(("127.0.0.1", 8000), Callback)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def read_password() -> str:
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values["LAB_USER_PASSWORD"]


def main() -> int:
    out = ROOT / "docs/evidence/live"
    out.mkdir(parents=True, exist_ok=True)
    (out / "keycloak-human.json").unlink(missing_ok=True)
    started = datetime.now(timezone.utc)
    password = read_password()
    observations = []
    auth = Authenticator(Settings(mode="live", database_url="postgresql://not-connected/p091", issuer=ISSUER, jwks_url=ISSUER + "/protocol/openid-connect/certs"))
    with callback_listener(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
        for username, tenant, admin in (
            ("nw-employee", "northwind", False), ("nw-admin", "northwind", True),
            ("co-employee", "contoso", False), ("co-admin", "contoso", True),
        ):
            context = browser.new_context()
            page = context.new_page()
            diagnostics = []
            page.on("console", lambda message: diagnostics.append(message.text) if message.type == "error" else None)
            verifier = secrets.token_urlsafe(48)
            state = secrets.token_urlsafe(24)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            query = urlencode({"client_id": "p091-web", "redirect_uri": REDIRECT, "response_type": "code", "scope": "openid read admin", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
            page.goto(ISSUER + "/protocol/openid-connect/auth?" + query)
            page.locator("#username").fill(username)
            page.locator("#password").fill(password)
            page.locator("#kc-login").click()
            page.wait_for_url(REDIRECT + "**", timeout=20000)
            callback = parse_qs(urlparse(page.url).query)
            assert callback.get("state") == [state], "OIDC state did not match"
            assert "code" in callback, "Identity provider did not return an authorization code"
            form = urlencode({"grant_type": "authorization_code", "client_id": "p091-web", "redirect_uri": REDIRECT, "code": callback["code"][0], "code_verifier": verifier})
            # Perform the exchange from the actual registered browser origin,
            # exercising Keycloak CORS as well as the cryptographic PKCE proof.
            try:
                exchanged = page.evaluate("""async ({url, body}) => {
                const response = await fetch(url, {
                    method: 'POST', credentials: 'omit', redirect: 'error',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body,
                });
                return {status: response.status, data: await response.json()};
                }""", {"url": ISSUER + "/protocol/openid-connect/token", "body": form})
            except Exception:
                # Browser CORS diagnostics contain endpoint URLs, not credentials.
                raise RuntimeError("Browser token exchange failed: " + "; ".join(diagnostics)) from None
            assert exchanged["status"] == 200, "Browser PKCE token exchange failed"
            token_response = exchanged["data"]
            access_token = token_response["access_token"]
            principal = auth.verify(access_token)
            assert principal.sub == username
            assert principal.tenant == tenant
            assert principal.actor_type == "human"
            assert "read" in principal.scopes
            assert ("admin" in principal.scopes) == admin, "Admin scope was not restricted by the user's realm role"
            assert "ingest" not in principal.scopes
            observations.append({"test_id": "KC-HUMAN-" + username.upper(), "status": "PASS", "synthetic_subject": principal.sub, "tenant": principal.tenant, "actor_type": principal.actor_type, "effective_scopes": sorted(principal.scopes), "state_verified": True, "pkce_s256_exchange": True, "browser_origin_cors_verified": True, "signature_issuer_audience_expiry_verified": True, "admin_scope_matches_role": True})
            # Verify the app's local logout revokes this actual Keycloak token.
            auth.revoke(access_token)
            try:
                auth.verify(access_token)
            except HTTPException as error:
                assert error.status_code == 401
            else:
                raise AssertionError("Locally revoked human token remained valid")
            observations.append({"test_id": "KC-LOGOUT-" + username.upper(), "status": "PASS", "synthetic_subject": username, "local_process_revocation_rejected": True})
            context.close()
        browser_version = browser.version
        browser.close()
    artifact = {
        "engagement": "P-091", "evidence_id": "P091-KEYCLOAK-HUMAN-" + started.strftime("%Y%m%dT%H%M%SZ"),
        "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python apps/web/check_keycloak.py", "target": ISSUER,
        "browser_version": browser_version, "denominator": len(observations), "PASS": len(observations), "FAIL": 0, "observations": observations,
        "secrets_or_tokens_retained": False,
        "limitation": "Real Keycloak human browser PKCE/CORS + app JWT verifier and per-process revocation tested. A minimal real loopback callback listener uses the registered URI; PostgreSQL/FastAPI live app and provider session revocation not tested by this script.",
    }
    (out / "keycloak-human.json").write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"PASS": len(observations), "denominator": len(observations), "evidence": str(out / "keycloak-human.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
