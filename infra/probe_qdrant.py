#!/usr/bin/env python3
"""Real local Qdrant component checks; payloads contain opaque identity only."""
from __future__ import annotations

import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from bootstrap_live import read_env  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from p091.adapters import Qdrant, embed  # noqa: E402
from p091.config import Settings  # noqa: E402


def main() -> None:
    values = read_env()
    settings = Settings(qdrant_key=values["QDRANT_KEY"])
    client = Qdrant(settings)
    nw_id = "00000000-0000-4000-8000-000000000091"
    co_id = "00000000-0000-4000-8000-000000000092"
    client.index(nw_id, "northwind", "Synthetic Northwind vacation policy canary QD-NW", "1")
    client.index(co_id, "contoso", "Synthetic Contoso vacation policy canary QD-CO", "1")
    results = []
    for tenant, expected, forbidden in [("northwind", nw_id, co_id), ("contoso", co_id, nw_id)]:
        observed = client.query(tenant, "vacation policy")
        passed = expected in observed and forbidden not in observed
        results.append({"test_id": "LIVE-QD-NAMESPACE-" + tenant.upper(), "status": "PASS" if passed else "FAIL",
                        "observed_candidates": observed})
    response = client._request("POST", "/collections/p091_northwind/points/scroll", {"limit": 10, "with_payload": True})
    payloads = [item["payload"] for item in response["result"]["points"]]
    passed = bool(payloads) and all(set(payload) == {"tenant", "doc_id", "version"} for payload in payloads)
    results.append({"test_id": "LIVE-QD-PAYLOAD-MINIMIZATION", "status": "PASS" if passed else "FAIL",
                    "observed_payload_keys": [sorted(payload) for payload in payloads]})
    # Inject a mislabeled candidate into a tenant collection as an authorized
    # local fixture operator. The API filter must independently reject it.
    client._request("PUT", "/collections/p091_northwind/points?wait=true", {"points": [{
        "id": str(uuid5(NAMESPACE_URL, "p091:metadata-probe")), "vector": embed("vacation policy"),
        "payload": {"tenant": "contoso", "doc_id": co_id, "version": "1"},
    }]})
    observed = client.query("northwind", "vacation policy")
    results.append({"test_id": "LIVE-QD-FILTER-POISONED-PAYLOAD", "status": "PASS" if co_id not in observed else "FAIL",
                    "observed_candidates": observed,
                    "limitation": "A forged same-tenant candidate still requires canonical app ACL rechecks; this is only the vector filter test"})
    try:
        Qdrant(dataclasses.replace(settings, qdrant_key="synthetic-invalid-key")).query("northwind", "policy")
        code = 200
    except HTTPException as exc:
        code = exc.status_code
    results.append({"test_id": "LIVE-QD-INVALID-API-KEY", "expected_http_status": 503, "observed_http_status": code,
                    "status": "PASS" if code == 503 else "FAIL"})
    client.delete(nw_id, "northwind")
    observed = client.query("northwind", "vacation policy")
    results.append({"test_id": "LIVE-QD-DELETE", "status": "PASS" if nw_id not in observed else "FAIL",
                    "observed_candidates": observed})
    artifact = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "command": ".venv/bin/python infra/probe_qdrant.py", "component": "Qdrant1.20.1",
        "configuration": "Real standalone Docker Qdrant with generated local API key; synthetic ephemeral corpus",
        "boundary": "Actual application Qdrant adapter -> real local Qdrant REST API",
        "limitation": "Not full Compose/assistant or source-backed authorization integration; deterministic hash embeddings only",
        "results": results,
    }
    output = ROOT / "docs/evidence/qdrant-component.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n")
    passed = sum(item["status"] == "PASS" for item in results)
    print(f"Real Qdrant component checks: {passed}/{len(results)} PASS; sanitized evidence {output.relative_to(ROOT)}")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
