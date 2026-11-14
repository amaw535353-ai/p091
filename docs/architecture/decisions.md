# Architecture decisions

Decision status records design choices. Execution status belongs to `../evidence/` and `../implementation-progress.md`.

## ADR-001: Deterministic vertical slice before external dependencies

**Accepted.** Use FastAPI, typed request schemas, a small relational repository and extractive answer generation. Offline mode uses explicitly synthetic authentication and local state. Tests can exercise identity and data boundaries without a provider key, model download or stochastic judgment. The tradeoff is limited semantic quality and no evidence about real-model compliance with instructions. Never describe deterministic extraction as a verified LLM integration.

## ADR-002: One trusted document gate for every outward representation

**Accepted.** List, search, preview, direct read, citation, chat, history, summary and export must call the same current-access policy before returning document-derived fields. Resolve trusted metadata from the database after retrieval; vectors only nominate candidates. Store source references for conversation reuse and regenerate authorized quotes rather than treating cached text as safe. The cost is repeated policy work and lower availability when dependencies fail.

## ADR-003: Current application policy plus independent live relationship check

**Accepted with limitation.** The application owns synthetic tenant membership, grants, document lifecycle and version state. In live mode a positive OpenFGA viewer check is required in addition to these gates. Reconciliation reads stored direct-user viewer tuples and applies both additions and removals; current application group policy is materialized into those direct entitlements. Deny while state is unknown or the authorization service is unavailable. This makes policy errors observable and protects against trusting vector labels; it does not prove an atomic transaction across PostgreSQL and OpenFGA. Run one API worker and do not claim multi-replica revocation assurance.

## ADR-004: Keycloak for live identity; explicit synthetic issuer offline

**Accepted.** Pin issuer, audience and trusted JWKS configuration; accept RS256 access-token claims only after verification. Human and workload principals are separate and route scopes are checked independently. Browser login should use authorization code with PKCE. Offline identity selection exists only for owned-loopback synthetic exercises and is unavailable in live mode. Provider session revocation is a separate control from JWT validity; document whether introspection is implemented and measured.

## ADR-005: Tenant separation in retrieval is defense in depth

**Accepted.** Use a tenant-specific Qdrant collection and tenant filter with opaque IDs and source versions. Store no document bodies, titles or human ACL assertions in vector payloads. Read authoritative content only after current authorization. Deterministic hashed embeddings suit the lab but are not a production quality retrieval model. Collections and filters do not replace object authorization.

## ADR-006: Nextcloud supplies content; source permission fidelity remains incomplete

**Accepted with limitation.** Use bounded text WebDAV reads, current ETags and known connector-readable metadata. Retain stable application identity and provenance independently from untrusted source fields. Application-mediated synthetic grants are authoritative for the demonstrated system. Content reindex preserves independent ACL certainty; it cannot turn an unknown human policy into a known one. A connector service account's permissions cannot establish individual end-user access, and external Nextcloud share/group changes are not completely reconciled. Full source ACL inheritance/revocation is therefore a remaining gate rather than a claimed integration success.

## ADR-007: Optional heavy integrations must earn their claims

**Accepted.** Keep the default answer engine provider-independent and local. Add Onyx only after checking the intended edition/API and available permission features; the custom retriever is a separate implementation. Keep Langfuse export and real-model calls disabled until configured, redaction-tested and explicitly authorized. Promptfoo can evaluate deterministic output, but model-specific robustness needs its own model/version, budget, dataset and sample-count evidence.

## ADR-008: Fail-closed output with minimal evidence disclosure

**Accepted.** Generic authorization and dependency errors must not include forbidden titles, service responses or raw token details. Audit records use correlation IDs, actor type, decision, policy/source version and outcome. Evidence retains sanitized requests and exact commands, distinguishing measured, mocked, assumed and not-tested results. The lab does not claim production-grade immutable auditing, high availability or complete denial-of-service resistance.
