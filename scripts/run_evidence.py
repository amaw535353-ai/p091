#!/usr/bin/env python3
"""Run observed pytest cases and retain a sanitized, hashed evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("PASS", "FAIL", "INCONCLUSIVE", "NOT_TESTED", "NOT_APPLICABLE")


def sanitize(value: str) -> str:
    value = re.sub(r"\x1b\[[0-9;]*m", "", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED_JWT]", value)
    value = re.sub(r"(?i)(bearer\s+)[^\s\"'<>]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:client_secret|access_token|refresh_token|password)\s*[=:]\s*)[^\s,<>]+", r"\1[REDACTED]", value)
    return value


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def versions() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for package in ("fastapi", "pydantic", "PyJWT", "httpx", "cryptography", "pytest", "psycopg", "uvicorn"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not installed"
    return result


def junit_records(path: Path, evidence_id: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    tree = ET.fromstring(path.read_text())
    records = []
    for case in tree.iter("testcase"):
        status = "PASS"
        if case.find("failure") is not None:
            status = "FAIL"
        elif case.find("error") is not None:
            status = "INCONCLUSIVE"
        elif case.find("skipped") is not None:
            status = "NOT_TESTED"
        node = f"{case.get('classname', '')}::{case.get('name', '')}"
        records.append({
            "test_id": "TEST-" + hashlib.sha256(node.encode()).hexdigest()[:10],
            "pytest_node_id": node,
            "status": status,
            "duration_seconds": case.get("time", "0"),
            "evidence_id": evidence_id,
            "measurement": "deterministic offline API/unit test; live services are not implied",
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/latest")
    parser.add_argument("pytest_args", nargs="*", default=["tests"])
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A collection/import failure must never reuse a previous run's JUnit cases.
    for filename in ("junit.xml", "manifest.json", "pytest.log"):
        (out / filename).unlink(missing_ok=True)
    started = datetime.now(timezone.utc)
    evidence_id = "P091-" + started.strftime("%Y%m%dT%H%M%S%fZ")
    with tempfile.TemporaryDirectory(prefix="p091-evidence-") as temporary:
        raw_xml = Path(temporary) / "junit.xml"
        command = [sys.executable, "-m", "pytest", *(args.pytest_args or ["tests"]), "-q", f"--junitxml={raw_xml}"]
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        output = sanitize(result.stdout)
        (out / "pytest.log").write_text(output)
        if raw_xml.exists():
            (out / "junit.xml").write_text(sanitize(raw_xml.read_text()))
    records = junit_records(out / "junit.xml", evidence_id)
    totals = {status: sum(record["status"] == status for record in records) for status in STATUSES}
    commit_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    source = {}
    for directory in ("p091", "tests", "fixtures", "apps/web", "infra", "scripts"):
        for path in sorted((ROOT / directory).rglob("*")):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
                and ".generated." not in path.name
                and not path.name.startswith(".env")
            ):
                source[str(path.relative_to(ROOT))] = file_hash(path)
    for filename in ("requirements.lock", "Makefile", "pyproject.toml", "Dockerfile"):
        if (ROOT / filename).is_file():
            source[filename] = file_hash(ROOT / filename)
    manifest = {
        "engagement": "P-091",
        "evidence_id": evidence_id,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-m", "pytest", *(args.pytest_args or ["tests"]), "-q", "--junitxml=<temporary>/junit.xml"],
        "working_directory": str(ROOT),
        "exit_code": result.returncode,
        "git_commit": commit_result.stdout.strip() if commit_result.returncode == 0 else None,
        "git_note": "No Git commit available" if commit_result.returncode else "Source hashes below identify this execution snapshot",
        "configuration": {"mode": "offline", "data": "synthetic", "external_llm": "disabled", "live_integrations": "not exercised by this suite"},
        "versions": versions(),
        "denominator": len(records),
        "totals": totals,
        "test_records": records,
        "source_sha256": source,
        "artifacts_sha256": {path.name: file_hash(path) for path in (out / "pytest.log", out / "junit.xml") if path.exists()},
        "interpretation": "PASS means the defined assertion held in this run; it does not mean a vulnerability was discovered or universal security was proven.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(output, end="")
    print(json.dumps({"evidence_id": evidence_id, "denominator": len(records), **totals, "manifest": str(out / "manifest.json")}, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
