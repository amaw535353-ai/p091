# Handover and reproducibility

Operate only the owned disposable lab. Install dependencies with `make setup`; seed and run the verified offline application using `make seed && make serve`. Keep the service on loopback and use one worker. `make check`, `make evidence` and optional `make evaluate` reproduce the automated core. The initial package/tool downloads require network access; the application/evaluation provider runs locally and makes no external model requests.

## Permission and version drill

1. Sign in as `nw-employee`, ask about the HR Handbook, and open the returned citation.
2. Sign in as `nw-admin`; remove `nw-employee` from `northwind-hr` using the documented PATCH endpoint. Sign back in as the employee. Subsequent source, search and saved-answer paths must deny that HR material. Restart the app and verify removal persists (F-001).
3. Share the manager-private document to the employee, ask a question matching its text, then unshare. The private source and dependent history, summary, citation and export must be unavailable. Ownership/group/tenant grants are unions, so choose the initially unshared private source.
4. Edit a permitted source in fixture mode. Reads deny while `source_version != synced_version`. Reindex it with a tenant administrator or same-tenant service identity. Current source reads recover; old version citations/history remain unavailable.
5. Delete the synthetic source and confirm direct/citation/history access stays denied. Reindex never resurrects a deleted document. Repeat the seed command; permissions must not be reset.

Tests automate these steps using fresh in-memory databases. Long-lived offline state is `work/lab.db`. Reset it only with `make clean-offline`. The synthetic signing key is ephemeral, so existing offline bearer tokens do not survive an application restart.

## Evidence commands

```sh
make check
make evidence
make evaluate
.venv/bin/python scripts/build_traceability.py
```

`docs/evidence/latest/manifest.json` records source SHA-256 hashes, dependency versions, exact command/time, per-case outcomes and denominator. There was no initial Git checkout to identify; a null commit field is intentional, not a fabricated revision. Preserve an evidence directory before rerunning if comparison matters. Browser runners live under `apps/web/`; their manifests include actual commands and Chromium versions. The browser runner additionally requires Playwright and a compatible Chromium executable, separate from the Python runtime lock.

The traceability builder uses latest observations. A passing regression describes its particular assertion; findings retain the earlier failing observations separately. Infrastructure setup failures remain inconclusive attempts, not software vulnerabilities. Review the limitation field for mocked source and component-only results.

## Live host recovery

The single next executable step on a machine with enough disk is `make core`. It creates local secrets, starts pinned components, imports the realm, initializes the relationship model, builds the API and invokes real workload-scoped indexing. The current environment could not extract PostgreSQL or Nextcloud images because Docker uses disk-intensive `vfs`; a complete command success is not claimed. Do not use global Docker prune to repair a shared host.

For extended validation run `make extended` after core succeeds. Validate actual Nextcloud edit/share/unshare/delete, source version transitions, outage behavior, and all egress paths before treating source permission fidelity as complete. Application ACL authority and native Nextcloud ACL inheritance are distinct; the latter is not implemented by the content connector.

## Troubleshooting and retention

- `503`: check required identity, authorization, retrieval and enabled source services. Do not weaken authorization or switch to stale cached content to recover availability.
- `404` on known source/history: inspect current tenant, effective grants, deletion and source/index/citation versions. The response deliberately does not reveal whether an unauthorized object exists.
- `403`: inspect actor type, scoped token and current trusted administrator/user record. Do not add user/tenant fields to request bodies.
- `make reset` discards only this project's Compose volumes and saved store IDs. It preserves generated secret values. `.env` must never be committed or included in a public archive.
- Audits use allowlisted fields and hashed actor IDs. History questions remain application data inside the local metadata store; they are not emitted to telemetry or evidence. No immutable audit retention guarantee is claimed.

Future changes must rerun the control suite, race regression and relevant component acceptance, regenerate traceability, and update source hashes/known limitations. Add model/provider-specific datasets and budgets only when actually implementing a provider. Never transfer the synthetic lab's authorization to a third-party system.
