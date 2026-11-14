# P-091 · Enterprise Knowledge Assistant Security Lab

A working local FastAPI assistant and reproducible, synthetic security assessment. Two tenants, current permissions, deterministic answers with independently checked citations, administrator workflows, adversarial fixtures, browser UI, and retained evidence. This is the custom reference path; it is not an Onyx implementation.

**Acceptance: partial.** The offline application is executed and tested. Real Keycloak/OpenFGA/Qdrant component evidence is separate from full-stack acceptance. Docker's `vfs` driver exhausted this environment's disk during PostgreSQL and Nextcloud image extraction. A complete PostgreSQL-backed Compose application and Nextcloud lifecycle have **not** been validated. See [implementation progress](docs/implementation-progress.md), [coverage totals](docs/evidence/coverage-summary.json), and [executive report](docs/reports/executive-summary.md).

## Run the verified offline application

Requires Python 3.12 and `make`. Initial dependency installation needs access to the Python package index; runtime needs no model key or external API. From this directory:

```sh
make setup
make seed
make serve
```

Open **http://localhost:8000**. The prominent offline badge and identity selector are deliberate synthetic lab features. Select `nw-employee` for Northwind HR, `nw-manager` for Finance, or `nw-admin` for tenant administration; Contoso has corresponding `co-*` users. The selector issues ephemeral, signed test tokens on loopback only; it is unavailable in live mode. Do not expose this service on a public interface. One API worker is supported.

```sh
make check       # Ruff and mypy
make test        # unit, integration, security and regression tests
make evidence    # pytest JUnit, sanitized output, source hashes, exact counts
make evaluate    # optional Node >=22.22.0; pinned Promptfoo, local provider only
```

The pinned `requirements.lock` contains the tested Python dependency set, including development checks. `evaluations/promptfoo/package-lock.json` pins the evaluation tool. Existing evidence is retained under `docs/evidence/`; a rerun replaces `latest` only. No stochastic model results are claimed. Full case totals and limitations are generated from actual records, not hardcoded into this README.

## Implemented workflows

| Workflow | API |
| --- | --- |
| Effective identity / logout | `GET /auth/me`, `POST /auth/logout` |
| Authorized source list, details, export | `GET /documents`, `/documents/{id}`, `/documents/{id}/export` |
| Search / extractive answer | `POST /search {query}`, `POST /chat {question}` |
| Current citation version | `GET /citations/{id}/{version}` |
| Revalidated history, export, summary | `GET /history`, `/history/{id}`, `/history/{id}/export`, `/summaries/{id}` |
| Individual share / unshare | `POST /admin/documents/{id}/share` or `/unshare` with `{user_id}` |
| Group membership | `PATCH /admin/groups/{group}/members/{user_id} {member}` |
| Edit / delete / reindex | `PATCH`, `DELETE /admin/documents/{id}`, `POST /admin/documents/{id}/reindex` |
| Least-privileged indexing workload | `POST /ingestion/reindex/{id}` with a service/ingest identity |
| Local health and scoped dashboard | `GET /health/live`, `/health/ready`, `/dashboard` |

Interactive request schemas are at `/docs`. Identity and tenant fields in request bodies are rejected. Administrative endpoints enforce stored tenant administrator status and scope. Unshare removes an individual grant; it does not override ownership, group membership, tenant visibility or administrator rights.

## What enforces access

Every document-derived response checks the current server-side user, tenant, lifecycle, ACL-known flag and source/index version. Live mode additionally requires a current OpenFGA viewer decision. Qdrant returns candidate IDs; canonical SQL records supply content and policy. Unknown ACLs stay denied even after a service account reindexes content. Edits deny reads until reindex. Historical answers retain document/version references and regenerate authorized quotations; old versions and revoked references deny the entire dependent answer.

The local retriever uses word matching; live vectors use deterministic 64-dimensional hashed word embeddings. Each bounded plain-text document is one indexed unit; a citation identifies an opaque UUID chunk for its first 320-character quote. This is intentionally limited extraction, not semantic-model quality or general prompt-injection immunity. Synthetic attack text can appear literally in an authorized quote without becoming an instruction.

Browser content uses `textContent`, bearer tokens stay in memory, and session epochs reject delayed responses from a previous identity. Logout denylisting uses verified token identity rather than malleable raw token text. Correlation/audit records omit source bodies, titles, questions and tokens.

## Live and extended topology (full acceptance pending)

Docker Engine and Compose are required. Plan for at least 4 CPUs, 6 GiB RAM for core, 8–10 GiB for extended, and 10 GiB disk with an efficient storage driver or 20 GiB with `vfs`; these are estimates. All exposed ports bind `127.0.0.1`.

```sh
make core       # prepare secrets; start DB/identity/policy/vector; configure; build API; service-token index
make extended   # additionally provision Nextcloud, seed source files/shares, enable source adapter, reindex
make stop       # stop only this Compose project; preserve volumes
make reset      # explicitly discard only this disposable project's volumes and clear service IDs
make clean-offline  # explicitly reset only work/lab.db
```

The unverified full bootstrap commands are supplied for a host with sufficient disk; they are not labeled passing. Do not run reset while preserving lab state. See [infra setup, versions and licenses](infra/README.md). Generated `.env` values and obsolete generated realm files are ignored and excluded from delivery. The committed Keycloak realm uses environment placeholders, authorization code + PKCE for humans and distinct client-credentials identities for indexing. Read the generated local `LAB_USER_PASSWORD` value privately when logging into Keycloak; never paste it into evidence.

Nextcloud is a **content** source in this policy variant. The application's synthetic policy plus OpenFGA are the assistant ACL authority. Connector-readable DAV permissions do not prove an individual user's rights. Arbitrary external source share/group changes, generic native ACL inheritance, multi-replica consistency, provider session introspection, production TLS, Onyx, Langfuse and external LLM adapters remain unimplemented or untested. See [residual risks](docs/reports/residual-risks.md).

## Reproduce the assessment

- [Scope and rules](docs/engagement/scope-and-rules-of-engagement.md), [dataflow and trust boundaries](docs/architecture/data-flow-and-trust-boundaries.md), [architecture decisions](docs/architecture/decisions.md).
- [Per-case traceability CSV](docs/requirements/control-and-test-traceability.csv), [verified standards identifiers](docs/requirements/standards-references.md).
- [Confirmed findings and retests](docs/reports/remediation-and-retest.md), [technical assessment](docs/reports/technical-assessment.md), [handover](docs/reports/handover-runbook.md).
- [Portfolio case study](docs/reports/portfolio-case-study.md), [independent human exercise](docs/competency/independent-assessment-challenge.md). Human competency is **PENDING**, never inferred from generated code or passing tests.

The opt-in vulnerable fixture is isolated from the app:

```sh
.venv/bin/python fixtures/vulnerable_demo.py --allow-vulnerable-fixture
```

It demonstrates a deliberately omitted tenant check with synthetic records. Its weakness is not counted as a vulnerability in the hardened application. Confirmed implementation defects are documented separately. No external targets were assessed and nothing was published or pushed.
