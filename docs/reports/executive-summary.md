# Executive summary · P-091

**Decision: the synthetic offline reference application is verified; complete live-stack acceptance is not achieved.** The implementation demonstrates a two-tenant knowledge assistant with current object permissions, separate human/workload identities, deterministic citations, permission lifecycle workflows and reproducible assessment evidence. The supplied planning files were absent; the attached P-091 specification governed the work.

Final observations on 2026-11-14: **145/145 Python cases, 6/6 Promptfoo cases, 9/9 basic Chromium checks and 10/10 browser race cases passed.** Real isolated components passed Keycloak service/JWKS 7/7, human PKCE/CORS 8/8, OpenFGA initial model 2/2 and application adapter 9/9, and Qdrant adapter 6/6. These are scoped observations, not a claim that all integrations ran together.

The coverage matrix has **221 rows: PASS 202, FAIL 0, INCONCLUSIVE 3, NOT_TESTED 13, NOT_APPLICABLE 3**. Three inconclusive rows are failed infrastructure setup attempts caused by disk exhaustion; they are not penetration-test vulnerabilities. Historical failures are retained in findings and are not added again to final regression totals.

Independent review found and corrected four implementation defects:

| Finding | Observed effect | Resolution |
| --- | --- | --- |
| F-001 | Routine reseed/restart restored removed group membership | Initialize memberships only for newly created users; repeat-seed and restart regressions |
| F-002 | Delayed previous-user response rendered after a browser tenant switch | Bind requests and all async UI continuations to session epochs; ten held-response regressions |
| F-003 | Equivalent JWT signature encoding bypassed same-process logout | Revoke verified issuer/jti identity; original and padded token variants denied |
| F-004 | Content-only indexing cleared unknown human ACL state | Preserve independent ACL certainty through reindex; actual adapter with mocked source retested |

All severities are Medium within the stated owned synthetic lab context. F-004 was confirmed against application code with a controlled source transport; no live Nextcloud vulnerability is alleged. A separate missing Keycloak subject mapper caused authentication to fail closed; configuration was corrected and real browser logins retested. The intentionally insecure fixture is excluded from the four implementation findings.

The principal business boundary is enforced outside generation: every tested source-derived read uses canonical current policy and version state. Prompt-injection text is treated as inert source quotation. The assessment establishes deterministic data-access behavior; it does not establish robustness of a real LLM.

Remaining acceptance blockers are substantial and explicit. PostgreSQL and Nextcloud images could not be extracted under this environment's approximately 8 GiB disk and Docker `vfs` storage driver. Full Compose bootstrap, PostgreSQL migrations in a running container, complete assistant integration and live source lifecycle/outages remain unverified. Native Nextcloud end-user ACL reconciliation, durable provider-session revocation, distributed concurrency, Langfuse, Onyx and external model integrations are not implemented/validated.

On a host with sufficient disk, the **single next executable step is `make core`**. Complete core and extended acceptance before treating this as a live enterprise deployment. The independent human competency exercise remains **PENDING**; automated outcomes do not demonstrate unassisted human skill. No external target was assessed and no project was published or pushed.
