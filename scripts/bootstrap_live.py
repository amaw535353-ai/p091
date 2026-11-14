#!/usr/bin/env python3
"""Local-only configuration: generated secrets, Keycloak realm and OpenFGA seed.

No process environment or credentials are printed. `configure` intentionally
uses only localhost OpenFGA, never a URL supplied by a document or command line.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
GENERATED_REALM = ROOT / "infra/keycloak/p091-realm.json"
SECRET_NAMES = (
    "POSTGRES_PASSWORD", "APP_DATABASE_PASSWORD", "FGA_DATABASE_PASSWORD",
    "KEYCLOAK_DATABASE_PASSWORD", "NEXTCLOUD_DATABASE_PASSWORD",
    "KEYCLOAK_ADMIN_PASSWORD", "LAB_USER_PASSWORD", "INDEXER_CLIENT_SECRET",
    "CONTOSO_INDEXER_CLIENT_SECRET", "FGA_TOKEN", "QDRANT_KEY",
    "NEXTCLOUD_ADMIN_PASSWORD", "NEXTCLOUD_CONNECTOR_PASSWORD",
)


def read_env() -> dict[str, str]:
    if not ENV.exists():
        return {}
    result: dict[str, str] = {}
    for line in ENV.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def write_env(values: dict[str, str]) -> None:
    # Refuse multiline/dangerous shell-like values; this file is a dotenv file,
    # not executable shell and scripts never source it.
    for key, value in values.items():
        if not key.replace("_", "").isalnum() or "\n" in value or "\r" in value:
            raise ValueError("Unsafe dotenv value")
    temporary = ENV.with_name(".env.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write("# GENERATED LOCAL SYNTHETIC LAB SECRETS — NEVER COMMIT\n")
        stream.writelines(f"{key}={value}\n" for key, value in sorted(values.items()))
    temporary.replace(ENV)
    ENV.chmod(0o600)


def mapper(name: str, protocol_mapper: str, config: dict[str, str]) -> dict:
    return {"name": name, "protocol": "openid-connect", "protocolMapper": protocol_mapper,
            "consentRequired": False, "config": config}


def common_mappers() -> list[dict]:
    return [
        mapper("subject", "oidc-sub-mapper", {"access.token.claim": "true", "introspection.token.claim": "true"}),
        mapper("audience", "oidc-audience-mapper", {
            "included.custom.audience": "p091-api", "access.token.claim": "true", "id.token.claim": "false"}),
        mapper("tenant", "oidc-usermodel-attribute-mapper", {
            "user.attribute": "tenant", "claim.name": "tenant", "jsonType.label": "String",
            "access.token.claim": "true", "id.token.claim": "true", "userinfo.token.claim": "true"}),
        mapper("actor_type", "oidc-usermodel-attribute-mapper", {
            "user.attribute": "actor_type", "claim.name": "actor_type", "jsonType.label": "String",
            "access.token.claim": "true", "id.token.claim": "true", "userinfo.token.claim": "true"}),
    ]


def realm(values: dict[str, str]) -> dict:
    users = []
    for prefix, tenant in [("nw", "northwind"), ("co", "contoso")]:
        for role in ["employee", "manager", "admin"]:
            uid = f"{prefix}-{role}"
            users.append({
                "id": uid, "username": uid, "enabled": True, "emailVerified": True,
                "firstName": "Synthetic", "lastName": role.title(), "email": uid + "@" + tenant + ".example.invalid",
                "attributes": {"tenant": [tenant], "actor_type": ["human"]},
                "credentials": [{"type": "password", "value": values["LAB_USER_PASSWORD"], "temporary": False}],
                "realmRoles": ["read"] + (["admin"] if role == "admin" else []),
                "requiredActions": [],
            })
    clients = [{
        "clientId": "p091-web", "enabled": True, "protocol": "openid-connect", "publicClient": True,
        "standardFlowEnabled": True, "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False, "fullScopeAllowed": False,
        "redirectUris": ["http://localhost:8000/", "http://127.0.0.1:8000/"],
        "webOrigins": ["http://localhost:8000", "http://127.0.0.1:8000"],
        "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": "http://localhost:8000/"},
        "defaultClientScopes": ["read"], "optionalClientScopes": ["admin"],
        "protocolMappers": common_mappers(),
    }]
    for client_id, tenant, uid, secret_name in [
        ("indexer", "northwind", "nw-indexer", "INDEXER_CLIENT_SECRET"),
        ("contoso-indexer", "contoso", "co-indexer", "CONTOSO_INDEXER_CLIENT_SECRET"),
    ]:
        clients.append({
            "clientId": client_id, "enabled": True, "protocol": "openid-connect", "publicClient": False,
            "secret": values[secret_name], "standardFlowEnabled": False, "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False, "serviceAccountsEnabled": True, "fullScopeAllowed": False,
            "defaultClientScopes": ["ingest"], "optionalClientScopes": [], "protocolMappers": common_mappers(),
        })
        users.append({
            "id": uid, "username": "service-account-" + client_id, "enabled": True,
            "serviceAccountClientId": client_id,
            "attributes": {"tenant": [tenant], "actor_type": ["service"]}, "realmRoles": ["ingest"],
        })
    scopes = [{"name": name, "protocol": "openid-connect", "attributes": {"include.in.token.scope": "true"}}
              for name in ["read", "admin", "ingest"]]
    return {
        "realm": "p091", "enabled": True, "displayName": "P-091 Synthetic Security Lab",
        "sslRequired": "none", "registrationAllowed": False, "resetPasswordAllowed": False,
        "editUsernameAllowed": False, "accessTokenLifespan": 300, "ssoSessionIdleTimeout": 900,
        "bruteForceProtected": True, "loginWithEmailAllowed": False, "duplicateEmailsAllowed": True,
        "roles": {"realm": [{"name": name} for name in ["read", "admin", "ingest"]]},
        "clientScopes": scopes,
        "scopeMappings": [{"clientScope": name, "roles": [name]} for name in ["read", "admin", "ingest"]],
        "clients": clients, "users": users,
    }


def prepare() -> None:
    values = read_env()
    for name in SECRET_NAMES:
        if not values.get(name) or values[name].startswith("CHANGE"):
            values[name] = secrets.token_hex(24)
    values.setdefault("FGA_STORE_ID", "")
    values.setdefault("FGA_MODEL_ID", "")
    values.setdefault("NEXTCLOUD_ENABLED", "false")
    write_env(values)
    GENERATED_REALM.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(GENERATED_REALM, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    with os.fdopen(fd, "w") as stream:
        json.dump(realm({name: "${" + name + "}" for name in SECRET_NAMES}), stream, indent=2)
        stream.write("\n")
    GENERATED_REALM.chmod(0o644)
    print("Prepared .env and Keycloak realm template (secret values remain only in .env).")


def request(path: str, token: str, data: dict | None = None) -> dict:
    req = urllib.request.Request("http://127.0.0.1:8082" + path,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read(1024 * 1024)
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # Service error body can contain submitted content: never print it.
        raise RuntimeError(f"Local OpenFGA returned HTTP {exc.code}; no credentials printed") from None


def configure() -> None:
    values = read_env()
    if not values.get("FGA_TOKEN"):
        raise SystemExit("Run prepare first")
    token = values["FGA_TOKEN"]
    store_id = values.get("FGA_STORE_ID", "")
    if store_id:
        try:
            request("/stores/" + store_id, token)
        except RuntimeError:
            raise SystemExit("Saved OpenFGA store unavailable. Restore service or reset only this lab volume and rerun prepare.") from None
    else:
        store_id = request("/stores", token, {"name": "p091-local-synthetic"})["id"]
        values["FGA_STORE_ID"] = store_id
        write_env(values)
    model = json.loads((ROOT / "infra/openfga/model.json").read_text())
    if not values.get("FGA_MODEL_ID"):
        model_id = request(f"/stores/{store_id}/authorization-models", token, model)["authorization_model_id"]
        values["FGA_MODEL_ID"] = model_id
        write_env(values)
    else:
        model_id = values["FGA_MODEL_ID"]
        request(f"/stores/{store_id}/authorization-models/{model_id}", token)
    if values.get("FGA_SEEDED") == "true":
        print("OpenFGA store/model already seeded; existing permission changes preserved.")
        return
    # App's effective policy remains authoritative together with FGA. Seed direct
    # viewer tuples for each currently authorized human to avoid treating claims
    # or untrusted vector/source metadata as authorization.
    fixture = json.loads((ROOT / "fixtures/synthetic-data/seed.json").read_text())
    users, docs = fixture["users"], fixture["documents"]
    tuples = []
    for user in users:
        if user.get("actor_type", "human") != "human":
            continue
        tuples.append({"user": "user:" + user["id"], "relation": "member", "object": "tenant:" + user["tenant"]})
        for group in user.get("groups", []):
            tuples.append({"user": "user:" + user["id"], "relation": "member", "object": f"group:{group}"})
            tuples.append({"user": "tenant:" + user["tenant"], "relation": "tenant", "object": f"group:{group}"})
        department = user["tenant"] + "-" + user["department"].casefold().replace(" ", "-")
        tuples.append({"user": "user:" + user["id"], "relation": "member", "object": "department:" + department})
        tuples.append({"user": "tenant:" + user["tenant"], "relation": "tenant", "object": "department:" + department})
        if user.get("admin", False):
            tuples.append({"user": "user:" + user["id"], "relation": "administrator", "object": "tenant:" + user["tenant"]})
    for doc in docs:
        tuples.append({"user": "tenant:" + doc["tenant"], "relation": "tenant", "object": "document:" + doc["id"]})
        for user in users:
            if user.get("actor_type", "human") != "human" or user["tenant"] != doc["tenant"] or doc.get("deleted"):
                continue
            allowed = (user.get("admin", False) or doc.get("owner") == user["id"] or user["id"] in doc.get("readers", [])
                       or doc.get("visibility") in ("tenant", "public")
                       or (doc.get("visibility") in ("group", "department") and doc.get("group") in user.get("groups", [])))
            if allowed:
                tuples.append({"user": "user:" + user["id"], "relation": "viewer", "object": "document:" + doc["id"]})
    # Read current tuples and add only missing ones; do not silently overwrite
    # deliberate revocations on rerun. This is an initial seed command.
    existing: set[tuple[str, str, str]] = set()
    continuation = ""
    while True:
        response = request(f"/stores/{store_id}/read", token,
                           {"page_size": 100, **({"continuation_token": continuation} if continuation else {})})
        for item in response.get("tuples", []):
            key = item["key"]
            existing.add((key["user"], key["relation"], key["object"]))
        continuation = response.get("continuation_token", "")
        if not continuation:
            break
    tuples = list({(item["user"], item["relation"], item["object"]): item for item in tuples}.values())
    additions = [item for item in tuples if (item["user"], item["relation"], item["object"]) not in existing]
    for offset in range(0, len(additions), 100):
        request(f"/stores/{store_id}/write", token,
                {"authorization_model_id": model_id, "writes": {"tuple_keys": additions[offset:offset + 100]}})
    values["FGA_SEEDED"] = "true"
    write_env(values)
    print(f"Configured local OpenFGA store/model and {len(additions)} new synthetic tuples (IDs saved to .env).")


def index() -> None:
    """Use real tenant-scoped workload tokens; never impersonate a human user."""
    values = read_env()
    fixture = json.loads((ROOT / "fixtures/synthetic-data/seed.json").read_text())
    indexed = 0
    for client_id, tenant, secret_name in [
        ("indexer", "northwind", "INDEXER_CLIENT_SECRET"),
        ("contoso-indexer", "contoso", "CONTOSO_INDEXER_CLIENT_SECRET"),
    ]:
        request = urllib.request.Request(
            "http://127.0.0.1:8081/realms/p091/protocol/openid-connect/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id,
                                         "client_secret": values[secret_name]}).encode(),
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            token = json.load(response)["access_token"]
        for doc in fixture["documents"]:
            if doc["tenant"] != tenant or doc.get("deleted"):
                continue
            # The local fixture contains UUID document IDs; percent encoding is
            # retained so the request path cannot acquire a query/host component.
            request = urllib.request.Request(
                "http://127.0.0.1:8000/ingestion/reindex/" + urllib.parse.quote(doc["id"], safe=""),
                method="POST", headers={"Authorization": "Bearer " + token},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    result = json.load(response)
                if result.get("state") != "synced":
                    raise RuntimeError("Local ingestion did not report synced")
                indexed += 1
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Local workload ingestion HTTP {exc.code}; response content suppressed") from None
    print(f"Indexed {indexed} synthetic documents through tenant-scoped workload credentials (tokens omitted).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "configure", "index"], nargs="?", default="prepare")
    args = parser.parse_args()
    try:
        {"prepare": prepare, "configure": configure, "index": index}[args.action]()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        # Exception values from secrets-bearing network operations are omitted.
        raise SystemExit(f"Bootstrap stopped: {type(exc).__name__}. Check local service health and documented setup.") from None


if __name__ == "__main__":
    main()
