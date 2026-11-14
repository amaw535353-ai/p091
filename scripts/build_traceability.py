"""Build per-observation coverage from retained evidence, never expected totals."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
COLUMNS = ["Engagement ID", "Risk ID", "Supporting P-ID", "Tool ID", "Architecture boundary", "Abuse case", "Requirement/control", "Preconditions", "Expected authorized behavior", "Expected denied behavior", "Test ID", "Evidence ID", "Observed result", "Status", "Remediation", "Retest", "Limitation", "Competency gate"]


def mapping(name: str) -> tuple[str, str, str, str]:
    low = name.lower()
    if any(s in low for s in ["jwt", "auth", "identity", "scope", "token", "signature", "claims", "login", "logout", "workload", "service", "issuer", "jwks"]):
        return "#1", "P-001/P-010", "#21 Keycloak / local RSA fixture", "Identity / API"
    if any(s in low for s in ["injection", "inject", "prompt", "markup", "xss"]):
        return "#5/#4", "P-022/P-029", "#3 Promptfoo / extractive reference", "Untrusted source / response"
    if any(s in low for s in ["qdrant", "vector", "embed", "ranking", "metadata"]):
        return "#35/#13", "P-032/P-034/P-039", "#28 Qdrant", "Vector candidates / canonical metadata"
    if any(s in low for s in ["nextcloud", "source", "size", "traversal", "content_type", "path"]):
        return "#3/#17", "P-031/P-037", "#143 Nextcloud / fixture", "Source / ingestion"
    return "#3/#35/#4", "P-017/P-029/P-031/P-037/P-040", "#22 OpenFGA / SQL policy", "API / canonical permissions"


def row(name: str, status: str, evidence: str, observation: str, limitation: str = "Deterministic synthetic case only; see evidence configuration") -> dict:
    risk, project, tool, boundary = mapping(name)
    standards = "ASVS v5.0.0-8.2.2/8.3.1/8.3.2/8.4.1; AISVS1.0 5.2.1/5.2.2/5.2.4"
    if risk == "#1":
        standards = "ASVS v5.0.0-8.2.1/9.2.1/9.2.3; AISVS1.0 5.1.2 (partial)"
    elif "#13" in risk:
        standards = "AISVS1.0 8.1.1/8.1.3; ASVS v5.0.0-8.4.1; threat AML.T0070"
    elif "#5" in risk:
        standards += "; threat AML.T0051.001; no AISVS model hierarchy claim"
    return dict(zip(COLUMNS, ["P-091", risk, project, tool, boundary, name,
        "Current permission/provenance before egress; " + standards,
        "Owned disposable lab; exact retained evidence config", "Only currently permitted content/citations returned",
        "Unauthorized or uncertain content absent; dependency failures fail closed", name, evidence, observation,
        status, "See F-001/F-002 where applicable; otherwise no confirmed issue implied",
        "Retained latest run" if status == "PASS" else "Pending", limitation, "HUMAN PENDING"]))


def main() -> None:
    rows = []
    latest = json.loads((DOCS / "evidence/latest/manifest.json").read_text())
    for test in latest["test_records"]:
        rows.append(row(test["pytest_node_id"], test["status"], "docs/evidence/latest/manifest.json#" + test["test_id"], test["measurement"]))
    ui = DOCS / "evidence/ui/manifest.json"
    if ui.exists():
        for test in json.loads(ui.read_text())["checks"]:
            rows.append(row(test["test_id"] + " " + test["description"], test["status"], "docs/evidence/ui/manifest.json", "Actual Chromium offline browser", "Offline synthetic browser; not full live stack"))
    race = DOCS / "evidence/ui/race-retest.json"
    if race.exists():
        manifest = json.loads(race.read_text())
        checks = manifest.get("checks", manifest.get("results", []))
        if checks:
            for test in checks:
                rows.append(row(str(test.get("test_id", "UI-RACE")), test.get("status", "INCONCLUSIVE"), str(race.relative_to(ROOT)), "Actual delayed-response browser race retest"))
    pf = json.loads((DOCS / "evidence/promptfoo/manifest.json").read_text())
    stats = pf["stats_observed"]
    for status, key in [("PASS", "successes"), ("FAIL", "failures"), ("INCONCLUSIVE", "errors")]:
        for number in range(stats.get(key, 0)):
            rows.append(row(f"PROMPTFOO-{status}-{number+1:03d}", status, "docs/evidence/promptfoo/results.json", "Local extractive custom provider assertion; zero remote model requests", "One deterministic sample/case; no stochastic model inference"))
    fga = ROOT / "infra/openfga/probe-results.json"
    if fga.exists():
        for test in json.loads(fga.read_text())["results"]:
            rows.append(row(test["test_id"], test["status"], str(fga.relative_to(ROOT)), f"Real container: expected={test['expected']} observed={test['observed']}", "Isolated in-memory OpenFGA component only; not app/PostgreSQL integration"))
    # Historical failures and derived summaries stay in findings, not counted
    # again as final regression observations.
    component_files = [DOCS / "evidence" / name for name in ["keycloak-component.json", "qdrant-component.json", "openfga-adapters.json"]]
    component_files.extend(sorted((DOCS / "evidence/live").glob("*.json")))
    for file in component_files:
        if not file.exists() or "before" in file.name:
            continue
        data = json.loads(file.read_text())
        for test in data.get("results", data.get("checks", data.get("observations", []))):
            if isinstance(test, dict) and "status" in test:
                rows.append(row(str(test.get("test_id", file.stem)), test["status"], str(file.relative_to(ROOT)), str(test.get("description", "Real isolated component; consult full manifest")), "Component probe only; complete Compose still unverified"))
    blockers = json.loads((DOCS / "evidence/infrastructure-blockers.json").read_text())
    for number, attempt in enumerate(blockers["attempts"], 1):
        rows.append(row(f"INFRA-ATTEMPT-{number:03d}", attempt["status"], "docs/evidence/infrastructure-blockers.json", attempt["observed"], "Setup attempt inconclusive; not a vulnerability or an application assertion"))
    for test, limitation in [
        ("LIVE-CLEAN-BOOTSTRAP", "PostgreSQL image extraction failed: Docker vfs ENOSPC"),
        ("LIVE-PG-MIGRATIONS", "App PostgreSQL migrations written; no actual PostgreSQL container available"),
        ("LIVE-APP-OIDC-FGA-QDRANT", "Complete live application identity-to-content path not run"),
        ("LIVE-FULL-DEPENDENCY-OUTAGES", "Offline faults and mocked adapter errors tested; complete real application outages not exercised"),
        ("LIVE-NEXTCLOUD-EDIT-SHARE-UNSHARE-DELETE", "Nextcloud image extraction ENOSPC; source lifecycle not measured live"),
        ("LIVE-NEXTCLOUD-NATIVE-ACL-INHERITANCE", "Not implemented: generic end-user ACL sync; app policy is authoritative"),
        ("LIVE-KEYCLOAK-PROVIDER-SESSION-REVOCATION", "No introspection; logout denylist is volatile and process local"),
        ("LIVE-MULTIWORKER-CONSISTENCY", "Single-worker lab only; no distributed serialization proof"),
        ("OPTIONAL-LLM-STOCHASTIC-EVALUATION", "External model adapter absent; disabled by design"),
        ("OPTIONAL-LANGFUSE-REDACTION", "No Langfuse adapter or live trace integration"),
        ("OPTIONAL-ONYX-PERMISSION-SYNC", "Not integrated; edition-dependent native permission capability not claimed"),
        ("DEPENDENCY-VULNERABILITY-AUDIT", "Pins/licenses recorded; no complete package/image advisory audit executed"),
        ("HUMAN-INDEPENDENT-COMPETENCY", "Exercise supplied; human unassisted performance not observed"),
    ]:
        rows.append(row(test, "NOT_TESTED", "docs/reports/residual-risks.md", "No passing evidence", limitation))
    for test in ["PDF-OFFICE-PARSER-CONTAINMENT", "ARBITRARY-USER-UPLOADS", "PROVIDER-COST-BUDGET"]:
        rows.append(row(test, "NOT_APPLICABLE", "docs/engagement/risk-selection.md", "Feature absent from implemented slice", "No such feature or provider enabled"))
    output = DOCS / "requirements/control-and-test-traceability.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    totals = {status: Counter(r["Status"] for r in rows)[status] for status in ["PASS", "FAIL", "INCONCLUSIVE", "NOT_TESTED", "NOT_APPLICABLE"]}
    summary = {"engagement": "P-091", "denominator": len(rows), "totals": totals, "meaning": "Coverage observations; PASS is an assertion outcome, not a count of vulnerabilities", "source": str(output.relative_to(ROOT))}
    (DOCS / "evidence/coverage-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
