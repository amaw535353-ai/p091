# Applicable risks, projects and tools

This is an implementation-focused P-091 engagement. The numbered risk, project and tool labels below originate in the supplied specification; they are portfolio taxonomy labels, not invented OWASP requirements. Standards references are verified separately in `../requirements/standards-references.md`.

| Risk | Supporting project | Boundary and abuse case | Implemented assessment approach |
| --- | --- | --- | --- |
| #1 Workload identity | P-001–P-010 foundation; P-017 object access | Human token substituted for indexer; wrong signature, expiry, issuer, audience or scope | Typed human/service principal, RS256 verification, current server identity lookup and endpoint scope checks |
| #3 Connector/RAG permissions | P-031 inheritance; P-037 revocation and sync | A stale share or group membership grants a read | Current application policy decision; source-version gate; independent live OpenFGA check |
| #4 Sensitive disclosure | P-029 context/data disclosure; P-040 grounded citations | Unauthorized marker escapes through text, title, history, summary, export, cache or citation | Revalidate each underlying source before response assembly; sanitized audit fields |
| #5 Indirect prompt injection | P-022 document injection | An accessible source tells the assistant to disclose an inaccessible Finance canary | Controlled text fixture evaluated against deterministic extraction; no model authority to grant access |
| #35 Tenant/user isolation | P-017; P-032 vector namespace | Tenant A guesses Tenant B document IDs or reuses a conversation | Trusted tenant bound to subject; tenant checks and document authorization on all tested read paths |
| #13 Retrieval manipulation | P-034 / P-039 metadata and ranking | Forged candidate ID, ranking or security label bypasses policy | Retrieval returns candidates only; trusted document metadata and authorization decide output |

Direct instruction-like user text may be exercised as an input to the deterministic system. It is not a model-jailbreak assessment. File-upload/parser risk #17 remains outside scope unless an upload/parsing route is added; bounded text retrieval through WebDAV does not establish general file-parser security. Model training, weight access, autonomous tool use, shared GPU side channels, real secret extraction and external exfiltration are excluded.

| Tool ID | Role | Verification boundary |
| --- | --- | --- |
| #21 Keycloak | Human OIDC and distinct workload credentials | Compose/JWKS integration is separate from offline synthetic token tests; use retained live evidence to establish actual success |
| #22 OpenFGA | Live relationship decision point | A positive viewer check is necessary alongside the application's tenant/state/policy gates; mocked REST tests are not live OpenFGA evidence |
| #28 Qdrant | Tenant-scoped vector candidates | Per-tenant collections plus tenant filter reduce errors; vector payloads never become the policy source of truth |
| #143 Nextcloud | Optional bounded content source | WebDAV content/ETag metadata supported; source-system sharing/group ACL fidelity is explicitly incomplete |
| #3 Promptfoo | Repeatable evaluation harness | Deterministic answer evaluation must be labeled as such; results do not establish real-model robustness |
| #117 Langfuse | Optional observability integration target | Disabled; no working live integration claimed without retained evidence |
| #1 Onyx | Optional comparison target | Excluded from core functionality; no Onyx deployment or permission feature is inferred from this custom implementation |

Onyx permissions-aware connector behavior may depend on edition and deployment. Confirm the chosen edition's official documentation, license and API before adding that target; do not describe the application's authorization-backed retriever as Onyx functionality. The repository's implementation and execution reports remain authoritative for what was actually run.
