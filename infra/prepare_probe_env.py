#!/usr/bin/env python3
"""Write minimal local container env files; print neither passwords nor tokens."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap_live import read_env  # noqa: E402


def main() -> None:
    values = read_env()
    destination = ROOT / "work"
    destination.mkdir(exist_ok=True)
    files = {
        "keycloak-probe.env": {
            "LAB_USER_PASSWORD": values["LAB_USER_PASSWORD"],
            "INDEXER_CLIENT_SECRET": values["INDEXER_CLIENT_SECRET"],
            "CONTOSO_INDEXER_CLIENT_SECRET": values["CONTOSO_INDEXER_CLIENT_SECRET"],
            "KC_DB": "dev-file", "KC_HEALTH_ENABLED": "true",
            "KC_BOOTSTRAP_ADMIN_USERNAME": "lab-admin",
            "KC_BOOTSTRAP_ADMIN_PASSWORD": values["KEYCLOAK_ADMIN_PASSWORD"],
        },
        "qdrant-probe.env": {"QDRANT__SERVICE__API_KEY": values["QDRANT_KEY"], "QDRANT__TELEMETRY_DISABLED": "true"},
    }
    for filename, content in files.items():
        fd = os.open(destination / filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.writelines(key + "=" + value + "\n" for key, value in content.items())
    print("Prepared minimal container probe env files in ignored work/; credential values omitted.")


if __name__ == "__main__":
    main()
