"""Probe current application adapters against a disposable real OpenFGA service.

Run from the repository root with `.venv/bin/python infra/probe_openfga_adapters.py`.
Only this script's newly created container is stopped/removed. This does not start
PostgreSQL or claim that the complete application/Compose stack was validated.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from p091.adapters import OpenFGA  # noqa: E402
from p091.config import Settings  # noqa: E402

IMAGE = "openfga/openfga:v1.22.1"
CONTAINER = "p091-fga-adapter-probe"
URL = "http://127.0.0.1:8793"
EVIDENCE = ROOT / "docs/evidence/openfga-adapters.json"


def docker(*arguments: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        environment.pop(name, None)
    return subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", *arguments],
        env=environment, capture_output=True, text=True, timeout=timeout, check=False,
    )


def run() -> int:
    ids = [f"FGA-ADAPTER-{number:03d}" for number in range(1, 10)]
    report: dict[str, Any] = {
        "evidence_id": "E-OPENFGA-APP-ADAPTERS",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": ".venv/bin/python infra/probe_openfga_adapters.py",
        "classification": "measured standalone real OpenFGA service; application HTTP adapters",
        "image": IMAGE, "endpoint": URL, "datastore": "disposable in-memory",
        "checks": [{"test_id": test_id, "status": "NOT_TESTED"} for test_id in ids],
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__).resolve(), ROOT / "p091/adapters.py", ROOT / "p091/config.py", ROOT / "infra/openfga/model.json")
        },
        "limitations": [
            "Standalone OpenFGA memory datastore only; PostgreSQL/Compose stack was not exercised.",
            "Synthetic tuple users/resources only; no human Keycloak identity flow in this probe.",
            "No Nextcloud source permissions, Qdrant retrieval, or complete app endpoint path tested.",
            "Group usersets are deliberately omitted by exact direct-tuple reconciliation reads.",
        ],
        "credentials_retained": False, "container_removed": False,
    }
    owned_id = ""
    env_path: Path | None = None

    def record(number: int, name: str, expected: Any, observed: Any) -> None:
        report["checks"][number - 1] = {
            "test_id": ids[number - 1], "name": name,
            "expected": expected, "observed": observed,
            "status": "PASS" if observed == expected else "FAIL",
        }

    try:
        metadata = docker("image", "inspect", IMAGE, "--format", "{{json .}}")
        if metadata.returncode:
            raise RuntimeError("Pinned OpenFGA image not available in the local daemon")
        image = json.loads(metadata.stdout)
        report["image_id"] = image["Id"]
        report["image_repository_digests"] = image.get("RepoDigests", [])
        (ROOT / "work").mkdir(exist_ok=True)
        descriptor, filename = tempfile.mkstemp(prefix="fga-adapter-", suffix=".env", dir=ROOT / "work")
        env_path = Path(filename)
        token = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w") as environment:
            environment.write(
                "OPENFGA_DATASTORE_ENGINE=memory\n"
                "OPENFGA_AUTHN_METHOD=preshared\n"
                f"OPENFGA_AUTHN_PRESHARED_KEYS={token}\n"
                "OPENFGA_PLAYGROUND_ENABLED=false\n"
                "OPENFGA_LOG_LEVEL=error\n"
            )
        started = docker(
            "run", "--detach", "--name", CONTAINER,
            "--publish", "127.0.0.1:8793:8080", "--env-file", str(env_path), IMAGE, "run",
        )
        if started.returncode:
            raise RuntimeError("Cannot create own OpenFGA probe container; existing containers untouched")
        candidate_id = started.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", candidate_id):
            raise RuntimeError("Container ownership ID not returned")
        owned_id = candidate_id
        with httpx.Client(timeout=3, follow_redirects=False) as client:
            deadline = time.monotonic() + 40
            while True:
                try:
                    if client.get(URL + "/healthz").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Own OpenFGA container did not become healthy within 40 seconds")
                time.sleep(0.25)

            unauthorized = client.post(URL + "/stores", json={"name": "unauthenticated-attempt"})
            record(1, "Preshared authentication rejects unauthenticated mutation", 401, unauthorized.status_code)
            headers = {"Authorization": "Bearer " + token}
            store = client.post(URL + "/stores", json={"name": "p091-adapter-probe"}, headers=headers)
            store.raise_for_status()
            store_id = store.json()["id"]
            model_body = json.loads((ROOT / "infra/openfga/model.json").read_text())
            model = client.post(URL + f"/stores/{store_id}/authorization-models", json=model_body, headers=headers)
            model.raise_for_status()
            model_id = model.json()["authorization_model_id"]
            report["model_accepted"] = True
            config = Settings(
                mode="offline", openfga_url=URL, fga_store_id=store_id,
                fga_model_id=model_id, fga_token=token,
            )
            adapter = OpenFGA(config, client)
            document = "synthetic-adapter-doc"
            alice = {"user": "user:nw-employee", "relation": "viewer", "object": f"document:{document}"}
            manager = {"user": "user:nw-manager", "relation": "viewer", "object": f"document:{document}"}
            record(2, "Absent relationship denies current adapter check", False, adapter.check("nw-employee", document))

            adapter.write([alice], [])
            record(3, "Adapter write grants exactly intended principal", {"employee": True, "manager": False}, {
                "employee": adapter.check("nw-employee", document), "manager": adapter.check("nw-manager", document),
            })
            record(4, "Adapter exact tuple read sees persisted direct grant", ["user:nw-employee"], sorted(adapter.read_document_viewers(document)))

            # Reconcile canonical desired direct viewers exactly as the app does.
            desired = {"user:nw-manager"}
            current = adapter.read_document_viewers(document)
            writes = [{"user": user, "relation": "viewer", "object": f"document:{document}"} for user in sorted(desired - current)]
            deletes = [{"user": user, "relation": "viewer", "object": f"document:{document}"} for user in sorted(current - desired)]
            adapter.write(writes, deletes)
            record(5, "Direct reconciliation removes old grant and adds current grant", {
                "employee": False, "manager": True, "direct_viewers": ["user:nw-manager"],
            }, {
                "employee": adapter.check("nw-employee", document), "manager": adapter.check("nw-manager", document),
                "direct_viewers": sorted(adapter.read_document_viewers(document)),
            })

            group_viewer = {"user": "group:synthetic-hr#member", "relation": "viewer", "object": f"document:{document}"}
            membership = {"user": "user:nw-employee", "relation": "member", "object": "group:synthetic-hr"}
            adapter.write([group_viewer, membership], [])
            observed_group = {
                "inherited_employee_allowed": adapter.check("nw-employee", document),
                "direct_viewers": sorted(adapter.read_document_viewers(document)),
            }
            adapter.write([], [group_viewer, membership])
            observed_group["employee_after_group_removal"] = adapter.check("nw-employee", document)
            record(6, "Exact tuple read excludes inherited users; group removal revokes inheritance", {
                "inherited_employee_allowed": True, "direct_viewers": ["user:nw-manager"], "employee_after_group_removal": False,
            }, observed_group)

            adapter.write([], [manager])
            record(7, "Removing direct viewer immediately denies and empties read set", {"manager": False, "direct_viewers": []}, {
                "manager": adapter.check("nw-manager", document), "direct_viewers": sorted(adapter.read_document_viewers(document)),
            })

            bad_config = Settings(mode="offline", openfga_url=URL, fga_store_id=store_id, fga_model_id=model_id, fga_token="deliberately-invalid-synthetic")
            bad_adapter = OpenFGA(bad_config, client)
            wrong_credential_status = 200
            try:
                bad_adapter.check("nw-employee", document)
            except HTTPException as error:
                wrong_credential_status = error.status_code
            record(8, "Invalid service credential causes sanitized fail-closed adapter error", 503, wrong_credential_status)

            stopped = docker("stop", "--time", "2", owned_id)
            if stopped.returncode:
                raise RuntimeError("Could not stop own container for outage probe")
            outage_status = 200
            try:
                adapter.check("nw-manager", document)
            except HTTPException as error:
                outage_status = error.status_code
            record(9, "Real service outage denies check and fails health", {"status": 503, "health": False}, {
                "status": outage_status, "health": adapter.health(),
            })
    except Exception as error:
        # Store no raw HTTP response, environment, credentials, or traceback.
        report["blocker"] = {"type": type(error).__name__, "message": str(error) if isinstance(error, RuntimeError) else "Probe could not complete; see remaining NOT_TESTED rows"}
    finally:
        if owned_id:
            removed = docker("rm", "--force", owned_id)
            report["container_removed"] = removed.returncode == 0
        if env_path is not None:
            env_path.unlink(missing_ok=True)
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["totals"] = {
            status: sum(check["status"] == status for check in report["checks"])
            for status in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_TESTED", "NOT_APPLICABLE")
        }
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"evidence": str(EVIDENCE.relative_to(ROOT)), "totals": report["totals"], "container_removed": report["container_removed"], "blocker": report.get("blocker")}, indent=2))
    return 0 if report["totals"]["PASS"] == len(ids) and report["container_removed"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
