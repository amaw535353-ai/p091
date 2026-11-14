#!/usr/bin/env python3
"""Seed only the owned localhost Nextcloud with synthetic users/documents/shares.

Application ACLs + OpenFGA remain authorization authorities for the assistant.
This creates realistic Nextcloud shares; it does NOT claim generic bidirectional
Nextcloud ACL synchronization. Never print passwords or HTTP error bodies.
"""
from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bootstrap_live import read_env

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8083"


def call(method: str, path: str, user: str, password: str, data: bytes | None = None,
         *, content_type: str = "application/x-www-form-urlencoded", expected: tuple[int, ...] = (200,)) -> bytes:
    credentials = base64.b64encode((user + ":" + password).encode()).decode()
    request = urllib.request.Request(BASE + path, method=method, data=data,
                                    headers={"Authorization": "Basic " + credentials,
                                             "OCS-APIRequest": "true", "Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in expected:
                raise RuntimeError(f"Unexpected localhost Nextcloud HTTP {response.status}")
            return response.read(1024 * 1024)
    except urllib.error.HTTPError as exc:
        if exc.code in expected:
            return b""
        raise RuntimeError(f"Local Nextcloud returned HTTP {exc.code}; details suppressed") from None


def ocs(method: str, path: str, user: str, password: str, fields: dict[str, str] | None = None,
        *, allowed: tuple[int, ...] = (100, 200)) -> dict:
    separator = "&" if "?" in path else "?"
    raw = call(method, path + separator + "format=json", user, password,
               urllib.parse.urlencode(fields).encode() if fields is not None else None)
    response = json.loads(raw)["ocs"]
    status = int(response["meta"]["statuscode"])
    if status not in allowed:
        raise RuntimeError(f"Local Nextcloud OCS status {status}; response content suppressed")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate fixture paths without contacting Nextcloud")
    args = parser.parse_args()
    values = read_env()
    fixture = json.loads((ROOT / "fixtures/synthetic-data/seed.json").read_text())
    documents = fixture["documents"]
    for doc in documents:
        path = doc.get("source_path") or f"p091/{doc['tenant']}/{doc['id']}.txt"
        if not path.startswith("p091/") or ".." in path or any(c in path for c in ["?", "#", "\\"]):
            raise SystemExit("Unsafe source path in synthetic fixture")
    if args.dry_run:
        print(f"Validated {len(documents)} local synthetic source paths; no network request performed.")
        return
    admin, admin_password = "lab-admin", values["NEXTCLOUD_ADMIN_PASSWORD"]
    provisioning = "/ocs/v1.php/cloud"
    existing_users = ocs("GET", provisioning + "/users", admin, admin_password)["data"]["users"]
    all_users = [("connector", values["NEXTCLOUD_CONNECTOR_PASSWORD"])]
    all_users += [(user["id"], values["LAB_USER_PASSWORD"]) for user in fixture["users"]
                  if user.get("actor_type", "human") == "human"]
    for uid, password in all_users:
        if uid not in existing_users:
            ocs("POST", provisioning + "/users", admin, admin_password, {"userid": uid, "password": password})
    group_names = {"tenant-" + user["tenant"] for user in fixture["users"]}
    group_names.update(group for user in fixture["users"] for group in user.get("groups", []))
    existing_groups = ocs("GET", provisioning + "/groups", admin, admin_password)["data"]["groups"]
    for group in sorted(group_names):
        if group not in existing_groups:
            ocs("POST", provisioning + "/groups", admin, admin_password, {"groupid": group})
    for user in fixture["users"]:
        if user.get("actor_type", "human") != "human":
            continue
        uid = urllib.parse.quote(user["id"], safe="")
        memberships = ocs("GET", f"{provisioning}/users/{uid}/groups", admin, admin_password)["data"]["groups"]
        requested = ["tenant-" + user["tenant"]] + [group for group in user.get("groups", [])]
        for group in requested:
            if group not in memberships:
                ocs("POST", f"{provisioning}/users/{uid}/groups", admin, admin_password, {"groupid": group})
    connector_password = values["NEXTCLOUD_CONNECTOR_PASSWORD"]
    dav_base = "/remote.php/dav/files/connector/"
    directories = {"p091"} | {"p091/" + doc["tenant"] for doc in documents}
    for directory in sorted(directories):
        call("MKCOL", dav_base + urllib.parse.quote(directory, safe="/"), "connector", connector_password,
             expected=(201, 405))
    shares_base = "/ocs/v2.php/apps/files_sharing/api/v1/shares"
    current_shares = ocs("GET", shares_base, "connector", connector_password)["data"]
    existing_shares = {(item.get("path"), str(item.get("share_type")), item.get("share_with")) for item in current_shares}
    seeded, etags = 0, {}
    for doc in documents:
        if doc.get("deleted"):
            continue
        path = doc.get("source_path") or f"p091/{doc['tenant']}/{doc['id']}.txt"
        # Writes are explicit seed operations to disposable local data only.
        call("PUT", dav_base + urllib.parse.quote(path, safe="/"), "connector", connector_password,
             doc["body"].encode(), content_type="text/plain; charset=utf-8", expected=(201, 204))
        recipient, share_type = None, "1"
        if doc.get("visibility") in ("public", "tenant"):
            recipient = "tenant-" + doc["tenant"]
        elif doc.get("visibility") in ("group", "department") and doc.get("group"):
            recipient = doc["group"]
        if recipient and ("/" + path, share_type, recipient) not in existing_shares:
            ocs("POST", shares_base, "connector", connector_password,
                {"path": "/" + path, "shareType": share_type, "shareWith": recipient, "permissions": "1"})
        individual = set(doc.get("readers", [])) | ({doc["owner"]} if doc.get("owner") else set())
        for reader in sorted(individual):
            if ("/" + path, "0", reader) not in existing_shares:
                ocs("POST", shares_base, "connector", connector_password,
                    {"path": "/" + path, "shareType": "0", "shareWith": reader, "permissions": "1"})
        # Record harmless IDs/version only; caller binds each ETag to metadata
        # through an authenticated ingestion command, never by trusting a file.
        credentials = base64.b64encode(("connector:" + connector_password).encode()).decode()
        request = urllib.request.Request(BASE + dav_base + urllib.parse.quote(path, safe="/"), method="HEAD",
                                         headers={"Authorization": "Basic " + credentials})
        with urllib.request.urlopen(request, timeout=10) as response:
            etags[doc["id"]] = {"source_path": path, "version": response.headers.get("ETag", "")}
        seeded += 1
    artifact = ROOT / "work/nextcloud-versions.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(etags, indent=2) + "\n")
    print(f"Seeded {seeded} synthetic documents and realistic Nextcloud shares.")
    print("ETags saved to work/nextcloud-versions.json. Reindex through the service identity before enabling reads.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        raise SystemExit(f"Nextcloud seed stopped: {type(exc).__name__}. No credential or response body printed.") from None
