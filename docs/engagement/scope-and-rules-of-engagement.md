# P-091 engagement scope and rules of engagement

Engagement: **P-091, Enterprise Knowledge Assistant security laboratory**. Fictional client: Northwind and its isolated demonstration peer Contoso. Classification: synthetic training material. Prepared 2026-11-14.

The operator owns the disposable lab created from this repository. All accounts, documents, canaries, credentials and business scenarios are synthetic. The user authorized implementation and local testing in the supplied workspace. This statement records the lab boundary; it grants no permission to assess an employer, customer, SaaS tenant or third-party network and implies no client endorsement.

## Objectives and acceptance criteria

Demonstrate an independently reproducible assessment of identity, object authorization, tenant isolation, permission changes and untrusted retrieved text. A successful negative security test is a denied attack, not a vulnerability finding. A passing offline test establishes behavior only for its tested configuration. Evidence must identify whether an observation came from a live service, a local deterministic implementation or a mocked adapter.

Before execution, define both an allowed request and a denied request for each control. The principal invariant is that every outgoing title, snippet, document, citation, answer, summary, history entry and export depends on a current independent document-access check. Losing access to one source must prevent reuse of an answer derived from that source. Successful authorized requests must remain useful after denial controls are applied.

## Authorized assets and identities

| Asset | Permitted activity | Boundary |
| --- | --- | --- |
| Repository application and its test fixtures | Unit, integration, adversarial and regression tests | Workspace and explicitly started localhost services |
| Compose project and named volumes | Create, seed, mutate, reset and remove this project | Never prune unrelated Docker resources |
| Northwind / Contoso | Synthetic HR and Finance policy exercises | Tenant administrator cannot administer another tenant |
| Human test users | Employee, Finance manager and tenant administrator per tenant | Human identity must not impersonate the indexer |
| Indexer identities | Scoped ingestion/reindex operations | No human search, chat or administrative privilege |
| Official project documentation / package registries | Read documentation and obtain dependencies | No security probing of those providers |

All published application ports must bind to loopback. Host or Docker administrators are trusted and can read lab storage; this lab does not protect against its operator. Offline identity selection is an explicitly labeled synthetic convenience and must never be internet exposed. The live path uses Keycloak rather than synthetic login.

## Execution limits and stop conditions

Use serial functional requests by default, at most 5 requests/second against this disposable lab and no more than 1,000 requests per assessment run unless the operator records a revised local load-test scope. These are engagement limits, not a claim that the API implements rate limiting. Do not brute-force passwords, execute uploaded code, use exploit payloads against external services or perform destructive infrastructure tests beyond the named project.

Stop the affected test if a destination is outside the allowlist, an unknown account or real secret appears, a control unexpectedly contacts a provider, or the host becomes unstable. Retain the minimum sanitized reproduction, isolate the test data, and review the scope before resuming. External model calls, telemetry export, Onyx assessment, deployment and publication are excluded unless separately enabled and authorized. No external provider key is required for the default suite.

## Data handling and evidence

Use harmless unique markers to detect unauthorized disclosure. Do not store bearer tokens, passwords, authorization headers, real personal data or secret-bearing prompts in evidence. Record UTC execution timestamps, command, configuration, source revision or content digest, test IDs, result, evidence ID and limitations. Hash retained result files and keep human conclusions separate from raw observations. Do not include `.env`, generated private keys, databases or service logs with credentials in the delivery archive.

Treat retrieved text, metadata and service responses as untrusted data. Tests may plant instruction-like text and forged retrieval candidates; permission decisions remain outside the extractive answer mechanism. Intentionally vulnerable behavior belongs in an isolated test fixture disabled by default. A fixture's simulated failure must not be reported as a confirmed vulnerability in the hardened application.

## Assessment lifecycle and project mapping

| Lifecycle | Repository artifact / activity | Completion rule |
| --- | --- | --- |
| A: Context and authorization | This scope and synthetic fixture inventory | Scope recorded before attack execution |
| B: Applicable risks and tools | `risk-selection.md` | Distinguish deployed, mocked and excluded tools |
| C: Architecture and threat model | `../architecture/data-flow-and-trust-boundaries.md` | Identify trust boundary and attacker control |
| D: Controls and tests | `../requirements/` and executable tests | Allowed and denied outcomes specified |
| E: Execute, fix, retest | `../evidence/` and `../findings/` | Each result has measured evidence or explicit blocker |
| F: Client handover | `../reports/`, root README and run commands | State tested configuration and residual risk |
| G: Independent competency | `../competency/independent-assessment-challenge.md` | Pending until a human independently demonstrates it |
| H: Feedback | Versioned traceability, threat model and regression tests | Reassess after policy, source or dependency changes |

The attachment listed five additional planning resources; they were not present in the initially empty workspace. The supplied P-091 specification therefore defines the local project mapping. No conclusion claims to validate absent planning documents.
