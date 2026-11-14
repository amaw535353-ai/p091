# Technical assessment

Engagement P-091; fictional tenants Northwind and Contoso; owned local synthetic infrastructure only. Core risks #1 identity, #3 connector/RAG authorization, #4 disclosure, #5 indirect injection and #35 isolation. Supporting controls cover P-017, P-022, P-029, P-031, P-032, P-034/P-039, P-037 and P-040. Official version-qualified standards mappings and their limits are in `../requirements/standards-references.md`.

## Implemented scope and files

`p091/` contains typed configuration, RS256 identity verification, SQL repository/migration, deterministic permission gates, seed, ingestion/indexing services and FastAPI routes. `apps/web/` contains the accessible browser UI and repeatable real-browser checks. `infra/` contains pinned Compose profiles, Keycloak realm placeholders, OpenFGA relationship model, database initialization and real component probes. `fixtures/` contains eight synthetic identities, twenty documents and the explicit opt-in vulnerable contrast. `tests/` covers units, integration, boundary abuse and finding regressions. `evaluations/promptfoo/` contains a pinned local provider and six cases. `scripts/` supplies bootstrap, source provisioning, evidence, reset, coverage and sanitized packaging. `docs/` retains scope, architecture, findings, standards, evidence, reports and a pending human challenge. No existing application files were overwritten; the starting workspace had no checkout/application.

## Measured execution

Commands below ran from `/workspace/work/p091` unless their retained manifest states another working directory. Environment-specific Python/Chromium paths are recorded verbatim in each browser manifest. Initial dependency installation and the subsequent upgrade produced the exact pinned `requirements.lock`; `pip check` reported no broken requirements. Initial installation is a network dependency, not an external model call.

| Exact command or manifest-recorded runner | Observed result | Evidence |
| --- | --- | --- |
| `.venv/bin/python -m p091.seed` | Exit 0; 8 synthetic identities, 20 documents | Seed fixture and command observation; repeated seed regression covers preservation |
| `.venv/bin/python scripts/run_evidence.py` | Exit 0; **145 passed**, one upstream Starlette/TestClient deprecation warning | `../evidence/latest/{manifest.json,junit.xml,pytest.log}` |
| `.venv/bin/ruff check p091 scripts tests fixtures infra apps/web --output-format concise` | Exit 0; All checks passed | Final check observation |
| `.venv/bin/mypy p091 scripts --ignore-missing-imports` | Exit 0; no issues in 18 source files | Final check observation |
| `.venv/bin/python scripts/run_promptfoo.py` | Exit 0; **6 passed**, 0 failed/errors; no external model requests | `../evidence/promptfoo/manifest.json` and `results.json` |
| `python apps/web/check_browser.py` | **9/9 PASS**, actual desktop/mobile Chromium screenshots | `../evidence/ui/manifest.json` includes exact executable/options |
| `python apps/web/check_session_race.py` | **10/10 PASS**, held responses across logout/tenant switch | `../evidence/ui/race-retest.json` |
| `python apps/web/check_keycloak.py` | **8/8 PASS**, real browser S256 PKCE/CORS exchange and actual JWT verifier | `../evidence/live/keycloak-human.json` |
| `.venv/bin/python infra/probe_keycloak.py` | Exit 0; **7/7 PASS**, real service grants/JWKS and negative checks | `../evidence/keycloak-component.json` |
| `.venv/bin/python infra/probe_openfga_adapters.py` | Exit 0; **9/9 PASS**, real adapter read/write/check/revoke/outage | `../evidence/openfga-adapters.json` |
| Initial isolated OpenFGA model requests | **2/2 PASS**, exact model accepted and allow/deny observed | `../../infra/openfga/probe-results.json` |
| `.venv/bin/python infra/probe_qdrant.py` | Exit 0; **6/6 PASS**, namespaces/payload/filter/key/delete | `../evidence/qdrant-component.json` |
| `docker compose --env-file .env -f infra/compose/compose.yaml --profile core config --quiet` and extended profile | Exit 0; topology parses | Infrastructure check; not a runtime acceptance result |
| `docker compose --env-file .env -f infra/compose/compose.yaml --profile core up -d postgres keycloak openfga qdrant vector-ready` | Exit 1; PostgreSQL extraction: **no space left on device** | `../evidence/infrastructure-blockers.json` |
| `docker compose --env-file .env -f infra/compose/compose.yaml --profile extended pull --quiet nextcloud` | Exit 1; same extraction/disk blocker | Same blocker manifest |
| `docker pull --quiet postgres:17.12-alpine` | Exit 1; smaller alternative also exhausted disk; not adopted | Same blocker manifest |
| `.venv/bin/python scripts/build_traceability.py` | **221 rows: 202 PASS / 0 FAIL / 3 INCONCLUSIVE / 13 NOT_TESTED / 3 NOT_APPLICABLE** | `../evidence/coverage-summary.json`, traceability CSV |

The four remediation retest commands and original measured failing statuses appear in the finding files. Early fixture-selection failures and a Promptfoo assertion correction are not product findings. The retained Promptfoo correction history explicitly distinguishes test error from a disclosure. No passing result is inferred from a file's mere existence.

## Interpretation of evidence

The final assertion denominator is **202 executed passing case observations**, across suites/components; it is not 202 independent business controls. Total coverage is **221 rows**, including explicit incomplete and inapplicable items. Historical pre-fix failures remain evidence of four confirmed defects, even though final regression FAIL is zero. Hashes identify tested source snapshots where captured; no initial Git commit existed, so the test manifest records a null commit rather than an invented SHA.

Offline faults simulate identity/authorization/vector/source/model unavailability. MockTransport tests exercise real adapter request/response handling with controlled inputs. Real component probes use actual containers but independent temporary datastores/corpora. None of those observations proves complete PostgreSQL-backed application acceptance or live Nextcloud permission parity. Actual source edit/share/unshare/delete propagation latency was **not measured**. Offline application-mediated mutation affects the next tested read; no distributed timing guarantee follows.

Authorized utilities include two-tenant logins, permitted HR/Finance/private sharing, searchable source details, current citations, history, lifecycle updates and workload indexing. Negative cases include signature/issuer/audience/time/scope failures, forged identity/group/admin claims, cross-tenant objects/search/history/citations/export, revoked/deleted/stale records, manipulated ranking/metadata, unknown ACLs and controlled injection text. Browser races and restart persistence required independent review beyond the first passing boundary suite.

Read-time checks represent a decision at server assembly time. They cannot retract data legitimately received earlier, eliminate external-source time-of-check races, or guarantee multi-process atomicity. Trace storage is local allowlisted SQL auditing; there is no Langfuse integration or stochastic model invocation.

## Findings and architecture disposition

See `remediation-and-retest.md` for F-001–F-004. The relationship system is a necessary additional live gate, while current canonical SQL rules also deny stale grants. Index metadata never confers access. Real OpenFGA tests confirm adapter reconciliation/removals and fail-closed errors; real Qdrant tests confirm candidate scoping and minimized payload. Human Keycloak tests validate the actual realm claim/scoping behavior after the missing-sub mapper fix.

The reference architecture and reports fulfill consultancy lifecycle A–F iteratively. Lifecycle G is supplied as an unassisted human exercise, not marked passed. Lifecycle H is represented by the regression/feedback instructions. Completion of all ten requested core gates is **not claimed**: live bootstrap, PostgreSQL acceptance and complete source-native permission synchronization remain open.
