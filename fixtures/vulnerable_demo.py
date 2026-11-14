"""Explicitly vulnerable local fixture. Not imported by the application.

Run only against synthetic seed data using the required opt-in flag. This
demonstrates a known missing authorization check, not a finding in the API.
"""
import argparse
import json
from pathlib import Path


def unsafe_lookup(documents: list[dict], needle: str, *, allow_vulnerable_fixture: bool = False) -> list[dict]:
    if not allow_vulnerable_fixture:
        raise RuntimeError("Vulnerable fixture disabled; explicit opt-in required")
    # Deliberately missing identity, tenant and ACL checks. Local fixture ONLY.
    return [doc for doc in documents if needle.casefold() in doc["body"].casefold()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-vulnerable-fixture", action="store_true", required=True)
    parser.parse_args()
    documents = json.loads((Path(__file__).parent / "synthetic-data/seed.json").read_text())["documents"]
    results = unsafe_lookup(documents, "CO_FINANCE_CANARY", allow_vulnerable_fixture=True)
    print(json.dumps({"fixture": "INTENTIONALLY_VULNERABLE", "cross_tenant_results": len(results), "raw_content_omitted": True}))
