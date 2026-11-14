# Optional integrations and edition boundary

The custom reference retriever is the implemented application. No Onyx server,
Onyx permission-sync integration, Langfuse exporter, external LLM adapter or
provider key is enabled. These are separate future acceptance items, not hidden
features of the default application.

On 2026-11-14 the official [Onyx connector documentation](https://docs.onyx.app/overview/core_features/connectors)
identified honoring source-user permissions as an Enterprise Edition capability.
The [official connector page](https://onyx.app/connectors) also describes automatic
permission synchronization as Enterprise functionality. This is a verified
documentation/edition limitation, not a tested capability in this lab. The
availability of a particular source connector and API must be checked again
before building a comparison target; no native Nextcloud integration is assumed.

Langfuse remains disabled because a real redacted trace ingestion and per-tenant
visibility boundary have not been exercised. The current SQL audit uses an
allowlist of correlation ID, hashed actor ID, actor type, action, decision,
policy/source version and time. It is not represented as Langfuse observability.

External generation remains absent. A future adapter must opt in explicitly,
restrict destinations/models, enforce cost limits and reuse deterministic source
authorization and citation gates. Model-specific tests must retain version,
settings, dataset and sample denominator. The existing Promptfoo provider calls
only the loopback deterministic API and makes no external model request.
