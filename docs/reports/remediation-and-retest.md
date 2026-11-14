# Remediation and retest

All outcomes below have observed evidence. Severity is contextual to this synthetic local lab. The intentionally vulnerable contrast fixture is excluded from confirmed application findings.

| ID / severity | Before observation | Implemented change | Observed retest and evidence |
| --- | --- | --- | --- |
| [F-001](../findings/F-001-seed-restores-membership.md) / Medium | HR read 200 → admin removes group → 404 → restart → 200 | Seed memberships only when inserting a new user | Two repeat-seed/restart cases PASS; included in final 145-case JUnit |
| [F-002](../findings/F-002-browser-session-race.md) / Medium | Held Northwind chat response appeared under Contoso after account switch | Session epochs across request successes, failures, loaders, OIDC and cleanup; clear old inputs | Ten actual Chromium delayed-response cases PASS, including stale 401; current tenant utility remains; `../evidence/ui/race-{before,retest}.json` |
| [F-003](../findings/F-003-logout-signature-padding.md) / Medium | Logout denied original token (401) but equivalent signature-padding serialization allowed (200) | Denylist verified issuer/jti identity after signature/claim validation | Six regression cases PASS; original and three padding variants deny; `../evidence/F003-auth-revocation.json` |
| [F-004](../findings/F-004-reindex-clears-unknown-acl.md) / Medium | Unknown ACL denied, then content-only service reindex cleared flag and allowed | Content reindex preserves independent ACL uncertainty | Known/unknown ACL cases PASS; actual source adapter with mocked transport; no live Nextcloud finding |

The final combined Python run passed **145/145** with all backend regressions included. F-002's browser assertions are separate from pytest and passed **10/10**. Basic browser utility passed **9/9**, and Promptfoo passed **6/6** after the final backend changes. See manifests for exact times, versions and source hashes.

Other corrections made during implementation: count incoming request bytes while streaming; preserve source-size bounds while reading; check configured identity/source readiness; reconcile removed OpenFGA direct grants as well as additions. These were design/review corrections and are not inflated into additional exploited findings. Keycloak's custom scopes initially omitted the subject mapper, causing correct fail-closed 401; the realm now includes the explicit mapper and actual human browser PKCE/CORS retested **8/8 PASS**. The derived mapper summary adds no extra denominator.

Prioritized remaining actions:

1. **Acceptance blocker:** run `make core` on adequately sized storage; observe actual PostgreSQL migrations and combined identity/policy/retrieval/egress paths. Then exercise real dependency outages.
2. **Source-policy blocker:** complete source-user ACL reconciliation or authoritative source-user read checks; measure actual share/group/edit/delete changes through Nextcloud and deny uncertain intervals. `make extended` supplies the content integration but does not implement generic native ACL parity.
3. **Deployment boundary:** replace volatile in-process logout/serialization with durable revocation and a distributed consistency design before adding replicas; verify concurrency and provider-session invalidation.
4. **Optional surfaces:** only introduce external model/trace/Onyx integrations after defining provider budgets, redaction and edition/API limits, then execute separate acceptance datasets.
5. **Maintenance:** conduct dependency/image advisory review, least-privilege/TLS hardening and recovery drills for any production variant. Existing version pins/license notes are not a vulnerability audit.

No full-live remediation is declared validated from the component tests. Residual risks and independent human gates remain explicit.
