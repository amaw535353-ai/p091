# Verified standards references and applicability

Identifiers below were checked against official published sources on **2026-11-14**. They are a focused mapping for this lab, not an ASVS/AISVS certification or a full compliance assessment. The control-and-test traceability artifact records actual observed results. A related requirement may be only partially addressed; no mapped requirement is automatically marked PASS.

## OWASP ASVS 5.0.0

The [official v5.0.0 authorization chapter](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x17-V8-Authorization.md) and [official v5.0.0 machine-readable requirements](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json) were read. Use version-qualified identifiers because numbering can change.

| Verified identifier | Lab applicability |
| --- | --- |
| v5.0.0-8.1.1 | Document subject/resource rules and allowed/denied behavior |
| v5.0.0-8.2.1 | Restrict administrative and ingestion functions |
| v5.0.0-8.2.2 | Enforce per-object reads, history ownership and citations |
| v5.0.0-8.3.1 | Enforce policy in the server rather than browser controls |
| v5.0.0-8.3.2 | Recheck changed permissions on subsequent reads; distributed/source limits remain |
| v5.0.0-8.4.1 | Prevent one tenant's operations affecting another tenant |
| v5.0.0-9.2.1 | Validate token time bounds |
| v5.0.0-9.2.3 | Accept only intended API audience |

These references select behavior to test. They do not imply the application satisfies every field-level, session, OAuth or infrastructure requirement in the standard.

## OWASP AISVS 1.0

The [official project page](https://owasp.org/projects/artificial-intelligence-security-verification-standard-aisvs-docs) identified 1.0 as stable and linked its requirements. Sources read: [C5 identity and access](https://github.com/OWASP/AISVS/blob/main/1.0/en/0x10-C05-Access-Control-and-Identity.md), [C8 memory/vector security](https://github.com/OWASP/AISVS/blob/main/1.0/en/0x10-C08-Memory-Embeddings-and-Vector-Database.md), [C2 input validation](https://github.com/OWASP/AISVS/blob/main/1.0/en/0x10-C02-Input-Validation.md). These are the published 1.0 folder; reverify on a future release.

| Verified identifier | Lab applicability and boundary |
| --- | --- |
| AISVS 1.0 5.1.2 | Short-lived scoped signed workload tokens; complete federation assurance needs live evidence |
| AISVS 1.0 5.2.1 | Default-deny AI resource access; service deployment controls remain a separate check |
| AISVS 1.0 5.2.2 | Carry originating human authorization through retrieval and assembly |
| AISVS 1.0 5.2.4 | Ensure assembled output contains only requester-authorized sources; extraction only |
| AISVS 1.0 8.1.1 | Tenant-specific vector identifiers/namespaces |
| AISVS 1.0 8.1.3 | Apply retrieval scope constraints |
| AISVS 1.0 8.3.1 | Related lifecycle objective: exclude expired/deleted versions; no complete TTL-expiry claim |
| AISVS 1.0 8.3.2 | Local disposable reset mechanism |

AISVS 1.0 2.1.3 and 2.1.6 concern input screening and instruction hierarchy. Deterministic inert quotation with external authorization provides a useful injection exercise but does **not** establish those real-model controls. AISVS 1.0 5.3.2 concerns stronger shared-compute isolation and is outside this local application test. Do not mark these requirements passed from a canary-only test.

## MITRE ATLAS

The official website's technique deep links returned HTTP 404 through the research tool. Identifiers were instead read directly from the [official ATLAS 2026.07 YAML, format 6.0.0](https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.07.yaml). The old `dist/ATLAS.yaml` identifies itself as deprecated and was not used for the final mapping.

| Verified technique | Use |
| --- | --- |
| AML.T0051 — LLM Prompt Injection | General threat label |
| AML.T0051.001 — Indirect | Instruction-like text delivered through retrieved sources |
| AML.T0070 — RAG Poisoning | Manipulated indexed content or ranking scenario |

ATLAS techniques characterize adversary behavior. They are not assurance requirements, proof of exploitation or control scores. The lab uses these as hypotheses exercised against synthetic content.

## NIST AI RMF 1.0

The [official AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) identifies its basis as AI RMF 1.0 (2023) and notes revision work. Verified mappings:

| Published identifier | Project activity |
| --- | --- |
| GOVERN 1.4 | Transparent scope, risk priorities and assessment rules |
| MAP 1.1 | Intended use, actors, limits and deployment context |
| MEASURE 2.1 | Dataset, tools, commands and evaluation details |
| MEASURE 2.7 | Evaluate and document security/resilience |
| MANAGE 1.4 | Record unmitigated residual risks |

The framework supports risk governance; selecting these activities does not establish NIST certification or universal safety. Recheck identifiers and assumptions when the framework or application changes.
