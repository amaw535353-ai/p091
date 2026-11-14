# Residual risks and limitations

| ID | Residual item | Current evidence/status | Required next proof |
| --- | --- | --- | --- |
| R-01 | Complete live bootstrap and combined authorization path | INCONCLUSIVE setup attempts; PostgreSQL/Nextcloud extraction ENOSPC under ~8 GiB disk and Docker vfs | `make core` on sufficient storage, migrations, end-to-end user/service flows |
| R-02 | Native source permission inheritance/revocation | NOT_TESTED; generic Nextcloud user/group/share reconciliation not implemented | Define authoritative source-user policy, reconcile/check it independently, measure uncertain windows and deny them |
| R-03 | Source content lifecycle and synchronization delay | Actual Nextcloud not run; adapter mocked, offline transitions tested | Live edit/share/unshare/delete/reindex with source/policy versions and elapsed measurements |
| R-04 | Provider session invalidation and durable logout | Live JWT/JWKS verified; application denylist process local/volatile; no introspection | Persist revocation, verify provider logout/revocation and multi-process reuse denial |
| R-05 | Distributed or concurrent authorization changes | Single process RLock only; PostgreSQL/OpenFGA updates not atomic together | Distributed policy epoch/transaction design plus concurrent revoke/read acceptance |
| R-06 | Source timing races | Current ETag/connector readability sampled during request; cannot retract delivered bytes | Define source consistency guarantees and bound/check authorization epochs through response assembly |
| R-07 | Retrieval/model utility and injection generalization | Hash/lexical retrieval and short extraction; deterministic cases only | Semantic quality dataset and explicit stochastic model/version/sample outcomes if a model is added |
| R-08 | Langfuse/Onyx/external model integration | NOT_TESTED; adapters absent or disabled; Onyx permission sync documented as Enterprise capability | Verify edition/API and observe sanitized per-tenant telemetry/provider execution before claims |
| R-09 | Production infrastructure | Local HTTP and trusted host operator; no TLS/hardening/backup/load acceptance | Separate production threat model and deployment acceptance; least-privilege runtime DB/migration roles |
| R-10 | Dependency supply-chain assurance | Exact tested Python pins, image tags/digests and licenses recorded; no complete advisory scan | Review current advisories/SBOMs and immutable base image provenance |
| R-11 | Audit retention/history data | Allowlists and actor hashes; local store holds application questions; no immutable retention or full erasure guarantee | Define access, retention, encryption, recovery and deletion policy for real data |
| R-12 | Browser/session scope | Race fix verified in one tab; other tabs require separate logout | Cross-tab coordination if product requirements need it; no memory-zeroization claim |
| R-13 | Human independent competency | PENDING / NOT_TESTED | Perform unassisted exercise, alternate policy variation and oral defense against objective rubric |

PDF/Office parsing, arbitrary uploads and provider cost enforcement are NOT_APPLICABLE to the implemented slice because those features are absent. The bounded plain-text/metadata connector is implemented and has relevant type/path/size tests. Empty directories or configuration placeholders do not establish an integration.

No remaining hypothesis here is presented as a confirmed exploited vulnerability. Four actual implementation findings were fixed and retested, with configuration/method limits in their individual records. The current work is suitable for a synthetic local portfolio lab, not production use or a blanket security certification.
