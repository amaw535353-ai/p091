# Security architecture review

Review basis: the supplied P-091 specification and the reference implementation's trust boundaries. This document evaluates design and coverage; it does not certify production readiness. Measured conclusions and exact test denominators belong to the retained execution reports. Review date: 2026-11-14.

## Design assessment

The architecture places authorization outside answer generation. Tenant and actor identity come from a verified token and current trusted user record. The relational document record supplies current lifecycle, ACL and version state. Retrieval metadata supplies candidate IDs only. In live mode OpenFGA is an additional necessary policy decision. This arrangement can contain a malicious retrieval result without depending on whether an answer generator follows an instruction-like source passage.

Historical answers are a material read path. Removing a share after answering a question must also prevent access to old quotations, summaries and exports. Rechecking only the current search result would leave a second disclosure path. The intended implementation retains provenance and regenerates permitted representations after current checks; it should deny a historical item when any underlying source is no longer available to that subject.

Fail-closed dependency handling trades availability for confidentiality. The test plan must cover permitted questions as well as failures so that an implementation returning errors for everything cannot count as a successful defense. A normal authorized query with a matching cited quotation is the baseline utility gate.

## Control review and evidence requirements

| Area | Design expectation | Evidence required before claiming success | Limitation |
| --- | --- | --- | --- |
| Authentication | Trusted RS256 key, issuer/audience/time checks; no request-supplied identity | Positive and negative token tests; separate live Keycloak observation | Valid self-contained JWT does not by itself prove current provider session validity |
| Workload separation | Distinct subject type and ingestion scope | Human→ingest and service→read/admin denials | Host operator and service configuration remain trusted |
| Object and tenant access | Current server ACL on all document-derived output | Cross-tenant and same-tenant denial plus authorized positive tests | A finite suite covers named routes only; new routes need new cases |
| Relationship policy | Live OpenFGA check on originating subject | Actual allow/deny and outage tests against OpenFGA | Mocked transport establishes adapter handling, not live policy correctness |
| Revocation | Unshare, group removal and deletion affect next read | Before/read, mutate, after/read across chat history/citation/export | Single-process serialization does not establish distributed atomicity |
| Source synchronization | Unknown/stale version or ACL blocks content | Edit/reindex and stale-state tests, measured source timestamps | Nextcloud external share/group ACL fidelity incomplete |
| Retrieval | Tenant collection/filter, opaque IDs, independent policy | Forged candidate/metadata cases and live Qdrant response evidence | Hashed embedding quality is limited; no information-theoretic embedding privacy claim |
| Untrusted source text | Inert quotation and deterministic access gates | Controlled injection fixture plus forbidden marker check | No LLM immunity or general poisoning-detection claim |
| Citation integrity | Citation identifies current permitted version and quote | Source equality test, wrong version denial and revoked source denial | Extractive grounding does not establish source factual accuracy |
| Audit and telemetry | Allowlisted fields; scoped dashboard and generic errors | Output inspection for dummy secrets and other-tenant metadata | Langfuse disabled; immutable log storage and long-term retention not established |

## Integration status distinctions

The offline implementation is a simulation of infrastructure boundaries using actual local application code, not an Onyx or Keycloak deployment. Mocked REST tests validate request construction and fail-closed adapter behavior. A healthy Compose container proves process readiness only; actual token verification, authorization, retrieval and source-change workflows require their own end-to-end observations.

Nextcloud is a content source in the implemented policy model. The app's synthetic ACLs are authoritative, while WebDAV permission letters describe the configured connector account. Because that is not a complete user/group authorization graph, the project cannot claim that changing a Nextcloud share outside the app immediately revokes every assistant read. Do not ingest production data under this assumption. Implement authoritative source-user checks or verified ACL reconciliation before claiming full connector permission parity.

Onyx is an optional comparison target. Confirm edition-specific permission-aware connector behavior against official documentation before enabling it. The custom retriever's tests establish no Onyx behavior. Real LLMs and Langfuse are optional, disabled surfaces and remain outside any deterministic passing-test claim unless separately observed.

## Priority residual work

1. Close the source-permission gap: define a complete source of truth, retrieve source user/group/role relationships and validate share/group revocations across all paths under measured sync delay.
2. Establish live stack acceptance: fresh setup and seed, browser OIDC with PKCE, current policy checks, actual vector retrieval, source changes and dependency outages with sanitized evidence.
3. If replicas are added, implement a distributed policy epoch or equivalent consistency protocol, transactional update strategy, and concurrent revoke/read tests. Avoid granting during reconciliation errors.
4. For real model support, constrain provider destinations and cost, sanitize output/telemetry, keep citation authorization deterministic, and report model-specific failures and samples.
5. Add production controls only with evidence: TLS, durable session revocation, service-network isolation, least-privilege database roles, secrets rotation, resource quotas and recoverable audit retention.

These are residual requirements or untested assumptions unless an evidence-backed finding says otherwise. They must not be inflated into confirmed exploited vulnerabilities. The project is suitable as an owned synthetic assessment exercise; a production deployment requires a separate threat model and acceptance decision.

## Corrections verified during implementation review

Independent review identified four implementation defects. Each was corrected and exercised again; its finding record retains the exact configuration, source hashes where captured, observed reproduction and retest scope. These are measured application defects, not invented demonstrations or findings against upstream products.

| Finding | Failed boundary | Architectural correction | Observation scope |
| --- | --- | --- | --- |
| [F-001](../findings/F-001-seed-restores-membership.md) | Bootstrap defaults overwrote persisted group revocation | Initialize fixture memberships only for newly created users | Actual offline API, persistent SQLite, repeated seed and restart |
| [F-002](../findings/F-002-browser-session-race.md) | An old authorized response rendered under a new browser identity | Bind async response handling and UI updates to the initiating session epoch | Actual Chromium with delayed responses across logout/tenant switch |
| [F-003](../findings/F-003-logout-signature-padding.md) | Serialized token representation bypassed identity revocation | Revoke verified issuer+jti identity after cryptographic claim validation | Actual offline API and additional mocked trusted-JWKS regression |
| [F-004](../findings/F-004-reindex-clears-unknown-acl.md) | Content indexing certified an unknown human policy | Preserve independent ACL certainty during content refresh | Actual app/NextcloudSource adapter with simulated HTTP source |

The corrections do not remove the residual limits above. Source ACL reconciliation, provider-session revocation, distributed consistency and real-model behavior require separate evidence.
