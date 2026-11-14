# P-091 portfolio case study

**Context:** fictional Northwind and Contoso want a knowledge assistant with HR, Finance, private and shared records. The engagement uses synthetic users and harmless unique canaries on owned local infrastructure.

**Contribution:** built a FastAPI reference application with a browser interface, deterministic retrieval/quotation, current per-document checks, version-bound citations, revalidated history, administrative permission/lifecycle operations, workload separation and adversarial evaluations. Supplied Keycloak/OpenFGA/Qdrant/PostgreSQL/Nextcloud integration code, pinned topology, official standards mapping and independently reproducible evidence.

**Assessment method:** scope and authorize → model trust boundaries → specify allowed/denied outcomes → execute → independently review → fix → retain retests. Prompt instructions were not treated as an authorization mechanism. Tests check useful permitted answers alongside denials, so a system returning no content cannot satisfy utility assertions.

**Findings:** independent review observed membership restored during seeding, cross-session browser response rendering, logout revocation bypass through an equivalent JWT encoding, and a content indexer clearing unknown ACL state. The last was exercised through an actual adapter with a mocked source, not a live Nextcloud deployment. See the individual findings for severity, proof, fix and exact retest results. The opt-in intentionally vulnerable fixture is separate from these implementation defects.

**Measured boundary:** the final evidence manifests provide exact counts and source hashes. Local extraction/injection regressions establish deterministic data access behavior, not immunity of a stochastic LLM. Isolated real-service probes establish component behavior; they do not prove the complete application stack.

**Limitation disclosed:** full PostgreSQL-backed Compose and live Nextcloud workflows were blocked by Docker image extraction disk exhaustion. Source-native permission reconciliation, durable provider-session invalidation, distributed concurrency, Onyx, Langfuse and external LLM adapters remain future work. The project is a reproducible portfolio laboratory, not a production assurance certificate or a claim of client endorsement.

**Interview walkthrough:** show the trust-boundary diagram; demonstrate a permitted HR quote; try a cross-tenant/private ID; revoke a grant and re-open its old citation/history; explain the F-001/F-003 identity-state failures and F-002 browser race; inspect the actual evidence hashes; explain exactly why incomplete source ACL fidelity prevents full acceptance. Finally complete the unassisted competency challenge. Its status remains PENDING until a human actually performs it.
