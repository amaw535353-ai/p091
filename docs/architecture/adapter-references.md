# Adapter contracts and official references

Reviewed 2026-11-14 against official documentation before implementing these adapters.
These HTTP contract tests use `httpx.MockTransport`: a passing mock proves request
construction and defensive parsing, and does **not** prove the external service runs.
See the evidence manifest and live smoke results for any measured live status.

| Component | Official reference | Implemented contract |
| --- | --- | --- |
| Keycloak | [OIDC endpoints and flows](https://www.keycloak.org/securing-apps/oidc-layers) | Live verification fetches trusted JWKS for every request; validates RS256, issuer, audience, expiry, issued-at and optional not-before. Browser code flow belongs to the application. Password grant is not implemented. |
| PyJWT | [Usage](https://pyjwt.readthedocs.io/en/stable/usage.html) | Requires identity and time claims; restricts accepted algorithms to RS256. Unverified headers select only a key in the configured issuer key set; `jku`/`x5u` cannot choose a network destination. |
| OpenFGA | [Relationship queries](https://openfga.dev/docs/interacting/relationship-queries), [query consistency](https://openfga.dev/docs/interacting/consistency) | POST check pins store/model and requests `HIGHER_CONSISTENCY`; only a boolean `allowed` is accepted. Malformed responses and transport failure deny access. Canonical app tenant equality is additionally required. |
| Qdrant | [Query points REST API](https://api.qdrant.tech/api-reference/search/query-points) | Per-tenant collection plus tenant payload filter, deterministic 64-dimensional hash vectors. Indexed payload contains only opaque document ID, tenant and source version. Returned IDs are candidates, never permissions. |
| Nextcloud | [WebDAV basics](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html) | Fixed configured WebDAV account, relative text paths, bounded Depth 0 PROPFIND, readable permission `G`, etag and size; GET with If-Match rejects source races. No arbitrary URLs, redirects, rich file parsing or uploads. |

The current Nextcloud manual is for a newer release than the pinned lab image;
the WebDAV properties used here are long-standing contracts but the live version
must still be exercised. OpenFGA and Qdrant endpoint contracts must likewise be
confirmed against the actual pinned image rather than inferred from mocks.

OpenFGA reconciliation also uses paginated POST `/stores/{store}/read` filtered to
the exact document and `viewer` relation. It returns only stored direct `user:...`
tuples, omitting group usersets and never expanding inheritance. Pagination loops,
malformed pages and incomplete bounded reads fail closed. Read has no model ID
parameter; egress authorization still uses the pinned-model `check` operation.

## Identity and source-of-truth limitations

Offline RSA identities are a synthetic local identity provider, **not Keycloak**.
Offline issuance exists only in explicit offline mode and must be loopback-bound.
Live mode contains no local signing key and cannot issue synthetic tokens.
Groups and administrative authority must come from the current application policy,
not from request headers or token group hints.

Fresh live JWKS fetching deliberately denies requests while Keycloak is unavailable.
It does not detect a Keycloak session revoked after an access token was issued.
Application logout blocks the token in the current process until expiry; multi-process
or restart-safe revocation requires a shared durable store or live introspection.
Short 15-minute offline tokens and ephemeral offline signing keys limit the lab case.

Nextcloud `oc:permissions` describes the connector account's current file access.
It is **not a complete end-user ACL or proof of a recipient's current permission**.
The application must separately enforce its canonical ACL and OpenFGA decision on
every egress path. Unmanaged Nextcloud native share changes and native group-folder
ACL inheritance are not silently represented as supported authorization sync.
Source version checks can prevent serving changed content; they cannot prove that
an unchanged-content source ACL still matches a cached user ACL. Any full native
Nextcloud permission-sync claim needs additional measured integration work.

The offline generator performs deterministic extraction; this does not measure
resistance of a stochastic LLM. There is no implemented real-provider API or Langfuse
export in these adapters. Those integrations remain disabled and unverified.
